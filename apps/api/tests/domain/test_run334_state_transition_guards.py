"""Red tests for RUN-334: Add Run state transition guards.

Problem: No guard prevents illegal state transitions. A completed run can be
cancelled. A failed run can transition to completed. The observer can overwrite
a cancelled status.

These tests verify:
1. VALID_TRANSITIONS map is defined
2. Illegal transitions raise InvalidStateTransition
3. Terminal states (completed, failed, cancelled) cannot transition to anything
4. All valid transitions are allowed
5. Observer and service use the guard on every status write
"""

import asyncio
import logging
import time
import uuid

import pytest
from sqlmodel import Session, SQLModel, create_engine

from runsight_api.domain.entities.run import Run, RunStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_run(*, status: RunStatus, **overrides) -> Run:
    """Build a Run with sensible defaults."""
    defaults = dict(
        id=f"run_{uuid.uuid4().hex[:8]}",
        workflow_id="wf_test",
        workflow_name="Test Workflow",
        task_json="{}",
        created_at=time.time(),
        updated_at=time.time(),
    )
    defaults.update(overrides)
    return Run(status=status, **defaults)


# ---------------------------------------------------------------------------
# 1. VALID_TRANSITIONS map exists and has correct shape
# ---------------------------------------------------------------------------


class TestValidTransitionsMap:
    def test_valid_transitions_importable(self):
        """VALID_TRANSITIONS can be imported from the run entity module."""
        from runsight_api.domain.entities.run import VALID_TRANSITIONS

        assert isinstance(VALID_TRANSITIONS, dict)

    def test_all_statuses_are_keys(self):
        """Every RunStatus value appears as a key in VALID_TRANSITIONS."""
        from runsight_api.domain.entities.run import VALID_TRANSITIONS

        for status in RunStatus:
            assert status in VALID_TRANSITIONS, f"Missing key: {status}"

    def test_pending_can_transition_to_running_cancelled_failed(self):
        """pending -> {running, cancelled, failed}."""
        from runsight_api.domain.entities.run import VALID_TRANSITIONS

        expected = {RunStatus.running, RunStatus.cancelled, RunStatus.failed}
        assert VALID_TRANSITIONS[RunStatus.pending] == expected

    def test_running_can_transition_to_completed_failed_cancelled(self):
        """running -> {completed, failed, cancelled}."""
        from runsight_api.domain.entities.run import VALID_TRANSITIONS

        expected = {RunStatus.completed, RunStatus.failed, RunStatus.cancelled}
        assert VALID_TRANSITIONS[RunStatus.running] == expected

    def test_completed_is_terminal(self):
        """completed -> empty set (terminal)."""
        from runsight_api.domain.entities.run import VALID_TRANSITIONS

        assert VALID_TRANSITIONS[RunStatus.completed] == set()

    def test_failed_is_terminal(self):
        """failed -> empty set (terminal)."""
        from runsight_api.domain.entities.run import VALID_TRANSITIONS

        assert VALID_TRANSITIONS[RunStatus.failed] == set()

    def test_cancelled_is_terminal(self):
        """cancelled -> empty set (terminal)."""
        from runsight_api.domain.entities.run import VALID_TRANSITIONS

        assert VALID_TRANSITIONS[RunStatus.cancelled] == set()


# ---------------------------------------------------------------------------
# 2. InvalidStateTransition error exists
# ---------------------------------------------------------------------------


class TestInvalidStateTransitionError:
    def test_error_class_importable(self):
        """InvalidStateTransition can be imported from domain.entities.run."""
        from runsight_api.domain.entities.run import InvalidStateTransition

        assert issubclass(InvalidStateTransition, Exception)

    def test_error_is_valueerror_subclass(self):
        """InvalidStateTransition inherits from ValueError for compatibility."""
        from runsight_api.domain.entities.run import InvalidStateTransition

        assert issubclass(InvalidStateTransition, ValueError)

    def test_error_message_includes_from_and_to(self):
        """Error message mentions both the current and target status."""
        from runsight_api.domain.entities.run import InvalidStateTransition

        err = InvalidStateTransition(RunStatus.completed, RunStatus.running)
        msg = str(err)
        assert "completed" in msg
        assert "running" in msg


