from unittest.mock import Mock

from fastapi.testclient import TestClient

from runsight_api.domain.value_objects import WorkflowEntity
from runsight_api.main import app
from runsight_api.transport.deps import get_workflow_service

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


def test_workflows_put_with_canvas_state():
    mock_service = Mock()
    canvas_state = {
        "nodes": [{"id": "node-1", "position": {"x": 10, "y": 20}}],
        "edges": [],
        "viewport": {"x": 1, "y": 2, "zoom": 0.75},
        "selected_node_id": "node-1",
        "canvas_mode": "dag",
    }
    mock_wf = WorkflowEntity(
        id="wf_1",
        name="Updated Flow",
        blocks={},
        edges=[],
        canvas_state=canvas_state,
    )
    mock_service.update_workflow.return_value = mock_wf
    app.dependency_overrides[get_workflow_service] = lambda: mock_service

    response = client.put("/api/workflows/wf_1", json={"canvas_state": canvas_state})
    assert response.status_code == 200
    assert response.json()["canvas_state"]["selected_node_id"] == "node-1"
    mock_service.update_workflow.assert_called_once()
    _, called_data = mock_service.update_workflow.call_args.args
    assert "canvas_state" in called_data
    assert called_data["canvas_state"]["viewport"]["zoom"] == 0.75
    app.dependency_overrides.clear()


def test_workflows_put_with_invalid_canvas_mode_422():
    mock_service = Mock()
    app.dependency_overrides[get_workflow_service] = lambda: mock_service

    response = client.put(
        "/api/workflows/wf_1",
        json={
            "canvas_state": {
                "nodes": [],
                "edges": [],
                "viewport": {"x": 0, "y": 0, "zoom": 1},
                "selected_node_id": None,
                "canvas_mode": "hsm",
            }
        },
    )
    assert response.status_code == 422
    app.dependency_overrides.clear()


def test_workflows_post_commit_returns_commit_metadata():
    mock_service = Mock()
    mock_service.commit_workflow.return_value = {
        "hash": "abc123def456",
        "message": "Save workflow to main",
    }
    app.dependency_overrides[get_workflow_service] = lambda: mock_service

    draft = {
        "yaml": "workflow:\n  name: Updated Flow\n",
        "canvas_state": {
            "nodes": [{"id": "node-1", "position": {"x": 10, "y": 20}}],
            "edges": [],
            "viewport": {"x": 1, "y": 2, "zoom": 0.75},
            "selected_node_id": "node-1",
            "canvas_mode": "dag",
        },
        "message": "Save workflow to main",
    }

    response = client.post("/api/workflows/wf_1/commits", json=draft)

    assert response.status_code == 200
    assert response.json() == {
        "hash": "abc123def456",
        "message": "Save workflow to main",
    }
    mock_service.commit_workflow.assert_called_once_with(
        "wf_1",
        {
            "yaml": "workflow:\n  name: Updated Flow\n",
            "canvas_state": {
                "nodes": [{"id": "node-1", "position": {"x": 10, "y": 20}}],
                "edges": [],
                "viewport": {"x": 1, "y": 2, "zoom": 0.75},
                "selected_node_id": "node-1",
                "canvas_mode": "dag",
            },
        },
        "Save workflow to main",
    )
    app.dependency_overrides.clear()


def test_workflows_post_commit_requires_commit_message():
    mock_service = Mock()
    app.dependency_overrides[get_workflow_service] = lambda: mock_service

    response = client.post(
        "/api/workflows/wf_1/commits",
        json={"yaml": "workflow:\n  name: Updated Flow\n"},
    )

    assert response.status_code == 422
    mock_service.commit_workflow.assert_not_called()
    app.dependency_overrides.clear()


def test_workflows_delete():
    mock_service = Mock()
    mock_service.delete_workflow.return_value = True
    app.dependency_overrides[get_workflow_service] = lambda: mock_service

    response = client.delete("/api/workflows/wf_1")
    assert response.status_code == 200
    assert response.json()["deleted"] is True
    app.dependency_overrides.clear()


def test_workflows_post_simulations_returns_branch_and_commit_sha():
    mock_service = Mock()
    posted_yaml = "workflow:\n  name: Sim Snapshot\n  steps:\n    - id: latest-step\n"
    mock_service.create_simulation.return_value = {
        "branch": "sim/wf_123/20260330/abc12",
        "commit_sha": "1234567890abcdef1234567890abcdef12345678",
    }
    app.dependency_overrides[get_workflow_service] = lambda: mock_service

    response = client.post(
        "/api/workflows/wf_123/simulations",
        json={"yaml": posted_yaml},
    )

    assert response.status_code == 200
    assert response.json() == {
        "branch": "sim/wf_123/20260330/abc12",
        "commit_sha": "1234567890abcdef1234567890abcdef12345678",
    }
    mock_service.create_simulation.assert_called_once()
    args, kwargs = mock_service.create_simulation.call_args
    forwarded_workflow_id = kwargs.get("workflow_id")
    if forwarded_workflow_id is None:
        forwarded_workflow_id = next((arg for arg in args if arg == "wf_123"), None)
    forwarded_yaml = kwargs.get("yaml")
    if forwarded_yaml is None:
        forwarded_yaml = next((arg for arg in args if arg == posted_yaml), None)
    assert forwarded_workflow_id == "wf_123"
    assert forwarded_yaml == posted_yaml
    app.dependency_overrides.clear()
