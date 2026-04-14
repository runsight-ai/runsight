"""
RUN-193: Validate retry + stateful interaction — no state corruption.

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
from runsight_core.primitives import Soul, Task
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
    runner.execute_task = AsyncMock()
    runner._build_prompt = MagicMock(side_effect=lambda task: task.instruction)
    return runner


@pytest.fixture
def soul():
    return Soul(
        id="agent_1", kind="soul", name="Analyst", role="Analyst", system_prompt="Analyze things."
    )


@pytest.fixture
def task():
    return Task(id="t1", instruction="Summarize the data")


# ── Helpers ───────────────────────────────────────────────────────────────


def _make_stateful_linear_block(block_id, soul, runner):
    """Create a stateful LinearBlock with retry config."""
    block = LinearBlock(block_id, soul, runner)
    block.stateful = True
    return block


def _make_workflow_with_single_block(block: BaseBlock) -> Workflow:
    """Create a one-block workflow."""
    wf = Workflow(name="test_retry_stateful_wf")
    wf.add_block(block)
    wf.add_transition(block.block_id, None)
    wf.set_entry(block.block_id)
    return wf


# ===========================================================================
# 1. Failed attempt does NOT pollute conversation_histories
# ===========================================================================


class TestFailedAttemptDoesNotPolluteHistory:
    """When a stateful block fails on attempt 1 and succeeds on attempt 2,
    the resulting conversation_histories must contain ONLY the successful
    attempt's messages — NOT any messages from the failed attempt."""

    @pytest.mark.asyncio
    async def test_fail_then_succeed_history_contains_only_success_messages(
        self, mock_runner, soul, task
    ):
        """Stateful block fails on attempt 1, succeeds on attempt 2.
        History should have exactly 1 user+assistant pair from the success."""
        call_count = 0

        async def side_effect(t, s, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("LLM timeout on attempt 1")
            return ExecutionResult(
                task_id="t1",
                soul_id="agent_1",
                output="Success on attempt 2.",
            )

        mock_runner.execute_task = AsyncMock(side_effect=side_effect)

        block = _make_stateful_linear_block("analyze", soul, mock_runner)
        block.retry_config = RetryConfig(max_attempts=3, backoff="fixed", backoff_base_seconds=0.1)

        wf = _make_workflow_with_single_block(block)
        initial_state = WorkflowState(current_task=task)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result_state = await wf.run(initial_state)

        # History must exist
        history_key = "analyze_agent_1"
        assert history_key in result_state.conversation_histories

        history = result_state.conversation_histories[history_key]

        # Only the successful attempt's user+assistant pair
        assert len(history) == 2, (
            f"Expected 2 messages (1 user + 1 assistant from success), got {len(history)}: {history}"
        )
        assert history[0]["role"] == "user"
        assert history[1]["role"] == "assistant"
        assert history[1]["content"] == "Success on attempt 2."

    @pytest.mark.asyncio
    async def test_fail_twice_then_succeed_no_stale_history(self, mock_runner, soul, task):
        """Fails on attempts 1 and 2, succeeds on attempt 3.
        History should have exactly 1 pair from the final success."""
        call_count = 0

        async def side_effect(t, s, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise RuntimeError(f"fail #{call_count}")
            return ExecutionResult(
                task_id="t1",
                soul_id="agent_1",
                output="Third time is the charm.",
            )

        mock_runner.execute_task = AsyncMock(side_effect=side_effect)

        block = _make_stateful_linear_block("analyze", soul, mock_runner)
        block.retry_config = RetryConfig(max_attempts=5, backoff="fixed", backoff_base_seconds=0.1)

        wf = _make_workflow_with_single_block(block)
        initial_state = WorkflowState(current_task=task)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result_state = await wf.run(initial_state)

        history = result_state.conversation_histories["analyze_agent_1"]
        assert len(history) == 2
        assert history[1]["content"] == "Third time is the charm."


# ===========================================================================
# 2. Successful retry creates clean history entry
# ===========================================================================


class TestSuccessfulRetryCreatesCleanHistory:
    """After a retry succeeds, the resulting history should be indistinguishable
    from a first-attempt success — clean user+assistant pair, no corruption."""

    @pytest.mark.asyncio
    async def test_retry_success_history_matches_first_attempt_format(
        self, mock_runner, soul, task
    ):
        """The history from a retried-then-succeeded block should look exactly
        like what a first-attempt success would produce."""
        call_count = 0

        async def side_effect(t, s, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("transient failure")
            return ExecutionResult(
                task_id="t1",
                soul_id="agent_1",
                output="Retry succeeded.",
            )

        mock_runner.execute_task = AsyncMock(side_effect=side_effect)

        block = _make_stateful_linear_block("analyze", soul, mock_runner)
        block.retry_config = RetryConfig(max_attempts=3, backoff="fixed", backoff_base_seconds=0.1)

        wf = _make_workflow_with_single_block(block)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result_state = await wf.run(WorkflowState(current_task=task))

        history = result_state.conversation_histories["analyze_agent_1"]

        # Should have user + assistant, same as a first-attempt success
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[0]["content"] == task.instruction  # _build_prompt returns instruction
        assert history[1]["role"] == "assistant"
        assert history[1]["content"] == "Retry succeeded."

    @pytest.mark.asyncio
    async def test_retry_success_no_system_messages_in_history(self, mock_runner, soul, task):
        """No system messages should leak into conversation_histories after retry."""
        call_count = 0

        async def side_effect(t, s, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("boom")
            return ExecutionResult(task_id="t1", soul_id="agent_1", output="ok")

        mock_runner.execute_task = AsyncMock(side_effect=side_effect)

        block = _make_stateful_linear_block("analyze", soul, mock_runner)
        block.retry_config = RetryConfig(max_attempts=3, backoff="fixed", backoff_base_seconds=0.1)

        wf = _make_workflow_with_single_block(block)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result_state = await wf.run(WorkflowState(current_task=task))

        history = result_state.conversation_histories["analyze_agent_1"]
        for msg in history:
            assert msg["role"] in ("user", "assistant"), (
                f"Found unexpected role '{msg['role']}' in conversation_histories"
            )


# ===========================================================================
# 3. Original state not mutated across retry attempts
# ===========================================================================


class TestOriginalStateNotMutated:
    """Each retry attempt receives the same original pre-execution state.
    The original state's conversation_histories must never be mutated."""

    @pytest.mark.asyncio
    async def test_input_state_conversation_histories_unchanged_after_retry(
        self, mock_runner, soul, task
    ):
        """The initial state's conversation_histories must remain empty
        after a retry that eventually succeeds."""
        call_count = 0

        async def side_effect(t, s, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("transient")
            return ExecutionResult(task_id="t1", soul_id="agent_1", output="done")

        mock_runner.execute_task = AsyncMock(side_effect=side_effect)

        block = _make_stateful_linear_block("analyze", soul, mock_runner)
        block.retry_config = RetryConfig(max_attempts=3, backoff="fixed", backoff_base_seconds=0.1)

        wf = _make_workflow_with_single_block(block)
        initial_state = WorkflowState(current_task=task)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result_state = await wf.run(initial_state)

        # Original state must be unchanged
        assert initial_state.conversation_histories == {}
        # Result state must have the history
        assert "analyze_agent_1" in result_state.conversation_histories

    @pytest.mark.asyncio
    async def test_existing_history_preserved_after_retry_of_different_block(
        self, mock_runner, soul, task
    ):
        """If state already has conversation_histories from a prior block,
        those must survive through a retry of a later block."""
        call_count = 0

        async def side_effect(t, s, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("transient")
            return ExecutionResult(task_id="t1", soul_id="agent_1", output="done")

        mock_runner.execute_task = AsyncMock(side_effect=side_effect)

        block = _make_stateful_linear_block("step_2", soul, mock_runner)
        block.retry_config = RetryConfig(max_attempts=3, backoff="fixed", backoff_base_seconds=0.1)

        wf = _make_workflow_with_single_block(block)

        prior_history = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ]
        initial_state = WorkflowState(
            current_task=task,
            conversation_histories={"step_1_agent_1": prior_history},
        )

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result_state = await wf.run(initial_state)

        # Prior block's history preserved
        assert result_state.conversation_histories["step_1_agent_1"] == prior_history
        # New block's history created
        assert "step_2_agent_1" in result_state.conversation_histories


# ===========================================================================
# 4. Retry passes empty history to each attempt (no accumulation)
# ===========================================================================


class TestRetryPassesSameHistoryToEachAttempt:
    """Because _execute_with_retry always passes the same `state` to execute_fn,
    each retry of a stateful block gets the same conversation_histories snapshot
    as the first attempt. Failed attempt's additions never accumulate."""

    @pytest.mark.asyncio
    async def test_runner_receives_empty_history_on_every_attempt(self, mock_runner, soul, task):
        """On a fresh state, every retry attempt should pass empty messages to runner."""
        received_messages = []
        call_count = 0

        async def side_effect(t, s, **kwargs):
            nonlocal call_count
            call_count += 1
            received_messages.append(kwargs.get("messages"))
            if call_count <= 2:
                raise RuntimeError(f"fail #{call_count}")
            return ExecutionResult(task_id="t1", soul_id="agent_1", output="success")

        mock_runner.execute_task = AsyncMock(side_effect=side_effect)

        block = _make_stateful_linear_block("analyze", soul, mock_runner)
        block.retry_config = RetryConfig(max_attempts=5, backoff="fixed", backoff_base_seconds=0.1)

        wf = _make_workflow_with_single_block(block)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            await wf.run(WorkflowState(current_task=task))

        # All 3 attempts should have received the same (empty) history
        assert len(received_messages) == 3
        for i, msgs in enumerate(received_messages):
            assert msgs == [], (
                f"Attempt {i + 1} received non-empty messages={msgs}; "
                "expected empty because state is the same pre-execution snapshot"
            )


# ===========================================================================
# 5. Stateful block inside LoopBlock: history accumulates across rounds
#    AND retry at the workflow level replays from pre-loop state
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
    async def test_stateful_history_accumulates_across_loop_rounds(self, mock_runner, soul, task):
        """LoopBlock with 2 rounds: round 1 adds 1 pair, round 2 adds 1 pair.
        Final history = 4 messages (2 pairs)."""
        call_count = 0

        async def side_effect(t, s, **kwargs):
            nonlocal call_count
            call_count += 1
            return ExecutionResult(
                task_id="t1",
                soul_id="agent_1",
                output=f"Output from round {call_count}.",
            )

        mock_runner.execute_task = AsyncMock(side_effect=side_effect)

        inner_block = _make_stateful_linear_block("inner", soul, mock_runner)

        loop = LoopBlock("loop", inner_block_refs=["inner"], max_rounds=2)

        wf = Workflow(name="loop_stateful_wf")
        wf.add_block(loop)
        wf.add_block(inner_block)
        wf.add_transition("loop", None)
        wf.set_entry("loop")

        result_state = await wf.run(WorkflowState(current_task=task))

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
    async def test_loop_with_retry_replays_from_pre_loop_state(self, mock_runner, soul, task):
        """LoopBlock with retry_config: if the loop fails on round 2,
        the retry replays the entire loop from scratch (pre-loop state).
        So round 1's history from the failed attempt is discarded."""
        call_count = 0

        async def side_effect(t, s, **kwargs):
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

        mock_runner.execute_task = AsyncMock(side_effect=side_effect)

        inner_block = _make_stateful_linear_block("inner", soul, mock_runner)
        # No retry on inner block — retry is on the LoopBlock itself
        loop = LoopBlock("loop", inner_block_refs=["inner"], max_rounds=2)
        loop.retry_config = RetryConfig(max_attempts=3, backoff="fixed", backoff_base_seconds=0.1)

        wf = Workflow(name="loop_retry_wf")
        wf.add_block(loop)
        wf.add_block(inner_block)
        wf.add_transition("loop", None)
        wf.set_entry("loop")

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result_state = await wf.run(WorkflowState(current_task=task))

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
    async def test_loop_retry_no_history_duplication(self, mock_runner, soul, task):
        """After a loop retry, history should have exactly 2 user messages
        (one per round in the successful attempt), not 3 or 4."""
        call_count = 0

        async def side_effect(t, s, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise RuntimeError("fail")
            return ExecutionResult(
                task_id="t1",
                soul_id="agent_1",
                output=f"response_{call_count}",
            )

        mock_runner.execute_task = AsyncMock(side_effect=side_effect)

        inner_block = _make_stateful_linear_block("inner", soul, mock_runner)
        loop = LoopBlock("loop", inner_block_refs=["inner"], max_rounds=2)
        loop.retry_config = RetryConfig(max_attempts=3, backoff="fixed", backoff_base_seconds=0.1)

        wf = Workflow(name="loop_retry_wf")
        wf.add_block(loop)
        wf.add_block(inner_block)
        wf.add_transition("loop", None)
        wf.set_entry("loop")

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result_state = await wf.run(WorkflowState(current_task=task))

        history = result_state.conversation_histories["inner_agent_1"]

        # Exactly 2 user messages (1 per round in the successful retry)
        user_messages = [m for m in history if m["role"] == "user"]
        assert len(user_messages) == 2, (
            f"Expected 2 user messages (1 per round), got {len(user_messages)}"
        )


# ===========================================================================
# 6. All retries exhausted on stateful block — no history pollution
# ===========================================================================


class TestAllRetriesExhaustedNoHistoryPollution:
    """When a stateful block exhausts all retries and raises,
    conversation_histories should remain as they were before the block ran."""

    @pytest.mark.asyncio
    async def test_exhausted_retries_leave_history_unchanged(self, mock_runner, soul, task):
        """All retry attempts fail -> exception raised,
        history should not be modified."""
        mock_runner.execute_task = AsyncMock(side_effect=RuntimeError("always fails"))

        block = _make_stateful_linear_block("analyze", soul, mock_runner)
        block.retry_config = RetryConfig(max_attempts=3, backoff="fixed", backoff_base_seconds=0.1)

        wf = _make_workflow_with_single_block(block)
        initial_state = WorkflowState(current_task=task)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(RuntimeError, match="always fails"):
                await wf.run(initial_state)

        # State was never returned (exception raised), so we verify
        # the initial state is untouched
        assert initial_state.conversation_histories == {}

    @pytest.mark.asyncio
    async def test_exhausted_retries_preserve_prior_history(self, mock_runner, soul, task):
        """If prior history exists from other blocks, exhausted retries
        should not corrupt it (the state is never returned)."""
        mock_runner.execute_task = AsyncMock(side_effect=RuntimeError("always fails"))

        block = _make_stateful_linear_block("step_2", soul, mock_runner)
        block.retry_config = RetryConfig(max_attempts=3, backoff="fixed", backoff_base_seconds=0.1)

        wf = _make_workflow_with_single_block(block)

        prior_history = [
            {"role": "user", "content": "q"},
            {"role": "assistant", "content": "a"},
        ]
        initial_state = WorkflowState(
            current_task=task,
            conversation_histories={"step_1_agent_1": prior_history},
        )

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(RuntimeError, match="always fails"):
                await wf.run(initial_state)

        # Prior history still intact on the initial state
        assert initial_state.conversation_histories["step_1_agent_1"] == prior_history


# ===========================================================================
# 7. Retry metadata coexists with conversation_histories
# ===========================================================================


class TestRetryMetadataCoexistsWithHistory:
    """When a stateful block succeeds after retry, both retry metadata
    in shared_memory AND conversation_histories should be correctly set."""

    @pytest.mark.asyncio
    async def test_retry_metadata_and_history_both_present(self, mock_runner, soul, task):
        """After fail-then-succeed, shared_memory has retry metadata AND
        conversation_histories has the history — both correct."""
        call_count = 0

        async def side_effect(t, s, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("transient")
            return ExecutionResult(task_id="t1", soul_id="agent_1", output="recovered")

        mock_runner.execute_task = AsyncMock(side_effect=side_effect)

        block = _make_stateful_linear_block("analyze", soul, mock_runner)
        block.retry_config = RetryConfig(max_attempts=3, backoff="fixed", backoff_base_seconds=0.1)

        wf = _make_workflow_with_single_block(block)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result_state = await wf.run(WorkflowState(current_task=task))

        # Retry metadata in shared_memory
        retry_meta = result_state.shared_memory.get("__retry__analyze")
        assert retry_meta is not None
        assert retry_meta["attempt"] == 2
        assert retry_meta["total_retries"] == 1

        # Conversation history — clean, 1 pair
        history = result_state.conversation_histories["analyze_agent_1"]
        assert len(history) == 2
        assert history[1]["content"] == "recovered"
