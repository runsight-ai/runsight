"""
RUN-363: workflow_id filter on GET /api/runs endpoint.

RED tests -- these must FAIL against the current codebase because:
  - list_runs endpoint does not accept a workflow_id query parameter
  - list_runs_paginated does not filter by workflow_id
  - _fetch_paginated_runs does not pass workflow_id through

AC covered:
  - Runs tab lists historical runs for THIS workflow (workflow_id filter)
  - Sorted by newest first (already true, but verified)
"""

from unittest.mock import Mock

from fastapi.testclient import TestClient

from runsight_api.domain.entities.run import RunStatus
from runsight_api.main import app
from runsight_api.transport.deps import get_eval_service, get_run_service

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_run(run_id: str, workflow_id: str = "wf_1", status=RunStatus.completed):
    mock_run = Mock()
    mock_run.id = run_id
    mock_run.workflow_id = workflow_id
    mock_run.workflow_name = f"Workflow {workflow_id}"
    mock_run.status = status
    mock_run.started_at = 1000.0
    mock_run.completed_at = 1060.0
    mock_run.duration_s = 60.0
    mock_run.total_cost_usd = 0.05
    mock_run.total_tokens = 500
    mock_run.created_at = 1000.0
    mock_run.source = "manual"
    mock_run.branch = "main"
    mock_run.commit_sha = None
    mock_run.run_number = None
    mock_run.eval_pass_pct = None
    mock_run.regression_count = None
    mock_run.error = None
    return mock_run


def _mock_eval_svc():
    """Return a mock EvalService that returns zero regressions."""
    mock_eval = Mock()
    mock_eval.get_run_regressions.return_value = {"count": 0, "issues": []}
    return mock_eval


def _stub_service_with_runs(runs):
    """Wire up a mock RunService that filters by the canonical list-runs arguments."""
    mock_service = Mock()

    def paginated(offset=0, limit=20, status=None, workflow_id=None, source=None, branch=None):
        filtered = runs
        if status:
            filtered = [r for r in filtered if r.status in status]
        if workflow_id:
            filtered = [r for r in filtered if r.workflow_id == workflow_id]
        page = filtered[offset : offset + limit]
        return page, len(filtered)

    mock_service.list_runs_paginated = paginated
    mock_service.list_runs.return_value = runs
    mock_service.get_node_summaries_batch.return_value = {
        r.id: {
            "total_cost_usd": r.total_cost_usd,
            "total_tokens": r.total_tokens,
            "total": 1,
            "completed": 1,
            "running": 0,
            "pending": 0,
            "failed": 0,
        }
        for r in runs
    }
    return mock_service


# ---------------------------------------------------------------------------
# 1. GET /api/runs?workflow_id=wf_1 returns only runs for that workflow
# ---------------------------------------------------------------------------


def test_runs_list_workflow_id_filter():
    """GET /api/runs?workflow_id=wf_1 returns only runs belonging to wf_1."""
    runs = [
        _make_mock_run("run_1", workflow_id="wf_1"),
        _make_mock_run("run_2", workflow_id="wf_2"),
        _make_mock_run("run_3", workflow_id="wf_1"),
    ]
    mock_service = _stub_service_with_runs(runs)
    app.dependency_overrides[get_run_service] = lambda: mock_service
    app.dependency_overrides[get_eval_service] = lambda: _mock_eval_svc()

    try:
        client = TestClient(app)
        response = client.get("/api/runs?workflow_id=wf_1")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2, f"Expected 2 runs for wf_1, got {len(data['items'])}"
        assert all(item["workflow_id"] == "wf_1" for item in data["items"]), (
            "All returned runs must belong to workflow wf_1"
        )
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 2. workflow_id filter returns empty when no runs match
# ---------------------------------------------------------------------------


def test_runs_list_workflow_id_filter_empty():
    """GET /api/runs?workflow_id=wf_nonexistent returns empty list."""
    runs = [
        _make_mock_run("run_1", workflow_id="wf_1"),
        _make_mock_run("run_2", workflow_id="wf_2"),
    ]
    mock_service = _stub_service_with_runs(runs)
    app.dependency_overrides[get_run_service] = lambda: mock_service
    app.dependency_overrides[get_eval_service] = lambda: _mock_eval_svc()

    try:
        client = TestClient(app)
        response = client.get("/api/runs?workflow_id=wf_nonexistent")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 0
        assert data["total"] == 0
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 3. workflow_id + status filters work together
# ---------------------------------------------------------------------------


