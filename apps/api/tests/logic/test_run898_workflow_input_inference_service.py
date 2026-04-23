from __future__ import annotations

from unittest.mock import Mock

from runsight_api.domain.value_objects import WorkflowEntity
from runsight_api.logic.services.workflow_service import WorkflowService


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


def _workflow_yaml_with_inferred_input() -> str:
    return """
id: workflow_inferred_inputs_response
kind: workflow
version: "1.0"
blocks:
  start:
    type: code
    inputs:
      query:
        from: workflow.query
      duplicate:
        from: workflow.query
    code: |
      def main(data):
          return {"ok": True}
workflow:
  name: workflow_inferred_inputs_response
  entry: start
  transitions:
    - from: start
      to: null
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


def _workflow_entity(workflow_id: str, yaml: str) -> WorkflowEntity:
    return WorkflowEntity(
        kind="workflow",
        id=workflow_id,
        name=workflow_id,
        yaml=yaml,
        valid=True,
        validation_error=None,
    )


class TestWorkflowInputInferenceService:
    def test_get_workflow_detail_returns_inferred_schema_when_no_explicit_inputs_exist(self):
        workflow = _workflow_entity(
            "workflow_inferred_inputs_response",
            _workflow_yaml_with_inferred_input(),
        )
        service = _service_with_workflows(workflow)

        detail = service.get_workflow_detail("workflow_inferred_inputs_response")

        assert detail is not None
        assert detail.model_dump()["input_schema"] == EXPECTED_INFERRED_SCHEMA

    def test_list_workflows_returns_inferred_schema_for_gui_run_forms(self):
        workflow = _workflow_entity(
            "workflow_inferred_inputs_response",
            _workflow_yaml_with_inferred_input(),
        )
        service = _service_with_workflows(workflow)

        listed = service.list_workflows()

        assert listed[0].model_dump()["input_schema"] == EXPECTED_INFERRED_SCHEMA
