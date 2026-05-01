"""Subworkflow integration expectations after public input mapping."""

from __future__ import annotations

import pytest
from runsight_core.block_io import BlockOutput, apply_block_output, build_block_context
from runsight_core.blocks.workflow_block import WorkflowBlock
from runsight_core.state import WorkflowState
from runsight_core.workflow import Workflow
from runsight_core.yaml.parser import parse_workflow_yaml
from runsight_core.yaml.registry import WorkflowRegistry
from runsight_core.yaml.schema import RunsightWorkflowFile


async def _exec(block: WorkflowBlock, state: WorkflowState) -> WorkflowState:
    ctx = build_block_context(block, state)
    output = await block.execute(ctx)
    return apply_block_output(state, block.block_id, output)


class _EchoInvocationInputBlock:
    def __init__(self, block_id: str, input_name: str) -> None:
        self.block_id = block_id
        self.retry_config = None
        self.stateful = False
        self.context_access = "declared"
        self.declared_inputs = {input_name: f"workflow.{input_name}"}
        self._input_name = input_name

    async def execute(self, ctx) -> BlockOutput:
        return BlockOutput(output=ctx.inputs[self._input_name])


class _WriterBlock:
    def __init__(self, block_id: str, value: str) -> None:
        self.block_id = block_id
        self.retry_config = None
        self.stateful = False
        self.context_access = "declared"
        self._value = value

    async def execute(self, ctx) -> BlockOutput:
        return BlockOutput(output=self._value)


def _workflow(name: str, block: object) -> Workflow:
    wf = Workflow(name=name)
    wf.add_block(block)
    wf.set_entry(block.block_id)
    return wf


@pytest.mark.asyncio
async def test_parent_workflow_passes_name_based_inputs_and_maps_child_state_outputs() -> None:
    child_workflow = _workflow(
        "mapped_input_child_workflow", _EchoInvocationInputBlock("topic_echo_step", "topic")
    )
    wb = WorkflowBlock(
        block_id="mapped_input_workflow_block",
        child_workflow=child_workflow,
        inputs={"topic": "shared_memory.parent_topic"},
        outputs={"results.child_summary": "results.topic_echo_step"},
    )

    parent_workflow = Workflow(name="mapped_input_parent_workflow")
    parent_workflow.add_block(wb)
    parent_workflow.set_entry("mapped_input_workflow_block")

    final_state = await parent_workflow.run(
        WorkflowState(shared_memory={"parent_topic": "quantum computing"})
    )

    assert str(final_state.results["child_summary"]) == "quantum computing"
    assert final_state.results["mapped_input_workflow_block"].exit_handle == "completed"


@pytest.mark.asyncio
async def test_child_results_do_not_leak_without_explicit_output_mapping() -> None:
    child_workflow = _workflow(
        "isolated_child_results_workflow", _WriterBlock("secret_child_step", "secret data")
    )
    wb = WorkflowBlock(
        block_id="isolated_results_workflow_block",
        child_workflow=child_workflow,
        inputs={"topic": "shared_memory.parent_topic"},
        outputs={},
    )

    result_state = await _exec(
        wb,
        WorkflowState(shared_memory={"parent_topic": "isolated topic"}),
    )

    assert "isolated_results_workflow_block" in result_state.results
    assert "secret_child_step" not in result_state.results
    assert "secret_child_step" not in (
        result_state.results["isolated_results_workflow_block"].metadata or {}
    )


@pytest.mark.asyncio
async def test_on_error_catch_continues_parent_routing() -> None:
    class _FailingBlock:
        block_id = "caught_error_step"
        retry_config = None
        stateful = False
        context_access = "none"

        async def execute(self, ctx) -> BlockOutput:
            raise RuntimeError("child kaboom")

    child_workflow = _workflow("catch_error_child_workflow", _FailingBlock())
    wb = WorkflowBlock(
        block_id="caught_error_workflow_block",
        child_workflow=child_workflow,
        inputs={"topic": "shared_memory.parent_topic"},
        outputs={},
        on_error="catch",
    )

    result_state = await _exec(
        wb,
        WorkflowState(shared_memory={"parent_topic": "catch topic"}),
    )

    br = result_state.results["caught_error_workflow_block"]
    assert br.exit_handle == "error"
    assert br.metadata["child_status"] == "failed"


