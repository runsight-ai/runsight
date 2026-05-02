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


class TestNestedLoopBlockKwargs:
    """LoopBlock nested inside another LoopBlock must receive blocks dict to work."""

    @pytest.mark.asyncio
    async def test_nested_loop_resolves_inner_blocks(self):
        """Inner LoopBlock must be able to resolve its own inner_block_refs from blocks dict.

        Setup: outer_loop[inner_loop[leaf_block]]
        Without kwargs forwarding, inner_loop gets an empty blocks dict and raises ValueError.
        """
        from runsight_core import LoopBlock

        leaf = SimplePassthroughBlock("leaf_block")
        inner_loop = LoopBlock(
            block_id="inner_loop",
            inner_block_refs=["leaf_block"],
            max_rounds=2,
        )
        outer_loop = LoopBlock(
            block_id="outer_loop",
            inner_block_refs=["inner_loop"],
            max_rounds=2,
        )
        blocks = {
            "leaf_block": leaf,
            "inner_loop": inner_loop,
            "outer_loop": outer_loop,
        }

        state = WorkflowState()
        # Without kwargs forwarding, inner_loop.execute(state) has no blocks dict
        # and raises ValueError: inner block ref 'leaf_block' not found
        result_state = await _exec(outer_loop, state, blocks=blocks)

        # leaf should have executed 2 (inner rounds) x 2 (outer rounds) = 4 times
        leaf_calls = result_state.shared_memory.get("leaf_block_calls", [])
        assert len(leaf_calls) == 4, (
            f"Expected 4 leaf executions (2 inner x 2 outer), got {len(leaf_calls)}"
        )

    @pytest.mark.asyncio
    async def test_deeply_nested_loop_three_levels(self):
        """Three levels deep: outer > middle > inner > leaf — kwargs chain all the way.

        Setup: outer_loop[middle_loop[inner_loop[leaf_block]]]
        """
        from runsight_core import LoopBlock

        leaf = SimplePassthroughBlock("leaf_block")
        inner_loop = LoopBlock(
            block_id="inner_loop",
            inner_block_refs=["leaf_block"],
            max_rounds=2,
        )
        middle_loop = LoopBlock(
            block_id="middle_loop",
            inner_block_refs=["inner_loop"],
            max_rounds=2,
        )
        outer_loop = LoopBlock(
            block_id="outer_loop",
            inner_block_refs=["middle_loop"],
            max_rounds=2,
        )
        blocks = {
            "leaf_block": leaf,
            "inner_loop": inner_loop,
            "middle_loop": middle_loop,
            "outer_loop": outer_loop,
        }

        state = WorkflowState()
        result_state = await _exec(outer_loop, state, blocks=blocks)

        # leaf: 2 (inner) x 2 (middle) x 2 (outer) = 8 executions
        leaf_calls = result_state.shared_memory.get("leaf_block_calls", [])
        assert len(leaf_calls) == 8, f"Expected 8 leaf executions (2^3), got {len(leaf_calls)}"

    @pytest.mark.asyncio
    async def test_nested_loop_via_workflow_run(self):
        """Nested LoopBlock through Workflow.run() — the real integration path.

        Workflow.run() passes blocks=self._blocks to LoopBlock; that must be
        forwarded so inner LoopBlock can also resolve its refs.
        """
        from runsight_core import LoopBlock

        leaf = SimplePassthroughBlock("leaf_block")
        inner_loop = LoopBlock(
            block_id="inner_loop",
            inner_block_refs=["leaf_block"],
            max_rounds=2,
        )
        outer_loop = LoopBlock(
            block_id="outer_loop",
            inner_block_refs=["inner_loop"],
            max_rounds=2,
        )

        workflow = Workflow(name="nested_loop_workflow")
        workflow.add_block(leaf)
        workflow.add_block(inner_loop)
        workflow.add_block(outer_loop)
        workflow.add_transition("outer_loop", None)
        workflow.set_entry("outer_loop")

        state = WorkflowState()
        result_state = await workflow.run(state)

        leaf_calls = result_state.shared_memory.get("leaf_block_calls", [])
        assert len(leaf_calls) == 4, (
            f"Expected 4 leaf executions via Workflow.run(), got {len(leaf_calls)}"
        )


# =============================================================================
# 3. WorkflowBlock inside LoopBlock — needs call_stack + workflow_registry
# =============================================================================
