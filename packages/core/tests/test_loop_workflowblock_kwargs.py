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


class TestWorkflowBlockInsideLoopBlock:
    """WorkflowBlock nested in LoopBlock must receive call_stack and workflow_registry."""

    @pytest.mark.asyncio
    async def test_workflow_block_gets_call_stack_via_loop(self):
        """WorkflowBlock inside LoopBlock should receive call_stack for cycle detection.

        Verify by using max_depth=1 on the WorkflowBlock: if call_stack is forwarded
        correctly (len=1 from parent), depth check (len >= max_depth) triggers.
        If the call_stack is omitted, WorkflowBlock defaults to [] (len=0),
        and the depth check passes when it should fail.
        """
        from runsight_core import LoopBlock, WorkflowBlock

        # Create a simple child workflow
        child_leaf = SimplePassthroughBlock("child_leaf")
        child_workflow = Workflow(name="depth_limit_child_workflow")
        child_workflow.add_block(child_leaf)
        child_workflow.add_transition("child_leaf", None)
        child_workflow.set_entry("child_leaf")

        # max_depth=1 means call_stack must have len < 1, i.e., only works at depth 0.
        # Workflow.run() passes call_stack=["depth_limit_parent_workflow"] (len=1) to LoopBlock.
        # If LoopBlock forwards it, WorkflowBlock sees len(call_stack)=1 >= max_depth=1 → RecursionError.
        # If LoopBlock omits it, WorkflowBlock defaults call_stack=[] and passes silently.
        workflow_block = WorkflowBlock(
            block_id="depth_limit_workflow_block",
            child_workflow=child_workflow,
            inputs={},
            outputs={},
            max_depth=1,
        )

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["depth_limit_workflow_block"],
            max_rounds=1,
        )

        parent_workflow = Workflow(name="depth_limit_parent_workflow")
        parent_workflow.add_block(workflow_block)
        parent_workflow.add_block(loop)
        parent_workflow.add_transition("loop_block", None)
        parent_workflow.set_entry("loop_block")

        state = WorkflowState()
        # Forwarded call_stack=["depth_limit_parent_workflow"] reaches WorkflowBlock, so
        # len(call_stack) >= 1 triggers RecursionError("depth ... exceeded").
        # If call_stack is omitted, the child executes silently.
        with pytest.raises(RecursionError, match="depth"):
            await parent_workflow.run(state)

    @pytest.mark.asyncio
    async def test_workflow_block_cycle_detection_inside_loop(self):
        """Cycle detection must work for WorkflowBlock inside LoopBlock.

        If call_stack is not forwarded, a recursive WorkflowBlock inside
        a LoopBlock would not detect the cycle via WorkflowBlock's own check
        (which produces a clean "cycle detected" message). Instead, Python's
        stack overflows with "maximum recursion depth exceeded".

        The parent workflow name is forwarded to WorkflowBlock, which raises
        RecursionError("cycle detected") before uncontrolled recursion.
        """
        from runsight_core import LoopBlock, WorkflowBlock

        # Create parent workflow that contains a LoopBlock with a WorkflowBlock
        # that references the SAME parent workflow (cycle).
        parent_workflow = Workflow(name="cycle_parent_workflow")

        workflow_block = WorkflowBlock(
            block_id="cycle_workflow_block",
            child_workflow=parent_workflow,  # cycle: child = parent
            inputs={},
            outputs={},
        )

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["cycle_workflow_block"],
            max_rounds=1,
        )

        parent_workflow.add_block(workflow_block)
        parent_workflow.add_block(loop)
        parent_workflow.add_transition("loop_block", None)
        parent_workflow.set_entry("loop_block")

        state = WorkflowState()
        # Clean RecursionError("cycle detected") comes from WorkflowBlock.
        # Uncontrolled recursion would raise maximum recursion depth instead.
        # We assert the CLEAN message to prove call_stack was forwarded.
        with pytest.raises(RecursionError, match="cycle detected"):
            await parent_workflow.run(state)


# =============================================================================
# 4. Observer forwarding — events from inner blocks should propagate
# =============================================================================
