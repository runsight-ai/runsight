"""Red tests for RUN-326 + RUN-333: single status writer + fresh session per operation.

RUN-326: _run_workflow must NOT call _set_run_status for completed/failed.
         ExecutionObserver is the sole writer of terminal Run status.

RUN-333: launch_execution must use a fresh session for its error-path DB writes,
         not a long-lived run_repo that holds a stale session.
"""

import asyncio
from unittest.mock import Mock

import pytest
from sqlmodel import Session, SQLModel, create_engine

from runsight_api.domain.entities.run import Run, RunStatus
from runsight_api.logic.observers.execution_observer import ExecutionObserver
from runsight_api.logic.services.execution_service import ExecutionService


# ======================================================================
# C1 — Single status writer (RUN-326)
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
# C8 — Fresh session per operation (RUN-333)
# ======================================================================


class TestFreshSessionPerOperation:
    """ExecutionService.launch_execution must not rely on a long-lived
    run_repo for its error-path DB writes. It should create its own
    session when writing the failure status."""

    @pytest.mark.asyncio
    async def test_launch_execution_error_path_writes_via_engine_session(self):
        """Integration test: when workflow_repo.get_by_id returns None,
        launch_execution should write the failure using a fresh session
        from self.engine, NOT via run_repo."""
        db_engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(db_engine)

        run_id = "run_session_test"
        with Session(db_engine) as session:
            run = Run(
                id=run_id,
                workflow_id="wf_missing",
                workflow_name="wf_missing",
                status=RunStatus.pending,
                task_json="{}",
            )
            session.add(run)
            session.commit()

        # run_repo is a mock — we verify it is NOT called
        run_repo = Mock()
        workflow_repo = Mock()
        workflow_repo.get_by_id.return_value = None  # triggers error path
        provider_repo = Mock()

        svc = ExecutionService(
            run_repo=run_repo,
            workflow_repo=workflow_repo,
            provider_repo=provider_repo,
            engine=db_engine,
        )

        await svc.launch_execution(run_id, "wf_missing", {"instruction": "test"})
        await asyncio.sleep(0.05)

        # run_repo.get_run should NOT have been called (fresh session used instead)
        run_repo.get_run.assert_not_called()
        run_repo.update_run.assert_not_called()

        # But the run should still be marked as failed in the DB
        with Session(db_engine) as session:
            run = session.get(Run, run_id)
            assert run.status == RunStatus.failed, (
                f"Expected run to be marked failed via engine session, got {run.status}"
            )
            assert run.error is not None
