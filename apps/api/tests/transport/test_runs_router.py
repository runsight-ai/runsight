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
