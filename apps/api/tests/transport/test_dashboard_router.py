from unittest.mock import Mock

from fastapi.testclient import TestClient

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
    assert "runs_today" in data
    assert "cost_today_usd" in data
    assert "eval_pass_rate" in data
    assert "regressions" in data
    assert "period_hours" in data
    assert data["period_hours"] == 24
    app.dependency_overrides.clear()
