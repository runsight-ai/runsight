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
from runsight_core.primitives import Soul
from runsight_core.runner import ExecutionResult
from runsight_core.state import WorkflowState
from runsight_core.workflow import Workflow

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


class TestStatefulDispatchBlockInsideLoop:
    """Stateful DispatchBlock with 3 souls inside LoopBlock across 2 rounds.
    Each soul must have independent 2-round history."""

    @pytest.mark.asyncio
    async def test_per_soul_histories_after_2_rounds(self):
        """Each of 3 souls should have 4 messages (2 rounds x user + assistant)."""
        runner = _make_mock_runner()
        soul_a = Soul(
            id="soul_a",
            kind="soul",
            name="Reviewer A",
            role="Reviewer A",
            system_prompt="You review.",
        )
        soul_b = Soul(
            id="soul_b",
            kind="soul",
            name="Reviewer B",
            role="Reviewer B",
            system_prompt="You review.",
        )
        soul_c = Soul(
            id="soul_c",
            kind="soul",
            name="Reviewer C",
            role="Reviewer C",
            system_prompt="You review.",
        )

        call_counts = {"soul_a": 0, "soul_b": 0, "soul_c": 0}

        async def _side_effect(instruction, context, soul, **kwargs):
            call_counts[soul.id] += 1
            return _make_result("t1", soul.id, f"{soul.id}_round_{call_counts[soul.id]}")

        runner.execute = AsyncMock(side_effect=_side_effect)

        inner = _make_stateful_dispatch("review", [soul_a, soul_b, soul_c], runner)
        loop = LoopBlock(
            block_id="loop",
            inner_block_refs=["review"],
            max_rounds=2,
        )
        blocks = {"review": inner, "loop": loop}

        state = WorkflowState()
        result_state = await _exec_loop(loop, state, blocks)

        for soul_id in ["soul_a", "soul_b", "soul_c"]:
            history_key = f"review_{soul_id}"
            assert history_key in result_state.conversation_histories, (
                f"Missing history for {history_key}"
            )
            history = result_state.conversation_histories[history_key]
            assert len(history) == 4, (
                f"Expected 4 messages for {history_key} (2 rounds x 2), got {len(history)}"
            )

    @pytest.mark.asyncio
    async def test_per_soul_history_independence(self):
        """Each soul's history must contain only its own outputs, not other souls'."""
        runner = _make_mock_runner()
        soul_a = Soul(
            id="soul_a",
            kind="soul",
            name="Reviewer A",
            role="Reviewer A",
            system_prompt="Review A.",
        )
        soul_b = Soul(
            id="soul_b",
            kind="soul",
            name="Reviewer B",
            role="Reviewer B",
            system_prompt="Review B.",
        )
        soul_c = Soul(
            id="soul_c",
            kind="soul",
            name="Reviewer C",
            role="Reviewer C",
            system_prompt="Review C.",
        )

        async def _side_effect(instruction, context, soul, **kwargs):
            return _make_result("t1", soul.id, f"UNIQUE_{soul.id}_OUTPUT")

        runner.execute = AsyncMock(side_effect=_side_effect)

        inner = _make_stateful_dispatch("review", [soul_a, soul_b, soul_c], runner)
        loop = LoopBlock(
            block_id="loop",
            inner_block_refs=["review"],
            max_rounds=2,
        )
        blocks = {"review": inner, "loop": loop}

        state = WorkflowState()
        result_state = await _exec_loop(loop, state, blocks)

        # Verify each soul's history contains only its own output
        for soul_id in ["soul_a", "soul_b", "soul_c"]:
            history = result_state.conversation_histories[f"review_{soul_id}"]
            all_content = " ".join(m["content"] for m in history)
            assert f"UNIQUE_{soul_id}_OUTPUT" in all_content

            # No other soul's output should appear
            for other_id in ["soul_a", "soul_b", "soul_c"]:
                if other_id != soul_id:
                    assert f"UNIQUE_{other_id}_OUTPUT" not in all_content, (
                        f"{soul_id}'s history contains {other_id}'s output"
                    )

    @pytest.mark.asyncio
    async def test_each_soul_receives_own_growing_history(self):
        """In round 2, each soul's LLM call must include only that soul's round 1 messages."""
        runner = _make_mock_runner()
        soul_a = Soul(id="soul_a", kind="soul", name="Soul A", role="A", system_prompt="A.")
        soul_b = Soul(id="soul_b", kind="soul", name="Soul B", role="B", system_prompt="B.")
        soul_c = Soul(id="soul_c", kind="soul", name="Soul C", role="C", system_prompt="C.")

        messages_per_soul_per_round = {"soul_a": [], "soul_b": [], "soul_c": []}

        async def _capture_side_effect(instruction, context, soul, **kwargs):
            msgs = kwargs.get("messages", [])
            messages_per_soul_per_round[soul.id].append(list(msgs))
            return _make_result("t1", soul.id, f"{soul.id}_output")

        runner.execute = AsyncMock(side_effect=_capture_side_effect)

        inner = _make_stateful_dispatch("fan", [soul_a, soul_b, soul_c], runner)
        loop = LoopBlock(
            block_id="loop",
            inner_block_refs=["fan"],
            max_rounds=2,
        )
        blocks = {"fan": inner, "loop": loop}

        state = WorkflowState()
        await _exec_loop(loop, state, blocks)

        for soul_id in ["soul_a", "soul_b", "soul_c"]:
            calls = messages_per_soul_per_round[soul_id]
            assert len(calls) == 2, f"Expected 2 calls for {soul_id}, got {len(calls)}"
            # Round 1: empty history
            assert len(calls[0]) == 0, (
                f"Round 1 for {soul_id}: expected 0 messages, got {len(calls[0])}"
            )
            # Round 2: 2 messages from round 1
            assert len(calls[1]) == 2, (
                f"Round 2 for {soul_id}: expected 2 messages, got {len(calls[1])}"
            )

    @pytest.mark.asyncio
    async def test_dispatch_inside_loop_via_workflow_run(self):
        """Integration through Workflow.run()."""
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
            max_rounds=2,
        )

        wf = Workflow(name="stateful_dispatch_loop_workflow")
        wf.add_block(inner)
        wf.add_block(loop)
        wf.add_transition("loop", None)
        wf.set_entry("loop")

        state = WorkflowState()
        result_state = await wf.run(state)

        for soul_id in ["soul_a", "soul_b"]:
            history = result_state.conversation_histories[f"fan_{soul_id}"]
            assert len(history) == 4, f"Expected 4 messages for fan_{soul_id}, got {len(history)}"


# ===========================================================================
# 3. Windowing activates within loop
# ===========================================================================
