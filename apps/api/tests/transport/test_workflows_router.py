"""Router-level tests for /api/workflows endpoints.

Uses the real app with dependency_overrides — no sys.modules stubbing.
"""

from unittest.mock import Mock

from fastapi.testclient import TestClient

from runsight_api.domain.value_objects import WorkflowEntity
from runsight_api.main import app
from runsight_api.transport.deps import get_workflow_service

client = TestClient(app, raise_server_exceptions=False)
WARNING_PAYLOAD = {
    "message": "Tool definition warning",
    "source": "tool_definitions",
    "context": "lookup_profile",
}
WORKFLOW_ID = "workflow-router-flow"
WORKFLOW_NAME = "Workflow router flow"


def teardown_function():
    app.dependency_overrides.clear()


def test_workflows_list():
    mock_service = Mock()
    mock_wf = WorkflowEntity(
        kind="workflow",
        id=WORKFLOW_ID,
        name=WORKFLOW_NAME,
        blocks={},
        edges=[],
        warnings=[WARNING_PAYLOAD],
    )
    mock_service.list_workflows.return_value = [mock_wf]
    app.dependency_overrides[get_workflow_service] = lambda: mock_service

    response = client.get("/api/workflows")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == WORKFLOW_ID
    assert data["items"][0]["warnings"] == [WARNING_PAYLOAD]


def test_workflows_get():
    mock_service = Mock()
    mock_service.get_workflow.return_value = WorkflowEntity(
        kind="workflow",
        id=WORKFLOW_ID,
        name=WORKFLOW_NAME,
        blocks={},
        edges=[],
    )
    mock_service.get_workflow_detail.return_value = WorkflowEntity(
        kind="workflow",
        id=WORKFLOW_ID,
        name=WORKFLOW_NAME,
        blocks={},
        edges=[],
        commit_sha="abc123def456",
        warnings=[WARNING_PAYLOAD],
    )
    app.dependency_overrides[get_workflow_service] = lambda: mock_service

    response = client.get(f"/api/workflows/{WORKFLOW_ID}")
    assert response.status_code == 200
    assert response.json()["id"] == WORKFLOW_ID
    assert response.json()["commit_sha"] == "abc123def456"
    assert response.json()["warnings"] == [WARNING_PAYLOAD]
    mock_service.get_workflow_detail.assert_called_once_with(WORKFLOW_ID)
    mock_service.get_workflow.assert_not_called()


def test_workflows_get_404():
    mock_service = Mock()
    mock_service.get_workflow.return_value = WorkflowEntity(
        kind="workflow",
        id="workflow-hidden-from-detail",
        name="Existing Flow",
        blocks={},
        edges=[],
    )
    mock_service.get_workflow_detail.return_value = None
    app.dependency_overrides[get_workflow_service] = lambda: mock_service

    response = client.get("/api/workflows/missing")
    assert response.status_code == 404


def test_workflows_post():
    mock_service = Mock()
    mock_wf = WorkflowEntity(
        kind="workflow",
        id="new-workflow",
        name="New Workflow",
        blocks={},
        edges=[],
        warnings=[WARNING_PAYLOAD],
    )
    mock_service.create_workflow.return_value = mock_wf
    app.dependency_overrides[get_workflow_service] = lambda: mock_service

    response = client.post(
        "/api/workflows",
        json={"name": "New Workflow", "yaml": "workflow:\n  name: New Workflow\n"},
    )
    assert response.status_code == 200
    assert response.json()["id"] == "new-workflow"
    assert response.json()["warnings"] == [WARNING_PAYLOAD]


def test_workflows_post_requires_yaml():
    mock_service = Mock()
    mock_service.create_workflow.return_value = WorkflowEntity(
        kind="workflow",
        id="new-workflow",
        name="New Workflow",
        blocks={},
        edges=[],
    )
    app.dependency_overrides[get_workflow_service] = lambda: mock_service

    response = client.post("/api/workflows", json={"name": "New Workflow"})

    assert response.status_code == 422
    mock_service.create_workflow.assert_not_called()


