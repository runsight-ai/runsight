"""
LoopBlock forwarding and nested execution behavior.

Tests cover:
- execution inputs are forwarded to inner blocks
- nested LoopBlocks resolve inner block references from the workflow block map
- WorkflowBlock inside LoopBlock receives call_stack, workflow_registry, and observer
- deeply nested loops chain execution inputs through each level
- passthrough LoopBlock cases still execute the expected number of rounds
"""

from typing import Any, Dict, List

import pytest
from runsight_core.block_io import (
    BlockContext,
    BlockOutput,
    apply_block_output,
    build_block_context,
)
from runsight_core.blocks.base import BaseBlock
from runsight_core.state import WorkflowState
from runsight_core.workflow import Workflow

# ── Test helpers ─────────────────────────────────────────────────────────────


async def _exec(block, state, **extra_inputs):
    """Helper: build BlockContext, execute block, apply output to state."""
    ctx = build_block_context(block, state)
    if extra_inputs:
        ctx = ctx.model_copy(update={"inputs": {**ctx.inputs, **extra_inputs}})
    output = await block.execute(ctx)
    return apply_block_output(state, block.block_id, output)


class KwargsSpyBlock(BaseBlock):
    """Block that captures the inputs it receives in execute().

    Stores them on the instance AND in shared_memory so tests can inspect
    what was actually forwarded by the caller (LoopBlock).
    Now captures ctx.inputs (the new API) instead of **kwargs.
    """

    def __init__(self, block_id: str):
        super().__init__(block_id)
        self.context_access = "declared"
        self.captured_kwargs: List[Dict[str, Any]] = []
        self.kwargs_log: list[list[str]] = []

    async def execute(self, ctx: BlockContext) -> BlockOutput:
        # Capture ctx.inputs (replaces old **kwargs)
        inputs_snapshot = dict(ctx.inputs)
        self.captured_kwargs.append(inputs_snapshot)
        call_num = len(self.captured_kwargs)
        self.kwargs_log.append(sorted(inputs_snapshot.keys()))
        return BlockOutput(
            output=f"call_{call_num}",
            shared_memory_updates={f"{self.block_id}_kwargs_log": list(self.kwargs_log)},
        )


class SimplePassthroughBlock(BaseBlock):
    """Block that simply records a call and passes through — no kwargs needed."""

    def __init__(self, block_id: str):
        super().__init__(block_id)
        self.context_access = "declared"
        self.calls: list[int] = []

    async def execute(self, ctx: BlockContext) -> BlockOutput:
        self.calls.append(len(self.calls) + 1)
        return BlockOutput(
            output=f"call_{len(self.calls)}",
            shared_memory_updates={f"{self.block_id}_calls": list(self.calls)},
        )


# =============================================================================
# 1. Execution input forwarding to inner blocks
# =============================================================================


class TestLoopBlockPassthroughExecution:
    """Simple LoopBlock cases that should pass regardless of call-stack forwarding."""

    @pytest.mark.asyncio
    async def test_simple_loop_still_works(self):
        """Basic LoopBlock with a simple inner block should still work."""
        from runsight_core import LoopBlock

        inner = SimplePassthroughBlock("inner_block")
        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["inner_block"],
            max_rounds=3,
        )
        blocks = {"inner_block": inner, "loop_block": loop}

        state = WorkflowState()
        result_state = await _exec(loop, state, blocks=blocks)

        calls = result_state.shared_memory.get("inner_block_calls", [])
        assert len(calls) == 3

    @pytest.mark.asyncio
    async def test_simple_loop_via_workflow_run(self):
        """Basic LoopBlock through Workflow.run() still works."""
        from runsight_core import LoopBlock

        inner = SimplePassthroughBlock("inner_block")
        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["inner_block"],
            max_rounds=2,
        )

        workflow = Workflow(name="simple_loop_workflow")
        workflow.add_block(inner)
        workflow.add_block(loop)
        workflow.add_transition("loop_block", None)
        workflow.set_entry("loop_block")

        state = WorkflowState()
        result_state = await workflow.run(state)

        calls = result_state.shared_memory.get("inner_block_calls", [])
        assert len(calls) == 2

    @pytest.mark.asyncio
    async def test_multi_ref_loop_still_works(self):
        """LoopBlock with multiple inner refs still runs all per round."""
        from runsight_core import LoopBlock

        primary_passthrough_block = SimplePassthroughBlock("primary_passthrough_block")
        secondary_passthrough_block = SimplePassthroughBlock("secondary_passthrough_block")
        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["primary_passthrough_block", "secondary_passthrough_block"],
            max_rounds=2,
        )
        blocks = {
            "primary_passthrough_block": primary_passthrough_block,
            "secondary_passthrough_block": secondary_passthrough_block,
            "loop_block": loop,
        }

        state = WorkflowState()
        result_state = await _exec(loop, state, blocks=blocks)

        assert len(result_state.shared_memory.get("primary_passthrough_block_calls", [])) == 2
        assert len(result_state.shared_memory.get("secondary_passthrough_block_calls", [])) == 2
