from __future__ import annotations

from unittest.mock import Mock

from fastapi.testclient import TestClient

from runsight_api.domain.value_objects import WorkflowEntity
from runsight_api.main import app
from runsight_api.transport.deps import get_workflow_service


client = TestClient(app, raise_server_exceptions=False)


EXPECTED_INFERRED_SCHEMA = {
    "query": {
        "type": "string",
        "required": True,
        "default": None,
        "description": None,
        "sensitive": False,
        "source": "inferred",
    }
}


def teardown_function():
    app.dependency_overrides.clear()


def _workflow(workflow_id: str, input_schema: dict) -> WorkflowEntity:
    return WorkflowEntity(
        kind="workflow",
        id=workflow_id,
        name=workflow_id,
        yaml="id: workflow_inferred_inputs_response\nkind: workflow\nworkflow:\n  name: response\n",
        valid=True,
        validation_error=None,
        input_schema=input_schema,
    )


def _stub_service(*workflows: WorkflowEntity):
    service = Mock()
    service.list_workflows.return_value = list(workflows)
    service.get_workflow_detail.side_effect = lambda workflow_id: next(
        (workflow for workflow in workflows if workflow.id == workflow_id),
        None,
    )
    return service


class TestWorkflowInputInferenceRouter:
    def test_get_workflow_preserves_inferred_source_marker_for_gui_display(self):
        workflow = _workflow("workflow_inferred_inputs_response", EXPECTED_INFERRED_SCHEMA)
        app.dependency_overrides[get_workflow_service] = lambda: _stub_service(workflow)

        response = client.get("/api/workflows/workflow_inferred_inputs_response")

        assert response.status_code == 200
        assert response.json()["input_schema"] == EXPECTED_INFERRED_SCHEMA

    def test_list_workflows_preserves_inferred_source_marker_for_gui_display(self):
        workflow = _workflow("workflow_inferred_inputs_response", EXPECTED_INFERRED_SCHEMA)
        app.dependency_overrides[get_workflow_service] = lambda: _stub_service(workflow)

        response = client.get("/api/workflows")

        assert response.status_code == 200
        assert response.json()["items"][0]["input_schema"] == EXPECTED_INFERRED_SCHEMA
