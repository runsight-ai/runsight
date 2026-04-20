from __future__ import annotations

import importlib

import pytest
from pydantic import TypeAdapter, ValidationError
from runsight_core.yaml.parser import parse_workflow_yaml
from runsight_core.yaml.registry import WorkflowRegistry
from runsight_core.yaml.schema import BlockDef, RunsightWorkflowFile


def _contract_names_module():
    return importlib.import_module("runsight_core.workflow_contract_names")


def _workflow_block(
    *,
    inputs: dict[str, str] | None = None,
    outputs: dict[str, str] | None = None,
) -> dict:
    block = {
        "type": "workflow",
        "workflow_ref": "custom/workflows/child.yaml",
    }
    if inputs is not None:
        block["inputs"] = inputs
    if outputs is not None:
        block["outputs"] = outputs
    return block


def _child_file_without_interface() -> RunsightWorkflowFile:
    return RunsightWorkflowFile.model_validate(
        {
            "version": "1.0",
            "id": "child_workflow",
            "kind": "workflow",
            "blocks": {
                "child_step": {
                    "type": "code",
                    "code": "def main(data):\n    return {'ok': True}",
                }
            },
            "workflow": {
                "id": "child_workflow",
                "kind": "workflow",
                "name": "child_workflow",
                "entry": "child_step",
                "transitions": [{"from": "child_step", "to": None}],
            },
        }
    )


class TestWorkflowContractNameValidator:
    def test_valid_lower_snake_names_pass_unchanged(self) -> None:
        contract_names = _contract_names_module()

        assert contract_names.validate_workflow_contract_name("query") == "query"
        assert contract_names.validate_workflow_contract_name("user_id_2") == "user_id_2"

    @pytest.mark.parametrize(
        "name",
        [
            "",
            "UserId",
            "user.id",
            "user-id",
            "user id",
            "../secret",
            "workflow/input",
            "user[0]",
            r"user\.id",
            "_user",
            "1user",
            "a" * 65,
        ],
    )
    def test_invalid_public_contract_names_fail_without_normalization(self, name: str) -> None:
        contract_names = _contract_names_module()

        with pytest.raises(ValueError, match="workflow contract name"):
            contract_names.validate_workflow_contract_name(name)

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
    def test_reserved_public_contract_names_fail(self, name: str) -> None:
        contract_names = _contract_names_module()

        assert name in contract_names.RESERVED_WORKFLOW_CONTRACT_NAMES
        with pytest.raises(ValueError, match="reserved"):
            contract_names.validate_workflow_contract_name(name)

    def test_collection_validator_preserves_order_and_rejects_duplicates(self) -> None:
        contract_names = _contract_names_module()

        assert contract_names.validate_workflow_contract_names(["query", "user_id_2"]) == [
            "query",
            "user_id_2",
        ]

        with pytest.raises(ValueError, match="duplicate"):
            contract_names.validate_workflow_contract_names(["query", "query"])


class TestWorkflowBlockBindingValidation:
    @pytest.mark.parametrize("name", ["UserId", "user-id", "user id", "workflow/input", "user[0]"])
    def test_workflow_block_input_bindings_use_contract_name_validator(self, name: str) -> None:
        adapter = TypeAdapter(BlockDef)

        with pytest.raises(ValidationError, match="workflow contract name"):
            adapter.validate_python(_workflow_block(inputs={name: "shared_memory.parent_value"}))

    def test_workflow_block_rejects_public_output_names_without_child_source_path(self) -> None:
        adapter = TypeAdapter(BlockDef)

        with pytest.raises(ValidationError, match="child source path|output contract|dotted"):
            adapter.validate_python(_workflow_block(outputs={"results.child": "summary"}))

    def test_workflow_block_output_binding_accepts_explicit_child_source_path(self) -> None:
        adapter = TypeAdapter(BlockDef)

        block_def = adapter.validate_python(
            _workflow_block(outputs={"results.child": "results.summary"})
        )

        assert block_def.outputs == {"results.child": "results.summary"}

    @pytest.mark.parametrize("target_path", ["metadata.child", "summary", "workflow.child"])
    def test_workflow_block_rejects_invalid_parent_output_targets(self, target_path: str) -> None:
        adapter = TypeAdapter(BlockDef)

        with pytest.raises(ValidationError, match="parent target path|results|shared_memory"):
            adapter.validate_python(_workflow_block(outputs={target_path: "results.summary"}))

    def test_parse_workflow_yaml_rejects_invalid_child_binding_before_runtime(self) -> None:
        child_file = _child_file_without_interface()
        registry = WorkflowRegistry()
        registry.register("child_workflow", child_file)

        parent_yaml = {
            "version": "1.0",
            "id": "parent_workflow",
            "kind": "workflow",
            "blocks": {
                "invoke_child": {
                    "type": "workflow",
                    "workflow_ref": "child_workflow",
                    "inputs": {"UserId": "shared_memory.parent_user_id"},
                }
            },
            "workflow": {
                "id": "parent_workflow",
                "kind": "workflow",
                "name": "parent_workflow",
                "entry": "invoke_child",
                "transitions": [{"from": "invoke_child", "to": None}],
            },
        }

        with pytest.raises((ValidationError, ValueError), match="workflow contract name"):
            parse_workflow_yaml(parent_yaml, workflow_registry=registry)

    def test_parse_workflow_yaml_rejects_duplicate_workflow_block_binding_names(self) -> None:
        child_file = _child_file_without_interface()
        registry = WorkflowRegistry()
        registry.register("child_workflow", child_file)

        parent_yaml = """
version: "1.0"
id: parent_workflow
kind: workflow
blocks:
  invoke_child:
    type: workflow
    workflow_ref: child_workflow
    inputs:
      topic: shared_memory.first_topic
      topic: shared_memory.second_topic
workflow:
  id: parent_workflow
  kind: workflow
  name: parent_workflow
  entry: invoke_child
  transitions:
    - from: invoke_child
      to: null
"""

        with pytest.raises((ValidationError, ValueError), match="duplicate"):
            parse_workflow_yaml(parent_yaml, workflow_registry=registry)
