from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError
from runsight_core.yaml.schema import BlockDef, RunsightWorkflowFile


def _minimal_workflow_with_interface(interface: dict) -> dict:
    return {
        "version": "1.0",
        "interface": interface,
        "workflow": {
            "name": "child-contract",
            "entry": "start",
            "transitions": [],
        },
    }


class TestWorkflowInterfaceSchema:
    def test_runsight_workflow_file_declares_interface_field(self) -> None:
        assert "interface" in RunsightWorkflowFile.model_fields

    def test_interface_inputs_and_outputs_parse_with_named_contract_fields(self) -> None:
        file_def = RunsightWorkflowFile.model_validate(
            _minimal_workflow_with_interface(
                {
                    "inputs": [
                        {
                            "name": "topic",
                            "target": "shared_memory.topic",
                            "required": False,
                            "default": "climate",
                            "description": "Research topic",
                        }
                    ],
                    "outputs": [
                        {
                            "name": "summary",
                            "source": "results.writer",
                            "description": "Final summary",
                        }
                    ],
                }
            )
        )

        assert file_def.interface is not None
        assert file_def.interface.inputs[0].name == "topic"
        assert file_def.interface.inputs[0].target == "shared_memory.topic"
        assert file_def.interface.inputs[0].required is False
        assert file_def.interface.inputs[0].default == "climate"
        assert file_def.interface.outputs[0].name == "summary"
        assert file_def.interface.outputs[0].source == "results.writer"

    def test_duplicate_interface_input_names_raise_validation_error(self) -> None:
        with pytest.raises(ValidationError, match="topic"):
            RunsightWorkflowFile.model_validate(
                _minimal_workflow_with_interface(
                    {
                        "inputs": [
                            {"name": "topic", "target": "shared_memory.topic"},
                            {"name": "topic", "target": "shared_memory.topic_2"},
                        ],
                        "outputs": [{"name": "summary", "source": "results.writer"}],
                    }
                )
            )


class TestWorkflowBlockCallsiteBindings:
    def test_workflow_block_rejects_raw_child_dotted_path_input_keys(self) -> None:
        adapter = TypeAdapter(BlockDef)

        with pytest.raises(ValidationError, match="interface"):
            adapter.validate_python(
                {
                    "type": "workflow",
                    "workflow_ref": "custom/workflows/child-contract.yaml",
                    "inputs": {"shared_memory.topic": "shared_memory.parent_topic"},
                    "outputs": {"results.parent_summary": "summary"},
                }
            )

    def test_workflow_block_rejects_raw_child_dotted_path_output_bindings(self) -> None:
        adapter = TypeAdapter(BlockDef)

        with pytest.raises(ValidationError, match="interface"):
            adapter.validate_python(
                {
                    "type": "workflow",
                    "workflow_ref": "custom/workflows/child-contract.yaml",
                    "inputs": {"topic": "shared_memory.parent_topic"},
                    "outputs": {"results.parent_summary": "results.writer"},
                }
            )
