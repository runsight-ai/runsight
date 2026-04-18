from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError
from runsight_core.yaml.schema import BlockDef, RunsightWorkflowFile


def _minimal_workflow(**overrides: object) -> dict[str, object]:
    workflow: dict[str, object] = {
        "version": "1.0",
        "id": "child-contract",
        "kind": "workflow",
        "workflow": {
            "name": "child_contract",
            "entry": "start",
            "transitions": [],
        },
    }
    workflow.update(overrides)
    return workflow


class TestWorkflowInterfaceSchemaRemoval:
    def test_runsight_workflow_file_no_longer_declares_interface_field(self) -> None:
        assert "interface" not in RunsightWorkflowFile.model_fields

    def test_legacy_interface_inputs_target_is_rejected(self) -> None:
        with pytest.raises((ValidationError, ValueError), match="legacy.*interface|unsupported"):
            RunsightWorkflowFile.model_validate(
                _minimal_workflow(
                    interface={
                        "inputs": [
                            {
                                "name": "topic",
                                "target": "shared_memory.topic",
                                "required": False,
                                "default": "climate",
                                "description": "Research topic",
                            }
                        ],
                    }
                )
            )

    def test_legacy_interface_outputs_source_is_rejected(self) -> None:
        with pytest.raises((ValidationError, ValueError), match="legacy.*interface|unsupported"):
            RunsightWorkflowFile.model_validate(
                _minimal_workflow(
                    interface={
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


class TestWorkflowBlockCallsiteBindings:
    def test_workflow_block_rejects_raw_child_dotted_path_input_keys(self) -> None:
        adapter = TypeAdapter(BlockDef)

        with pytest.raises(
            ValidationError,
            match="private child state|child invocation input|dotted child path",
        ):
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

        with pytest.raises(
            ValidationError,
            match="private child state|child invocation input|dotted child path",
        ):
            adapter.validate_python(
                {
                    "type": "workflow",
                    "workflow_ref": "custom/workflows/child-contract.yaml",
                    "inputs": {"topic": "shared_memory.parent_topic"},
                    "outputs": {"results.parent_summary": "results.writer"},
                }
            )
