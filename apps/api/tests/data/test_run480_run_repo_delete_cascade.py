"""Red tests for RUN-480 workflow delete run cascade and active-run guard."""

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
            "run_target_1",
            workflow_id="wf_target",
            workflow_name="Target Flow",
            created_at=100.0,
        )
        _seed_node(db_session, "run_target_1", "node_1")
        _seed_log(db_session, "run_target_1", "node_1", "target log 1")

        _seed_run(
            db_session,
            "run_target_2",
            workflow_id="wf_target",
            workflow_name="Target Flow",
            created_at=200.0,
        )
        _seed_node(db_session, "run_target_2", "node_1")
        _seed_log(db_session, "run_target_2", "node_1", "target log 2")

        _seed_run(
            db_session,
            "run_other",
            workflow_id="wf_other",
            workflow_name="Other Flow",
            created_at=300.0,
        )
        _seed_node(db_session, "run_other", "node_1")
        _seed_log(db_session, "run_other", "node_1", "other log")
        db_session.commit()

        commit_calls = 0
        original_commit = db_session.commit

        def counted_commit():
            nonlocal commit_calls
            commit_calls += 1
            return original_commit()

        monkeypatch.setattr(db_session, "commit", counted_commit)

        repo = RunRepository(db_session)
        runs_deleted = repo.delete_runs_for_workflow("wf_target")

        assert runs_deleted == 2
        assert commit_calls == 1
        assert db_session.exec(select(Run).where(Run.workflow_id == "wf_target")).all() == []
        assert (
            db_session.exec(
                select(RunNode).where(RunNode.run_id.in_(["run_target_1", "run_target_2"]))
            ).all()
            == []
        )
        assert (
            db_session.exec(
                select(LogEntry).where(LogEntry.run_id.in_(["run_target_1", "run_target_2"]))
            ).all()
            == []
        )

        remaining_runs = db_session.exec(select(Run).where(Run.workflow_id == "wf_other")).all()
        remaining_nodes = db_session.exec(
            select(RunNode).where(RunNode.run_id == "run_other")
        ).all()
        remaining_logs = db_session.exec(
            select(LogEntry).where(LogEntry.run_id == "run_other")
        ).all()
        assert [run.id for run in remaining_runs] == ["run_other"]
        assert [node.id for node in remaining_nodes] == ["run_other:node_1"]
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
            "run_pending",
            workflow_id="wf_target",
            workflow_name="Target Flow",
            status=RunStatus.pending,
        )
        _seed_run(
            db_session,
            "run_completed",
            workflow_id="wf_target",
            workflow_name="Target Flow",
            status=RunStatus.completed,
            created_at=200.0,
        )
        db_session.commit()

        repo = RunRepository(db_session)

        with pytest.raises(WorkflowHasActiveRuns):
            repo.delete_runs_for_workflow("wf_target", force=False)

        remaining_runs = db_session.exec(select(Run).where(Run.workflow_id == "wf_target")).all()
        assert {run.id for run in remaining_runs} == {"run_pending", "run_completed"}

    def test_delete_runs_for_workflow_force_true_deletes_even_with_active_runs(
        self,
        db_session: Session,
    ):
        """force=True should delete the workflow's runs even when one is still running."""
        RunRepository = _import_run_repository()

        _seed_run(
            db_session,
            "run_running",
            workflow_id="wf_target",
            workflow_name="Target Flow",
            status=RunStatus.running,
        )
        _seed_node(db_session, "run_running", "node_1")
        _seed_log(db_session, "run_running", "node_1", "running log")
        db_session.commit()

        repo = RunRepository(db_session)
        runs_deleted = repo.delete_runs_for_workflow("wf_target", force=True)

        assert runs_deleted == 1
        assert db_session.exec(select(Run).where(Run.workflow_id == "wf_target")).all() == []
        assert db_session.exec(select(RunNode).where(RunNode.run_id == "run_running")).all() == []
        assert db_session.exec(select(LogEntry).where(LogEntry.run_id == "run_running")).all() == []

    def test_delete_runs_for_workflow_raises_when_running_runs_exist_without_force(
        self,
        db_session: Session,
    ):
        """A running workflow run should also block delete until force=True is used."""
        RunRepository = _import_run_repository()
        from runsight_api.domain.errors import WorkflowHasActiveRuns

        _seed_run(
            db_session,
            "run_running",
            workflow_id="wf_target",
            workflow_name="Target Flow",
            status=RunStatus.running,
        )
        _seed_run(
            db_session,
            "run_completed",
            workflow_id="wf_target",
            workflow_name="Target Flow",
            status=RunStatus.completed,
            created_at=200.0,
        )
        db_session.commit()

        repo = RunRepository(db_session)

        with pytest.raises(WorkflowHasActiveRuns):
            repo.delete_runs_for_workflow("wf_target", force=False)

        remaining_runs = db_session.exec(select(Run).where(Run.workflow_id == "wf_target")).all()
        assert {run.id for run in remaining_runs} == {"run_running", "run_completed"}
