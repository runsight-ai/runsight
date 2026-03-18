"""Red tests for RUN-127: Router wiring — POST /runs triggers execution_service.launch_execution().

After run_service.create_run(), the router must also call
execution_service.launch_execution() to start background workflow execution.
"""

from unittest.mock import AsyncMock, Mock

from fastapi.testclient import TestClient

from runsight_api.main import app
from runsight_api.transport.deps import get_run_service
from runsight_api.domain.entities.run import RunStatus


def _make_mock_run(run_id="run_new"):
    mock_run = Mock()
    mock_run.id = run_id
    mock_run.workflow_id = "wf_1"
    mock_run.workflow_name = "wf_1"
    mock_run.status = RunStatus.pending
    mock_run.started_at = None
    mock_run.completed_at = None
    mock_run.duration_s = None
    mock_run.total_cost_usd = 0.0
    mock_run.total_tokens = 0
    mock_run.created_at = 123.0
    return mock_run


client = TestClient(app)


class TestPostRunsTriggersExecution:
    def test_post_runs_calls_launch_execution(self):
        """POST /api/runs must call execution_service.launch_execution() after creating the run."""
        mock_run_service = Mock()
        mock_run = _make_mock_run("run_exec_1")
        mock_run_service.create_run.return_value = mock_run

        app.dependency_overrides[get_run_service] = lambda: mock_run_service

        # We need to also override the execution_service dependency
        try:
            from runsight_api.transport.deps import get_execution_service

            mock_exec_service = Mock()
            mock_exec_service.launch_execution = AsyncMock()
            app.dependency_overrides[get_execution_service] = lambda: mock_exec_service

            response = client.post(
                "/api/runs",
                json={"workflow_id": "wf_1", "task_data": {"instruction": "do stuff"}},
            )

            assert response.status_code == 200
            assert response.json()["id"] == "run_exec_1"

            # Verify launch_execution was called with correct args
            mock_exec_service.launch_execution.assert_called_once()
            call_args = mock_exec_service.launch_execution.call_args
            assert call_args[0][0] == "run_exec_1"  # run_id
            assert call_args[0][1] == "wf_1"  # workflow_id

        finally:
            app.dependency_overrides.clear()

    def test_post_runs_returns_pending_status(self):
        """POST /api/runs returns the run in pending status (execution is background)."""
        mock_run_service = Mock()
        mock_run = _make_mock_run("run_pending_1")
        mock_run_service.create_run.return_value = mock_run

        app.dependency_overrides[get_run_service] = lambda: mock_run_service

        try:
            from runsight_api.transport.deps import get_execution_service

            mock_exec_service = Mock()
            mock_exec_service.launch_execution = AsyncMock()
            app.dependency_overrides[get_execution_service] = lambda: mock_exec_service

            response = client.post(
                "/api/runs",
                json={"workflow_id": "wf_1", "task_data": {"instruction": "go"}},
            )

            assert response.status_code == 200
            assert response.json()["status"] == "pending"

        finally:
            app.dependency_overrides.clear()

    def test_get_execution_service_dependency_exists(self):
        """The deps module must export a get_execution_service function."""
        from runsight_api.transport.deps import get_execution_service

        assert callable(get_execution_service)