# ---------------------------------------------------------------------------
# 3. validate_transition function
# ---------------------------------------------------------------------------


class TestValidateTransitionFunction:
    def test_function_importable(self):
        """validate_transition can be imported from domain.entities.run."""
        from runsight_api.domain.entities.run import validate_transition

        assert callable(validate_transition)

    def test_valid_pending_to_running(self):
        """pending -> running does not raise."""
        from runsight_api.domain.entities.run import validate_transition

        validate_transition(RunStatus.pending, RunStatus.running)  # no exception

    def test_valid_pending_to_cancelled(self):
        """pending -> cancelled does not raise."""
        from runsight_api.domain.entities.run import validate_transition

        validate_transition(RunStatus.pending, RunStatus.cancelled)

    def test_valid_pending_to_failed(self):
        """pending -> failed does not raise."""
        from runsight_api.domain.entities.run import validate_transition

        validate_transition(RunStatus.pending, RunStatus.failed)

    def test_valid_running_to_completed(self):
        """running -> completed does not raise."""
        from runsight_api.domain.entities.run import validate_transition

        validate_transition(RunStatus.running, RunStatus.completed)

    def test_valid_running_to_failed(self):
        """running -> failed does not raise."""
        from runsight_api.domain.entities.run import validate_transition

        validate_transition(RunStatus.running, RunStatus.failed)

    def test_valid_running_to_cancelled(self):
        """running -> cancelled does not raise."""
        from runsight_api.domain.entities.run import validate_transition

        validate_transition(RunStatus.running, RunStatus.cancelled)

    def test_invalid_completed_to_cancelled(self):
        """completed -> cancelled raises InvalidStateTransition."""
        from runsight_api.domain.entities.run import (
            InvalidStateTransition,
            validate_transition,
        )

        with pytest.raises(InvalidStateTransition):
            validate_transition(RunStatus.completed, RunStatus.cancelled)

    def test_invalid_completed_to_failed(self):
        """completed -> failed raises InvalidStateTransition."""
        from runsight_api.domain.entities.run import (
            InvalidStateTransition,
            validate_transition,
        )

        with pytest.raises(InvalidStateTransition):
            validate_transition(RunStatus.completed, RunStatus.failed)

    def test_invalid_completed_to_running(self):
        """completed -> running raises InvalidStateTransition."""
        from runsight_api.domain.entities.run import (
            InvalidStateTransition,
            validate_transition,
        )

        with pytest.raises(InvalidStateTransition):
            validate_transition(RunStatus.completed, RunStatus.running)

    def test_invalid_failed_to_completed(self):
        """failed -> completed raises InvalidStateTransition."""
        from runsight_api.domain.entities.run import (
            InvalidStateTransition,
            validate_transition,
        )

        with pytest.raises(InvalidStateTransition):
            validate_transition(RunStatus.failed, RunStatus.completed)

    def test_invalid_failed_to_running(self):
        """failed -> running raises InvalidStateTransition."""
        from runsight_api.domain.entities.run import (
            InvalidStateTransition,
            validate_transition,
        )

        with pytest.raises(InvalidStateTransition):
            validate_transition(RunStatus.failed, RunStatus.running)

    def test_invalid_cancelled_to_completed(self):
        """cancelled -> completed raises InvalidStateTransition."""
        from runsight_api.domain.entities.run import (
            InvalidStateTransition,
            validate_transition,
        )

        with pytest.raises(InvalidStateTransition):
            validate_transition(RunStatus.cancelled, RunStatus.completed)

    def test_invalid_cancelled_to_running(self):
        """cancelled -> running raises InvalidStateTransition."""
        from runsight_api.domain.entities.run import (
            InvalidStateTransition,
            validate_transition,
        )

        with pytest.raises(InvalidStateTransition):
            validate_transition(RunStatus.cancelled, RunStatus.running)

    def test_invalid_pending_to_completed(self):
        """pending -> completed raises (must go through running first)."""
        from runsight_api.domain.entities.run import (
            InvalidStateTransition,
            validate_transition,
        )

        with pytest.raises(InvalidStateTransition):
            validate_transition(RunStatus.pending, RunStatus.completed)

    def test_same_status_is_noop(self):
        """Transitioning to the same status does not raise (idempotent)."""
        from runsight_api.domain.entities.run import validate_transition

        for status in RunStatus:
            validate_transition(status, status)  # should not raise


