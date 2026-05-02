"""WorkflowBlock name-based invocation after legacy interface removal."""

from __future__ import annotations

from typing import Any

import pytest
from runsight_core.block_io import BlockOutput, apply_block_output, build_block_context
from runsight_core.blocks.workflow_block import WorkflowBlock
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.workflow import Workflow


async def _exec(block: WorkflowBlock, state: WorkflowState, **extra_inputs: Any) -> WorkflowState:
    ctx = build_block_context(block, state)
    if extra_inputs:
        ctx = ctx.model_copy(update={"inputs": {**ctx.inputs, **extra_inputs}})
    output = await block.execute(ctx)
    return apply_block_output(state, block.block_id, output)


class _CapturingWorkflow:
    def __init__(self, name: str = "analysis_child_workflow") -> None:
        self.name = name
        self.received_state: WorkflowState | None = None
        self.received_kwargs: dict[str, Any] | None = None

    async def run(self, state: WorkflowState, **kwargs: Any) -> WorkflowState:
        self.received_state = state
        self.received_kwargs = kwargs
        return WorkflowState(
            artifact_store=state.artifact_store,
            total_cost_usd=0.25,
            total_tokens=17,
            results={"writer": BlockResult(output="child analysis output")},
        )


class _InvocationEchoBlock:
    def __init__(self, block_id: str, input_name: str) -> None:
        self.block_id = block_id
        self.retry_config = None
        self.stateful = False
        self.context_access = "declared"
        self.declared_inputs = {input_name: f"workflow.{input_name}"}
        self._input_name = input_name

    async def execute(self, ctx: Any) -> BlockOutput:
        return BlockOutput(output=ctx.inputs[self._input_name])


def _parent_state() -> WorkflowState:
    return WorkflowState(
        shared_memory={"parent_topic": "climate change"},
        results={"prepare_input": BlockResult(output="from result")},
    )


@pytest.mark.asyncio
class TestNameBasedWorkflowInvocation:
    async def test_workflow_block_passes_public_input_names_via_child_inputs_kwarg(self) -> None:
        analysis_child_workflow = _CapturingWorkflow()
        wb = WorkflowBlock(
            block_id="analysis_child_invocation_block",
            child_workflow=analysis_child_workflow,
            inputs={"query": "shared_memory.parent_topic"},
            outputs={},
        )

        result_state = await _exec(wb, _parent_state())

        assert analysis_child_workflow.received_kwargs is not None
        assert analysis_child_workflow.received_kwargs["inputs"] == {"query": "climate change"}
        assert analysis_child_workflow.received_state is not None
        assert analysis_child_workflow.received_state.results == {}
        assert analysis_child_workflow.received_state.shared_memory == {}
        assert analysis_child_workflow.received_state.metadata == {}
        assert result_state.results["analysis_child_invocation_block"].exit_handle == "completed"

    async def test_workflow_block_unwraps_parent_block_results_for_invocation_inputs(self) -> None:
        analysis_child_workflow = _CapturingWorkflow()
        wb = WorkflowBlock(
            block_id="analysis_child_invocation_block",
            child_workflow=analysis_child_workflow,
            inputs={"query": "results.prepare_input"},
            outputs={},
        )

        await _exec(wb, _parent_state())

        assert analysis_child_workflow.received_kwargs is not None
        assert analysis_child_workflow.received_kwargs["inputs"] == {"query": "from result"}

    async def test_child_can_read_name_based_invocation_input_through_direct_run_path(self) -> None:
        child_block = _InvocationEchoBlock("echo", input_name="query")
        analysis_child_workflow = Workflow(name="analysis_child_workflow")
        analysis_child_workflow.add_block(child_block)
        analysis_child_workflow.set_entry("echo")

        wb = WorkflowBlock(
            block_id="analysis_child_invocation_block",
            child_workflow=analysis_child_workflow,
            inputs={"query": "shared_memory.parent_topic"},
            outputs={"results.analysis": "results.echo"},
        )

        result_state = await _exec(wb, _parent_state())

        assert str(result_state.results["analysis"]) == "climate change"

    async def test_workflow_block_returns_compact_metadata_without_raw_child_results(self) -> None:
        analysis_child_workflow = _CapturingWorkflow()
        wb = WorkflowBlock(
            block_id="analysis_child_invocation_block",
            child_workflow=analysis_child_workflow,
            inputs={"query": "shared_memory.parent_topic"},
            outputs={},
        )

        result_state = await _exec(wb, _parent_state())

        br = result_state.results.get("analysis_child_invocation_block")
        assert isinstance(br, BlockResult)
        assert br.metadata is not None
        assert br.metadata["child_status"] == "completed"
        assert br.metadata["child_cost_usd"] == 0.25
        assert br.metadata["child_tokens"] == 17
        assert "child_duration_s" in br.metadata
        assert "child_run_id" in br.metadata
        assert "writer" not in br.metadata
        assert "results" not in br.metadata

    async def test_workflow_block_rejects_private_child_state_input_targets(self) -> None:
        analysis_child_workflow = _CapturingWorkflow()

        with pytest.raises(ValueError, match="private child state|child invocation input"):
            wb = WorkflowBlock(
                block_id="analysis_child_invocation_block",
                child_workflow=analysis_child_workflow,
                inputs={"shared_memory.topic": "shared_memory.parent_topic"},
                outputs={},
            )
            await _exec(wb, _parent_state())

        assert analysis_child_workflow.received_state is None

    async def test_nested_workflow_blocks_forward_public_invocation_names_recursively(
        self,
    ) -> None:
        grandchild = _CapturingWorkflow(name="nested_grandchild_workflow")
        child_block = WorkflowBlock(
            block_id="nested_grandchild_invocation",
            child_workflow=grandchild,
            inputs={"query": "workflow.query"},
            outputs={},
        )
        child_workflow = Workflow(name="nested_child_workflow")
        child_workflow.add_block(child_block)
        child_workflow.set_entry("nested_grandchild_invocation")

        parent_block = WorkflowBlock(
            block_id="nested_child_invocation",
            child_workflow=child_workflow,
            inputs={"query": "shared_memory.parent_topic"},
            outputs={},
        )

        await _exec(parent_block, _parent_state())

        assert grandchild.received_kwargs is not None
        assert grandchild.received_kwargs["inputs"] == {"query": "climate change"}
        assert grandchild.received_state is not None
        assert grandchild.received_state.results == {}
        assert grandchild.received_state.shared_memory == {}
