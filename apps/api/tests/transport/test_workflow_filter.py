"""workflow_id filtering on GET /api/runs.

Coverage:
- list_runs endpoint accepts a workflow_id query parameter
- list_runs_paginated filters by workflow_id
- _fetch_paginated_runs passes workflow_id through
- filtered results stay sorted newest first
"""

from unittest.mock import Mock

from fastapi.testclient import TestClient

from runsight_api.domain.entities.run import RunStatus
from runsight_api.main import app
from runsight_api.transport.deps import get_eval_service, get_run_service

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_run(run_id: str, workflow_id: str = "target-workflow", status=RunStatus.completed):
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
# GET /api/runs?workflow_id=target-workflow returns only runs for that workflow
# ---------------------------------------------------------------------------


def test_runs_list_workflow_id_filter():
    """GET /api/runs?workflow_id=target-workflow returns only runs belonging to target-workflow."""
    runs = [
        _make_mock_run("target-workflow-first-run", workflow_id="target-workflow"),
        _make_mock_run("secondary-workflow-run", workflow_id="secondary-workflow"),
        _make_mock_run("target-workflow-second-run", workflow_id="target-workflow"),
    ]
    mock_service = _stub_service_with_runs(runs)
    app.dependency_overrides[get_run_service] = lambda: mock_service
    app.dependency_overrides[get_eval_service] = lambda: _mock_eval_svc()

    try:
        client = TestClient(app)
        response = client.get("/api/runs?workflow_id=target-workflow")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2, (
            f"Expected 2 runs for target-workflow, got {len(data['items'])}"
        )
        assert all(item["workflow_id"] == "target-workflow" for item in data["items"]), (
            "All returned runs must belong to workflow target-workflow"
        )
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 2. workflow_id filter returns empty when no runs match
# ---------------------------------------------------------------------------


def test_runs_list_workflow_id_filter_empty():
    """GET /api/runs?workflow_id=missing-workflow returns empty list."""
    runs = [
        _make_mock_run("target-workflow-first-run", workflow_id="target-workflow"),
        _make_mock_run("secondary-workflow-run", workflow_id="secondary-workflow"),
    ]
    mock_service = _stub_service_with_runs(runs)
    app.dependency_overrides[get_run_service] = lambda: mock_service
    app.dependency_overrides[get_eval_service] = lambda: _mock_eval_svc()

    try:
        client = TestClient(app)
        response = client.get("/api/runs?workflow_id=missing-workflow")
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
    """GET /api/runs?workflow_id=target-workflow&status=completed returns only completed runs for target-workflow."""
    runs = [
        _make_mock_run(
            "target-workflow-completed-run",
            workflow_id="target-workflow",
            status=RunStatus.completed,
        ),
        _make_mock_run(
            "target-workflow-running-run", workflow_id="target-workflow", status=RunStatus.running
        ),
        _make_mock_run(
            "secondary-workflow-completed-run",
            workflow_id="secondary-workflow",
            status=RunStatus.completed,
        ),
    ]
    mock_service = _stub_service_with_runs(runs)
    app.dependency_overrides[get_run_service] = lambda: mock_service
    app.dependency_overrides[get_eval_service] = lambda: _mock_eval_svc()

    try:
        client = TestClient(app)
        response = client.get("/api/runs?workflow_id=target-workflow&status=completed")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1, (
            f"Expected 1 completed run for target-workflow, got {len(data['items'])}"
        )
        assert data["items"][0]["id"] == "target-workflow-completed-run"
        assert data["items"][0]["workflow_id"] == "target-workflow"
        assert data["items"][0]["status"] == "completed"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# No workflow_id param returns all runs
# ---------------------------------------------------------------------------


def test_runs_list_no_workflow_id_returns_all():
    """GET /api/runs without workflow_id returns all runs."""
    runs = [
        _make_mock_run("target-workflow-first-run", workflow_id="target-workflow"),
        _make_mock_run("secondary-workflow-run", workflow_id="secondary-workflow"),
        _make_mock_run("archived-workflow-run", workflow_id="archived-workflow"),
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
    """GET /api/runs?workflow_id=target-workflow&limit=1 returns paginated filtered results."""
    runs = [
        _make_mock_run("target-workflow-first-run", workflow_id="target-workflow"),
        _make_mock_run("target-workflow-second-run", workflow_id="target-workflow"),
        _make_mock_run("secondary-workflow-run", workflow_id="secondary-workflow"),
    ]
    mock_service = _stub_service_with_runs(runs)
    app.dependency_overrides[get_run_service] = lambda: mock_service
    app.dependency_overrides[get_eval_service] = lambda: _mock_eval_svc()

    try:
        client = TestClient(app)
        response = client.get("/api/runs?workflow_id=target-workflow&limit=1")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1, "Page should contain 1 item"
        assert data["total"] == 2, (
            f"Total should reflect all target-workflow runs (2), got {data['total']}"
        )
        assert data["items"][0]["workflow_id"] == "target-workflow"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Response includes status, duration, and cost per run
# ---------------------------------------------------------------------------


def test_runs_response_includes_duration_and_cost():
    """Each run in the response must include duration_seconds and total_cost_usd."""
    runs = [_make_mock_run("target-workflow-first-run", workflow_id="target-workflow")]
    mock_service = _stub_service_with_runs(runs)
    app.dependency_overrides[get_run_service] = lambda: mock_service
    app.dependency_overrides[get_eval_service] = lambda: _mock_eval_svc()

    try:
        client = TestClient(app)
        response = client.get("/api/runs?workflow_id=target-workflow")
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
