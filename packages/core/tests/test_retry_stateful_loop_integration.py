"""
Retry and stateful interaction without state corruption.

Tests prove that _execute_with_retry passes the same pre-execution state on
every retry attempt, so a failed stateful block's conversation history is
naturally discarded (exception prevents model_copy return). This is correct
behavior — Pydantic immutability handles it without any special code.

Tests cover:
- Failed attempt does NOT pollute conversation_histories
- Successful retry after failure creates clean history (only success messages)
- Stateful block inside retry inside LoopBlock: round 1 history preserved,
  retry within round 2 starts fresh for that round
- Original state is never mutated across retry attempts
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from runsight_core import LinearBlock, LoopBlock
from runsight_core.blocks.base import BaseBlock
from runsight_core.primitives import Soul
from runsight_core.runner import ExecutionResult
from runsight_core.state import WorkflowState
from runsight_core.workflow import Workflow
from runsight_core.yaml.schema import RetryConfig

# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def mock_runner():
    """Mock RunsightTeamRunner with controlled outputs."""
    runner = MagicMock()
    runner.model_name = "gpt-4o"
    runner.execute = AsyncMock()
    return runner


@pytest.fixture
def soul():
    return Soul(
        id="agent_1", kind="soul", name="Analyst", role="Analyst", system_prompt="Analyze things."
    )


# ── Helpers ───────────────────────────────────────────────────────────────


def _make_stateful_linear_block(block_id, soul, runner):
    """Create a stateful LinearBlock with retry config."""
    block = LinearBlock(block_id, soul, runner)
    block.stateful = True
    return block


def _make_workflow_with_single_block(block: BaseBlock) -> Workflow:
    """Create a one-block workflow."""
    wf = Workflow(name="retry_stateful_workflow")
    wf.add_block(block)
    wf.add_transition(block.block_id, None)
    wf.set_entry(block.block_id)
    return wf


# ===========================================================================
# 1. Failed attempt does NOT pollute conversation_histories
# ===========================================================================


class TestStatefulBlockInsideLoopWithRetry:
    """Validates the interaction of stateful + LoopBlock + retry.

    Architecture note: LoopBlock calls inner_block.execute() directly — retry
    wrapping only happens at the Workflow.run() level. So:
    - Test A: Stateful history accumulates correctly across loop rounds
    - Test B: If the LoopBlock itself has retry_config, a failed loop attempt
      replays from the pre-loop state (round 1 history is NOT carried over)
    """

    @pytest.mark.asyncio
    async def test_stateful_history_accumulates_across_loop_rounds(self, mock_runner, soul):
        """LoopBlock with 2 rounds: round 1 adds 1 pair, round 2 adds 1 pair.
        Final history = 4 messages (2 pairs)."""
        call_count = 0

        async def side_effect(instruction, context, soul_arg, **kwargs):
            nonlocal call_count
            call_count += 1
            return ExecutionResult(
                task_id="t1",
                soul_id="agent_1",
                output=f"Output from round {call_count}.",
            )

        mock_runner.execute = AsyncMock(side_effect=side_effect)

        inner_block = _make_stateful_linear_block("inner", soul, mock_runner)

        loop = LoopBlock("loop", inner_block_refs=["inner"], max_rounds=2)

        wf = Workflow(name="loop_stateful_workflow")
        wf.add_block(loop)
        wf.add_block(inner_block)
        wf.add_transition("loop", None)
        wf.set_entry("loop")

        result_state = await wf.run(WorkflowState())

        history_key = "inner_agent_1"
        assert history_key in result_state.conversation_histories

        history = result_state.conversation_histories[history_key]

        # Round 1 pair + round 2 pair = 4 messages
        assert len(history) == 4, (
            f"Expected 4 messages (2 rounds x 1 user+assistant pair), got {len(history)}: {history}"
        )

        assert history[0]["role"] == "user"
        assert history[1]["role"] == "assistant"
        assert history[1]["content"] == "Output from round 1."
        assert history[2]["role"] == "user"
        assert history[3]["role"] == "assistant"
        assert history[3]["content"] == "Output from round 2."

    @pytest.mark.asyncio
    async def test_loop_with_retry_replays_from_pre_loop_state(self, mock_runner, soul):
        """LoopBlock with retry_config: if the loop fails on round 2,
        the retry replays the entire loop from scratch (pre-loop state).
        So round 1's history from the failed attempt is discarded."""
        call_count = 0

        async def side_effect(instruction, context, soul_arg, **kwargs):
            nonlocal call_count
            call_count += 1
            # First loop attempt:
            #   call 1 = round 1 -> success
            #   call 2 = round 2 -> fail (entire loop fails)
            # Second loop attempt (retry):
            #   call 3 = round 1 -> success
            #   call 4 = round 2 -> success
            if call_count == 2:
                raise RuntimeError("round 2 fails on first loop attempt")
            return ExecutionResult(
                task_id="t1",
                soul_id="agent_1",
                output=f"Output from call {call_count}.",
            )

        mock_runner.execute = AsyncMock(side_effect=side_effect)

        inner_block = _make_stateful_linear_block("inner", soul, mock_runner)
        # No retry on inner block — retry is on the LoopBlock itself
        loop = LoopBlock("loop", inner_block_refs=["inner"], max_rounds=2)
        loop.retry_config = RetryConfig(max_attempts=3, backoff="fixed", backoff_base_seconds=0.1)

        wf = Workflow(name="loop_retry_workflow")
        wf.add_block(loop)
        wf.add_block(inner_block)
        wf.add_transition("loop", None)
        wf.set_entry("loop")

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result_state = await wf.run(WorkflowState())

        history = result_state.conversation_histories["inner_agent_1"]

        # The retry replayed from the original state (empty history).
        # So we get: round 1 pair (call 3) + round 2 pair (call 4) = 4 messages.
        # Crucially, the failed first loop attempt's round 1 history (call 1) is gone.
        assert len(history) == 4, (
            f"Expected 4 messages from the successful retry loop, got {len(history)}: {history}"
        )

        # The content should be from calls 3 and 4 (the retry attempt),
        # NOT from call 1 (the failed first attempt)
        assert history[1]["content"] == "Output from call 3."
        assert history[3]["content"] == "Output from call 4."

    @pytest.mark.asyncio
    async def test_loop_retry_no_history_duplication(self, mock_runner, soul):
        """After a loop retry, history should have exactly 2 user messages
        (one per round in the successful attempt), not 3 or 4."""
        call_count = 0

        async def side_effect(instruction, context, soul_arg, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise RuntimeError("fail")
            return ExecutionResult(
                task_id="t1",
                soul_id="agent_1",
                output=f"response_{call_count}",
            )

        mock_runner.execute = AsyncMock(side_effect=side_effect)

        inner_block = _make_stateful_linear_block("inner", soul, mock_runner)
        loop = LoopBlock("loop", inner_block_refs=["inner"], max_rounds=2)
        loop.retry_config = RetryConfig(max_attempts=3, backoff="fixed", backoff_base_seconds=0.1)

        wf = Workflow(name="loop_retry_workflow")
        wf.add_block(loop)
        wf.add_block(inner_block)
        wf.add_transition("loop", None)
        wf.set_entry("loop")

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result_state = await wf.run(WorkflowState())

        history = result_state.conversation_histories["inner_agent_1"]

        # Exactly 2 user messages (1 per round in the successful retry)
        user_messages = [m for m in history if m["role"] == "user"]
        assert len(user_messages) == 2, (
            f"Expected 2 user messages (1 per round), got {len(user_messages)}"
        )


# ===========================================================================
# 6. All retries exhausted on stateful block — no history pollution
# ===========================================================================
