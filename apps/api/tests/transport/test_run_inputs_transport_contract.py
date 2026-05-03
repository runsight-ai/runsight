"""
Transport contract for the task_data to inputs API removal.

Owner: apps/api transport.
Boundary: FastAPI routes and transport schemas must expose /api/runs with
inputs and must not expose the removed /api/tasks CRUD surface.
Exit criteria: keep as the behavior owner for the route contract; remove only
if superseded by equivalent transport contract coverage.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

from fastapi.testclient import TestClient
from runsight_core.redaction import RunRedactor

from runsight_api.logic.services.execution_service import PreparedRunInputs


def _prepared_inputs(inputs: dict[str, object]) -> PreparedRunInputs:
    return PreparedRunInputs(
        normalized_inputs=dict(inputs),
        input_redactor=RunRedactor(),
    )


class TestRunCreateInputsTransportContract:
    """Owner: apps/api transport schemas. Exit: remove only with replacement contract tests."""

    def test_run_create_schema_has_inputs_field(self):
        from runsight_api.transport.schemas.runs import RunCreate

        fields = RunCreate.model_fields
        assert "inputs" in fields, (
            f"RunCreate.model_fields must contain 'inputs'; got {list(fields.keys())}"
        )

    def test_run_create_schema_has_no_task_data_field(self):
        from runsight_api.transport.schemas.runs import RunCreate

        fields = RunCreate.model_fields
        assert "task_data" not in fields, (
            "RunCreate.model_fields must not contain 'task_data' after the rename"
        )


class TestRunsInputsHttpContract:
    """Owner: apps/api runs router. Exit: remove only with equivalent route tests."""

    def test_post_runs_passes_inputs_to_service(self):
        from runsight_api.domain.entities.run import RunStatus
        from runsight_api.main import app
        from runsight_api.transport.deps import (
            get_execution_service,
            get_run_service,
        )

        mock_run = Mock()
        mock_run.id = "run_task_removal_contract"
        mock_run.workflow_id = "wf_task_removal"
        mock_run.workflow_name = "Task removal workflow"
        mock_run.status = RunStatus.pending
        mock_run.started_at = 1.0
        mock_run.completed_at = None
        mock_run.duration_s = None
        mock_run.total_cost_usd = 0.0
        mock_run.total_tokens = 0
        mock_run.created_at = 1.0
        mock_run.source = "manual"
        mock_run.branch = "main"
        mock_run.commit_sha = None
        mock_run.run_number = None
        mock_run.eval_pass_pct = None
        mock_run.regression_count = None
        mock_run.parent_run_id = None
        mock_run.root_run_id = None
        mock_run.depth = 0
        mock_run.error = None

        mock_run_svc = Mock()
        mock_run_svc.create_run.return_value = mock_run
        mock_run_svc.refresh_run.return_value = mock_run

        payload = {"instruction": "test run"}
        mock_exec_svc = Mock()
        prepared = _prepared_inputs(payload)
        mock_exec_svc.prepare_run_inputs.return_value = prepared
        mock_exec_svc.launch_execution = AsyncMock()

        app.dependency_overrides[get_run_service] = lambda: mock_run_svc
        app.dependency_overrides[get_execution_service] = lambda: mock_exec_svc

        try:
            client = TestClient(app, raise_server_exceptions=True)
            response = client.post(
                "/api/runs",
                json={
                    "workflow_id": "wf_task_removal",
                    "branch": "main",
                    "inputs": payload,
                },
            )
            assert response.status_code in (200, 201), (
                f"POST /api/runs with 'inputs' key returned {response.status_code}: {response.text}"
            )
            args, kwargs = mock_run_svc.create_run.call_args
            actual_inputs = kwargs.get("inputs") or (args[1] if len(args) > 1 else None)
            assert actual_inputs is prepared
            assert actual_inputs.normalized_inputs == payload, (
                f"run_service.create_run must be called with prepared inputs={payload!r}, "
                f"but got inputs={actual_inputs!r}. "
                "The router must prepare body.inputs before create_run."
            )
        finally:
            app.dependency_overrides.pop(get_run_service, None)
            app.dependency_overrides.pop(get_execution_service, None)

    def test_post_runs_rejects_task_data_field(self):
        from runsight_api.main import app

        client = TestClient(app, raise_server_exceptions=False)
        response = client.post(
            "/api/runs",
            json={
                "workflow_id": "wf_task_removal",
                "branch": "main",
                "task_data": {"instruction": "legacy task payload"},
            },
        )
        assert response.status_code == 422, (
            f"POST /api/runs with 'task_data' key should return 422, got {response.status_code}"
        )


class TestTasksRouteRemovalTransportContract:
    """Owner: apps/api transport routes. Exit: remove only with equivalent 404 coverage."""

    def test_no_api_tasks_route_in_app(self):
        from runsight_api.main import app

        task_routes = [
            route
            for route in app.routes
            if hasattr(route, "path") and route.path.startswith("/api/tasks")
        ]
        assert task_routes == [], (
            f"Found /api/tasks routes that should have been removed: "
            f"{[r.path for r in task_routes]}"
        )

    def test_get_api_tasks_returns_404(self):
        from runsight_api.main import app

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/tasks")
        assert response.status_code == 404, (
            f"GET /api/tasks should return 404 after route removal, got {response.status_code}"
        )

    def test_get_api_tasks_by_id_route_not_registered(self):
        from runsight_api.main import app

        task_id_routes = [
            route
            for route in app.routes
            if hasattr(route, "path") and "/tasks/" in route.path and "/api/tasks/" in route.path
        ]
        assert task_id_routes == [], (
            f"Found /api/tasks/{{id}} routes that should have been removed: "
            f"{[r.path for r in task_id_routes]}"
        )

    def test_post_api_tasks_returns_404(self):
        from runsight_api.main import app

        client = TestClient(app, raise_server_exceptions=False)
        response = client.post("/api/tasks", json={"name": "x", "type": "task"})
        assert response.status_code == 404, (
            f"POST /api/tasks should return 404 after route removal, got {response.status_code}"
        )

    def test_put_api_tasks_route_not_registered(self):
        from runsight_api.main import app

        task_put_routes = [
            route
            for route in app.routes
            if hasattr(route, "path")
            and route.path.startswith("/api/tasks")
            and hasattr(route, "methods")
            and "PUT" in (route.methods or set())
        ]
        assert task_put_routes == [], (
            f"Found PUT /api/tasks routes that should have been removed: "
            f"{[r.path for r in task_put_routes]}"
        )

    def test_delete_api_tasks_returns_404(self):
        from runsight_api.main import app

        client = TestClient(app, raise_server_exceptions=False)
        response = client.delete("/api/tasks/some-id")
        assert response.status_code == 404, (
            "DELETE /api/tasks/some-id should return 404 after route removal, "
            f"got {response.status_code}"
        )
