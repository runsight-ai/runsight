from fastapi.testclient import TestClient
from unittest.mock import Mock
from runsight_api.main import app
from runsight_api.transport.deps import get_workflow_service
from runsight_api.domain.value_objects import WorkflowEntity

client = TestClient(app)


def test_workflows_list():
    mock_service = Mock()
    mock_wf = WorkflowEntity(id="wf_1", name="Test Flow", blocks={}, edges=[])
    mock_service.list_workflows.return_value = [mock_wf]
    app.dependency_overrides[get_workflow_service] = lambda: mock_service

    response = client.get("/api/workflows")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == "wf_1"
    app.dependency_overrides.clear()


def test_workflows_get():
    mock_service = Mock()
    mock_wf = WorkflowEntity(id="wf_1", name="Test Flow", blocks={}, edges=[])
    mock_service.get_workflow.return_value = mock_wf
    app.dependency_overrides[get_workflow_service] = lambda: mock_service

    response = client.get("/api/workflows/wf_1")
    assert response.status_code == 200
    assert response.json()["id"] == "wf_1"
    app.dependency_overrides.clear()


def test_workflows_get_404():
    mock_service = Mock()
    mock_service.get_workflow.return_value = None
    app.dependency_overrides[get_workflow_service] = lambda: mock_service

    response = client.get("/api/workflows/missing")
    assert response.status_code == 404
    app.dependency_overrides.clear()


def test_workflows_post():
    mock_service = Mock()
    mock_wf = WorkflowEntity(id="wf_new", name="New Workflow", blocks={}, edges=[])
    mock_service.create_workflow.return_value = mock_wf
    app.dependency_overrides[get_workflow_service] = lambda: mock_service

    response = client.post("/api/workflows", json={"name": "New Workflow"})
    assert response.status_code == 200
    assert response.json()["id"] == "wf_new"
    app.dependency_overrides.clear()


def test_workflows_post_422():
    app.dependency_overrides.clear()
    response = client.post("/api/workflows", json={"name": 123})  # name must be str
    assert response.status_code == 422


def test_workflows_put():
    mock_service = Mock()
    mock_wf = WorkflowEntity(id="wf_1", name="Updated Flow", blocks={}, edges=[])
    mock_service.update_workflow.return_value = mock_wf
    app.dependency_overrides[get_workflow_service] = lambda: mock_service

    response = client.put("/api/workflows/wf_1", json={"name": "Updated Flow"})
    assert response.status_code == 200
    assert response.json()["name"] == "Updated Flow"
    app.dependency_overrides.clear()


def test_workflows_delete():
    mock_service = Mock()
    mock_service.delete_workflow.return_value = True
    app.dependency_overrides[get_workflow_service] = lambda: mock_service

    response = client.delete("/api/workflows/wf_1")
    assert response.status_code == 200
    assert response.json()["deleted"] is True
    app.dependency_overrides.clear()
