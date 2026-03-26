"""Red tests for RUN-209: Wire cancel endpoint to asyncio.Task.cancel().

The cancel endpoint currently only sets DB status via RunService.cancel_run()
but never actually stops the running asyncio task. These tests verify:

1. ExecutionService.cancel_execution(run_id) method exists
2. It calls task.cancel() when the task is in _running_tasks
3. It returns True when a task was found and cancelled
4. It returns False when no task is found (already finished)
5. After cancel, task.cancel() was actually invoked
6. The cancel route integrates with execution_service
"""

import asyncio
from unittest.mock import Mock

from fastapi.testclient import TestClient

from runsight_api.logic.services.execution_service import ExecutionService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_service(**overrides) -> ExecutionService:
    """Create an ExecutionService with mock dependencies."""
    defaults = dict(
        run_repo=Mock(),
        workflow_repo=Mock(),
        provider_repo=Mock(),
    )
    defaults.update(overrides)
    return ExecutionService(**defaults)


def _make_mock_task(*, done: bool = False) -> Mock:
    """Create a mock asyncio.Task with cancel() and done() methods."""
    task = Mock(spec=asyncio.Task)
    task.cancel.return_value = True
    task.done.return_value = done
    return task


# ---------------------------------------------------------------------------
# 1. cancel_execution method exists
# ---------------------------------------------------------------------------


class TestCancelExecutionExists:
    def test_cancel_execution_is_not_coroutine(self):
        """cancel_execution should be a regular (sync) method since
        asyncio.Task.cancel() is synchronous."""
        svc = _make_service()
        assert not asyncio.iscoroutinefunction(svc.cancel_execution), (
            "cancel_execution should be a regular method, not async"
        )


# ---------------------------------------------------------------------------
# 2. cancel_execution calls task.cancel()
# ---------------------------------------------------------------------------


class TestCancelExecutionCallsTaskCancel:
    def test_calls_task_cancel_when_task_exists(self):
        """When run_id is in _running_tasks, cancel_execution must call
        task.cancel() on the corresponding asyncio.Task."""
        svc = _make_service()
        mock_task = _make_mock_task()
        svc._running_tasks["run_1"] = mock_task

        svc.cancel_execution("run_1")

        mock_task.cancel.assert_called_once()

    def test_task_cancel_called_with_no_args(self):
        """task.cancel() should be called without arguments (standard usage)."""
        svc = _make_service()
        mock_task = _make_mock_task()
        svc._running_tasks["run_2"] = mock_task

        svc.cancel_execution("run_2")

        mock_task.cancel.assert_called_once_with()


# ---------------------------------------------------------------------------
# 3. cancel_execution returns True when task found
# ---------------------------------------------------------------------------


class TestCancelExecutionReturnsTrue:
    def test_returns_true_when_task_found_and_cancelled(self):
        """cancel_execution returns True when the task was found in
        _running_tasks and cancel() was called."""
        svc = _make_service()
        mock_task = _make_mock_task()
        svc._running_tasks["run_active"] = mock_task

        result = svc.cancel_execution("run_active")

        assert result is True


# ---------------------------------------------------------------------------
# 4. cancel_execution returns False when task not found
# ---------------------------------------------------------------------------


class TestCancelExecutionReturnsFalse:
    def test_returns_false_when_task_not_in_running_tasks(self):
        """cancel_execution returns False when run_id is not in _running_tasks
        (task already finished or never existed)."""
        svc = _make_service()
        # _running_tasks is empty — no task for this run_id

        result = svc.cancel_execution("run_finished")

        assert result is False

    def test_returns_false_for_unknown_run_id(self):
        """cancel_execution returns False for a completely unknown run_id."""
        svc = _make_service()
        svc._running_tasks["run_other"] = _make_mock_task()

        result = svc.cancel_execution("run_nonexistent")

        assert result is False


# ---------------------------------------------------------------------------
# 5. After cancel, task.cancel() was actually called (integration check)
# ---------------------------------------------------------------------------


class TestCancelActuallyCancelsTask:
    def test_cancel_invoked_on_correct_task(self):
        """When multiple tasks are tracked, cancel_execution only cancels
        the task matching the given run_id."""
        svc = _make_service()
        task_a = _make_mock_task()
        task_b = _make_mock_task()
        svc._running_tasks["run_a"] = task_a
        svc._running_tasks["run_b"] = task_b

        svc.cancel_execution("run_a")

        task_a.cancel.assert_called_once()
        task_b.cancel.assert_not_called()

    def test_cancel_does_not_remove_task_from_running_tasks(self):
        """cancel_execution should NOT eagerly remove the task — the
        done_callback handles cleanup when CancelledError propagates."""
        svc = _make_service()
        mock_task = _make_mock_task()
        svc._running_tasks["run_x"] = mock_task

        svc.cancel_execution("run_x")

        # Task removal is handled by done_callback, not cancel_execution itself.
        # The task should still be in _running_tasks after cancel_execution returns.
        assert "run_x" in svc._running_tasks, (
            "cancel_execution should not remove the task from _running_tasks"
        )


