"""Router smoke coverage for /api/workflows endpoints."""

from unittest.mock import Mock

import pytest
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


@pytest.fixture(autouse=True)
def _clear_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def _workflow(**overrides) -> WorkflowEntity:
    data = {
        "kind": "workflow",
        "id": WORKFLOW_ID,
        "name": WORKFLOW_NAME,
        "blocks": {},
        "edges": [],
    }
    data.update(overrides)
    return WorkflowEntity(**data)


def test_workflows_list_smoke_serializes_items_and_warnings() -> None:
    workflow_service = Mock()
    workflow_service.list_workflows.return_value = [_workflow(warnings=[WARNING_PAYLOAD])]
    app.dependency_overrides[get_workflow_service] = lambda: workflow_service

    response = client.get("/api/workflows")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == WORKFLOW_ID
    assert payload["items"][0]["warnings"] == [WARNING_PAYLOAD]
    workflow_service.list_workflows.assert_called_once_with(query=None)


def test_workflows_post_smoke_forwards_yaml_to_service() -> None:
    workflow_service = Mock()
    workflow_service.create_workflow.return_value = _workflow(
        id="new-workflow",
        name="New Workflow",
        warnings=[WARNING_PAYLOAD],
    )
    app.dependency_overrides[get_workflow_service] = lambda: workflow_service

    response = client.post(
        "/api/workflows",
        json={"name": "New Workflow", "yaml": "workflow:\n  name: New Workflow\n"},
    )

    assert response.status_code == 200
    assert response.json()["id"] == "new-workflow"
    assert response.json()["warnings"] == [WARNING_PAYLOAD]
    workflow_service.create_workflow.assert_called_once()
    args, kwargs = workflow_service.create_workflow.call_args
    assert args[0]["yaml"] == "workflow:\n  name: New Workflow\n"
    assert kwargs["commit"] is True


def test_workflows_commit_smoke_forwards_draft_and_message() -> None:
    workflow_service = Mock()
    workflow_service.commit_workflow.return_value = {
        "hash": "abc123def456",
        "message": "Save workflow to main",
    }
    app.dependency_overrides[get_workflow_service] = lambda: workflow_service

    response = client.post(
        f"/api/workflows/{WORKFLOW_ID}/commits",
        json={
            "yaml": "workflow:\n  name: Updated Flow\n",
            "canvas_state": {"nodes": [], "edges": [], "canvas_mode": "dag"},
            "message": "Save workflow to main",
        },
    )

    assert response.status_code == 200
    assert response.json()["hash"] == "abc123def456"
    workflow_service.commit_workflow.assert_called_once()
    args, _kwargs = workflow_service.commit_workflow.call_args
    assert args[0] == WORKFLOW_ID
    assert args[1]["yaml"] == "workflow:\n  name: Updated Flow\n"
    assert args[1]["canvas_state"]["canvas_mode"] == "dag"
    assert args[2] == "Save workflow to main"


def test_workflows_delete_smoke_forwards_force_flag() -> None:
    workflow_service = Mock()
    workflow_service.delete_workflow.return_value = {
        "id": WORKFLOW_ID,
        "deleted": True,
        "runs_deleted": 2,
    }
    app.dependency_overrides[get_workflow_service] = lambda: workflow_service

    response = client.delete(f"/api/workflows/{WORKFLOW_ID}?force=true")

    assert response.status_code == 200
    assert response.json() == {"id": WORKFLOW_ID, "deleted": True, "runs_deleted": 2}
    workflow_service.delete_workflow.assert_called_once_with(WORKFLOW_ID, force=True)
