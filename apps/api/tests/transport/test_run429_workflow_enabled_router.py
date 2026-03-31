from unittest.mock import Mock

from fastapi.testclient import TestClient

from runsight_api.domain.errors import WorkflowNotFound
from runsight_api.domain.value_objects import WorkflowEntity
from runsight_api.main import app
from runsight_api.transport.deps import get_workflow_service

client = TestClient(app)


def test_workflows_patch_enabled_updates_and_returns_enabled_state():
    mock_service = Mock()
    mock_service.set_workflow_enabled.return_value = WorkflowEntity(
        id="wf_research",
        name="Research & Review",
        enabled=True,
    )
    app.dependency_overrides[get_workflow_service] = lambda: mock_service

    response = client.patch("/api/workflows/wf_research/enabled", json={"enabled": True})

    assert response.status_code == 200
    assert response.json()["id"] == "wf_research"
    assert response.json()["enabled"] is True
    mock_service.set_workflow_enabled.assert_called_once_with("wf_research", True)
    app.dependency_overrides.clear()


def test_workflows_patch_enabled_can_disable_and_returns_updated_workflow():
    mock_service = Mock()
    mock_service.set_workflow_enabled.return_value = WorkflowEntity(
        id="wf_research",
        name="Research & Review",
        enabled=False,
    )
    app.dependency_overrides[get_workflow_service] = lambda: mock_service

    response = client.patch("/api/workflows/wf_research/enabled", json={"enabled": False})

    assert response.status_code == 200
    assert response.json()["id"] == "wf_research"
    assert response.json()["enabled"] is False
    mock_service.set_workflow_enabled.assert_called_once_with("wf_research", False)
    app.dependency_overrides.clear()


def test_workflows_patch_enabled_returns_404_when_workflow_is_missing():
    mock_service = Mock()
    mock_service.set_workflow_enabled.side_effect = WorkflowNotFound(
        "Workflow wf_missing not found"
    )
    app.dependency_overrides[get_workflow_service] = lambda: mock_service

    response = client.patch("/api/workflows/wf_missing/enabled", json={"enabled": False})

    assert response.status_code == 404
    app.dependency_overrides.clear()
