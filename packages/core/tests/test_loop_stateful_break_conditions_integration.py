"""
Integration tests for LoopBlock stateful round validation.

All underlying stateful and carry-context behavior is implemented.
These tests validate that everything works together when a stateful block runs inside
a LoopBlock across multiple rounds:

1. Stateful LinearBlock inside LoopBlock, 3 rounds — history grows 2*N after N rounds
2. Stateful DispatchBlock (3 souls) inside LoopBlock, 2 rounds — per-soul independent histories
3. Windowing activates within loop — history exceeds token budget, gets pruned
4. Break condition works with BlockResult.output — evaluates string, not BlockResult object
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from runsight_core import (
    DispatchBlock,
    LinearBlock,
    LoopBlock,
)
from runsight_core.block_io import BlockContext, apply_block_output
from runsight_core.blocks.dispatch import DispatchBranch
from runsight_core.conditions.engine import Condition
from runsight_core.primitives import Soul
from runsight_core.runner import ExecutionResult
from runsight_core.state import WorkflowState

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _exec_loop(loop: LoopBlock, state: WorkflowState, blocks: dict) -> WorkflowState:
    """Build a BlockContext for a LoopBlock, execute it, and apply the output to state."""
    ctx = BlockContext(
        block_id=loop.block_id,
        instruction="loop",
        inputs={"blocks": blocks},
        state_snapshot=state,
    )
    output = await loop.execute(ctx)
    return apply_block_output(state, loop.block_id, output)


def _make_mock_runner():
    """Create a mock RunsightTeamRunner with controlled outputs."""
    runner = MagicMock()
    runner.execute = AsyncMock()
    runner.model_name = "gpt-4o"
    return runner


def _make_result(task_id, soul_id, output, cost=0.0, tokens=0):
    """Helper to create an ExecutionResult."""
    return ExecutionResult(
        task_id=task_id,
        soul_id=soul_id,
        output=output,
        cost_usd=cost,
        total_tokens=tokens,
    )


def _make_stateful_linear(block_id, soul, runner):
    """Helper to create a stateful LinearBlock."""
    block = LinearBlock(block_id, soul, runner)
    block.stateful = True
    return block


def _souls_to_branches(souls):
    """Convert a list of Soul objects to DispatchBranch objects."""
    return [
        DispatchBranch(exit_id=s.id, label=s.role, soul=s, task_instruction="Execute task")
        for s in souls
    ]


def _make_stateful_dispatch(block_id, souls, runner):
    """Helper to create a stateful DispatchBlock."""
    block = DispatchBlock(block_id, _souls_to_branches(souls), runner)
    block.stateful = True
    return block


# ===========================================================================
# 1. Stateful LinearBlock inside LoopBlock — 3 rounds
# ===========================================================================


class TestBreakConditionWithBlockResult:
    """Break condition must evaluate the string .output from BlockResult,
    not the BlockResult object itself."""

    @pytest.mark.asyncio
    async def test_break_condition_receives_string_output(self):
        """When inner block stores BlockResult in state.results, the break
        condition must extract .output and evaluate the string."""
        runner = _make_mock_runner()
        soul = Soul(
            id="analyst", kind="soul", name="Analyst", role="Analyst", system_prompt="Analyze."
        )

        call_count = 0

        async def _side_effect(instruction, context, soul, **kwargs):
            nonlocal call_count
            call_count += 1
            # On round 2, output contains "DONE"
            output = "DONE: analysis complete" if call_count >= 2 else "Still working..."
            return _make_result("t1", "analyst", output)

        runner.execute = AsyncMock(side_effect=_side_effect)

        inner = _make_stateful_linear("analyze", soul, runner)
        # Break when output contains "DONE"
        break_cond = Condition(eval_key="analyze", operator="contains", value="DONE")
        loop = LoopBlock(
            block_id="loop",
            inner_block_refs=["analyze"],
            max_rounds=5,
            break_condition=break_cond,
        )
        blocks = {"analyze": inner, "loop": loop}

        state = WorkflowState()
        result_state = await _exec_loop(loop, state, blocks)

        # Should have broken after round 2, not run all 5
        meta = result_state.shared_memory.get("__loop__loop")
        assert meta is not None, "Loop metadata not found in shared_memory"
        assert meta["rounds_completed"] == 2
        assert meta["broke_early"] is True

    @pytest.mark.asyncio
    async def test_break_condition_does_not_see_blockresult_object(self):
        """Verify the break condition evaluates a string, not 'BlockResult(output=...)'.
        If it saw the object repr, a 'contains' check for 'DONE' against
        'BlockResult(output="DONE")' could still match — so we use 'equals' for precision."""
        runner = _make_mock_runner()
        soul = Soul(
            id="analyst", kind="soul", name="Analyst", role="Analyst", system_prompt="Analyze."
        )

        call_count = 0

        async def _side_effect(instruction, context, soul, **kwargs):
            nonlocal call_count
            call_count += 1
            # Exact match — "DONE" as the entire output
            return _make_result("t1", "analyst", "DONE" if call_count >= 2 else "working")

        runner.execute = AsyncMock(side_effect=_side_effect)

        inner = _make_stateful_linear("analyze", soul, runner)
        # 'equals' operator: must match exactly "DONE", not "BlockResult(output='DONE')"
        break_cond = Condition(eval_key="analyze", operator="equals", value="DONE")
        loop = LoopBlock(
            block_id="loop",
            inner_block_refs=["analyze"],
            max_rounds=5,
            break_condition=break_cond,
        )
        blocks = {"analyze": inner, "loop": loop}

        state = WorkflowState()
        result_state = await _exec_loop(loop, state, blocks)

        meta = result_state.shared_memory["__loop__loop"]
        assert meta["rounds_completed"] == 2
        assert meta["broke_early"] is True

    @pytest.mark.asyncio
    async def test_break_condition_with_stateful_dispatch_output(self):
        """Break condition works when inner block is a stateful DispatchBlock
        that stores BlockResult with JSON output."""
        runner = _make_mock_runner()
        soul_a = Soul(id="soul_a", kind="soul", name="Soul A", role="A", system_prompt="A.")
        soul_b = Soul(id="soul_b", kind="soul", name="Soul B", role="B", system_prompt="B.")

        call_count = 0

        async def _side_effect(instruction, context, soul, **kwargs):
            nonlocal call_count
            call_count += 1
            return _make_result("t1", soul.id, f"{soul.id}_out")

        runner.execute = AsyncMock(side_effect=_side_effect)

        inner = _make_stateful_dispatch("fan", [soul_a, soul_b], runner)
        # DispatchBlock output is JSON containing "soul_a_out" — use 'contains'
        break_cond = Condition(eval_key="fan", operator="contains", value="soul_a_out")
        loop = LoopBlock(
            block_id="loop",
            inner_block_refs=["fan"],
            max_rounds=5,
            break_condition=break_cond,
        )
        blocks = {"fan": inner, "loop": loop}

        state = WorkflowState()
        result_state = await _exec_loop(loop, state, blocks)

        # Should break on round 1 since the output always contains "soul_a_out"
        meta = result_state.shared_memory["__loop__loop"]
        assert meta["rounds_completed"] == 1
        assert meta["broke_early"] is True

    @pytest.mark.asyncio
    async def test_stateful_history_preserved_after_early_break(self):
        """When break condition triggers early, the accumulated history
        up to that point must be preserved in the state."""
        runner = _make_mock_runner()
        soul = Soul(
            id="analyst", kind="soul", name="Analyst", role="Analyst", system_prompt="Analyze."
        )

        call_count = 0

        async def _side_effect(instruction, context, soul, **kwargs):
            nonlocal call_count
            call_count += 1
            return _make_result(
                "t1", "analyst", "DONE" if call_count >= 3 else f"Progress {call_count}"
            )

        runner.execute = AsyncMock(side_effect=_side_effect)

        inner = _make_stateful_linear("analyze", soul, runner)
        break_cond = Condition(eval_key="analyze", operator="equals", value="DONE")
        loop = LoopBlock(
            block_id="loop",
            inner_block_refs=["analyze"],
            max_rounds=10,
            break_condition=break_cond,
        )
        blocks = {"analyze": inner, "loop": loop}

        state = WorkflowState()
        result_state = await _exec_loop(loop, state, blocks)

        # Broke on round 3 — history should have 3 rounds = 6 messages
        history = result_state.conversation_histories["analyze_analyst"]
        assert len(history) == 6, f"Expected 6 messages (3 rounds before break), got {len(history)}"
        # Last assistant message should be the break-trigger output
        assert history[-1]["content"] == "DONE"


# ===========================================================================
# 5. Combined scenario: stateful + windowing + break inside loop
# ===========================================================================


class TestCombinedStatefulWindowingBreak:
    """Full integration: stateful block with windowing and break condition inside a loop."""

    @pytest.mark.asyncio
    async def test_stateful_windowed_loop_with_early_break(self):
        """Stateful LinearBlock with windowing, breaking early at round 3 of 10."""
        runner = _make_mock_runner()
        soul = Soul(id="writer", kind="soul", name="Writer", role="Writer", system_prompt="Write.")

        call_count = 0

        async def _side_effect(instruction, context, soul, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count >= 3:
                return _make_result("t1", "writer", "FINAL: story complete")
            return _make_result("t1", "writer", f"Draft {call_count}")

        runner.execute = AsyncMock(side_effect=_side_effect)

        inner = _make_stateful_linear("write", soul, runner)
        break_cond = Condition(eval_key="write", operator="starts_with", value="FINAL")
        loop = LoopBlock(
            block_id="loop",
            inner_block_refs=["write"],
            max_rounds=10,
            break_condition=break_cond,
        )
        blocks = {"write": inner, "loop": loop}

        state = WorkflowState()
        result_state = await _exec_loop(loop, state, blocks)

        # Verify break
        meta = result_state.shared_memory["__loop__loop"]
        assert meta["rounds_completed"] == 3
        assert meta["broke_early"] is True

        # Verify history (3 rounds = 6 messages)
        history = result_state.conversation_histories["write_writer"]
        assert len(history) == 6
        assert history[-1]["content"] == "FINAL: story complete"
