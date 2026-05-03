from __future__ import annotations

import importlib
from typing import Any

import pytest
from pydantic import ValidationError
from runsight_core.yaml.schema import RunsightWorkflowFile

_UNSET = object()


def _workflow_file(*, inputs: object = _UNSET, **overrides: object) -> dict[str, object]:
    workflow: dict[str, object] = {
        "version": "1.0",
        "id": "workflow_inputs_contract",
        "kind": "workflow",
        "blocks": {
            "start": {
                "type": "code",
                "code": "def main(data):\n    return {'ok': True}",
            }
        },
        "workflow": {
            "name": "workflow_inputs_contract",
            "entry": "start",
            "transitions": [{"from": "start", "to": None}],
        },
    }
    if inputs is not _UNSET:
        workflow["inputs"] = inputs
    workflow.update(overrides)
    return workflow


def _validate_inputs(inputs: dict[str, dict[str, Any]]) -> RunsightWorkflowFile:
    return RunsightWorkflowFile.model_validate(_workflow_file(inputs=inputs))


class TestWorkflowInputSchemaContract:
    def test_workflow_input_model_is_exported_from_schema_module(self) -> None:
        schema = importlib.import_module("runsight_core.yaml.schema")

        workflow_input_def = getattr(schema, "WorkflowInputDef")

        assert set(workflow_input_def.model_fields) == {
            "type",
            "required",
            "default",
            "description",
            "sensitive",
        }

    def test_workflow_file_declares_optional_inputs_field(self) -> None:
        assert "inputs" in RunsightWorkflowFile.model_fields

        workflow_file = RunsightWorkflowFile.model_validate(_workflow_file())

        assert workflow_file.inputs is None

    def test_valid_top_level_inputs_are_part_of_workflow_schema(self) -> None:
        workflow_file = _validate_inputs({"query": {"type": "string"}})

        assert workflow_file.inputs is not None
        assert set(workflow_file.inputs) == {"query"}
        assert workflow_file.inputs["query"].type == "string"
        assert workflow_file.inputs["query"].required is True
        assert workflow_file.inputs["query"].default is None
        assert workflow_file.inputs["query"].description is None
        assert workflow_file.inputs["query"].sensitive is False

    @pytest.mark.parametrize(
        ("input_type", "default"),
        [
            ("string", "climate"),
            ("number", 10),
            ("number", 3.5),
            ("boolean", False),
            ("json", {"topic": "climate", "limit": 2}),
            ("array", ["summary", "citations"]),
        ],
    )
    def test_defaults_matching_declared_type_are_accepted(
        self, input_type: str, default: object
    ) -> None:
        workflow_file = _validate_inputs(
            {"query_options": {"type": input_type, "required": False, "default": default}}
        )

        assert workflow_file.inputs is not None
        assert workflow_file.inputs["query_options"].default == default

    @pytest.mark.parametrize(
        ("input_type", "default"),
        [
            ("string", 10),
            ("number", "10"),
            ("number", True),
            ("boolean", "false"),
            ("json", ["not", "an", "object"]),
            ("json", "plain text is valid json but not an object"),
            ("json", 42),
            ("json", False),
            ("array", {"not": "an array"}),
        ],
    )
    def test_defaults_must_match_declared_type(self, input_type: str, default: object) -> None:
        with pytest.raises(ValidationError, match="default"):
            _validate_inputs({"query": {"type": input_type, "default": default}})

    def test_unknown_input_type_fails_validation(self) -> None:
        with pytest.raises(ValidationError, match="type"):
            _validate_inputs({"query": {"type": "integer"}})

    def test_unknown_fields_under_input_definition_fail_validation(self) -> None:
        with pytest.raises(ValidationError, match="placeholder"):
            _validate_inputs({"query": {"type": "string", "placeholder": "Search"}})


class TestWorkflowInputNames:
    @pytest.mark.parametrize(
        "name",
        [
            "",
            "ApiToken",
            "user.name",
            "user-name",
            "user name",
            "../secret",
            "workflow/input",
            "user[0]",
            r"user\.name",
            "_user",
            "1user",
            "a" * 65,
        ],
    )
    def test_input_names_must_be_valid_workflow_contract_names(self, name: str) -> None:
        with pytest.raises((ValidationError, ValueError), match="workflow contract name"):
            _validate_inputs({name: {"type": "string"}})

    @pytest.mark.parametrize(
        "name",
        [
            "workflow",
            "results",
            "shared_memory",
            "metadata",
            "blocks",
            "ctx",
            "call_stack",
            "workflow_registry",
            "observer",
        ],
    )
    def test_reserved_input_names_fail_validation(self, name: str) -> None:
        with pytest.raises((ValidationError, ValueError), match="reserved"):
            _validate_inputs({name: {"type": "string"}})


class TestSensitiveWorkflowInputs:
    @pytest.mark.parametrize(
        ("input_type", "default"),
        [
            ("string", "secret"),
            ("number", 42),
            ("boolean", True),
            ("json", {"token": "secret"}),
            ("array", ["secret"]),
        ],
    )
    def test_sensitive_defaults_are_forbidden_for_every_supported_type(
        self, input_type: str, default: object
    ) -> None:
        with pytest.raises(ValidationError, match="sensitive.*default|default.*sensitive"):
            _validate_inputs(
                {"secret_value": {"type": input_type, "sensitive": True, "default": default}}
            )

    @pytest.mark.parametrize("input_type", ["string", "number", "boolean", "json", "array"])
    def test_sensitive_inputs_are_accepted_for_every_supported_type(self, input_type: str) -> None:
        workflow_file = _validate_inputs({"secret_value": {"type": input_type, "sensitive": True}})

        assert workflow_file.inputs is not None
        assert workflow_file.inputs["secret_value"].sensitive is True
        assert workflow_file.inputs["secret_value"].type == input_type

    @pytest.mark.parametrize("name", ["api_token", "password", "secret_key"])
    def test_secret_like_names_are_not_automatically_forced_to_sensitive(self, name: str) -> None:
        workflow_file = _validate_inputs({name: {"type": "string"}})

        assert workflow_file.inputs is not None
        assert workflow_file.inputs[name].sensitive is False


class TestLegacyInterfaceIsNotWorkflowInputSchema:
    def test_legacy_interface_inputs_target_is_not_accepted_as_inputs_model(self) -> None:
        assert "inputs" in RunsightWorkflowFile.model_fields
        assert "interface" not in RunsightWorkflowFile.model_fields

        with pytest.raises((ValidationError, ValueError), match="legacy.*interface|unsupported"):
            RunsightWorkflowFile.model_validate(
                _workflow_file(
                    interface={
                        "inputs": [
                            {
                                "name": "query",
                                "target": "shared_memory.query",
                                "type": "string",
                            }
                        ],
                    }
                )
            )

    def test_legacy_interface_outputs_source_is_rejected(self) -> None:
        with pytest.raises((ValidationError, ValueError), match="legacy.*interface|unsupported"):
            RunsightWorkflowFile.model_validate(
                _workflow_file(
                    interface={
                        "outputs": [
                            {
                                "name": "summary",
                                "source": "results.writer",
                            }
                        ],
                    }
                )
            )
