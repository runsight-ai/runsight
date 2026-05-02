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


class TestStatefulLinearBlockInsideLoop:
    """Stateful LinearBlock inside LoopBlock across multiple rounds.
    Conversation history should grow by 2 messages (user + assistant) per round."""

    @pytest.mark.asyncio
    async def test_history_grows_2n_after_n_rounds(self):
        """After 3 rounds, conversation_histories[key] must have 2*3 = 6 messages."""
        runner = _make_mock_runner()
        soul = Soul(
            id="analyst", kind="soul", name="Analyst", role="Analyst", system_prompt="You analyze."
        )

        # Runner returns different output each call to verify round ordering
        call_count = 0

        async def _side_effect(instruction, context, soul, **kwargs):
            nonlocal call_count
            call_count += 1
            return _make_result("t1", "analyst", f"Analysis round {call_count}")

        runner.execute = AsyncMock(side_effect=_side_effect)

        inner = _make_stateful_linear("analyze", soul, runner)
        loop = LoopBlock(
            block_id="loop",
            inner_block_refs=["analyze"],
            max_rounds=3,
        )
        blocks = {"analyze": inner, "loop": loop}

        state = WorkflowState()
        result_state = await _exec_loop(loop, state, blocks)

        history_key = "analyze_analyst"
        assert history_key in result_state.conversation_histories

        history = result_state.conversation_histories[history_key]
        assert len(history) == 6, f"Expected 6 messages (3 rounds x 2), got {len(history)}"

    @pytest.mark.asyncio
    async def test_each_round_alternates_user_assistant(self):
        """History must alternate user/assistant for every message."""
        runner = _make_mock_runner()
        soul = Soul(
            id="analyst", kind="soul", name="Analyst", role="Analyst", system_prompt="You analyze."
        )

        call_count = 0

        async def _side_effect(instruction, context, soul, **kwargs):
            nonlocal call_count
            call_count += 1
            return _make_result("t1", "analyst", f"Round {call_count}")

        runner.execute = AsyncMock(side_effect=_side_effect)

        inner = _make_stateful_linear("analyze", soul, runner)
        loop = LoopBlock(
            block_id="loop",
            inner_block_refs=["analyze"],
            max_rounds=3,
        )
        blocks = {"analyze": inner, "loop": loop}

        state = WorkflowState()
        result_state = await _exec_loop(loop, state, blocks)

        history = result_state.conversation_histories["analyze_analyst"]
        for i, msg in enumerate(history):
            expected_role = "user" if i % 2 == 0 else "assistant"
            assert msg["role"] == expected_role, (
                f"Message {i}: expected role '{expected_role}', got '{msg['role']}'"
            )

    @pytest.mark.asyncio
    async def test_llm_receives_growing_history_each_round(self):
        """Each round's LLM call must include all prior rounds' messages."""
        runner = _make_mock_runner()
        soul = Soul(
            id="analyst", kind="soul", name="Analyst", role="Analyst", system_prompt="You analyze."
        )

        messages_received_per_call = []

        async def _capture_side_effect(instruction, context, soul, **kwargs):
            msgs = kwargs.get("messages", [])
            messages_received_per_call.append(list(msgs))
            return _make_result("t1", "analyst", f"Output {len(messages_received_per_call)}")

        runner.execute = AsyncMock(side_effect=_capture_side_effect)

        inner = _make_stateful_linear("analyze", soul, runner)
        loop = LoopBlock(
            block_id="loop",
            inner_block_refs=["analyze"],
            max_rounds=3,
        )
        blocks = {"analyze": inner, "loop": loop}

        state = WorkflowState()
        await _exec_loop(loop, state, blocks)

        assert len(messages_received_per_call) == 3

        # Round 1: empty history (no prior rounds)
        assert len(messages_received_per_call[0]) == 0

        # Round 2: 2 messages from round 1 (user + assistant)
        assert len(messages_received_per_call[1]) == 2

        # Round 3: 4 messages from rounds 1 and 2
        assert len(messages_received_per_call[2]) == 4

    @pytest.mark.asyncio
    async def test_round_outputs_in_correct_order(self):
        """Assistant messages in history must be in chronological order."""
        runner = _make_mock_runner()
        soul = Soul(
            id="analyst", kind="soul", name="Analyst", role="Analyst", system_prompt="You analyze."
        )

        call_count = 0

        async def _side_effect(instruction, context, soul, **kwargs):
            nonlocal call_count
            call_count += 1
            return _make_result("t1", "analyst", f"Response_{call_count}")

        runner.execute = AsyncMock(side_effect=_side_effect)

        inner = _make_stateful_linear("analyze", soul, runner)
        loop = LoopBlock(
            block_id="loop",
            inner_block_refs=["analyze"],
            max_rounds=3,
        )
        blocks = {"analyze": inner, "loop": loop}

        state = WorkflowState()
        result_state = await _exec_loop(loop, state, blocks)

        history = result_state.conversation_histories["analyze_analyst"]
        assistant_msgs = [m["content"] for m in history if m["role"] == "assistant"]
        assert assistant_msgs == ["Response_1", "Response_2", "Response_3"]

    @pytest.mark.asyncio
    async def test_works_via_workflow_run(self):
        """Integration through Workflow.run() — the real execution path."""
        runner = _make_mock_runner()
        soul = Soul(
            id="analyst", kind="soul", name="Analyst", role="Analyst", system_prompt="You analyze."
        )

        call_count = 0

        async def _side_effect(instruction, context, soul, **kwargs):
            nonlocal call_count
            call_count += 1
            return _make_result("t1", "analyst", f"Round {call_count}")

        runner.execute = AsyncMock(side_effect=_side_effect)

        inner = _make_stateful_linear("analyze", soul, runner)
        loop = LoopBlock(
            block_id="loop",
            inner_block_refs=["analyze"],
            max_rounds=3,
        )

        wf = Workflow(name="stateful_linear_loop_workflow")
        wf.add_block(inner)
        wf.add_block(loop)
        wf.add_transition("loop", None)
        wf.set_entry("loop")

        state = WorkflowState()
        result_state = await wf.run(state)

        history = result_state.conversation_histories["analyze_analyst"]
        assert len(history) == 6


# ===========================================================================
# 2. Stateful DispatchBlock (3 souls) inside LoopBlock — 2 rounds
# ===========================================================================
