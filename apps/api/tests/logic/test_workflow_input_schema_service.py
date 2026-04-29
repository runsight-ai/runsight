from __future__ import annotations

from unittest.mock import Mock

from runsight_api.domain.value_objects import WorkflowEntity
from runsight_api.logic.services.workflow_service import WorkflowService


EXPECTED_INPUT_SCHEMA = {
    "query": {
        "type": "string",
        "required": True,
        "default": None,
        "description": "Search phrase",
        "sensitive": False,
    },
    "max_results": {
        "type": "number",
        "required": False,
        "default": 3,
        "description": "Result cap",
        "sensitive": False,
    },
    "api_key": {
        "type": "string",
        "required": True,
        "default": None,
        "description": None,
        "sensitive": True,
    },
}


def _workflow_yaml_with_inputs() -> str:
    return """
id: workflow_inputs_response
kind: workflow
version: "1.0"
inputs:
  query:
    type: string
    description: Search phrase
  max_results:
    type: number
    required: false
    default: 3
    description: Result cap
  api_key:
    type: string
    sensitive: true
blocks:
  start:
    type: code
    code: |
      def main(data):
          return {"ok": True}
workflow:
  name: workflow_inputs_response
  entry: start
  transitions:
    - from: start
      to: null
"""


def _workflow_yaml_without_inputs() -> str:
    return """
id: workflow_without_inputs
kind: workflow
version: "1.0"
blocks:
  start:
    type: code
    code: |
      def main(data):
          return {"ok": True}
workflow:
  name: workflow_without_inputs
  entry: start
  transitions:
    - from: start
      to: null
"""


def _legacy_interface_yaml() -> str:
    return """
id: legacy_interface_response
kind: workflow
version: "1.0"
interface:
  inputs:
    - name: query
      type: string
      target: shared_memory.query
  outputs:
    - name: answer
      source: results.answer
blocks: {}
workflow:
  name: legacy_interface_response
  entry: null
  transitions: []
"""


def _service_with_workflows(*workflows: WorkflowEntity) -> WorkflowService:
    workflow_repo = Mock()
    workflow_repo.list_all.return_value = list(workflows)
    workflow_repo.get_by_id.side_effect = lambda workflow_id: next(
        (workflow for workflow in workflows if workflow.id == workflow_id),
        None,
    )
    workflow_repo.get_block_count.return_value = 1
    workflow_repo.get_file_mtime.return_value = 1711900000.0

    run_repo = Mock()
    run_read_model = Mock()
    run_read_model.get_workflow_health_metrics.return_value = {}

    return WorkflowService(workflow_repo, run_repo, run_read_model=run_read_model)


def _workflow_entity(
    workflow_id: str,
    yaml: str,
    *,
    valid: bool = True,
    validation_error: str | None = None,
) -> WorkflowEntity:
    return WorkflowEntity(
        kind="workflow",
        id=workflow_id,
        name=workflow_id,
        yaml=yaml,
        valid=valid,
        validation_error=validation_error,
    )


class TestWorkflowInputSchemaService:
    def test_get_workflow_detail_adds_explicit_top_level_inputs_as_current_schema(self):
        workflow = _workflow_entity("workflow_inputs_response", _workflow_yaml_with_inputs())
        service = _service_with_workflows(workflow)

        detail = service.get_workflow_detail("workflow_inputs_response")

        assert detail is not None
        assert detail.model_dump()["input_schema"] == EXPECTED_INPUT_SCHEMA

    def test_list_workflows_adds_null_schema_for_workflows_without_inputs(self):
        workflow = _workflow_entity("workflow_without_inputs", _workflow_yaml_without_inputs())
        service = _service_with_workflows(workflow)

        listed = service.list_workflows()

        assert listed[0].id == "workflow_without_inputs"
        assert listed[0].model_dump()["input_schema"] is None

    def test_list_workflows_preserves_invalid_yaml_state_and_uses_null_schema(self):
        workflow = _workflow_entity(
            "invalid_yaml",
            "id: [",
            valid=False,
            validation_error="Malformed YAML",
        )
        service = _service_with_workflows(workflow)

        listed = service.list_workflows()

        assert listed[0].valid is False
        assert listed[0].validation_error == "Malformed YAML"
        assert listed[0].model_dump()["input_schema"] is None

    def test_legacy_interface_is_not_translated_into_input_schema(self):
        workflow = _workflow_entity(
            "legacy_interface_response",
            _legacy_interface_yaml(),
            valid=False,
            validation_error="legacy workflow interface is unsupported",
        )
        service = _service_with_workflows(workflow)

        detail = service.get_workflow_detail("legacy_interface_response")

        assert detail is not None
        assert detail.validation_error == "legacy workflow interface is unsupported"
        assert detail.model_dump()["input_schema"] is None
