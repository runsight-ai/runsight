"""Single status writer and explicit lifecycle repo contract.

_run_workflow must not call _set_run_status for completed/failed outcomes;
ExecutionObserver is the sole writer of terminal Run status.

Engine-backed ExecutionService must still use the supplied lifecycle
persistence repo when error-path writes are required.
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlmodel import Session, SQLModel, create_engine

from runsight_api.domain.entities.run import Run, RunStatus
from runsight_api.logic.observers.execution_observer import ExecutionObserver
from runsight_api.logic.services.execution_service import ExecutionService, PreparedRunInputs
from runsight_core.redaction import RunRedactor

# ======================================================================
# Single status writer.
# ======================================================================


class TestObserverWritesTerminalStatus:
    """Verify ExecutionObserver correctly sets terminal Run status."""

    @pytest.fixture
    def db_engine(self):
        engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(engine)
        return engine

    @pytest.fixture
    def run_in_db(self, db_engine):
        """Insert a pending Run record and return its id."""
        run_id = "run_obs_test"
        with Session(db_engine) as session:
            run = Run(
                id=run_id,
                workflow_id="wf_1",
                workflow_name="wf_1",
                status=RunStatus.running,
                task_json="{}",
                branch="main",
            )
            session.add(run)
            session.commit()
        return run_id

    def test_observer_on_workflow_complete_sets_completed(self, db_engine, run_in_db):
        """ExecutionObserver.on_workflow_complete sets Run.status = completed."""
        from runsight_core.state import WorkflowState

        obs = ExecutionObserver(engine=db_engine, run_id=run_in_db)
        state = WorkflowState()
        obs.on_workflow_complete("test_wf", state, duration_s=1.0)

        with Session(db_engine) as session:
            run = session.get(Run, run_in_db)
            assert run.status == RunStatus.completed, f"Expected completed, got {run.status}"

    def test_observer_on_workflow_error_sets_failed(self, db_engine, run_in_db):
        """ExecutionObserver.on_workflow_error sets Run.status = failed."""
        obs = ExecutionObserver(engine=db_engine, run_id=run_in_db)
        error = RuntimeError("something broke")
        obs.on_workflow_error("test_wf", error, duration_s=0.5)

        with Session(db_engine) as session:
            run = session.get(Run, run_in_db)
            assert run.status == RunStatus.failed, f"Expected failed, got {run.status}"


# ======================================================================
# Fresh session per operation.
# ======================================================================


def _prepared_inputs(inputs):
    return PreparedRunInputs(
        normalized_inputs=inputs,
        input_redactor=RunRedactor(),
    )


class TestExplicitLifecycleRepoContract:
    """ExecutionService must honor the supplied lifecycle-capable repo contract."""

    def test_store_branch_and_sha_uses_supplied_mock_lifecycle_repo_even_with_engine(self):
        db_engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(db_engine)

        run = Mock()
        run.id = "run_mock_repo"
        run.status = RunStatus.pending
        run.branch = None
        run.commit_sha = None
        run.updated_at = None

        run_repo = Mock()
        run_repo.list_runs.return_value = []
        run_repo.get_run.return_value = run

        svc = ExecutionService(
            run_repo=run_repo,
            workflow_repo=Mock(),
            provider_repo=Mock(),
            engine=db_engine,
        )

        svc._store_branch_and_sha("run_mock_repo", "main", "abc123")

        run_repo.get_run.assert_called_once_with("run_mock_repo")
        run_repo.update_run.assert_called_once_with(run)
        assert run.branch == "main"
        assert run.commit_sha == "abc123"

    @pytest.mark.asyncio
    async def test_launch_execution_error_path_writes_via_supplied_lifecycle_repo(self):
        """Prepare-time failures should be persisted through the supplied repo."""
        db_engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(db_engine)

        run = SimpleNamespace(
            id="run_session_test",
            workflow_id="wf_missing",
            workflow_name="wf_missing",
            status=RunStatus.pending,
            task_json="{}",
            branch="main",
            error=None,
            completed_at=None,
            updated_at=None,
        )
        updated_runs: list[object] = []
        run_repo = SimpleNamespace(
            list_runs=lambda: [],
            get_run=lambda run_id: run if run_id == "run_session_test" else None,
            update_run=lambda updated: updated_runs.append(updated),
        )
        workflow_repo = Mock()
        workflow_repo.get_by_id.return_value = None  # triggers error path
        provider_repo = Mock()

        svc = ExecutionService(
            run_repo=run_repo,
            workflow_repo=workflow_repo,
            provider_repo=provider_repo,
            engine=db_engine,
        )

        await svc.launch_execution(
            "run_session_test",
            "wf_missing",
            _prepared_inputs({"instruction": "test"}),
        )
        await asyncio.sleep(0.05)

        assert updated_runs == [run]
        assert run.status == RunStatus.failed
        assert run.error is not None
