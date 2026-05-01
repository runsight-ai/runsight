"""Legacy workflow interface removal and name-based WorkflowBlock contract."""

from __future__ import annotations

import inspect
import json
from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError
from runsight_core.block_io import build_block_context
from runsight_core.blocks.workflow_block import WorkflowBlock
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.workflow import Workflow
from runsight_core.yaml.parser import parse_workflow_yaml
from runsight_core.yaml.registry import WorkflowRegistry
from runsight_core.yaml.schema import BlockDef, RunsightWorkflowFile


def _minimal_workflow(**overrides: Any) -> dict[str, Any]:
    workflow: dict[str, Any] = {
        "version": "1.0",
        "id": "interface-contract-child-workflow",
        "kind": "workflow",
        "blocks": {},
        "workflow": {
            "name": "interface_contract_child_workflow",
            "entry": "start",
            "transitions": [],
        },
    }
    workflow.update(overrides)
    return workflow


def _child_file_without_interface() -> RunsightWorkflowFile:
    return RunsightWorkflowFile.model_validate(
        _minimal_workflow(
            id="interface-contract-child-workflow",
            inputs={
                "query": {
                    "type": "string",
                }
            },
            blocks={
                "echo": {
                    "type": "code",
                    "code": ("def main(query):\n    return {'summary': query}\n"),
                }
            },
            workflow={
                "name": "interface_contract_child_workflow",
                "entry": "echo",
                "transitions": [{"from": "echo", "to": None}],
            },
        )
    )


class CapturingWorkflow:
    """Child workflow spy that records how WorkflowBlock invokes it."""

    def __init__(self, name: str = "interface_contract_child_workflow") -> None:
        self.name = name
        self.received_state: WorkflowState | None = None
        self.received_kwargs: dict[str, Any] | None = None

    async def run(self, state: WorkflowState, **kwargs: Any) -> WorkflowState:
        self.received_state = state
        self.received_kwargs = kwargs
        return WorkflowState(
            artifact_store=state.artifact_store,
            results={"echo": BlockResult(output=json.dumps({"summary": "child summary"}))},
        )


def _parent_state() -> WorkflowState:
    return WorkflowState(
        metadata={"request": {"query": "climate"}},
        shared_memory={"topic": "climate"},
        results={
            "draft": BlockResult(output=json.dumps({"query": "climate"})),
        },
    )


class TestLegacyInterfaceDeclarationsAreUnsupported:
    def test_workflow_interface_inputs_target_is_rejected_loudly(self) -> None:
        with pytest.raises((ValidationError, ValueError), match="legacy.*interface|unsupported"):
            RunsightWorkflowFile.model_validate(
                _minimal_workflow(
                    interface={
                        "inputs": [
                            {
                                "name": "query",
                                "target": "shared_memory.query",
                                "required": True,
                            }
                        ]
                    }
                )
            )

    def test_workflow_interface_outputs_are_rejected_loudly(self) -> None:
        with pytest.raises((ValidationError, ValueError), match="legacy.*interface|unsupported"):
            RunsightWorkflowFile.model_validate(
                _minimal_workflow(
                    interface={
                        "outputs": [
                            {
                                "name": "summary",
                                "source": "results.echo",
                            }
                        ]
                    }
                )
            )

    def test_workflowblock_constructor_exposes_no_legacy_interface_surface(self) -> None:
        signature = inspect.signature(WorkflowBlock.__init__)
        assert "interface" not in signature.parameters

        block = WorkflowBlock(
            block_id="interface_child_invocation_block",
            child_workflow=CapturingWorkflow(),
            inputs={},
            outputs={},
        )

        assert not hasattr(block, "interface")

    def test_parser_rejects_legacy_interface_yaml_instead_of_translating_it(self) -> None:
        legacy_yaml = """
version: "1.0"
id: legacy-child
kind: workflow
interface:
  inputs:
    - name: query
      target: shared_memory.query
  outputs:
    - name: summary
      source: results.echo
blocks:
  echo:
    type: code
    code: |
      def main(query=None):
          return {"summary": query}
workflow:
  name: legacy_child
  entry: echo
  transitions:
    - from: echo
      to: null
"""

        with pytest.raises((ValidationError, ValueError), match="legacy.*interface|unsupported"):
            parse_workflow_yaml(legacy_yaml)