@pytest.mark.asyncio
async def test_workflowblock_rejects_private_child_state_input_targets() -> None:
    child_workflow = _workflow(
        "private_input_child_workflow",
        _WriterBlock("private_input_writer_step", "done"),
    )

    with pytest.raises(ValueError, match="private child state|child invocation input"):
        wb = WorkflowBlock(
            block_id="private_input_workflow_block",
            child_workflow=child_workflow,
            inputs={"shared_memory.topic": "shared_memory.parent_topic"},
            outputs={},
        )
        await _exec(wb, WorkflowState(shared_memory={"parent_topic": "private topic"}))


@pytest.mark.asyncio
async def test_missing_child_output_source_path_raises() -> None:
    child_workflow = _workflow(
        "missing_output_child_workflow",
        _WriterBlock("available_output_step", "some output"),
    )
    wb = WorkflowBlock(
        block_id="missing_output_workflow_block",
        child_workflow=child_workflow,
        inputs={"topic": "shared_memory.parent_topic"},
        outputs={"results.parent_summary": "results.nonexistent"},
    )

    with pytest.raises((KeyError, ValueError), match="nonexistent"):
        await _exec(wb, WorkflowState(shared_memory={"parent_topic": "missing output topic"}))


@pytest.mark.asyncio
async def test_nested_subflows_use_name_based_invocation_recursively() -> None:
    grandchild_workflow = _workflow(
        "nested_invocation_grandchild_workflow",
        _EchoInvocationInputBlock("nested_payload_echo_step", "msg"),
    )
    nested_grandchild_block = WorkflowBlock(
        block_id="nested_grandchild_workflow_block",
        child_workflow=grandchild_workflow,
        inputs={"msg": "workflow.topic"},
        outputs={"results.gc_output": "results.nested_payload_echo_step"},
    )
    child_workflow = _workflow("nested_invocation_child_workflow", nested_grandchild_block)
    nested_child_block = WorkflowBlock(
        block_id="nested_child_workflow_block",
        child_workflow=child_workflow,
        inputs={"topic": "shared_memory.parent_topic"},
        outputs={"results.final_output": "results.nested_grandchild_workflow_block"},
    )

    result_state = await _exec(
        nested_child_block,
        WorkflowState(shared_memory={"parent_topic": "nested payload"}),
    )

    assert "final_output" in result_state.results


def test_parser_builds_workflowblock_without_child_interface() -> None:
    parser_child_workflow_file = RunsightWorkflowFile.model_validate(
        {
            "version": "1.0",
            "id": "parser_child_workflow",
            "kind": "workflow",
            "inputs": {"topic": {"type": "string"}},
            "blocks": {
                "parser_child_step": {
                    "type": "code",
                    "code": "def main(topic=None):\n    return {'ok': True}",
                }
            },
            "workflow": {
                "id": "parser_child_workflow",
                "kind": "workflow",
                "name": "parser_child_workflow",
                "entry": "parser_child_step",
                "transitions": [{"from": "parser_child_step", "to": None}],
            },
        }
    )
    registry = WorkflowRegistry()
    registry.register("parser_child_workflow", parser_child_workflow_file)

    parser_parent_workflow_yaml = {
        "version": "1.0",
        "id": "parser_parent_workflow",
        "kind": "workflow",
        "blocks": {
            "parser_child_workflow_block": {
                "type": "workflow",
                "workflow_ref": "parser_child_workflow",
                "inputs": {"topic": "shared_memory.parent_topic"},
                "outputs": {"results.analysis": "results.parser_child_step"},
            }
        },
        "workflow": {
            "id": "parser_parent_workflow",
            "kind": "workflow",
            "name": "parser_parent_workflow",
            "entry": "parser_child_workflow_block",
            "transitions": [{"from": "parser_child_workflow_block", "to": None}],
        },
    }

    wf = parse_workflow_yaml(parser_parent_workflow_yaml, workflow_registry=registry)

    block = wf.blocks["parser_child_workflow_block"]
    assert isinstance(block, WorkflowBlock)
    assert block.inputs == {"topic": "shared_memory.parent_topic"}
    assert block.outputs == {"results.analysis": "results.parser_child_step"}