def test_workflows_post_422():
    app.dependency_overrides.clear()
    response = client.post("/api/workflows", json={"name": 123})  # name must be str
    assert response.status_code == 422


def test_workflows_put():
    mock_service = Mock()
    mock_wf = WorkflowEntity(
        kind="workflow",
        id=WORKFLOW_ID,
        name="Updated Flow",
        blocks={},
        edges=[],
        warnings=[WARNING_PAYLOAD],
    )
    mock_service.update_workflow.return_value = mock_wf
    app.dependency_overrides[get_workflow_service] = lambda: mock_service

    response = client.put(
        f"/api/workflows/{WORKFLOW_ID}",
        json={"name": "Updated Flow", "yaml": "workflow:\n  name: Updated Flow\n"},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Updated Flow"
    assert response.json()["warnings"] == [WARNING_PAYLOAD]


def test_workflows_put_requires_yaml():
    mock_service = Mock()
    mock_service.update_workflow.return_value = WorkflowEntity(
        kind="workflow",
        id=WORKFLOW_ID,
        name="Updated Flow",
        blocks={},
        edges=[],
    )
    app.dependency_overrides[get_workflow_service] = lambda: mock_service

    response = client.put(f"/api/workflows/{WORKFLOW_ID}", json={"name": "Updated Flow"})

    assert response.status_code == 422
    mock_service.update_workflow.assert_not_called()


def test_workflows_put_with_canvas_state():
    mock_service = Mock()
    canvas_state = {
        "nodes": [{"id": "router-canvas-node", "position": {"x": 10, "y": 20}}],
        "edges": [],
        "viewport": {"x": 1, "y": 2, "zoom": 0.75},
        "selected_node_id": "router-canvas-node",
        "canvas_mode": "dag",
    }
    mock_wf = WorkflowEntity(
        kind="workflow",
        id=WORKFLOW_ID,
        name="Updated Flow",
        blocks={},
        edges=[],
        warnings=[WARNING_PAYLOAD],
        canvas_state=canvas_state,
    )
    mock_service.update_workflow.return_value = mock_wf
    app.dependency_overrides[get_workflow_service] = lambda: mock_service

    response = client.put(
        f"/api/workflows/{WORKFLOW_ID}",
        json={
            "yaml": "workflow:\n  name: Updated Flow\n",
            "canvas_state": canvas_state,
        },
    )
    assert response.status_code == 200
    assert response.json()["canvas_state"]["selected_node_id"] == "router-canvas-node"
    assert response.json()["warnings"] == [WARNING_PAYLOAD]
    mock_service.update_workflow.assert_called_once()
    _, called_data = mock_service.update_workflow.call_args.args
    assert "canvas_state" in called_data
    assert called_data["canvas_state"]["viewport"]["zoom"] == 0.75


def test_workflows_put_with_invalid_canvas_mode_422():
    mock_service = Mock()
    app.dependency_overrides[get_workflow_service] = lambda: mock_service

    response = client.put(
        f"/api/workflows/{WORKFLOW_ID}",
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
            "nodes": [{"id": "router-canvas-node", "position": {"x": 10, "y": 20}}],
            "edges": [],
            "viewport": {"x": 1, "y": 2, "zoom": 0.75},
            "selected_node_id": "router-canvas-node",
            "canvas_mode": "dag",
        },
        "message": "Save workflow to main",
    }

    response = client.post(f"/api/workflows/{WORKFLOW_ID}/commits", json=draft)

    assert response.status_code == 200
    assert response.json() == {
        "hash": "abc123def456",
        "message": "Save workflow to main",
    }
    mock_service.commit_workflow.assert_called_once_with(
        WORKFLOW_ID,
        {
            "yaml": "workflow:\n  name: Updated Flow\n",
            "canvas_state": {
                "nodes": [{"id": "router-canvas-node", "position": {"x": 10, "y": 20}}],
                "edges": [],
                "viewport": {"x": 1, "y": 2, "zoom": 0.75},
                "selected_node_id": "router-canvas-node",
                "canvas_mode": "dag",
            },
        },
        "Save workflow to main",
    )


