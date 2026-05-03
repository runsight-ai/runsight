"""Workflow delete run cascade and active-run guard."""

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from runsight_api.domain.entities.log import LogEntry
from runsight_api.domain.entities.run import Run, RunNode, RunStatus


def _import_run_repository():
    from runsight_api.data.repositories.run_repo import RunRepository

    return RunRepository


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _seed_run(
    session: Session,
    run_id: str,
    *,
    workflow_id: str,
    workflow_name: str,
    status: RunStatus = RunStatus.completed,
    created_at: float = 100.0,
) -> None:
    session.add(
        Run(
            id=run_id,
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            status=status,
            task_json="{}",
            branch="main",
            created_at=created_at,
            updated_at=created_at,
        )
    )


def _seed_node(session: Session, run_id: str, node_id: str) -> None:
    session.add(
        RunNode(
            id=f"{run_id}:{node_id}",
            run_id=run_id,
            node_id=node_id,
            block_type="llm",
            status="completed",
        )
    )


def _seed_log(session: Session, run_id: str, node_id: str | None, message: str) -> None:
    session.add(
        LogEntry(
            run_id=run_id,
            node_id=node_id,
            level="info",
            message=message,
        )
    )


class TestRunRepositoryCreateRead:
    def test_create_run_and_node_can_be_read_back(self, db_session: Session):
        RunRepository = _import_run_repository()
        repo = RunRepository(db_session)
        run = Run(
            id="run-primary",
            workflow_id="wf-primary",
            workflow_name="WF",
            task_json="{}",
            branch="main",
        )
        repo.create_run(run)

        fetched_run = repo.get_run("run-primary")
        assert fetched_run is not None
        assert fetched_run.id == "run-primary"

        node = RunNode(
            id="run-primary:node-primary",
            run_id="run-primary",
            node_id="node-primary",
            block_type="llm",
        )
        repo.create_node(node)

        nodes = repo.list_nodes_for_run("run-primary")
        assert [node.id for node in nodes] == ["run-primary:node-primary"]


