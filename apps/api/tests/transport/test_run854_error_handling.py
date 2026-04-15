"""Red tests for RUN-854: Standardize API error handling patterns.

These tests verify that all routers use Pattern A (raise RunsightError, let global
handler catch) rather than Pattern B (manual try/catch with JSONResponse) or
Pattern C (HTTPException producing a different response shape).

Tests 1–4 verify consistent response shape: {"error", "error_code", "status_code"}.
Tests 5–6 verify the offending patterns have been removed from source.

Expected failures before the fix:
- test_workflow_not_found_returns_runsight_error_shape         → FAIL (returns JSONResponse via Pattern B)
- test_patch_workflow_not_found_returns_runsight_error_shape   → FAIL (returns JSONResponse via Pattern B)
- test_delete_workflow_not_found_returns_runsight_error_shape  → FAIL (returns JSONResponse via Pattern B)
- test_run_regressions_not_found_returns_runsight_error_shape  → FAIL (returns {"detail": ...} via HTTPException)
- test_no_manual_json_response_in_workflows                    → FAIL (pattern still exists)
- test_no_http_exception_in_runs                               → FAIL (pattern still exists)
"""

from __future__ import annotations

import inspect
from unittest.mock import Mock

from fastapi.testclient import TestClient

from runsight_api.domain.errors import WorkflowNotFound
from runsight_api.main import app
from runsight_api.transport.deps import get_eval_service, get_workflow_service

client = TestClient(app, raise_server_exceptions=False)


def teardown_function():
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _stub_workflow_service_not_found() -> Mock:
    """Return a WorkflowService mock whose methods raise WorkflowNotFound."""
    mock = Mock()
    mock.get_workflow_detail.side_effect = WorkflowNotFound("Workflow not found")
    mock.set_enabled.side_effect = WorkflowNotFound("Workflow not found")
    mock.delete_workflow.side_effect = WorkflowNotFound("Workflow not found")
    return mock


def _stub_eval_service_run_not_found() -> Mock:
    """Return an EvalService mock whose get_run_regressions returns None (run not found)."""
    mock = Mock()
    mock.get_run_regressions.return_value = None
    return mock


def _assert_runsight_error_shape(data: dict, expected_status: int = 404) -> None:
    """Assert the response body matches the RunsightError canonical shape."""
    assert "error" in data, f"Response must contain 'error' key; got: {list(data.keys())}"
    assert "error_code" in data, f"Response must contain 'error_code' key; got: {list(data.keys())}"
    assert "status_code" in data, (
        f"Response must contain 'status_code' key; got: {list(data.keys())}"
    )
    assert "detail" not in data, (
        f"Response must NOT use FastAPI 'detail' key; got: {list(data.keys())}"
    )
    assert data["status_code"] == expected_status, (
        f"status_code in body must be {expected_status}; got {data['status_code']}"
    )


# ---------------------------------------------------------------------------
# 1. GET /api/workflows/:id — not found → RunsightError shape
# ---------------------------------------------------------------------------


def test_workflow_not_found_returns_runsight_error_shape():
    """GET /api/workflows/:id with a nonexistent id must return the canonical
    RunsightError shape: {"error", "error_code", "status_code"} — not {"detail"}."""
    app.dependency_overrides[get_workflow_service] = _stub_workflow_service_not_found

    response = client.get("/api/workflows/nonexistent-workflow-854")

    assert response.status_code == 404
    data = response.json()
    _assert_runsight_error_shape(data, expected_status=404)
    assert data["error_code"] == "WORKFLOW_NOT_FOUND"


# ---------------------------------------------------------------------------
# 2. PATCH /api/workflows/:id/enabled — not found → RunsightError shape
# ---------------------------------------------------------------------------


def test_patch_workflow_not_found_returns_runsight_error_shape():
    """PATCH /api/workflows/:id/enabled for a nonexistent workflow must return the
    canonical RunsightError shape — not {"detail"}."""
    app.dependency_overrides[get_workflow_service] = _stub_workflow_service_not_found

    response = client.patch(
        "/api/workflows/nonexistent-workflow-854/enabled",
        json={"enabled": True},
    )

    assert response.status_code == 404
    data = response.json()
    _assert_runsight_error_shape(data, expected_status=404)
    assert data["error_code"] == "WORKFLOW_NOT_FOUND"


# ---------------------------------------------------------------------------
# 3. DELETE /api/workflows/:id — not found → RunsightError shape
# ---------------------------------------------------------------------------


def test_delete_workflow_not_found_returns_runsight_error_shape():
    """DELETE /api/workflows/:id for a nonexistent workflow must return the
    canonical RunsightError shape — not {"detail"}."""
    app.dependency_overrides[get_workflow_service] = _stub_workflow_service_not_found

    response = client.delete("/api/workflows/nonexistent-workflow-854")

    assert response.status_code == 404
    data = response.json()
    _assert_runsight_error_shape(data, expected_status=404)
    assert data["error_code"] == "WORKFLOW_NOT_FOUND"


# ---------------------------------------------------------------------------
# 4. GET /api/runs/:id/regressions — run not found → RunsightError shape
# ---------------------------------------------------------------------------


def test_run_regressions_not_found_returns_runsight_error_shape():
    """GET /api/runs/:id/regressions when the run does not exist must return the
    canonical RunsightError shape — not the HTTPException {"detail": ...} shape."""
    app.dependency_overrides[get_eval_service] = _stub_eval_service_run_not_found

    response = client.get("/api/runs/nonexistent-run-854/regressions")

    assert response.status_code == 404
    data = response.json()
    _assert_runsight_error_shape(data, expected_status=404)
    # Must NOT use FastAPI's default {"detail": "..."} shape
    assert "detail" not in data, (
        "HTTPException produces {'detail': ...}; RunsightError must be used instead"
    )


# ---------------------------------------------------------------------------
# 5. workflows.py must NOT contain manual JSONResponse(status_code= pattern
# ---------------------------------------------------------------------------


def test_no_manual_json_response_in_workflows():
    """workflows.py must not contain any manual JSONResponse(status_code= calls.
    All error handling must propagate via RunsightError to the global handler."""
    import runsight_api.transport.routers.workflows as workflows_module

    source = inspect.getsource(workflows_module)

    assert "JSONResponse(status_code=" not in source, (
        "workflows.py contains manual JSONResponse(status_code=...) calls — "
        "these must be removed in favour of raising RunsightError and letting "
        "the global handler produce the response."
    )


# ---------------------------------------------------------------------------
# 6. runs.py must NOT contain HTTPException( pattern
# ---------------------------------------------------------------------------


def test_no_http_exception_in_runs():
    """runs.py must not contain any HTTPException( calls.
    All error handling must propagate via RunsightError to the global handler."""
    import runsight_api.transport.routers.runs as runs_module

    source = inspect.getsource(runs_module)

    assert "HTTPException(" not in source, (
        "runs.py contains HTTPException(...) — this must be replaced with the "
        "appropriate RunsightError subclass (RunNotFound) so the global handler "
        "produces a consistent response shape."
    )