def test_workflows_post_commit_requires_commit_message():
    mock_service = Mock()
    app.dependency_overrides[get_workflow_service] = lambda: mock_service

    response = client.post(
        f"/api/workflows/{WORKFLOW_ID}/commits",
        json={"yaml": "workflow:\n  name: Updated Flow\n"},
    )

    assert response.status_code == 422
    mock_service.commit_workflow.assert_not_called()


def test_workflows_post_commit_requires_yaml():
    mock_service = Mock()
    mock_service.commit_workflow.return_value = {
        "hash": "abc123def456",
        "message": "Save workflow to main",
    }
    app.dependency_overrides[get_workflow_service] = lambda: mock_service

    response = client.post(
        f"/api/workflows/{WORKFLOW_ID}/commits",
        json={"message": "Save workflow to main"},
    )

    assert response.status_code == 422
    mock_service.commit_workflow.assert_not_called()


def test_workflows_delete():
    mock_service = Mock()
    mock_service.delete_workflow.return_value = {
        "id": WORKFLOW_ID,
        "deleted": True,
        "runs_deleted": 2,
    }
    app.dependency_overrides[get_workflow_service] = lambda: mock_service

    response = client.delete(f"/api/workflows/{WORKFLOW_ID}")
    assert response.status_code == 200
    assert response.json()["deleted"] is True
    assert response.json()["runs_deleted"] == 2
    mock_service.delete_workflow.assert_called_once_with(WORKFLOW_ID, force=False)


def test_workflows_delete_force_true_forwards_and_returns_runs_deleted():
    mock_service = Mock()
    mock_service.delete_workflow.return_value = {
        "id": WORKFLOW_ID,
        "deleted": True,
        "runs_deleted": 4,
    }
    app.dependency_overrides[get_workflow_service] = lambda: mock_service

    response = client.delete(f"/api/workflows/{WORKFLOW_ID}?force=true")
    assert response.status_code == 200
    assert response.json() == {"id": WORKFLOW_ID, "deleted": True, "runs_deleted": 4}
    mock_service.delete_workflow.assert_called_once_with(WORKFLOW_ID, force=True)


def test_workflows_delete_active_runs_returns_409():
    from runsight_api.domain.errors import WorkflowHasActiveRuns

    mock_service = Mock()
    mock_service.delete_workflow.side_effect = WorkflowHasActiveRuns(
        f"Workflow {WORKFLOW_ID} has active runs"
    )
    app.dependency_overrides[get_workflow_service] = lambda: mock_service

    response = client.delete(f"/api/workflows/{WORKFLOW_ID}")
    assert response.status_code == 409
    assert response.json()["error_code"] == "WORKFLOW_HAS_ACTIVE_RUNS"


def test_workflows_post_simulations_returns_branch_and_commit_sha():
    mock_service = Mock()
    posted_yaml = "workflow:\n  name: Sim Snapshot\n  steps:\n    - id: latest-step\n"
    mock_service.create_simulation.return_value = {
        "branch": "sim/simulation-route-workflow/20260330/abc12",
        "commit_sha": "1234567890abcdef1234567890abcdef12345678",
        "input_schema": {},
    }
    app.dependency_overrides[get_workflow_service] = lambda: mock_service

    response = client.post(
        "/api/workflows/simulation-route-workflow/simulations",
        json={"yaml": posted_yaml},
    )

    assert response.status_code == 200
    assert response.json() == {
        "branch": "sim/simulation-route-workflow/20260330/abc12",
        "commit_sha": "1234567890abcdef1234567890abcdef12345678",
        "input_schema": {},
    }
    mock_service.create_simulation.assert_called_once()
    args, kwargs = mock_service.create_simulation.call_args
    forwarded_workflow_id = kwargs.get("workflow_id")
    if forwarded_workflow_id is None:
        forwarded_workflow_id = next(
            (arg for arg in args if arg == "simulation-route-workflow"),
            None,
        )
    forwarded_yaml = kwargs.get("yaml")
    if forwarded_yaml is None:
        forwarded_yaml = next((arg for arg in args if arg == posted_yaml), None)
    assert forwarded_workflow_id == "simulation-route-workflow"
    assert forwarded_yaml == posted_yaml