class TestRunRepositoryDeleteRunsForWorkflow:
    def test_delete_runs_for_workflow_cascades_logs_nodes_and_runs_in_a_single_commit(
        self,
        db_session: Session,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """Deleting a workflow's runs should remove logs, nodes, and runs in one transaction."""
        RunRepository = _import_run_repository()

        _seed_run(
            db_session,
            "target_workflow_run_first",
            workflow_id="target_workflow",
            workflow_name="Target Flow",
            created_at=100.0,
        )
        _seed_node(db_session, "target_workflow_run_first", "cleanup_node")
        _seed_log(db_session, "target_workflow_run_first", "cleanup_node", "target log 1")

        _seed_run(
            db_session,
            "target_workflow_run_second",
            workflow_id="target_workflow",
            workflow_name="Target Flow",
            created_at=200.0,
        )
        _seed_node(db_session, "target_workflow_run_second", "cleanup_node")
        _seed_log(db_session, "target_workflow_run_second", "cleanup_node", "target log 2")

        _seed_run(
            db_session,
            "other_workflow_run",
            workflow_id="other_workflow",
            workflow_name="Other Flow",
            created_at=300.0,
        )
        _seed_node(db_session, "other_workflow_run", "cleanup_node")
        _seed_log(db_session, "other_workflow_run", "cleanup_node", "other log")
        db_session.commit()

        commit_calls = 0
        original_commit = db_session.commit

        def counted_commit():
            nonlocal commit_calls
            commit_calls += 1
            return original_commit()

        monkeypatch.setattr(db_session, "commit", counted_commit)

        repo = RunRepository(db_session)
        runs_deleted = repo.delete_runs_for_workflow("target_workflow")

        assert runs_deleted == 2
        assert commit_calls == 1
        assert db_session.exec(select(Run).where(Run.workflow_id == "target_workflow")).all() == []
        assert (
            db_session.exec(
                select(RunNode).where(
                    RunNode.run_id.in_(["target_workflow_run_first", "target_workflow_run_second"])
                )
            ).all()
            == []
        )
        assert (
            db_session.exec(
                select(LogEntry).where(
                    LogEntry.run_id.in_(["target_workflow_run_first", "target_workflow_run_second"])
                )
            ).all()
            == []
        )

        remaining_runs = db_session.exec(
            select(Run).where(Run.workflow_id == "other_workflow")
        ).all()
        remaining_nodes = db_session.exec(
            select(RunNode).where(RunNode.run_id == "other_workflow_run")
        ).all()
        remaining_logs = db_session.exec(
            select(LogEntry).where(LogEntry.run_id == "other_workflow_run")
        ).all()
        assert [run.id for run in remaining_runs] == ["other_workflow_run"]
        assert [node.id for node in remaining_nodes] == ["other_workflow_run:cleanup_node"]
        assert len(remaining_logs) == 1

    def test_delete_runs_for_workflow_raises_when_active_runs_exist_without_force(
        self,
        db_session: Session,
    ):
        """Pending or running workflow runs should block delete unless force=True."""
        RunRepository = _import_run_repository()
        from runsight_api.domain.errors import WorkflowHasActiveRuns

        _seed_run(
            db_session,
            "pending_target_run",
            workflow_id="target_workflow",
            workflow_name="Target Flow",
            status=RunStatus.pending,
        )
        _seed_run(
            db_session,
            "completed_target_run",
            workflow_id="target_workflow",
            workflow_name="Target Flow",
            status=RunStatus.completed,
            created_at=200.0,
        )
        db_session.commit()

        repo = RunRepository(db_session)

        with pytest.raises(WorkflowHasActiveRuns):
            repo.delete_runs_for_workflow("target_workflow", force=False)

        remaining_runs = db_session.exec(
            select(Run).where(Run.workflow_id == "target_workflow")
        ).all()
        assert {run.id for run in remaining_runs} == {"pending_target_run", "completed_target_run"}

    def test_delete_runs_for_workflow_force_true_deletes_even_with_active_runs(
        self,
        db_session: Session,
    ):
        """force=True should delete the workflow's runs even when one is still running."""
        RunRepository = _import_run_repository()

        _seed_run(
            db_session,
            "running_target_run",
            workflow_id="target_workflow",
            workflow_name="Target Flow",
            status=RunStatus.running,
        )
        _seed_node(db_session, "running_target_run", "cleanup_node")
        _seed_log(db_session, "running_target_run", "cleanup_node", "running log")
        db_session.commit()

        repo = RunRepository(db_session)
        runs_deleted = repo.delete_runs_for_workflow("target_workflow", force=True)

        assert runs_deleted == 1
        assert db_session.exec(select(Run).where(Run.workflow_id == "target_workflow")).all() == []
        assert (
            db_session.exec(select(RunNode).where(RunNode.run_id == "running_target_run")).all()
            == []
        )
        assert (
            db_session.exec(select(LogEntry).where(LogEntry.run_id == "running_target_run")).all()
            == []
        )

    def test_delete_runs_for_workflow_raises_when_running_runs_exist_without_force(
        self,
        db_session: Session,
    ):
        """A running workflow run should also block delete until force=True is used."""
        RunRepository = _import_run_repository()
        from runsight_api.domain.errors import WorkflowHasActiveRuns

        _seed_run(
            db_session,
            "running_target_run",
            workflow_id="target_workflow",
            workflow_name="Target Flow",
            status=RunStatus.running,
        )
        _seed_run(
            db_session,
            "completed_target_run",
            workflow_id="target_workflow",
            workflow_name="Target Flow",
            status=RunStatus.completed,
            created_at=200.0,
        )
        db_session.commit()

        repo = RunRepository(db_session)

        with pytest.raises(WorkflowHasActiveRuns):
            repo.delete_runs_for_workflow("target_workflow", force=False)

        remaining_runs = db_session.exec(
            select(Run).where(Run.workflow_id == "target_workflow")
        ).all()
        assert {run.id for run in remaining_runs} == {"running_target_run", "completed_target_run"}
