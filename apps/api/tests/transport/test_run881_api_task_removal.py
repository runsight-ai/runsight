"""
RUN-881 — Red tests: task_data → inputs rename, tasks CRUD removal.

These tests verify the post-removal state.  Every test FAILS on the
current codebase and MUST PASS after the Green team applies the changes.
"""

import ast
import inspect
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

API_SRC = Path(__file__).parents[2] / "src" / "runsight_api"


def _source_path(*parts: str) -> Path:
    return API_SRC.joinpath(*parts)


# ---------------------------------------------------------------------------
# 1.  Deleted-file assertions
# ---------------------------------------------------------------------------


def test_tasks_router_file_does_not_exist():
    """transport/routers/tasks.py must be deleted."""
    path = _source_path("transport", "routers", "tasks.py")
    assert not path.exists(), f"tasks.py router should have been deleted but still exists at {path}"


def test_tasks_schema_file_does_not_exist():
    """transport/schemas/tasks.py must be deleted."""
    path = _source_path("transport", "schemas", "tasks.py")
    assert not path.exists(), f"tasks.py schema should have been deleted but still exists at {path}"


def test_task_repo_file_does_not_exist():
    """data/filesystem/task_repo.py must be deleted."""
    path = _source_path("data", "filesystem", "task_repo.py")
    assert not path.exists(), f"task_repo.py should have been deleted but still exists at {path}"


# ---------------------------------------------------------------------------
# 2.  RunCreate schema uses `inputs`, not `task_data`
# ---------------------------------------------------------------------------


def test_run_create_schema_has_inputs_field():
    """RunCreate must declare an `inputs` field."""
    from runsight_api.transport.schemas.runs import RunCreate

    fields = RunCreate.model_fields
    assert "inputs" in fields, (
        f"RunCreate.model_fields must contain 'inputs'; got {list(fields.keys())}"
    )


def test_run_create_schema_has_no_task_data_field():
    """RunCreate must NOT have a `task_data` field."""
    from runsight_api.transport.schemas.runs import RunCreate

    fields = RunCreate.model_fields
    assert "task_data" not in fields, (
        "RunCreate.model_fields must not contain 'task_data' after the rename"
    )


def test_runs_schema_source_has_no_task_data():
    """Source code of schemas/runs.py must contain no reference to task_data."""
    path = _source_path("transport", "schemas", "runs.py")
    source = path.read_text()
    assert "task_data" not in source, (
        "schemas/runs.py still mentions 'task_data'; rename it to 'inputs'"
    )


# ---------------------------------------------------------------------------
# 3.  tasks router NOT registered in the app
# ---------------------------------------------------------------------------


def test_no_api_tasks_route_in_app():
    """The FastAPI app must not expose any route under /api/tasks."""
    from runsight_api.main import app

    task_routes = [
        route
        for route in app.routes
        if hasattr(route, "path") and route.path.startswith("/api/tasks")
    ]
    assert task_routes == [], (
        f"Found /api/tasks routes that should have been removed: {[r.path for r in task_routes]}"
    )


def test_main_does_not_import_tasks_module():
    """main.py must not import the tasks router."""
    path = _source_path("main.py")
    source = path.read_text()
    # After removal, the import of 'tasks' from the routers package must be gone
    assert "tasks" not in source or _tasks_import_removed(source), (
        "main.py still imports the tasks router; remove it from the import block and include_router call"
    )


