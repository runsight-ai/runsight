from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, Mock
from runsight_api.main import app
from runsight_api.transport.deps import get_run_service, get_execution_service
from runsight_api.domain.entities.run import RunStatus

client = TestClient(app)


def _make_mock_run(run_id="run_123"):
    mock_run = Mock()
    mock_run.id = run_id
    mock_run.workflow_id = "wf_1"
    mock_run.workflow_name = "wf_1"
    mock_run.status = RunStatus.pending
    mock_run.started_at = 123.0
    mock_run.completed_at = None
    mock_run.duration_s = None
    mock_run.total_cost_usd = 0.0
    mock_run.total_tokens = 0
    mock_run.created_at = 123.0
    return mock_run


def test_runs_list():
    mock_service = Mock()
    mock_run = _make_mock_run()
    mock_service.list_runs.return_value = [mock_run]
    mock_service.get_node_summary.return_value = {
        "total_cost_usd": 0.0,
        "total_tokens": 0,
        "nodes_count": 0,
        "total": 0,
        "completed": 0,
        "running": 0,
        "pending": 0,
        "failed": 0,
    }
    app.dependency_overrides[get_run_service] = lambda: mock_service

    response = client.get("/api/runs")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == "run_123"
    app.dependency_overrides.clear()


def test_runs_get():
    mock_service = Mock()
    mock_run = _make_mock_run()
    mock_service.get_run.return_value = mock_run
    mock_service.get_node_summary.return_value = {
        "total_cost_usd": 0.0,
        "total_tokens": 0,
        "nodes_count": 0,
        "total": 0,
        "completed": 0,
        "running": 0,
        "pending": 0,
        "failed": 0,
    }
    app.dependency_overrides[get_run_service] = lambda: mock_service

    response = client.get("/api/runs/run_123")
    assert response.status_code == 200
    assert response.json()["id"] == "run_123"
    app.dependency_overrides.clear()


def test_runs_get_404():
    mock_service = Mock()
    mock_service.get_run.return_value = None
    app.dependency_overrides[get_run_service] = lambda: mock_service

    response = client.get("/api/runs/missing")
    assert response.status_code == 404
    app.dependency_overrides.clear()


def test_runs_post():
    mock_service = Mock()
    mock_run = _make_mock_run("run_new")
    mock_service.create_run.return_value = mock_run
    mock_exec_service = Mock()
    mock_exec_service.launch_execution = AsyncMock()
    app.dependency_overrides[get_run_service] = lambda: mock_service
    app.dependency_overrides[get_execution_service] = lambda: mock_exec_service

    response = client.post("/api/runs", json={"workflow_id": "wf_1", "task_data": {}})
    assert response.status_code == 200
    assert response.json()["id"] == "run_new"
    app.dependency_overrides.clear()


def test_runs_post_422():
    mock_exec_service = Mock()
    mock_exec_service.launch_execution = AsyncMock()
    app.dependency_overrides[get_execution_service] = lambda: mock_exec_service
    response = client.post("/api/runs", json={"workflow_id": 123})  # must be str
    assert response.status_code == 422
    app.dependency_overrides.clear()


def test_runs_cancel():
    mock_service = Mock()
    mock_run = _make_mock_run()
    mock_run.status = RunStatus.cancelled
    mock_service.cancel_run.return_value = mock_run
    app.dependency_overrides[get_run_service] = lambda: mock_service

    response = client.post("/api/runs/run_123/cancel")
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    app.dependency_overrides.clear()


def test_runs_logs():
    mock_service = Mock()
    mock_service.get_run_logs.return_value = []
    app.dependency_overrides[get_run_service] = lambda: mock_service

    response = client.get("/api/runs/run_123/logs")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    app.dependency_overrides.clear()


def test_runs_nodes():
    mock_service = Mock()
    mock_service.get_run_nodes.return_value = []
    app.dependency_overrides[get_run_service] = lambda: mock_service

    response = client.get("/api/runs/run_123/nodes")
    assert response.status_code == 200
    assert response.json() == []
    app.dependency_overrides.clear()


# ===========================================================================
# RUN-339: Status filter on GET /api/runs
# ===========================================================================


def _make_mock_run_with_status(run_id: str, status: RunStatus):
    """Create a mock run with a specific status."""
    mock_run = _make_mock_run(run_id)
    mock_run.status = status
    return mock_run


def _stub_service_with_runs(runs):
    """Wire up a mock RunService that returns the given runs list."""
    mock_service = Mock()

    def paginated(offset=0, limit=20, status=None):
        if status:
            filtered = [r for r in runs if r.status in status]
        else:
            filtered = runs
        page = filtered[offset : offset + limit]
        return page, len(filtered)

    mock_service.list_runs_paginated = paginated
    mock_service.list_runs.return_value = runs
    mock_service.get_node_summaries_batch.return_value = {}
    mock_service.get_node_summary.return_value = {
        "total_cost_usd": 0.0,
        "total_tokens": 0,
        "nodes_count": 0,
        "total": 0,
        "completed": 0,
        "running": 0,
        "pending": 0,
        "failed": 0,
    }
    return mock_service


def test_runs_list_status_filter_running():
    """GET /api/runs?status=running returns only running runs."""
    runs = [
        _make_mock_run_with_status("run_1", RunStatus.running),
        _make_mock_run_with_status("run_2", RunStatus.pending),
        _make_mock_run_with_status("run_3", RunStatus.completed),
    ]
    mock_service = _stub_service_with_runs(runs)
    app.dependency_overrides[get_run_service] = lambda: mock_service

    response = client.get("/api/runs?status=running")
    assert response.status_code == 200
    data = response.json()
    assert all(item["status"] == "running" for item in data["items"])
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == "run_1"
    app.dependency_overrides.clear()


def test_runs_list_status_filter_multiple():
    """GET /api/runs?status=running&status=pending returns running + pending runs."""
    runs = [
        _make_mock_run_with_status("run_1", RunStatus.running),
        _make_mock_run_with_status("run_2", RunStatus.pending),
        _make_mock_run_with_status("run_3", RunStatus.completed),
        _make_mock_run_with_status("run_4", RunStatus.failed),
    ]
    mock_service = _stub_service_with_runs(runs)
    app.dependency_overrides[get_run_service] = lambda: mock_service

    response = client.get("/api/runs?status=running&status=pending")
    assert response.status_code == 200
    data = response.json()
    statuses = {item["status"] for item in data["items"]}
    assert statuses == {"running", "pending"}
    assert len(data["items"]) == 2
    app.dependency_overrides.clear()


def test_runs_list_no_status_filter_returns_all():
    """GET /api/runs without status param returns all runs (backwards compatible)."""
    runs = [
        _make_mock_run_with_status("run_1", RunStatus.running),
        _make_mock_run_with_status("run_2", RunStatus.pending),
        _make_mock_run_with_status("run_3", RunStatus.completed),
    ]
    mock_service = _stub_service_with_runs(runs)
    app.dependency_overrides[get_run_service] = lambda: mock_service

    response = client.get("/api/runs")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 3
    app.dependency_overrides.clear()


def test_runs_list_status_filter_empty_result():
    """GET /api/runs?status=running returns empty list when no runs match."""
    runs = [
        _make_mock_run_with_status("run_1", RunStatus.completed),
        _make_mock_run_with_status("run_2", RunStatus.failed),
    ]
    mock_service = _stub_service_with_runs(runs)
    app.dependency_overrides[get_run_service] = lambda: mock_service

    response = client.get("/api/runs?status=running")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 0
    assert data["total"] == 0
    app.dependency_overrides.clear()
