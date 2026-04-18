from __future__ import annotations

from unittest.mock import Mock

import pytest

from runsight_api.domain.errors import InputValidationError
from runsight_api.domain.value_objects import WorkflowEntity
from runsight_api.logic.services.execution_service import ExecutionService


def _workflow_yaml_with_inputs() -> str:
    return """
id: run896_inputs
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
  name: run896_inputs
  entry: start
  transitions:
    - from: start
      to: null
"""


def _workflow_yaml_without_inputs() -> str:
    return """
id: run896_no_inputs
kind: workflow
version: "1.0"
blocks:
  start:
    type: code
    code: |
      def main(data):
          return {"ok": True}
workflow:
  name: run896_no_inputs
  entry: start
  transitions:
    - from: start
      to: null
"""


def _service(yaml: str, *, workflow_id: str = "run896_inputs") -> ExecutionService:
    workflow_repo = Mock()
    workflow_repo.get_by_id.return_value = WorkflowEntity(
        kind="workflow",
        id=workflow_id,
        name=workflow_id,
        yaml=yaml,
        valid=True,
        validation_error=None,
    )
    workflow_repo._get_path.return_value = f"/custom/workflows/{workflow_id}.yaml"
    return ExecutionService(
        run_repo=Mock(),
        workflow_repo=workflow_repo,
        provider_repo=Mock(),
    )


def _error_payload(exc: InputValidationError) -> dict:
    payload = exc.to_dict()
    assert payload["error"] == "Workflow input validation failed"
    assert payload["error_code"] == "WORKFLOW_INPUT_VALIDATION_ERROR"
    assert payload["status_code"] == 422
    assert payload["details"]["kind"] == "workflow_input_validation"
    return payload


class TestWorkflowInputValidationPreparation:
    def test_missing_required_input_raises_canonical_field_error_without_values(self):
        service = _service(_workflow_yaml_with_inputs())

        with pytest.raises(InputValidationError) as exc_info:
            service.prepare_run_inputs("run896_inputs", {}, branch="main")

        payload = _error_payload(exc_info.value)
        assert payload["details"]["workflow_id"] == "run896_inputs"
        assert payload["details"]["fields"] == [
            {
                "field": "query",
                "code": "required",
                "message": "Input 'query' is required.",
                "input_path": ["inputs", "query"],
                "expected_type": "string",
                "actual_type": None,
            }
        ]

    def test_number_type_mismatch_rejects_strings_and_does_not_echo_submitted_value(self):
        service = _service(_workflow_yaml_with_inputs())

        with pytest.raises(InputValidationError) as exc_info:
            service.prepare_run_inputs(
                "run896_inputs",
                {"query": "search", "max_results": "ten"},
                branch="main",
            )

        payload = _error_payload(exc_info.value)
        assert payload["details"]["fields"] == [
            {
                "field": "max_results",
                "code": "type_mismatch",
                "message": "Input 'max_results' must be a number.",
                "input_path": ["inputs", "max_results"],
                "expected_type": "number",
                "actual_type": "string",
            }
        ]
        assert "ten" not in str(payload)

    def test_number_type_mismatch_rejects_bool_even_though_bool_is_int_subclass(self):
        service = _service(_workflow_yaml_with_inputs())

        with pytest.raises(InputValidationError) as exc_info:
            service.prepare_run_inputs(
                "run896_inputs",
                {"query": "search", "max_results": True},
                branch="main",
            )

        payload = _error_payload(exc_info.value)
        assert payload["details"]["fields"][0]["code"] == "type_mismatch"
        assert payload["details"]["fields"][0]["expected_type"] == "number"
        assert payload["details"]["fields"][0]["actual_type"] == "boolean"

    def test_unknown_input_key_raises_unknown_field_error(self):
        service = _service(_workflow_yaml_with_inputs())

        with pytest.raises(InputValidationError) as exc_info:
            service.prepare_run_inputs(
                "run896_inputs",
                {"query": "search", "debug": True},
                branch="main",
            )

        payload = _error_payload(exc_info.value)
        assert payload["details"]["fields"] == [
            {
                "field": "debug",
                "code": "unknown",
                "message": "Input 'debug' is not declared by this workflow.",
                "input_path": ["inputs", "debug"],
                "expected_type": None,
                "actual_type": "boolean",
            }
        ]

    def test_optional_defaults_are_applied_to_normalized_inputs(self):
        service = _service(_workflow_yaml_with_inputs())

        normalized = service.prepare_run_inputs(
            "run896_inputs",
            {"query": "search"},
            branch="main",
        )

        assert normalized == {
            "query": "search",
            "max_results": 10,
            "include_archived": False,
            "payload": {"region": "us"},
            "tags": ["support"],
        }

    def test_no_schema_no_inputs_keeps_no_input_path_empty(self):
        service = _service(_workflow_yaml_without_inputs(), workflow_id="run896_no_inputs")

        assert service.prepare_run_inputs("run896_no_inputs", {}, branch="main") == {}