def _tasks_import_removed(source: str) -> bool:
    """Return True only if any remaining 'tasks' mention is NOT an import or include_router call."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        # Check for: from .transport.routers import ..., tasks, ...
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == "tasks" or alias.asname == "tasks":
                    return False
        # Check for: tasks.router reference in include_router(tasks.router, ...)
        if isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name) and node.value.id == "tasks":
                return False
    return True


# ---------------------------------------------------------------------------
# 4.  HTTP contract: POST /api/runs accepts `inputs` key
# ---------------------------------------------------------------------------


def test_post_runs_passes_inputs_to_service():
    """POST /api/runs with `inputs` must forward that dict to run_service.create_run."""
    from unittest.mock import AsyncMock, Mock

    from fastapi.testclient import TestClient

    from runsight_api.domain.entities.run import RunStatus
    from runsight_api.main import app
    from runsight_api.transport.deps import (
        get_execution_service,
        get_run_service,
    )

    mock_run = Mock()
    mock_run.id = "run_test_881"
    mock_run.workflow_id = "wf_1"
    mock_run.workflow_name = "wf_1"
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

    mock_exec_svc = AsyncMock()
    mock_exec_svc.launch_execution = AsyncMock()

    app.dependency_overrides[get_run_service] = lambda: mock_run_svc
    app.dependency_overrides[get_execution_service] = lambda: mock_exec_svc

    payload = {"instruction": "test run"}
    try:
        client = TestClient(app, raise_server_exceptions=True)
        response = client.post(
            "/api/runs",
            json={
                "workflow_id": "wf_1",
                "inputs": payload,
            },
        )
        assert response.status_code in (200, 201), (
            f"POST /api/runs with 'inputs' key returned {response.status_code}: {response.text}"
        )
        # The service must receive the actual inputs dict, not an empty dict
        args, kwargs = mock_run_svc.create_run.call_args
        # create_run(workflow_id, inputs, source=..., branch=...)
        # inputs should be the second positional arg or the 'inputs' kwarg
        actual_inputs = kwargs.get("inputs") or (args[1] if len(args) > 1 else None)
        assert actual_inputs == payload, (
            f"run_service.create_run must be called with inputs={payload!r}, "
            f"but got inputs={actual_inputs!r}. "
            "The router must pass body.inputs (not body.task_data) to create_run."
        )
    finally:
        app.dependency_overrides.pop(get_run_service, None)
        app.dependency_overrides.pop(get_execution_service, None)


def test_post_runs_rejects_task_data_field():
    """POST /api/runs must reject a body that uses the old `task_data` key (422)."""
    from fastapi.testclient import TestClient

    from runsight_api.main import app

    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(
        "/api/runs",
        json={
            "workflow_id": "wf_1",
            "task_data": {"instruction": "should fail"},
        },
    )
    assert response.status_code == 422, (
        f"POST /api/runs with 'task_data' key should return 422 (unknown field), got {response.status_code}"
    )


# ---------------------------------------------------------------------------
# 5.  HTTP contract: /api/tasks/* must return 404
# ---------------------------------------------------------------------------


def test_get_api_tasks_returns_404():
    """GET /api/tasks must return 404 — route has been removed."""
    from fastapi.testclient import TestClient

    from runsight_api.main import app

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/tasks")
    assert response.status_code == 404, (
        f"GET /api/tasks should return 404 after route removal, got {response.status_code}"
    )


def test_get_api_tasks_by_id_route_not_registered():
    """GET /api/tasks/{id} must not be a registered route — the tasks router was removed."""
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


def test_post_api_tasks_returns_404():
    """POST /api/tasks must return 404 — route has been removed."""
    from fastapi.testclient import TestClient

    from runsight_api.main import app

    client = TestClient(app, raise_server_exceptions=False)
    response = client.post("/api/tasks", json={"name": "x", "type": "task"})
    assert response.status_code == 404, (
        f"POST /api/tasks should return 404 after route removal, got {response.status_code}"
    )


def test_put_api_tasks_route_not_registered():
    """PUT /api/tasks/{id} must not be a registered route — the tasks router was removed."""
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


def test_delete_api_tasks_returns_404():
    """DELETE /api/tasks/{id} must return 404 — route has been removed."""
    from fastapi.testclient import TestClient

    from runsight_api.main import app

    client = TestClient(app, raise_server_exceptions=False)
    response = client.delete("/api/tasks/some-id")
    assert response.status_code == 404, (
        f"DELETE /api/tasks/some-id should return 404 after route removal, got {response.status_code}"
    )


# ---------------------------------------------------------------------------
# 6.  execution_service.py and run_service.py use `inputs`, not `task_data`
# ---------------------------------------------------------------------------


def test_execution_service_launch_execution_uses_inputs_param():
    """ExecutionService.launch_execution must accept `inputs`, not `task_data`."""
    from runsight_api.logic.services.execution_service import ExecutionService

    sig = inspect.signature(ExecutionService.launch_execution)
    params = list(sig.parameters.keys())
    assert "inputs" in params, (
        f"ExecutionService.launch_execution must have an 'inputs' parameter; got {params}"
    )
    assert "task_data" not in params, (
        f"ExecutionService.launch_execution must not have 'task_data' parameter; got {params}"
    )


def test_execution_service_source_has_no_task_data():
    """Source code of execution_service.py must not mention task_data."""
    path = _source_path("logic", "services", "execution_service.py")
    source = path.read_text()
    assert "task_data" not in source, (
        "execution_service.py still mentions 'task_data'; rename all occurrences to 'inputs'"
    )


def test_run_service_create_run_uses_inputs_param():
    """RunService.create_run must accept `inputs`, not `task_data`."""
    from runsight_api.logic.services.run_service import RunService

    sig = inspect.signature(RunService.create_run)
    params = list(sig.parameters.keys())
    assert "inputs" in params, (
        f"RunService.create_run must have an 'inputs' parameter; got {params}"
    )
    assert "task_data" not in params, (
        f"RunService.create_run must not have 'task_data' parameter; got {params}"
    )


def test_run_service_source_has_no_task_data():
    """Source code of run_service.py must not mention task_data."""
    path = _source_path("logic", "services", "run_service.py")
    source = path.read_text()
    assert "task_data" not in source, (
        "run_service.py still mentions 'task_data'; rename all occurrences to 'inputs'"
    )


# ---------------------------------------------------------------------------
# 7.  Docs: running-workflows.md uses `inputs`, not `task_data`
# ---------------------------------------------------------------------------


def test_running_workflows_md_has_no_task_data():
    """running-workflows.md must use `inputs` instead of `task_data`."""
    docs_path = (
        Path(__file__).parents[4]
        / "apps"
        / "site"
        / "src"
        / "content"
        / "docs"
        / "docs"
        / "execution"
        / "running-workflows.md"
    )
    assert docs_path.exists(), f"running-workflows.md not found at {docs_path}"
    source = docs_path.read_text()
    assert "task_data" not in source, (
        "running-workflows.md still mentions 'task_data'; update all occurrences to 'inputs'"
    )


def test_running_workflows_md_mentions_inputs():
    """running-workflows.md must reference `inputs` after the rename."""
    docs_path = (
        Path(__file__).parents[4]
        / "apps"
        / "site"
        / "src"
        / "content"
        / "docs"
        / "docs"
        / "execution"
        / "running-workflows.md"
    )
    assert docs_path.exists(), f"running-workflows.md not found at {docs_path}"
    source = docs_path.read_text()
    assert "inputs" in source, (
        "running-workflows.md must mention 'inputs' after the task_data → inputs rename"
    )