class TestWorkflowBlockNameBasedInvocation:
    def test_schema_accepts_explicit_child_state_output_source_paths(self) -> None:
        adapter = TypeAdapter(BlockDef)

        block_def = adapter.validate_python(
            {
                "type": "workflow",
                "workflow_ref": "interface_contract_child_workflow",
                "inputs": {"query": "shared_memory.topic"},
                "outputs": {"results.parent_summary": "results.echo"},
            }
        )

        assert block_def.inputs == {"query": "shared_memory.topic"}
        assert block_def.outputs == {"results.parent_summary": "results.echo"}

    def test_schema_rejects_public_child_output_names_until_output_contract_exists(self) -> None:
        adapter = TypeAdapter(BlockDef)

        with pytest.raises(ValidationError, match="child source path|output contract|dotted"):
            adapter.validate_python(
                {
                    "type": "workflow",
                    "workflow_ref": "interface_contract_child_workflow",
                    "inputs": {"query": "shared_memory.topic"},
                    "outputs": {"results.parent_summary": "summary"},
                }
            )

    def test_parser_no_longer_requires_child_interface_for_workflowblock(self) -> None:
        registry = WorkflowRegistry()
        registry.register("interface_contract_child_workflow", _child_file_without_interface())

        parent_yaml = {
            "version": "1.0",
            "id": "interface-contract-parent-workflow",
            "kind": "workflow",
            "blocks": {
                "interface_child_invocation_block": {
                    "type": "workflow",
                    "workflow_ref": "interface_contract_child_workflow",
                    "inputs": {"query": "shared_memory.topic"},
                }
            },
            "workflow": {
                "name": "interface_contract_parent_workflow",
                "entry": "interface_child_invocation_block",
                "transitions": [{"from": "interface_child_invocation_block", "to": None}],
            },
        }

        interface_contract_parent_workflow = parse_workflow_yaml(
            parent_yaml, workflow_registry=registry
        )

        block = interface_contract_parent_workflow._blocks["interface_child_invocation_block"]
        assert isinstance(block, WorkflowBlock)
        assert block.inputs == {"query": "shared_memory.topic"}
        assert not hasattr(block, "interface")

    @pytest.mark.asyncio
    async def test_workflowblock_passes_parent_mapping_as_child_invocation_inputs(self) -> None:
        interface_contract_child_workflow = CapturingWorkflow()
        block = WorkflowBlock(
            block_id="interface_child_invocation_block",
            child_workflow=interface_contract_child_workflow,
            inputs={"query": "shared_memory.topic"},
            outputs={},
        )
        ctx = build_block_context(block, _parent_state())

        await block.execute(ctx)

        assert interface_contract_child_workflow.received_state is not None
        assert interface_contract_child_workflow.received_kwargs is not None
        assert interface_contract_child_workflow.received_kwargs["inputs"] == {"query": "climate"}
        assert interface_contract_child_workflow.received_state.results == {}
        assert interface_contract_child_workflow.received_state.shared_memory == {}
        assert interface_contract_child_workflow.received_state.metadata == {}

    @pytest.mark.asyncio
    async def test_workflowblock_extracts_outputs_from_explicit_child_state_paths(self) -> None:
        interface_contract_child_workflow = CapturingWorkflow()
        block = WorkflowBlock(
            block_id="interface_child_invocation_block",
            child_workflow=interface_contract_child_workflow,
            inputs={},
            outputs={"results.parent_summary": "results.echo"},
        )
        ctx = build_block_context(block, _parent_state())

        output = await block.execute(ctx)

        assert output.extra_results == {
            "parent_summary": BlockResult(output=json.dumps({"summary": "child summary"}))
        }

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "private_target", ["shared_memory.query", "results.query", "metadata.query"]
    )
    async def test_workflowblock_runtime_rejects_private_child_state_targets(
        self,
        private_target: str,
    ) -> None:
        interface_contract_child_workflow = CapturingWorkflow()

        with pytest.raises(ValueError, match="private child state|child invocation input"):
            block = WorkflowBlock(
                block_id="interface_child_invocation_block",
                child_workflow=interface_contract_child_workflow,
                inputs={private_target: "shared_memory.topic"},
                outputs={},
            )
            ctx = build_block_context(block, _parent_state())
            await block.execute(ctx)

        assert interface_contract_child_workflow.received_state is None

    @pytest.mark.asyncio
    async def test_nested_workflowblocks_forward_public_invocation_names_recursively(self) -> None:
        grandchild = CapturingWorkflow(name="interface_contract_grandchild_workflow")
        child_block = WorkflowBlock(
            block_id="interface_grandchild_invocation_block",
            child_workflow=grandchild,
            inputs={"query": "workflow.query"},
            outputs={},
        )
        interface_contract_child_workflow = Workflow(name="interface_contract_child_workflow")
        interface_contract_child_workflow.add_block(child_block)
        interface_contract_child_workflow.set_entry("interface_grandchild_invocation_block")

        parent_block = WorkflowBlock(
            block_id="interface_child_invocation_block",
            child_workflow=interface_contract_child_workflow,
            inputs={"query": "shared_memory.topic"},
            outputs={},
        )
        parent_ctx = build_block_context(parent_block, _parent_state())

        await parent_block.execute(parent_ctx)

        assert grandchild.received_kwargs is not None
        assert grandchild.received_kwargs["inputs"] == {"query": "climate"}
        assert grandchild.received_state is not None
        assert grandchild.received_state.shared_memory == {}
