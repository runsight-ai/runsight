"""Red tests for RUN-208: Remove double observer calls from execution_service.

Bug: execution_service._run_workflow() manually calls observer.on_workflow_start,
on_workflow_complete, and on_workflow_error — but Workflow.run() ALSO calls them
internally. This results in every observer method firing TWICE per lifecycle event,
causing duplicate LogEntry records in the DB and duplicate Run status updates.

Fix: Remove the manual observer calls from _run_workflow(). Workflow.run() is the
single source of observer events.

All tests should FAIL until the manual observer calls are removed.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from runsight_api.domain.entities.log import LogEntry
from runsight_api.domain.entities.run import Run, RunStatus
from runsight_api.logic.services.execution_service import ExecutionService
from runsight_core.state import WorkflowState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_service(**overrides):
    """Create an ExecutionService with mocked repos."""
    return ExecutionService(
        run_repo=overrides.get("run_repo", Mock()),
        workflow_repo=overrides.get("workflow_repo", Mock()),
        provider_repo=overrides.get("provider_repo", Mock()),
        engine=overrides.get("engine", None),
    )


def _make_db():
    """Create an in-memory SQLite DB with all tables."""
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine


def _seed_run(engine, run_id: str) -> None:
    """Insert a pending Run into the DB."""
    with Session(engine) as session:
        run = Run(
            id=run_id,
            workflow_id="wf_1",
            workflow_name="test_workflow",
            status=RunStatus.pending,
            task_json="{}",
        )
        session.add(run)
        session.commit()


# ---------------------------------------------------------------------------
# 1. on_workflow_start called exactly ONCE per run
# ---------------------------------------------------------------------------


class TestOnWorkflowStartCalledOnce:
    """on_workflow_start must fire exactly once — from Workflow.run(), not manually."""

    @pytest.mark.asyncio
    async def test_on_workflow_start_called_once_not_twice(self):
        """on_workflow_start must be called exactly 1 time, not 2.

        Currently FAILS because _run_workflow() calls it manually (line 134)
        AND wf.run() calls it internally — total = 2.
        """
        svc = _make_service()

        call_count = 0

        # We mock wf.run() to simulate what the real Workflow.run() does:
        # it calls observer.on_workflow_start() internally.
        async def fake_wf_run(state, observer=None):
            nonlocal call_count
            if observer:
                observer.on_workflow_start("workflow", state)
            # Count total calls AFTER wf.run returns (including manual ones)
            return state

        mock_wf = Mock()
        mock_wf.run = fake_wf_run

        with patch(
            "runsight_api.logic.services.execution_service.CompositeObserver"
        ) as MockComposite:
            mock_observer = Mock()
            MockComposite.return_value = mock_observer

            await svc._run_workflow("run_1", mock_wf, {"instruction": "test"})

            assert mock_observer.on_workflow_start.call_count == 1, (
                f"on_workflow_start called {mock_observer.on_workflow_start.call_count} times, "
                f"expected exactly 1 (Workflow.run() should be the single source)"
            )


# ---------------------------------------------------------------------------
# 2. on_workflow_complete called exactly ONCE on success
# ---------------------------------------------------------------------------


class TestOnWorkflowCompleteCalledOnce:
    """on_workflow_complete must fire exactly once — from Workflow.run(), not manually."""

    @pytest.mark.asyncio
    async def test_on_workflow_complete_called_once_not_twice(self):
        """on_workflow_complete must be called exactly 1 time on success.

        Currently FAILS because _run_workflow() calls it manually (line 139)
        AND wf.run() calls it internally — total = 2.
        """
        svc = _make_service()

        async def fake_wf_run(state, observer=None):
            if observer:
                observer.on_workflow_start("workflow", state)
                observer.on_workflow_complete("workflow", state, 0.5)
            return state

        mock_wf = Mock()
        mock_wf.run = fake_wf_run

        with patch(
            "runsight_api.logic.services.execution_service.CompositeObserver"
        ) as MockComposite:
            mock_observer = Mock()
            MockComposite.return_value = mock_observer

            await svc._run_workflow("run_2", mock_wf, {"instruction": "test"})

            assert mock_observer.on_workflow_complete.call_count == 1, (
                f"on_workflow_complete called {mock_observer.on_workflow_complete.call_count} times, "
                f"expected exactly 1 (Workflow.run() should be the single source)"
            )


# ---------------------------------------------------------------------------
# 3. on_workflow_error called exactly ONCE on failure
# ---------------------------------------------------------------------------


class TestOnWorkflowErrorCalledOnce:
    """on_workflow_error must fire exactly once — from Workflow.run(), not manually."""

    @pytest.mark.asyncio
    async def test_on_workflow_error_called_once_not_twice(self):
        """on_workflow_error must be called exactly 1 time on failure.

        Currently FAILS because _run_workflow() catches the exception and calls
        on_workflow_error manually (line 142), but Workflow.run() already called
        it internally before re-raising — total = 2.
        """
        svc = _make_service()
        error = RuntimeError("LLM exploded")

        async def fake_wf_run(state, observer=None):
            if observer:
                observer.on_workflow_start("workflow", state)
                observer.on_workflow_error("workflow", error, 0.1)
            raise error

        mock_wf = Mock()
        mock_wf.run = fake_wf_run

        with patch(
            "runsight_api.logic.services.execution_service.CompositeObserver"
        ) as MockComposite:
            mock_observer = Mock()
            MockComposite.return_value = mock_observer

            await svc._run_workflow("run_3", mock_wf, {"instruction": "test"})

            assert mock_observer.on_workflow_error.call_count == 1, (
                f"on_workflow_error called {mock_observer.on_workflow_error.call_count} times, "
                f"expected exactly 1 (Workflow.run() should be the single source)"
            )


# ---------------------------------------------------------------------------
# 4. No duplicate LogEntry records in DB
# ---------------------------------------------------------------------------


class TestNoDuplicateLogEntries:
    """With a real ExecutionObserver and DB, each lifecycle event produces
    exactly one LogEntry — not two."""

    @pytest.mark.asyncio
    async def test_workflow_start_creates_one_log_entry(self):
        """on_workflow_start should produce exactly 1 LogEntry with event=workflow_start.

        Currently FAILS because on_workflow_start fires twice, each inserting a LogEntry.
        """
        engine = _make_db()
        run_id = "run_log_start"
        _seed_run(engine, run_id)

        svc = _make_service(engine=engine)

        async def fake_wf_run(state, observer=None):
            if observer:
                observer.on_workflow_start("workflow", state)
                observer.on_workflow_complete("workflow", state, 0.5)
            return state

        mock_wf = Mock()
        mock_wf.run = fake_wf_run

        await svc._run_workflow(run_id, mock_wf, {"instruction": "test"})

        with Session(engine) as session:
            logs = session.exec(select(LogEntry).where(LogEntry.run_id == run_id)).all()
            start_logs = [log for log in logs if "workflow_start" in log.message]
            assert len(start_logs) == 1, (
                f"Expected 1 workflow_start LogEntry, got {len(start_logs)}. "
                f"Double observer calls produce duplicate DB records."
            )

    @pytest.mark.asyncio
    async def test_workflow_complete_creates_one_log_entry(self):
        """on_workflow_complete should produce exactly 1 LogEntry with event=workflow_complete.

        Currently FAILS because on_workflow_complete fires twice.
        """
        engine = _make_db()
        run_id = "run_log_complete"
        _seed_run(engine, run_id)

        svc = _make_service(engine=engine)

        async def fake_wf_run(state, observer=None):
            if observer:
                observer.on_workflow_start("workflow", state)
                observer.on_workflow_complete("workflow", state, 0.5)
            return state

        mock_wf = Mock()
        mock_wf.run = fake_wf_run

        await svc._run_workflow(run_id, mock_wf, {"instruction": "test"})

        with Session(engine) as session:
            logs = session.exec(select(LogEntry).where(LogEntry.run_id == run_id)).all()
            complete_logs = [log for log in logs if "workflow_complete" in log.message]
            assert len(complete_logs) == 1, (
                f"Expected 1 workflow_complete LogEntry, got {len(complete_logs)}. "
                f"Double observer calls produce duplicate DB records."
            )

    @pytest.mark.asyncio
    async def test_workflow_error_creates_one_log_entry(self):
        """on_workflow_error should produce exactly 1 LogEntry with event=workflow_error.

        Currently FAILS because on_workflow_error fires twice.
        """
        engine = _make_db()
        run_id = "run_log_error"
        _seed_run(engine, run_id)

        svc = _make_service(engine=engine)
        error = RuntimeError("boom")

        async def fake_wf_run(state, observer=None):
            if observer:
                observer.on_workflow_start("workflow", state)
                observer.on_workflow_error("workflow", error, 0.1)
            raise error

        mock_wf = Mock()
        mock_wf.run = fake_wf_run

        await svc._run_workflow(run_id, mock_wf, {"instruction": "test"})

        with Session(engine) as session:
            logs = session.exec(select(LogEntry).where(LogEntry.run_id == run_id)).all()
            error_logs = [log for log in logs if "workflow_error" in log.message]
            assert len(error_logs) == 1, (
                f"Expected 1 workflow_error LogEntry, got {len(error_logs)}. "
                f"Double observer calls produce duplicate DB records."
            )


# ---------------------------------------------------------------------------
# 5. No duplicate Run status updates in DB
# ---------------------------------------------------------------------------


class TestNoDuplicateRunStatusUpdates:
    """ExecutionObserver.on_workflow_start sets Run.status=running, and
    on_workflow_complete sets Run.status=completed. When called twice, the
    DB write happens twice (wasteful and could cause race conditions)."""

    @pytest.mark.asyncio
    async def test_total_log_count_matches_expected_on_success(self):
        """A successful run should produce exactly 2 LogEntries total:
        1x workflow_start + 1x workflow_complete.

        Currently FAILS because each fires twice = 4 total.
        """
        engine = _make_db()
        run_id = "run_total_success"
        _seed_run(engine, run_id)

        svc = _make_service(engine=engine)

        async def fake_wf_run(state, observer=None):
            if observer:
                observer.on_workflow_start("workflow", state)
                observer.on_workflow_complete("workflow", state, 0.5)
            return state

        mock_wf = Mock()
        mock_wf.run = fake_wf_run

        await svc._run_workflow(run_id, mock_wf, {"instruction": "test"})

        with Session(engine) as session:
            logs = session.exec(select(LogEntry).where(LogEntry.run_id == run_id)).all()
            assert len(logs) == 2, (
                f"Expected exactly 2 LogEntries (start + complete), got {len(logs)}. "
                f"Duplicate observer calls produce {len(logs)} records."
            )

    @pytest.mark.asyncio
    async def test_total_log_count_matches_expected_on_failure(self):
        """A failed run should produce exactly 2 LogEntries total:
        1x workflow_start + 1x workflow_error.

        Currently FAILS because each fires twice = 4 total.
        """
        engine = _make_db()
        run_id = "run_total_failure"
        _seed_run(engine, run_id)

        svc = _make_service(engine=engine)
        error = RuntimeError("fail")

        async def fake_wf_run(state, observer=None):
            if observer:
                observer.on_workflow_start("workflow", state)
                observer.on_workflow_error("workflow", error, 0.1)
            raise error

        mock_wf = Mock()
        mock_wf.run = fake_wf_run

        await svc._run_workflow(run_id, mock_wf, {"instruction": "test"})

        with Session(engine) as session:
            logs = session.exec(select(LogEntry).where(LogEntry.run_id == run_id)).all()
            assert len(logs) == 2, (
                f"Expected exactly 2 LogEntries (start + error), got {len(logs)}. "
                f"Duplicate observer calls produce {len(logs)} records."
            )


# ---------------------------------------------------------------------------
# 6. execution_service does NOT call observer methods directly
# ---------------------------------------------------------------------------


class TestExecutionServiceDoesNotCallObserverDirectly:
    """_run_workflow should only pass the observer to wf.run() and let
    Workflow.run() be the single source of all observer events. The execution
    service should NOT call on_workflow_start, on_workflow_complete, or
    on_workflow_error on the observer object itself."""

    @pytest.mark.asyncio
    async def test_no_manual_on_workflow_start(self):
        """execution_service must not call observer.on_workflow_start() directly.

        We give wf.run() a mock that does NOT call any observer methods.
        If on_workflow_start is still called, it means the execution_service
        is calling it manually — which is the bug.
        """
        svc = _make_service()

        # wf.run() that does NOT call observer methods (simulates removing
        # observer interaction to isolate what the execution_service itself does)
        mock_wf = Mock()
        mock_wf.run = AsyncMock(return_value=WorkflowState())

        with patch(
            "runsight_api.logic.services.execution_service.CompositeObserver"
        ) as MockComposite:
            mock_observer = Mock()
            MockComposite.return_value = mock_observer

            await svc._run_workflow("run_no_manual", mock_wf, {"instruction": "test"})

            # wf.run() was a plain AsyncMock (no observer calls inside).
            # If on_workflow_start was called, it must have been by _run_workflow itself.
            assert mock_observer.on_workflow_start.call_count == 0, (
                f"execution_service called on_workflow_start {mock_observer.on_workflow_start.call_count} "
                f"time(s) manually — it should not call observer methods directly"
            )

    @pytest.mark.asyncio
    async def test_no_manual_on_workflow_complete(self):
        """execution_service must not call observer.on_workflow_complete() directly."""
        svc = _make_service()

        mock_wf = Mock()
        mock_wf.run = AsyncMock(return_value=WorkflowState())

        with patch(
            "runsight_api.logic.services.execution_service.CompositeObserver"
        ) as MockComposite:
            mock_observer = Mock()
            MockComposite.return_value = mock_observer

            await svc._run_workflow("run_no_manual_c", mock_wf, {"instruction": "test"})

            assert mock_observer.on_workflow_complete.call_count == 0, (
                f"execution_service called on_workflow_complete {mock_observer.on_workflow_complete.call_count} "
                f"time(s) manually — it should not call observer methods directly"
            )

    @pytest.mark.asyncio
    async def test_no_manual_on_workflow_error(self):
        """execution_service must not call observer.on_workflow_error() directly."""
        svc = _make_service()

        mock_wf = Mock()
        mock_wf.run = AsyncMock(side_effect=RuntimeError("kaboom"))

        with patch(
            "runsight_api.logic.services.execution_service.CompositeObserver"
        ) as MockComposite:
            mock_observer = Mock()
            MockComposite.return_value = mock_observer

            await svc._run_workflow("run_no_manual_e", mock_wf, {"instruction": "test"})

            assert mock_observer.on_workflow_error.call_count == 0, (
                f"execution_service called on_workflow_error {mock_observer.on_workflow_error.call_count} "
                f"time(s) manually — it should not call observer methods directly"
            )