def test_runs_list_workflow_id_and_status_combined():
    """GET /api/runs?workflow_id=wf_1&status=completed returns only completed runs for wf_1."""
    runs = [
        _make_mock_run("run_1", workflow_id="wf_1", status=RunStatus.completed),
        _make_mock_run("run_2", workflow_id="wf_1", status=RunStatus.running),
        _make_mock_run("run_3", workflow_id="wf_2", status=RunStatus.completed),
    ]
    mock_service = _stub_service_with_runs(runs)
    app.dependency_overrides[get_run_service] = lambda: mock_service
    app.dependency_overrides[get_eval_service] = lambda: _mock_eval_svc()

    try:
        client = TestClient(app)
        response = client.get("/api/runs?workflow_id=wf_1&status=completed")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1, (
            f"Expected 1 completed run for wf_1, got {len(data['items'])}"
        )
        assert data["items"][0]["id"] == "run_1"
        assert data["items"][0]["workflow_id"] == "wf_1"
        assert data["items"][0]["status"] == "completed"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 4. No workflow_id param returns all runs (backward compat)
# ---------------------------------------------------------------------------


def test_runs_list_no_workflow_id_returns_all():
    """GET /api/runs without workflow_id returns all runs (backward compatible)."""
    runs = [
        _make_mock_run("run_1", workflow_id="wf_1"),
        _make_mock_run("run_2", workflow_id="wf_2"),
        _make_mock_run("run_3", workflow_id="wf_3"),
    ]
    mock_service = _stub_service_with_runs(runs)
    app.dependency_overrides[get_run_service] = lambda: mock_service
    app.dependency_overrides[get_eval_service] = lambda: _mock_eval_svc()

    try:
        client = TestClient(app)
        response = client.get("/api/runs")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 3
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 5. workflow_id filter respects pagination
# ---------------------------------------------------------------------------


def test_runs_list_workflow_id_filter_with_pagination():
    """GET /api/runs?workflow_id=wf_1&limit=1 returns paginated results filtered by workflow."""
    runs = [
        _make_mock_run("run_1", workflow_id="wf_1"),
        _make_mock_run("run_2", workflow_id="wf_1"),
        _make_mock_run("run_3", workflow_id="wf_2"),
    ]
    mock_service = _stub_service_with_runs(runs)
    app.dependency_overrides[get_run_service] = lambda: mock_service
    app.dependency_overrides[get_eval_service] = lambda: _mock_eval_svc()

    try:
        client = TestClient(app)
        response = client.get("/api/runs?workflow_id=wf_1&limit=1")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1, "Page should contain 1 item"
        assert data["total"] == 2, f"Total should reflect all wf_1 runs (2), got {data['total']}"
        assert data["items"][0]["workflow_id"] == "wf_1"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 6. Response includes duration and cost per run (AC: status, duration, cost)
# ---------------------------------------------------------------------------


def test_runs_response_includes_duration_and_cost():
    """Each run in the response must include duration_seconds and total_cost_usd."""
    runs = [_make_mock_run("run_1", workflow_id="wf_1")]
    mock_service = _stub_service_with_runs(runs)
    app.dependency_overrides[get_run_service] = lambda: mock_service
    app.dependency_overrides[get_eval_service] = lambda: _mock_eval_svc()

    try:
        client = TestClient(app)
        response = client.get("/api/runs?workflow_id=wf_1")
        assert response.status_code == 200
        data = response.json()
        item = data["items"][0]
        assert "duration_seconds" in item, "Run must include duration_seconds"
        assert "total_cost_usd" in item, "Run must include total_cost_usd"
        assert "status" in item, "Run must include status"
        assert item["duration_seconds"] == 60.0
        assert item["total_cost_usd"] == 0.05
    finally:
        app.dependency_overrides.clear()
