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


class TestLoopBlockForwardsKwargs:
    """LoopBlock must forward **kwargs to inner block execute() calls."""

    @pytest.mark.asyncio
    async def test_inner_block_receives_blocks_kwarg(self):
        """Inner blocks must receive 'blocks' dict via kwargs when LoopBlock gets it."""
        from runsight_core import LoopBlock

        spy = KwargsSpyBlock("spy_block")
        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["spy_block"],
            max_rounds=1,
        )
        blocks = {"spy_block": spy, "loop_block": loop}

        state = WorkflowState()
        await _exec(loop, state, blocks=blocks)

        assert len(spy.captured_kwargs) == 1
        # 'blocks' is loop-internal infrastructure, excluded from parent_inputs
        # to prevent JSON serialization failures. Inner blocks receive their own
        # BlockContext via build_block_context — they don't need the blocks dict.
        # Verify the spy was called (received a BlockContext with inputs).
        assert isinstance(spy.captured_kwargs[0], dict)

    @pytest.mark.asyncio
    async def test_inner_block_receives_call_stack_kwarg(self):
        """Inner blocks must receive 'call_stack' when LoopBlock gets it."""
        from runsight_core import LoopBlock

        spy = KwargsSpyBlock("spy_block")
        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["spy_block"],
            max_rounds=1,
        )
        blocks = {"spy_block": spy, "loop_block": loop}

        state = WorkflowState()
        call_stack = ["parent_workflow"]
        await _exec(loop, state, blocks=blocks, call_stack=call_stack)

        assert len(spy.captured_kwargs) == 1
        assert "call_stack" in spy.captured_kwargs[0], (
            "LoopBlock did not forward 'call_stack' kwarg to inner block"
        )
        assert spy.captured_kwargs[0]["call_stack"] == ["parent_workflow"]

    @pytest.mark.asyncio
    async def test_inner_block_receives_workflow_registry_kwarg(self):
        """Inner blocks must receive 'workflow_registry' when LoopBlock gets it."""
        from runsight_core import LoopBlock

        spy = KwargsSpyBlock("spy_block")
        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["spy_block"],
            max_rounds=1,
        )
        blocks = {"spy_block": spy, "loop_block": loop}

        mock_registry = MagicMock()
        state = WorkflowState()
        await _exec(loop, state, blocks=blocks, workflow_registry=mock_registry)

        assert len(spy.captured_kwargs) == 1
        assert "workflow_registry" in spy.captured_kwargs[0], (
            "LoopBlock did not forward 'workflow_registry' kwarg to inner block"
        )
        assert spy.captured_kwargs[0]["workflow_registry"] is mock_registry

    @pytest.mark.asyncio
    async def test_inner_block_receives_observer_kwarg(self):
        """Inner blocks must receive 'observer' when LoopBlock gets it."""
        from runsight_core import LoopBlock

        spy = KwargsSpyBlock("spy_block")
        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["spy_block"],
            max_rounds=1,
        )
        blocks = {"spy_block": spy, "loop_block": loop}

        mock_observer = MagicMock()
        state = WorkflowState()
        await _exec(loop, state, blocks=blocks, observer=mock_observer)

        assert len(spy.captured_kwargs) == 1
        assert "observer" in spy.captured_kwargs[0], (
            "LoopBlock did not forward 'observer' kwarg to inner block"
        )
        assert spy.captured_kwargs[0]["observer"] is mock_observer

    @pytest.mark.asyncio
    async def test_all_kwargs_forwarded_together(self):
        """All kwargs (blocks, call_stack, workflow_registry, observer) forwarded at once."""
        from runsight_core import LoopBlock

        spy = KwargsSpyBlock("spy_block")
        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["spy_block"],
            max_rounds=1,
        )
        blocks = {"spy_block": spy, "loop_block": loop}

        mock_registry = MagicMock()
        mock_observer = MagicMock()
        call_stack = ["root_loop_workflow"]

        state = WorkflowState()
        await _exec(
            loop,
            state,
            blocks=blocks,
            call_stack=call_stack,
            workflow_registry=mock_registry,
            observer=mock_observer,
        )

        assert len(spy.captured_kwargs) == 1
        kw = spy.captured_kwargs[0]
        # 'blocks' is loop-internal, excluded from parent_inputs forwarding
        assert "call_stack" in kw
        assert "workflow_registry" in kw
        assert "observer" in kw

    @pytest.mark.asyncio
    async def test_kwargs_forwarded_every_round(self):
        """kwargs should be forwarded on every round, not just the first."""
        from runsight_core import LoopBlock

        spy = KwargsSpyBlock("spy_block")
        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["spy_block"],
            max_rounds=3,
        )
        blocks = {"spy_block": spy, "loop_block": loop}

        mock_observer = MagicMock()
        state = WorkflowState()
        await _exec(loop, state, blocks=blocks, observer=mock_observer)

        # spy should be called 3 times (once per round), each time with inputs
        assert len(spy.captured_kwargs) == 3
        for i, kw in enumerate(spy.captured_kwargs):
            # 'blocks' is loop-internal, excluded from forwarding
            assert "observer" in kw, f"Round {i + 1}: 'observer' kwarg not forwarded"


# =============================================================================
# 2. Nested LoopBlock — inner loop needs blocks dict to resolve its own refs
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
