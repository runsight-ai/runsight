from fastapi.testclient import TestClient
from unittest.mock import Mock
from runsight_api.main import app
from runsight_api.transport.deps import get_run_service

client = TestClient(app)


def test_dashboard_get():
    mock_service = Mock()
    mock_service.list_runs.return_value = []
    app.dependency_overrides[get_run_service] = lambda: mock_service

    response = client.get("/api/dashboard")
    assert response.status_code == 200
    data = response.json()
    assert "active_runs" in data
    assert "completed_runs" in data
    assert "total_cost_usd" in data
    assert "recent_errors" in data
    assert "system_status" in data
    assert data["system_status"] == "online"
    app.dependency_overrides.clear()