# ---------------------------------------------------------------------------
# 4. Observer uses guard — terminal states are protected
# ---------------------------------------------------------------------------


@pytest.fixture
def db_engine():
    """In-memory SQLite engine with all tables."""
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine


def _seed_run(engine, *, status: RunStatus) -> str:
    """Insert a run with a given status and return its id."""
    run_id = f"run_{uuid.uuid4().hex[:8]}"
    with Session(engine) as session:
        run = Run(
            id=run_id,
            workflow_id="wf_test",
            workflow_name="Test Workflow",
            status=status,
            task_json="{}",
        )
        session.add(run)
        session.commit()
    return run_id


class TestObserverRespectsGuard:
    """Observer methods must not overwrite terminal states."""

    def test_on_workflow_complete_skips_if_already_cancelled(self, db_engine):
        """If run is already cancelled, on_workflow_complete must not overwrite to completed."""
        from runsight_api.logic.observers.execution_observer import ExecutionObserver
        from runsight_core.state import WorkflowState

        run_id = _seed_run(db_engine, status=RunStatus.cancelled)
        obs = ExecutionObserver(engine=db_engine, run_id=run_id)
        obs.on_workflow_complete("wf", WorkflowState(), 5.0)

        with Session(db_engine) as session:
            run = session.get(Run, run_id)
            assert run.status == RunStatus.cancelled, "Observer overwrote cancelled with completed"

    def test_on_workflow_error_skips_if_already_completed(self, db_engine):
        """If run is already completed, on_workflow_error must not overwrite to failed."""
        from runsight_api.logic.observers.execution_observer import ExecutionObserver

        run_id = _seed_run(db_engine, status=RunStatus.completed)
        obs = ExecutionObserver(engine=db_engine, run_id=run_id)
        obs.on_workflow_error("wf", RuntimeError("late error"), 1.0)

        with Session(db_engine) as session:
            run = session.get(Run, run_id)
            assert run.status == RunStatus.completed, "Observer overwrote completed with failed"

    def test_on_workflow_error_skips_if_already_cancelled(self, db_engine):
        """If run is already cancelled, on_workflow_error must not overwrite to failed."""
        from runsight_api.logic.observers.execution_observer import ExecutionObserver

        run_id = _seed_run(db_engine, status=RunStatus.cancelled)
        obs = ExecutionObserver(engine=db_engine, run_id=run_id)
        obs.on_workflow_error("wf", RuntimeError("late"), 1.0)

        with Session(db_engine) as session:
            run = session.get(Run, run_id)
            assert run.status == RunStatus.cancelled, "Observer overwrote cancelled with failed"

    def test_on_workflow_start_skips_if_already_failed(self, db_engine):
        """If run is already failed, on_workflow_start must not overwrite to running."""
        from runsight_api.logic.observers.execution_observer import ExecutionObserver
        from runsight_core.state import WorkflowState

        run_id = _seed_run(db_engine, status=RunStatus.failed)
        obs = ExecutionObserver(engine=db_engine, run_id=run_id)
        obs.on_workflow_start("wf", WorkflowState())

        with Session(db_engine) as session:
            run = session.get(Run, run_id)
            assert run.status == RunStatus.failed, "Observer overwrote failed with running"

    def test_on_workflow_complete_after_cancel_via_error(self, db_engine):
        """A CancelledError sets cancelled; subsequent complete must not overwrite."""
        from runsight_api.logic.observers.execution_observer import ExecutionObserver
        from runsight_core.state import WorkflowState

        run_id = _seed_run(db_engine, status=RunStatus.running)
        obs = ExecutionObserver(engine=db_engine, run_id=run_id)

        # First: cancel via CancelledError
        obs.on_workflow_error("wf", asyncio.CancelledError(), 1.0)

        # Then: a late on_workflow_complete arrives
        obs.on_workflow_complete("wf", WorkflowState(), 2.0)

        with Session(db_engine) as session:
            run = session.get(Run, run_id)
            assert run.status == RunStatus.cancelled, (
                "Late on_workflow_complete overwrote cancelled status"
            )


