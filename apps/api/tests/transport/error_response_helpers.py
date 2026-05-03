"""Shared helpers for Runsight error response tests."""

from unittest.mock import Mock

from fastapi.testclient import TestClient

from runsight_api.domain.errors import WorkflowNotFound
from runsight_api.main import app

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
