"""Not-found route failures return normalized Runsight error bodies."""

from fastapi.testclient import TestClient

from runsight_api.main import app
from runsight_api.transport.deps import get_eval_service, get_workflow_service
from tests.transport.error_response_helpers import (
    _assert_runsight_error_shape,
    _stub_eval_service_run_not_found,
    _stub_workflow_service_not_found,
)

client = TestClient(app, raise_server_exceptions=False)


def teardown_function():
    app.dependency_overrides.clear()


def test_workflow_not_found_returns_runsight_error_shape():
    """GET /api/workflows/:id with a nonexistent id must return the canonical
    RunsightError shape: {"error", "error_code", "status_code"} — not {"detail"}."""
    app.dependency_overrides[get_workflow_service] = _stub_workflow_service_not_found

    response = client.get("/api/workflows/nonexistent-workflow-error-shape")

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
        "/api/workflows/nonexistent-workflow-error-shape/enabled",
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

    response = client.delete("/api/workflows/nonexistent-workflow-error-shape")

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

    response = client.get("/api/runs/nonexistent-run-error-shape/regressions")

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