# ---------------------------------------------------------------------------
# 5. RunService.cancel_run uses guard
# ---------------------------------------------------------------------------


class TestRunServiceCancelGuard:
    """cancel_run must only cancel runs that are in a cancellable state."""

    def test_cancel_completed_run_raises(self):
        """Cancelling an already-completed run must raise InvalidStateTransition."""
        from unittest.mock import Mock

        from runsight_api.domain.entities.run import InvalidStateTransition
        from runsight_api.logic.services.run_service import RunService

        run = _make_run(status=RunStatus.completed)
        run_repo = Mock()
        run_repo.get_run.return_value = run

        svc = RunService(run_repo, Mock())
        with pytest.raises(InvalidStateTransition):
            svc.cancel_run(run.id)

    def test_cancel_failed_run_raises(self):
        """Cancelling an already-failed run must raise InvalidStateTransition."""
        from unittest.mock import Mock

        from runsight_api.domain.entities.run import InvalidStateTransition
        from runsight_api.logic.services.run_service import RunService

        run = _make_run(status=RunStatus.failed)
        run_repo = Mock()
        run_repo.get_run.return_value = run

        svc = RunService(run_repo, Mock())
        with pytest.raises(InvalidStateTransition):
            svc.cancel_run(run.id)

    def test_cancel_already_cancelled_run_is_idempotent(self):
        """Cancelling an already-cancelled run is idempotent (same-status no-op)."""
        from unittest.mock import Mock

        from runsight_api.logic.services.run_service import RunService

        run = _make_run(status=RunStatus.cancelled)
        run_repo = Mock()
        run_repo.get_run.return_value = run
        run_repo.update_run.return_value = run

        svc = RunService(run_repo, Mock())
        result = svc.cancel_run(run.id)
        assert result.status == RunStatus.cancelled

    def test_cancel_pending_run_succeeds(self):
        """Cancelling a pending run succeeds."""
        from unittest.mock import Mock

        from runsight_api.logic.services.run_service import RunService

        run = _make_run(status=RunStatus.pending)
        run_repo = Mock()
        run_repo.get_run.return_value = run
        run_repo.update_run.return_value = run

        svc = RunService(run_repo, Mock())
        result = svc.cancel_run(run.id)
        assert result.status == RunStatus.cancelled

    def test_cancel_running_run_succeeds(self):
        """Cancelling a running run succeeds."""
        from unittest.mock import Mock

        from runsight_api.logic.services.run_service import RunService

        run = _make_run(status=RunStatus.running, started_at=time.time())
        run_repo = Mock()
        run_repo.get_run.return_value = run
        run_repo.update_run.return_value = run

        svc = RunService(run_repo, Mock())
        result = svc.cancel_run(run.id)
        assert result.status == RunStatus.cancelled


# ---------------------------------------------------------------------------
# 6. Guard logging — invalid transitions log a warning
# ---------------------------------------------------------------------------


class TestGuardLogging:
    """Invalid transitions in the observer should be logged, not silently swallowed."""

    def test_observer_logs_warning_on_invalid_transition(self, db_engine, caplog):
        """Observer logs a warning when it skips an invalid state transition."""
        from runsight_api.logic.observers.execution_observer import ExecutionObserver

        run_id = _seed_run(db_engine, status=RunStatus.completed)
        obs = ExecutionObserver(engine=db_engine, run_id=run_id)

        with caplog.at_level(logging.WARNING):
            obs.on_workflow_error("wf", RuntimeError("late"), 1.0)

        # Should have logged a warning about the invalid transition
        assert any("transition" in record.message.lower() for record in caplog.records), (
            "Expected a warning log about the invalid state transition"
        )
