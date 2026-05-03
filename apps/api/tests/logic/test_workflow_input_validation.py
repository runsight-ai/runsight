from __future__ import annotations

import subprocess
from unittest.mock import Mock

import pytest

from runsight_api.domain.errors import InputValidationError
from runsight_api.domain.errors import ServiceUnavailable
from runsight_api.domain.errors import WorkflowNotFound
from runsight_api.logic.services.execution_service import ExecutionService
from tests.logic.workflow_input_validation_fixtures import WORKFLOW_INPUT_CONTRACT_PATH
from tests.logic.workflow_input_validation_fixtures import branch_workflow_service
from tests.logic.workflow_input_validation_fixtures import service_with_yaml
from tests.logic.workflow_input_validation_fixtures import workflow_entity
from tests.logic.workflow_input_validation_fixtures import workflow_yaml_with_inputs
from tests.logic.workflow_input_validation_fixtures import (
    workflow_yaml_with_invalid_workflow_input_ref,
)
from tests.logic.workflow_input_validation_fixtures import workflow_yaml_without_inputs


def _error_payload(exc: InputValidationError) -> dict:
    payload = exc.to_dict()
    assert payload["error"] == "Workflow input validation failed"
    assert payload["error_code"] == "WORKFLOW_INPUT_VALIDATION_ERROR"
    assert payload["status_code"] == 422
    assert payload["details"]["kind"] == "workflow_input_validation"
    return payload


