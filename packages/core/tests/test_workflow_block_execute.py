"""Smoke coverage for WorkflowBlock execution wiring."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from runsight_core import WorkflowBlock
from runsight_core.state import BlockResult, WorkflowState


async def _run_block(block, state: WorkflowState) -> WorkflowState:
    from runsight_core.block_io import BlockOutput, apply_block_output, build_block_context

    ctx = build_block_context(block, state)
    output = await block.execute(ctx)
    if isinstance(output, WorkflowState):
        return output
    if isinstance(output, BlockOutput):
        return apply_block_output(state, block.block_id, output)
    return state


@pytest.mark.asyncio
async def test_workflow_block_isolates_child_state_and_maps_declared_outputs() -> None:
    child_final_state = WorkflowState(
        results={
            "final": BlockResult(output="child output"),
            "scratch": BlockResult(output="must stay private"),
        },
        shared_memory={"child_private": "hidden"},
        total_cost_usd=0.05,
        total_tokens=50,
    )
    child_workflow = SimpleNamespace(
        name="child_without_assertion_configs",
        run=AsyncMock(return_value=child_final_state),
    )
    block = WorkflowBlock(
        block_id="invoke_child",
        child_workflow=child_workflow,
        inputs={"topic": "shared_memory.research_topic"},
        outputs={
            "results.parent_summary": "results.final",
            "shared_memory.child_summary": "results.final",
        },
        max_depth=10,
    )
    parent_state = WorkflowState(
        shared_memory={"research_topic": "AI safety", "other": "data"},
        results={"existing": BlockResult(output="previous output")},
        metadata={"workflow_id": "parent"},
        total_cost_usd=0.10,
        total_tokens=200,
    )

    result = await _run_block(block, parent_state)

    child_state = child_workflow.run.call_args.args[0]
    assert child_workflow.run.call_args.kwargs["inputs"] == {"topic": "AI safety"}
    assert child_state.workflow_inputs == {"topic": "AI safety"}
    assert child_state.results == {}
    assert child_state.shared_memory == {}
    assert child_state.metadata == {}

    assert result.results["existing"] == BlockResult(output="previous output")
    assert result.results["parent_summary"] == BlockResult(output="child output")
    assert "scratch" not in result.results
    assert result.shared_memory["child_summary"] == "child output"
    assert result.results["invoke_child"].exit_handle == "completed"
    assert result.total_cost_usd == pytest.approx(0.15)
    assert result.total_tokens == 250
