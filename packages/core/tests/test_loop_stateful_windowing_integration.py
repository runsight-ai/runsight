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

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from runsight_core import (
    DispatchBlock,
    LinearBlock,
    LoopBlock,
)
from runsight_core.block_io import BlockContext, apply_block_output
from runsight_core.blocks.dispatch import DispatchBranch
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


class TestWindowingActivatesInsideLoop:
    """When history exceeds token budget inside a loop, budget fitting must prune."""

    @pytest.mark.asyncio
    async def test_windowing_prunes_during_loop_rounds(self):
        """With a tiny token budget simulated by mock, old messages get dropped."""
        runner = _make_mock_runner()
        soul = Soul(
            id="analyst", kind="soul", name="Analyst", role="Analyst", system_prompt="You analyze."
        )

        call_count = 0

        async def _side_effect(instruction, context, soul, **kwargs):
            nonlocal call_count
            call_count += 1
            return _make_result("t1", "analyst", f"Response {call_count}")

        runner.execute = AsyncMock(side_effect=_side_effect)

        inner = _make_stateful_linear("analyze", soul, runner)
        loop = LoopBlock(
            block_id="loop",
            inner_block_refs=["analyze"],
            max_rounds=5,
        )
        blocks = {"analyze": inner, "loop": loop}

        from runsight_core.memory.budget import BudgetedContext, BudgetReport

        # Pre-call budget fitting keeps only the last 2 messages (1 pair)
        # so after appending the new pair: 2 + 2 = 4 messages stored
        def _aggressive_budget(request, counter):
            msgs = list(request.conversation_history)
            if len(msgs) > 2:
                msgs = msgs[-2:]
            report = BudgetReport(
                model=request.model,
                max_input_tokens=0,
                output_reserve=0,
                effective_budget=100000,
                p1_tokens=0,
                p2_tokens_before=0,
                p2_tokens_after=0,
                p3_tokens_before=0,
                p3_tokens_after=0,
                p3_pairs_dropped=0,
                total_tokens=0,
                headroom=100000,
                warnings=[],
            )
            return BudgetedContext(
                instruction=request.instruction,
                context=request.context,
                messages=msgs,
                report=report,
            )

        state = WorkflowState()

        with patch(
            "runsight_core.block_io.fit_to_budget",
            side_effect=_aggressive_budget,
        ):
            result_state = await _exec_loop(loop, state, blocks)

        history = result_state.conversation_histories["analyze_analyst"]
        # Pre-call pruning keeps 2 msgs + appends 2 new = 4 stored
        assert len(history) == 4, (
            f"Expected 4 messages after aggressive pruning, got {len(history)}"
        )
        # The latest round's output must be the last message
        assert history[-1]["role"] == "assistant"
        assert history[-1]["content"] == "Response 5"

    @pytest.mark.asyncio
    async def test_windowing_prunes_dispatch_per_soul_inside_loop(self):
        """Budget fitting should prune per-soul histories independently inside a loop."""
        runner = _make_mock_runner()
        soul_a = Soul(id="soul_a", kind="soul", name="Soul A", role="A", system_prompt="A.")
        soul_b = Soul(id="soul_b", kind="soul", name="Soul B", role="B", system_prompt="B.")

        async def _side_effect(instruction, context, soul, **kwargs):
            return _make_result("t1", soul.id, f"{soul.id}_out")

        runner.execute = AsyncMock(side_effect=_side_effect)

        inner = _make_stateful_dispatch("fan", [soul_a, soul_b], runner)
        loop = LoopBlock(
            block_id="loop",
            inner_block_refs=["fan"],
            max_rounds=4,
        )
        blocks = {"fan": inner, "loop": loop}

        from runsight_core.memory.budget import BudgetedContext, BudgetReport

        # Pre-call budget fitting returns empty messages (drops all history)
        # so after appending the new pair: 0 + 2 = 2 messages stored
        def _aggressive_budget(request, counter):
            msgs = []  # drop all history
            report = BudgetReport(
                model=request.model,
                max_input_tokens=0,
                output_reserve=0,
                effective_budget=100000,
                p1_tokens=0,
                p2_tokens_before=0,
                p2_tokens_after=0,
                p3_tokens_before=0,
                p3_tokens_after=0,
                p3_pairs_dropped=0,
                total_tokens=0,
                headroom=100000,
                warnings=[],
            )
            return BudgetedContext(
                instruction=request.instruction,
                context=request.context,
                messages=msgs,
                report=report,
            )

        state = WorkflowState()

        with patch(
            "runsight_core.blocks.dispatch.fit_to_budget",
            side_effect=_aggressive_budget,
        ):
            result_state = await _exec_loop(loop, state, blocks)

        for soul_id in ["soul_a", "soul_b"]:
            history = result_state.conversation_histories[f"fan_{soul_id}"]
            assert len(history) == 2, (
                f"Expected 2 messages for fan_{soul_id} after pruning, got {len(history)}"
            )
            assert history[-1]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_pruned_history_still_passed_to_next_round(self):
        """After budget fitting, the pruned (shorter) history should be what the
        next round's LLM call receives — proving state passthrough works."""
        runner = _make_mock_runner()
        soul = Soul(
            id="analyst", kind="soul", name="Analyst", role="Analyst", system_prompt="Analyze."
        )

        messages_received = []

        async def _capture(instruction, context, soul, **kwargs):
            msgs = kwargs.get("messages", [])
            messages_received.append(list(msgs))
            return _make_result("t1", "analyst", f"Out {len(messages_received)}")

        runner.execute = AsyncMock(side_effect=_capture)

        inner = _make_stateful_linear("analyze", soul, runner)
        loop = LoopBlock(
            block_id="loop",
            inner_block_refs=["analyze"],
            max_rounds=4,
        )
        blocks = {"analyze": inner, "loop": loop}

        from runsight_core.memory.budget import BudgetedContext, BudgetReport

        # Pre-call budget fitting prunes to last 2 messages
        def _budget_prune_to_2(request, counter):
            msgs = list(request.conversation_history)
            if len(msgs) > 2:
                msgs = msgs[-2:]
            report = BudgetReport(
                model=request.model,
                max_input_tokens=0,
                output_reserve=0,
                effective_budget=100000,
                p1_tokens=0,
                p2_tokens_before=0,
                p2_tokens_after=0,
                p3_tokens_before=0,
                p3_tokens_after=0,
                p3_pairs_dropped=0,
                total_tokens=0,
                headroom=100000,
                warnings=[],
            )
            return BudgetedContext(
                instruction=request.instruction,
                context=request.context,
                messages=msgs,
                report=report,
            )

        state = WorkflowState()

        with patch(
            "runsight_core.block_io.fit_to_budget",
            side_effect=_budget_prune_to_2,
        ):
            await _exec_loop(loop, state, blocks)

        assert len(messages_received) == 4

        # Round 1: no history (fit_to_budget gets [], returns [])
        assert len(messages_received[0]) == 0
        # Round 2: 2 messages from round 1 (not pruned yet — only 2 messages)
        assert len(messages_received[1]) == 2
        # Round 3: pruned to 2 by fit_to_budget (had 4, pruned to 2)
        assert len(messages_received[2]) == 2
        # Round 4: pruned to 2 by fit_to_budget (had 4, pruned to 2)
        assert len(messages_received[3]) == 2


# ===========================================================================
# 4. Break condition works with BlockResult.output
# ===========================================================================
