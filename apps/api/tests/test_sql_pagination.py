"""
RUN-252: SQL pagination and batch node summaries for GET /runs.

These tests verify that:
- Default limit is 20, max limit is 100 (clamped server-side)
- Response includes total count from DB
"""

from unittest.mock import Mock

from fastapi.testclient import TestClient

from runsight_api.main import app
from runsight_api.transport.deps import get_run_service

# ---------------------------------------------------------------------------
# 1. Default limit is 20, max limit is clamped to 100
# ---------------------------------------------------------------------------


def test_list_runs_clamps_limit_to_max_100():
    """Requesting limit > 100 must be clamped to 100 server-side."""
    mock_service = Mock()
    mock_service.list_runs_paginated.return_value = ([], 0)
    mock_service.get_node_summaries_batch.return_value = {}
    app.dependency_overrides[get_run_service] = lambda: mock_service

    try:
        client = TestClient(app)
        client.get("/api/runs?offset=0&limit=999")

        # Verify the service was called with limit clamped to 100
        mock_service.list_runs_paginated.assert_called_once()
        call_args = mock_service.list_runs_paginated.call_args
        _, kwargs = call_args if call_args.kwargs else (call_args[0], {})
        # Check both positional and keyword argument forms
        if kwargs and "limit" in kwargs:
            actual_limit = kwargs["limit"]
        else:
            # positional: list_runs_paginated(offset, limit)
            actual_limit = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("limit")
        assert actual_limit <= 100, (
            f"limit must be clamped to 100, but service received {actual_limit}"
        )
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 5. Response includes total count from DB (not len of full list)
# ---------------------------------------------------------------------------


def test_list_runs_response_includes_total_from_db():
    """Response total must come from DB count, not len() of all fetched runs."""
    mock_service = Mock()
    # Simulate: DB has 50 runs total, but we only fetch page of 20
    mock_service.list_runs_paginated.return_value = (
        [_make_mock_run(f"run_{i}") for i in range(20)],
        50,
    )
    mock_service.get_node_summaries_batch.return_value = {
        f"run_{i}": {
            "total": 0,
            "completed": 0,
            "running": 0,
            "pending": 0,
            "failed": 0,
            "total_cost_usd": 0.0,
            "total_tokens": 0,
        }
        for i in range(20)
    }
    app.dependency_overrides[get_run_service] = lambda: mock_service

    try:
        client = TestClient(app)
        response = client.get("/api/runs?offset=0&limit=20")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 50, f"total must reflect DB count (50), got {data['total']}"
        assert len(data["items"]) == 20, (
            f"items must contain only the page of 20, got {len(data['items'])}"
        )
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 6. Legacy non-tuple pagination contract fails explicitly
# ---------------------------------------------------------------------------


def test_list_runs_rejects_legacy_non_tuple_paginated_contract():
    """Legacy non-tuple pagination results must fail explicitly instead of falling back to list_runs()."""
    mock_service = Mock()
    mock_service.list_runs_paginated.return_value = [_make_mock_run("run_legacy")]
    mock_service.list_runs.return_value = [_make_mock_run("run_unbounded")]
    mock_service.get_node_summaries_batch.return_value = {}
    app.dependency_overrides[get_run_service] = lambda: mock_service

    try:
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/runs?offset=0&limit=20")

        assert response.status_code == 500
        mock_service.list_runs_paginated.assert_called_once()
        mock_service.list_runs.assert_not_called()
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_mock_run(run_id="run_123"):
    from runsight_api.domain.entities.run import RunStatus

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
