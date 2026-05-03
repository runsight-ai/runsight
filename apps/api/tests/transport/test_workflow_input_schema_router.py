from __future__ import annotations

from unittest.mock import Mock

from fastapi.testclient import TestClient

from runsight_api.domain.value_objects import WorkflowEntity
from runsight_api.main import app
from runsight_api.transport.deps import get_workflow_service


client = TestClient(app, raise_server_exceptions=False)


EXPECTED_INPUT_SCHEMA = {
    "query": {
        "type": "string",
        "required": True,
        "default": None,
        "description": "Search phrase",
        "sensitive": False,
    }
}


def teardown_function():
    app.dependency_overrides.clear()


def _workflow(
    workflow_id: str,
    *,
    input_schema: dict | None,
    valid: bool = True,
    validation_error: str | None = None,
) -> WorkflowEntity:
    return WorkflowEntity(
        kind="workflow",
        id=workflow_id,
        name=workflow_id,
        yaml="id: workflow_inputs_response\nkind: workflow\nworkflow:\n  name: response\n",
        valid=valid,
        validation_error=validation_error,
        input_schema=input_schema,
        input_snapshot={"query": "old run value"},
        inputs={"query": "old run value"},
    )


def _stub_service(*workflows: WorkflowEntity):
    service = Mock()
    service.list_workflows.return_value = list(workflows)
    service.get_workflow_detail.side_effect = lambda workflow_id: next(
        (workflow for workflow in workflows if workflow.id == workflow_id),
        None,
    )
    return service


class TestWorkflowInputSchemaRouter:
    def test_get_workflow_returns_input_schema_without_historical_run_values(self):
        workflow = _workflow("workflow_inputs_response", input_schema=EXPECTED_INPUT_SCHEMA)
        app.dependency_overrides[get_workflow_service] = lambda: _stub_service(workflow)

        response = client.get("/api/workflows/workflow_inputs_response")

        assert response.status_code == 200
        payload = response.json()
        assert payload["input_schema"] == EXPECTED_INPUT_SCHEMA
        assert "input_snapshot" not in payload
        assert "inputs" not in payload

    def test_get_workflow_returns_null_input_schema_when_current_workflow_has_no_inputs(self):
        workflow = _workflow("workflow_without_inputs", input_schema=None)
        app.dependency_overrides[get_workflow_service] = lambda: _stub_service(workflow)

        response = client.get("/api/workflows/workflow_without_inputs")

        assert response.status_code == 200
        assert response.json()["input_schema"] is None

    def test_list_workflows_returns_null_input_schema_for_invalid_yaml_without_changing_error_state(
        self,
    ):
        workflow = _workflow(
            "invalid_yaml",
            input_schema=None,
            valid=False,
            validation_error="Malformed YAML",
        )
        app.dependency_overrides[get_workflow_service] = lambda: _stub_service(workflow)

        response = client.get("/api/workflows")

        assert response.status_code == 200
        item = response.json()["items"][0]
        assert item["input_schema"] is None
        assert item["valid"] is False
        assert item["validation_error"] == "Malformed YAML"

    def test_list_workflows_does_not_expose_legacy_interface_as_invocation_schema(self):
        workflow = _workflow(
            "legacy_interface_response",
            input_schema=None,
            valid=False,
            validation_error="legacy workflow interface is unsupported",
        )
        app.dependency_overrides[get_workflow_service] = lambda: _stub_service(workflow)

        response = client.get("/api/workflows")

        assert response.status_code == 200
        item = response.json()["items"][0]
        assert item["input_schema"] is None
        assert "target" not in item
        assert item["validation_error"] == "legacy workflow interface is unsupported"