# ---------------------------------------------------------------------------
# 6. Cancel route integrates with execution_service
# ---------------------------------------------------------------------------


class TestCancelRouteIntegration:
    """Route-level tests using FastAPI TestClient to verify the cancel
    endpoint calls execution_service.cancel_execution() in addition to
    run_service.cancel_run()."""

    def _make_mock_run(self, run_id="run_123", status="cancelled"):
        from runsight_api.domain.entities.run import RunStatus

        mock_run = Mock()
        mock_run.id = run_id
        mock_run.status = RunStatus.cancelled if status == "cancelled" else status
        return mock_run

    def test_cancel_route_calls_execution_service(self):
        """POST /runs/{id}/cancel must inject execution_service and call
        cancel_execution(run_id)."""
        from runsight_api.main import app
        from runsight_api.transport.deps import get_run_service, get_execution_service

        mock_run_svc = Mock()
        mock_run_svc.cancel_run.return_value = self._make_mock_run()

        mock_exec_svc = Mock()
        mock_exec_svc.cancel_execution.return_value = True

        app.dependency_overrides[get_run_service] = lambda: mock_run_svc
        app.dependency_overrides[get_execution_service] = lambda: mock_exec_svc

        try:
            client = TestClient(app)
            response = client.post("/api/runs/run_123/cancel")

            assert response.status_code == 200
            mock_exec_svc.cancel_execution.assert_called_once_with("run_123")
        finally:
            app.dependency_overrides.clear()

    def test_cancel_route_still_calls_run_service(self):
        """POST /runs/{id}/cancel must still call run_service.cancel_run()
        for DB status update (backwards compatibility)."""
        from runsight_api.main import app
        from runsight_api.transport.deps import get_run_service, get_execution_service

        mock_run_svc = Mock()
        mock_run_svc.cancel_run.return_value = self._make_mock_run()

        mock_exec_svc = Mock()
        mock_exec_svc.cancel_execution.return_value = True

        app.dependency_overrides[get_run_service] = lambda: mock_run_svc
        app.dependency_overrides[get_execution_service] = lambda: mock_exec_svc

        try:
            client = TestClient(app)
            client.post("/api/runs/run_123/cancel")

            mock_run_svc.cancel_run.assert_called_once_with("run_123")
        finally:
            app.dependency_overrides.clear()

    def test_cancel_route_passes_correct_run_id(self):
        """The run_id from the URL path is forwarded to both services."""
        from runsight_api.main import app
        from runsight_api.transport.deps import get_run_service, get_execution_service

        mock_run_svc = Mock()
        mock_run_svc.cancel_run.return_value = self._make_mock_run("run_abc")

        mock_exec_svc = Mock()
        mock_exec_svc.cancel_execution.return_value = False

        app.dependency_overrides[get_run_service] = lambda: mock_run_svc
        app.dependency_overrides[get_execution_service] = lambda: mock_exec_svc

        try:
            client = TestClient(app)
            client.post("/api/runs/run_abc/cancel")

            mock_run_svc.cancel_run.assert_called_once_with("run_abc")
            mock_exec_svc.cancel_execution.assert_called_once_with("run_abc")
        finally:
            app.dependency_overrides.clear()

    def test_cancel_route_handles_already_finished_gracefully(self):
        """When execution_service.cancel_execution() returns False (task
        already finished), the route should still succeed — it's a no-op
        on the execution side but DB status is still updated."""
        from runsight_api.main import app
        from runsight_api.transport.deps import get_run_service, get_execution_service

        mock_run_svc = Mock()
        mock_run_svc.cancel_run.return_value = self._make_mock_run()

        mock_exec_svc = Mock()
        mock_exec_svc.cancel_execution.return_value = False  # already done

        app.dependency_overrides[get_run_service] = lambda: mock_run_svc
        app.dependency_overrides[get_execution_service] = lambda: mock_exec_svc

        try:
            client = TestClient(app)
            response = client.post("/api/runs/run_123/cancel")

            assert response.status_code == 200
            assert response.json()["status"] == "cancelled"
        finally:
            app.dependency_overrides.clear()
