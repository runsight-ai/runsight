from __future__ import annotations

from unittest.mock import Mock

from runsight_api.domain.value_objects import WorkflowEntity
from runsight_api.logic.services.execution_service import ExecutionService

WORKFLOW_INPUT_CONTRACT_ID = "workflow_input_contract"
WORKFLOW_INPUT_CONTRACT_PATH = "/custom/workflows/workflow_input_contract.yaml"


def workflow_yaml_with_inputs() -> str:
    return """
id: workflow_input_contract
kind: workflow
version: "1.0"
inputs:
  query:
    type: string
  max_results:
    type: number
    required: false
    default: 10
  include_archived:
    type: boolean
    required: false
    default: false
  payload:
    type: json
    required: false
    default:
      region: us
  tags:
    type: array
    required: false
    default:
      - support
blocks:
  start:
    type: code
    code: |
      def main(data):
          return {"ok": True}
workflow:
  name: workflow_input_validation
  entry: start
  transitions:
    - from: start
      to: null
"""


def workflow_yaml_without_inputs() -> str:
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


def workflow_yaml_with_invalid_workflow_input_ref() -> str:
    return """
id: workflow_input_contract
kind: workflow
version: "1.0"
inputs:
  query:
    type: string
blocks:
  start:
    type: code
    inputs:
      prompt:
        from: workflow.missing
    code: |
      def main(data):
          return {"ok": True}
workflow:
  name: workflow_input_contract
  entry: start
  transitions:
    - from: start
      to: null
"""


def workflow_entity(workflow_id: str, yaml_text: str) -> WorkflowEntity:
    return WorkflowEntity(
        kind="workflow",
        id=workflow_id,
        name=workflow_id,
        yaml=yaml_text,
        valid=True,
        validation_error=None,
    )


def service_with_yaml(
    yaml_text: str,
    *,
    workflow_id: str = "workflow_input_validation",
    git_service=None,
) -> ExecutionService:
    workflow_repo = Mock()
    workflow_repo.get_by_id.return_value = workflow_entity(workflow_id, yaml_text)
    workflow_repo._get_path.return_value = f"/custom/workflows/{workflow_id}.yaml"
    return ExecutionService(
        run_repo=Mock(),
        workflow_repo=workflow_repo,
        provider_repo=Mock(),
        git_service=git_service,
    )


def branch_workflow_service(*, repository_yaml: str, git_yaml: str, git_error=None):
    workflow_repo = Mock()
    workflow_repo.get_by_id.return_value = workflow_entity(
        WORKFLOW_INPUT_CONTRACT_ID,
        repository_yaml,
    )
    workflow_repo._get_path.return_value = WORKFLOW_INPUT_CONTRACT_PATH

    git_service = Mock()
    if git_error is None:
        git_service.read_file.return_value = git_yaml
    else:
        git_service.read_file.side_effect = git_error

    service = ExecutionService(
        run_repo=Mock(),
        workflow_repo=workflow_repo,
        provider_repo=Mock(),
        git_service=git_service,
    )
    return service, workflow_repo, git_service
