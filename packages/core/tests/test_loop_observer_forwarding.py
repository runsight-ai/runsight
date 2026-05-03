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
from unittest.mock import MagicMock

import pytest
from runsight_core.block_io import (
    BlockContext,
    BlockOutput,
    apply_block_output,
    build_block_context,
)
from runsight_core.blocks.base import BaseBlock
from runsight_core.state import WorkflowState

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


class TestObserverForwardingInsideLoop:
    """Observer kwarg must be forwarded so inner blocks can emit events."""

    @pytest.mark.asyncio
    async def test_observer_forwarded_to_inner_block(self):
        """Inner block inside LoopBlock should receive the observer kwarg."""
        from runsight_core import LoopBlock

        spy = KwargsSpyBlock("spy_block")
        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["spy_block"],
            max_rounds=2,
        )
        blocks = {"spy_block": spy, "loop_block": loop}

        mock_observer = MagicMock()
        state = WorkflowState()
        await _exec(loop, state, blocks=blocks, observer=mock_observer)

        # Verify observer was forwarded in both rounds
        assert len(spy.captured_kwargs) == 2
        for i, kw in enumerate(spy.captured_kwargs):
            assert kw.get("observer") is mock_observer, (
                f"Round {i + 1}: observer not forwarded to inner block"
            )


# =============================================================================
# 5. Passthrough LoopBlock cases still work
# =============================================================================