class TestWorkflowInputValidationPreparation:
    def test_missing_workflow_raises_domain_not_found_error_instead_of_value_error(self):
        workflow_repo = Mock()
        workflow_repo.get_by_id.return_value = None
        workflow_repo._get_path.return_value = "/custom/workflows/workflow_input_contract.yaml"
        service = ExecutionService(
            run_repo=Mock(),
            workflow_repo=workflow_repo,
            provider_repo=Mock(),
        )

        with pytest.raises(WorkflowNotFound) as exc_info:
            service.prepare_run_inputs("workflow_input_contract", {})

        assert exc_info.value.status_code == 404
        assert exc_info.value.error_code == "WORKFLOW_NOT_FOUND"
        assert "workflow_input_contract" in str(exc_info.value)

    def test_missing_required_input_raises_canonical_field_error_without_values(self):
        service = service_with_yaml(workflow_yaml_with_inputs())

        with pytest.raises(InputValidationError) as exc_info:
            service.prepare_run_inputs("workflow_input_contract", {})

        payload = _error_payload(exc_info.value)
        assert payload["details"]["workflow_id"] == "workflow_input_contract"
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
        service = service_with_yaml(workflow_yaml_with_inputs())

        with pytest.raises(InputValidationError) as exc_info:
            service.prepare_run_inputs(
                "workflow_input_contract",
                {"query": "search", "max_results": "ten"},
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
        service = service_with_yaml(workflow_yaml_with_inputs())

        with pytest.raises(InputValidationError) as exc_info:
            service.prepare_run_inputs(
                "workflow_input_contract",
                {"query": "search", "max_results": True},
            )

        payload = _error_payload(exc_info.value)
        assert payload["details"]["fields"][0]["code"] == "type_mismatch"
        assert payload["details"]["fields"][0]["expected_type"] == "number"
        assert payload["details"]["fields"][0]["actual_type"] == "boolean"

    def test_unknown_input_key_raises_unknown_field_error(self):
        service = service_with_yaml(workflow_yaml_with_inputs())

        with pytest.raises(InputValidationError) as exc_info:
            service.prepare_run_inputs(
                "workflow_input_contract",
                {"query": "search", "debug": True},
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

    def test_invalid_workflow_input_reference_raises_canonical_422_error(self):
        service = service_with_yaml(workflow_yaml_with_invalid_workflow_input_ref())

        with pytest.raises(InputValidationError) as exc_info:
            service.prepare_run_inputs(
                "workflow_input_contract",
                {"query": "search"},
            )

        payload = _error_payload(exc_info.value)
        assert payload["details"]["workflow_id"] == "workflow_input_contract"
        field = payload["details"]["fields"][0]
        assert field["field"] == "__schema__"
        assert field["code"] == "invalid"

    def test_optional_defaults_are_applied_to_normalized_inputs(self):
        service = service_with_yaml(workflow_yaml_with_inputs())

        normalized = service.prepare_run_inputs(
            "workflow_input_contract",
            {"query": "search"},
        )

        assert normalized == {
            "query": "search",
            "max_results": 10,
            "include_archived": False,
            "payload": {"region": "us"},
            "tags": ["support"],
        }

    def test_structured_json_and_array_inputs_are_preserved_in_normalized_inputs(self):
        service = service_with_yaml(workflow_yaml_with_inputs())

        submitted_inputs = {
            "query": "search",
            "payload": {"region": "eu", "filters": [{"name": "tier", "value": 1}]},
            "tags": ["support", "vip"],
        }

        normalized = service.prepare_run_inputs("workflow_input_contract", submitted_inputs)

        assert normalized == {
            "query": "search",
            "max_results": 10,
            "include_archived": False,
            "payload": {"region": "eu", "filters": [{"name": "tier", "value": 1}]},
            "tags": ["support", "vip"],
        }

    @pytest.mark.parametrize(
        ("payload_value", "actual_type", "submitted_value_text"),
        [
            (["not", "object"], "array", "not"),
            ("plain json text", "string", "plain json text"),
            (481516, "number", "481516"),
            (True, "boolean", "True"),
        ],
    )
    def test_json_input_rejects_arrays_and_scalars_without_echoing_submitted_value(
        self,
        payload_value,
        actual_type,
        submitted_value_text,
    ):
        service = service_with_yaml(workflow_yaml_with_inputs())

        with pytest.raises(InputValidationError) as exc_info:
            service.prepare_run_inputs(
                "workflow_input_contract",
                {"query": "search", "payload": payload_value},
            )

        payload = _error_payload(exc_info.value)
        assert payload["details"]["fields"] == [
            {
                "field": "payload",
                "code": "type_mismatch",
                "message": "Input 'payload' must be a json.",
                "input_path": ["inputs", "payload"],
                "expected_type": "json",
                "actual_type": actual_type,
            }
        ]
        assert submitted_value_text not in str(payload)

    @pytest.mark.parametrize("branch", ["feature-x", "main"])
    def test_branch_specific_yaml_snapshot_is_used_for_input_validation(self, branch):
        service, _, git_service = branch_workflow_service(
            repository_yaml=workflow_yaml_without_inputs(),
            git_yaml=workflow_yaml_with_inputs(),
        )

        normalized = service.prepare_run_inputs(
            "workflow_input_contract",
            {"query": "search"},
            branch=branch,
        )

        assert normalized == {
            "query": "search",
            "max_results": 10,
            "include_archived": False,
            "payload": {"region": "us"},
            "tags": ["support"],
        }
        git_service.read_file.assert_called_once_with(WORKFLOW_INPUT_CONTRACT_PATH, branch)

    def test_explicit_main_snapshot_requires_git_service_for_input_preparation(self):
        workflow_repo = Mock()
        workflow_repo.get_by_id.return_value = workflow_entity(
            "workflow_input_contract",
            workflow_yaml_with_inputs(),
        )
        workflow_repo._get_path.return_value = WORKFLOW_INPUT_CONTRACT_PATH

        service = ExecutionService(
            run_repo=Mock(),
            workflow_repo=workflow_repo,
            provider_repo=Mock(),
        )

        with pytest.raises(ValueError, match="Requested snapshot could not be loaded"):
            service.prepare_run_inputs(
                "workflow_input_contract",
                {"query": "search"},
                branch="main",
            )

    @pytest.mark.parametrize(
        ("branch", "error"),
        [
            ("feature-x", ServiceUnavailable("git snapshot unavailable")),
            (
                "feature-x",
                subprocess.CalledProcessError(
                    128, ["git", "show"], stderr="fatal: not a git repository"
                ),
            ),
            ("main", ServiceUnavailable("git snapshot unavailable")),
            (
                "main",
                subprocess.CalledProcessError(
                    128, ["git", "show"], stderr="fatal: not a git repository"
                ),
            ),
        ],
    )
    def test_branch_specific_input_preparation_fails_closed_when_git_snapshot_read_fails(
        self, branch, error
    ):
        service, _, _ = branch_workflow_service(
            repository_yaml=workflow_yaml_with_inputs(),
            git_yaml=workflow_yaml_with_inputs(),
            git_error=error,
        )

        with pytest.raises(type(error)):
            service.prepare_run_inputs(
                "workflow_input_contract",
                {"query": "search"},
                branch=branch,
            )

    def test_no_schema_no_inputs_keeps_no_input_path_empty(self):
        service = service_with_yaml(
            workflow_yaml_without_inputs(),
            workflow_id="workflow_without_inputs",
        )

        assert service.prepare_run_inputs("workflow_without_inputs", {}) == {}
