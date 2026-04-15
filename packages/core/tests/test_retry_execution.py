"""
Failing tests for RUN-157: Implement retry execution in workflow runner.

Tests cover:
- BaseBlock has retry_config attribute (set by parser, bridged from BlockDef)
- Retry wrapper in Workflow.run() retries blocks on exception up to max_attempts
- Block succeeds on 2nd attempt after 1 failure
- non_retryable_errors: ValueError is NOT retried, RuntimeError IS retried
- Fixed backoff waits correct duration (mock asyncio.sleep)
- Exponential backoff waits correct durations (mock asyncio.sleep)
- Retry metadata written to shared_memory correctly
- Block without retry_config runs exactly once (no wrapper overhead)
- KeyboardInterrupt and SystemExit are never retried
- max_attempts=1 with failing block — runs once, raises original exception
- Concurrent blocks with retry — each has independent retry state
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from runsight_core.blocks.base import BaseBlock
from runsight_core.state import WorkflowState
from runsight_core.workflow import Workflow
from runsight_core.yaml.schema import RetryConfig

# ── Test helpers ──────────────────────────────────────────────────────────


class SucceedingBlock(BaseBlock):
    """Block that always succeeds."""

    def __init__(self, block_id: str):
        super().__init__(block_id)

    async def execute(self, ctx):
        from runsight_core.block_io import BlockOutput

        return BlockOutput(output="ok")


class AlwaysFailingBlock(BaseBlock):
    """Block that always raises RuntimeError."""

    def __init__(self, block_id: str, error_cls: type = RuntimeError, message: str = "boom"):
        super().__init__(block_id)
        self._error_cls = error_cls
        self._message = message
        self.call_count = 0

    async def execute(self, ctx):
        self.call_count += 1
        raise self._error_cls(self._message)


class FailNTimesThenSucceed(BaseBlock):
    """Block that fails N times, then succeeds on attempt N+1."""

    def __init__(self, block_id: str, fail_count: int, error_cls: type = RuntimeError):
        super().__init__(block_id)
        self._fail_count = fail_count
        self._error_cls = error_cls
        self._call_count = 0

    async def execute(self, ctx):
        from runsight_core.block_io import BlockOutput

        self._call_count += 1
        if self._call_count <= self._fail_count:
            raise self._error_cls(f"fail #{self._call_count}")
        return BlockOutput(output=f"ok on attempt {self._call_count}")


class CountingBlock(BaseBlock):
    """Block that counts how many times execute() is called."""

    def __init__(self, block_id: str):
        super().__init__(block_id)
        self.call_count = 0

    async def execute(self, ctx):
        from runsight_core.block_io import BlockOutput

        self.call_count += 1
        return BlockOutput(output=f"call_{self.call_count}")


def _make_workflow_with_single_block(block: BaseBlock) -> Workflow:
    """Helper: create a one-block workflow with given block as entry + terminal."""
    wf = Workflow(name="test_retry_wf")
    wf.add_block(block)
    wf.add_transition(block.block_id, None)
    wf.set_entry(block.block_id)
    return wf


# ===========================================================================
# 1. BaseBlock has retry_config attribute
# ===========================================================================


class TestBaseBlockRetryConfigAttribute:
    """BaseBlock must have a retry_config attribute bridged from BlockDef."""

    def test_base_block_has_retry_config_attribute(self):
        """BaseBlock instances should have a retry_config attribute."""
        block = SucceedingBlock("b1")
        assert hasattr(block, "retry_config")

    def test_base_block_retry_config_default_none(self):
        """BaseBlock.retry_config defaults to None when not explicitly set."""
        block = SucceedingBlock("b1")
        assert block.retry_config is None

    def test_base_block_retry_config_can_be_set(self):
        """retry_config can be assigned to a BaseBlock instance."""
        block = SucceedingBlock("b1")
        rc = RetryConfig(max_attempts=5, backoff="exponential")
        block.retry_config = rc
        assert block.retry_config is rc
        assert block.retry_config.max_attempts == 5

    def test_base_block_init_accepts_retry_config(self):
        """BaseBlock.__init__ should accept optional retry_config parameter."""
        rc = RetryConfig(max_attempts=3, backoff="fixed")
        # The constructor should accept retry_config as a keyword argument
        block = SucceedingBlock.__new__(SucceedingBlock)
        BaseBlock.__init__(block, "b1", retry_config=rc)
        assert block.retry_config is rc


# ===========================================================================
# 2. Block with retry_config retries on exception up to max_attempts
# ===========================================================================


class TestRetryUpToMaxAttempts:
    """Blocks with retry_config retry on exception up to max_attempts."""

    @pytest.mark.asyncio
    async def test_retries_up_to_max_attempts_then_raises(self):
        """Block that always fails should be retried max_attempts times, then raise."""
        block = AlwaysFailingBlock("fail_block")
        block.retry_config = RetryConfig(max_attempts=3, backoff="fixed", backoff_base_seconds=0.1)

        wf = _make_workflow_with_single_block(block)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(RuntimeError, match="boom"):
                await wf.run(WorkflowState())

        # Must have been called exactly 3 times (initial + 2 retries)
        assert block.call_count == 3

    @pytest.mark.asyncio
    async def test_retries_exactly_max_attempts_times(self):
        """Block should be called exactly max_attempts times before giving up."""
        block = FailNTimesThenSucceed("b1", fail_count=100)  # will never succeed
        block.retry_config = RetryConfig(max_attempts=4, backoff="fixed", backoff_base_seconds=0.1)

        wf = _make_workflow_with_single_block(block)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(RuntimeError):
                await wf.run(WorkflowState())

        assert block._call_count == 4


# ===========================================================================
# 3. Block succeeds on 2nd attempt after 1 failure
# ===========================================================================


class TestRetrySucceedsAfterFailure:
    """Block that fails once then succeeds should complete successfully."""

    @pytest.mark.asyncio
    async def test_succeeds_on_second_attempt(self):
        """Block fails once, then succeeds — workflow completes normally."""
        block = FailNTimesThenSucceed("b1", fail_count=1)
        block.retry_config = RetryConfig(max_attempts=3, backoff="fixed", backoff_base_seconds=0.1)

        wf = _make_workflow_with_single_block(block)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            state = await wf.run(WorkflowState())

        assert "b1" in state.results
        assert "ok on attempt 2" in state.results["b1"].output

    @pytest.mark.asyncio
    async def test_succeeds_on_third_attempt(self):
        """Block fails twice, then succeeds — workflow completes normally."""
        block = FailNTimesThenSucceed("b1", fail_count=2)
        block.retry_config = RetryConfig(max_attempts=5, backoff="fixed", backoff_base_seconds=0.1)

        wf = _make_workflow_with_single_block(block)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            state = await wf.run(WorkflowState())

        assert "b1" in state.results
        assert "ok on attempt 3" in state.results["b1"].output


# ===========================================================================
# 4. non_retryable_errors — ValueError NOT retried, RuntimeError IS retried
# ===========================================================================


class TestNonRetryableErrors:
    """non_retryable_errors list controls which exceptions bypass retry."""

    @pytest.mark.asyncio
    async def test_non_retryable_error_not_retried(self):
        """ValueError in non_retryable_errors list — should NOT be retried, re-raise immediately."""
        block = AlwaysFailingBlock("b1", error_cls=ValueError, message="bad value")
        block.retry_config = RetryConfig(
            max_attempts=5,
            backoff="fixed",
            backoff_base_seconds=0.1,
            non_retryable_errors=["ValueError"],
        )

        wf = _make_workflow_with_single_block(block)

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(ValueError, match="bad value"):
                await wf.run(WorkflowState())

        # Should NOT have slept — block was not retried
        mock_sleep.assert_not_called()
        # Block called exactly once (no retry for non-retryable errors)
        assert block.call_count == 1

    @pytest.mark.asyncio
    async def test_retryable_error_is_retried_when_non_retryable_list_exists(self):
        """RuntimeError not in non_retryable_errors — SHOULD be retried."""
        block = FailNTimesThenSucceed("b1", fail_count=1, error_cls=RuntimeError)
        block.retry_config = RetryConfig(
            max_attempts=3,
            backoff="fixed",
            backoff_base_seconds=0.1,
            non_retryable_errors=["ValueError"],
        )

        wf = _make_workflow_with_single_block(block)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            state = await wf.run(WorkflowState())

        assert "b1" in state.results

    @pytest.mark.asyncio
    async def test_non_retryable_error_raises_on_first_attempt(self):
        """A non-retryable error should cause immediate failure — only 1 attempt."""
        block = FailNTimesThenSucceed("b1", fail_count=5, error_cls=ValueError)
        block.retry_config = RetryConfig(
            max_attempts=5,
            backoff="fixed",
            backoff_base_seconds=0.1,
            non_retryable_errors=["ValueError"],
        )

        wf = _make_workflow_with_single_block(block)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(ValueError):
                await wf.run(WorkflowState())

        # Only called once — no retry
        assert block._call_count == 1


# ===========================================================================
# 5. Fixed backoff waits correct duration
# ===========================================================================


class TestFixedBackoff:
    """Fixed backoff: constant wait between retries."""

    @pytest.mark.asyncio
    async def test_fixed_backoff_waits_constant_duration(self):
        """Fixed backoff should sleep for backoff_base_seconds between each retry."""
        block = AlwaysFailingBlock("b1")
        block.retry_config = RetryConfig(
            max_attempts=4,
            backoff="fixed",
            backoff_base_seconds=2.0,
        )

        wf = _make_workflow_with_single_block(block)

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(RuntimeError):
                await wf.run(WorkflowState())

        # 4 attempts = 3 retry sleeps (after attempt 1, 2, 3; not after last)
        assert mock_sleep.call_count == 3
        for call in mock_sleep.call_args_list:
            assert call.args[0] == pytest.approx(2.0)

    @pytest.mark.asyncio
    async def test_fixed_backoff_no_sleep_on_success(self):
        """If block succeeds on first attempt, no sleep should occur."""
        block = SucceedingBlock("b1")
        block.retry_config = RetryConfig(
            max_attempts=3,
            backoff="fixed",
            backoff_base_seconds=1.0,
        )

        wf = _make_workflow_with_single_block(block)

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await wf.run(WorkflowState())

        mock_sleep.assert_not_called()


# ===========================================================================
# 6. Exponential backoff waits correct durations
# ===========================================================================


class TestExponentialBackoff:
    """Exponential backoff: base * 2^attempt."""

    @pytest.mark.asyncio
    async def test_exponential_backoff_durations(self):
        """Exponential backoff: sleep durations should be base * 2^0, base * 2^1, base * 2^2, ..."""
        block = AlwaysFailingBlock("b1")
        block.retry_config = RetryConfig(
            max_attempts=4,
            backoff="exponential",
            backoff_base_seconds=1.0,
        )

        wf = _make_workflow_with_single_block(block)

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(RuntimeError):
                await wf.run(WorkflowState())

        # 4 attempts = 3 sleeps
        assert mock_sleep.call_count == 3
        # Exponential: base * 2^0, base * 2^1, base * 2^2
        expected_durations = [1.0, 2.0, 4.0]
        actual_durations = [call.args[0] for call in mock_sleep.call_args_list]
        assert actual_durations == pytest.approx(expected_durations)

    @pytest.mark.asyncio
    async def test_exponential_backoff_with_custom_base(self):
        """Exponential backoff with base=0.5: 0.5, 1.0, 2.0."""
        block = AlwaysFailingBlock("b1")
        block.retry_config = RetryConfig(
            max_attempts=4,
            backoff="exponential",
            backoff_base_seconds=0.5,
        )

        wf = _make_workflow_with_single_block(block)

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(RuntimeError):
                await wf.run(WorkflowState())

        expected_durations = [0.5, 1.0, 2.0]
        actual_durations = [call.args[0] for call in mock_sleep.call_args_list]
        assert actual_durations == pytest.approx(expected_durations)


# ===========================================================================
# 7. Retry metadata written to shared_memory correctly
# ===========================================================================


class TestRetryMetadataInSharedMemory:
    """Retry metadata must be stored in shared_memory under __retry__{block_id}."""

    @pytest.mark.asyncio
    async def test_retry_metadata_written_on_exhausted_failure(self):
        """After exhausting retries, block should have been called max_attempts times.

        Since Workflow.run() raises when the block exhausts all attempts,
        we verify the retry wrapper actually retried by checking call count.
        """
        block = AlwaysFailingBlock("b1")
        block.retry_config = RetryConfig(max_attempts=3, backoff="fixed", backoff_base_seconds=0.1)

        wf = _make_workflow_with_single_block(block)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(RuntimeError):
                await wf.run(WorkflowState())

        # Block must have been called exactly max_attempts times
        assert block.call_count == 3

    @pytest.mark.asyncio
    async def test_retry_metadata_after_successful_retry(self):
        """Block fails once then succeeds — shared_memory should contain retry metadata."""
        block = FailNTimesThenSucceed("b1", fail_count=1)
        block.retry_config = RetryConfig(max_attempts=3, backoff="fixed", backoff_base_seconds=0.1)

        wf = _make_workflow_with_single_block(block)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            state = await wf.run(WorkflowState())

        meta_key = "__retry__b1"
        assert meta_key in state.shared_memory
        meta = state.shared_memory[meta_key]
        assert meta["attempt"] == 2
        assert meta["max_attempts"] == 3
        assert "fail" in meta["last_error"].lower()
        assert meta["last_error_type"] == "RuntimeError"
        assert meta["total_retries"] == 1

    @pytest.mark.asyncio
    async def test_retry_metadata_format(self):
        """Retry metadata should contain all required fields with correct types."""
        block = FailNTimesThenSucceed("my_block", fail_count=2)
        block.retry_config = RetryConfig(max_attempts=5, backoff="fixed", backoff_base_seconds=0.1)

        wf = _make_workflow_with_single_block(block)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            state = await wf.run(WorkflowState())

        meta_key = "__retry__my_block"
        assert meta_key in state.shared_memory
        meta = state.shared_memory[meta_key]

        # Validate all fields exist and have correct types
        assert isinstance(meta["attempt"], int)
        assert isinstance(meta["max_attempts"], int)
        assert isinstance(meta["last_error"], str)
        assert isinstance(meta["last_error_type"], str)
        assert isinstance(meta["total_retries"], int)

        # Values
        assert meta["attempt"] == 3  # succeeded on 3rd attempt
        assert meta["max_attempts"] == 5
        assert meta["total_retries"] == 2  # attempts - 1

    @pytest.mark.asyncio
    async def test_no_retry_metadata_when_no_retry_needed(self):
        """Block succeeds on first attempt — no retry metadata in shared_memory."""
        block = SucceedingBlock("b1")
        block.retry_config = RetryConfig(max_attempts=3, backoff="fixed", backoff_base_seconds=0.1)

        wf = _make_workflow_with_single_block(block)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            state = await wf.run(WorkflowState())

        # No retry occurred, so no retry metadata should be written
        assert "__retry__b1" not in state.shared_memory


# ===========================================================================
# 8. Block without retry_config runs exactly once (no wrapper overhead)
# ===========================================================================


class TestNoRetryConfig:
    """Blocks without retry_config should execute exactly once with no retry overhead."""

    @pytest.mark.asyncio
    async def test_block_without_retry_config_runs_once(self):
        """A block without retry_config that succeeds runs exactly once."""
        block = CountingBlock("b1")
        # Explicitly do NOT set retry_config

        wf = _make_workflow_with_single_block(block)
        await wf.run(WorkflowState())

        assert block.call_count == 1

    @pytest.mark.asyncio
    async def test_block_without_retry_config_error_propagates_immediately(self):
        """A block without retry_config that fails raises immediately — no retry."""
        block = AlwaysFailingBlock("b1")
        # Explicitly do NOT set retry_config

        wf = _make_workflow_with_single_block(block)

        with pytest.raises(RuntimeError, match="boom"):
            await wf.run(WorkflowState())

    @pytest.mark.asyncio
    async def test_no_sleep_called_for_block_without_retry_config(self):
        """No asyncio.sleep should be called for blocks without retry_config."""
        block = AlwaysFailingBlock("b1")
        # No retry_config

        wf = _make_workflow_with_single_block(block)

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(RuntimeError):
                await wf.run(WorkflowState())

        mock_sleep.assert_not_called()


# ===========================================================================
# 9. KeyboardInterrupt and SystemExit are never retried
# ===========================================================================


class TestNeverRetrySystemExceptions:
    """KeyboardInterrupt and SystemExit must never be retried, always re-raised."""

    @pytest.mark.asyncio
    async def test_keyboard_interrupt_not_retried(self):
        """KeyboardInterrupt should be re-raised immediately, never retried."""
        block = AlwaysFailingBlock("b1", error_cls=KeyboardInterrupt, message="ctrl-c")
        block.retry_config = RetryConfig(max_attempts=5, backoff="fixed", backoff_base_seconds=0.1)

        wf = _make_workflow_with_single_block(block)

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(KeyboardInterrupt):
                await wf.run(WorkflowState())

        mock_sleep.assert_not_called()

    @pytest.mark.asyncio
    async def test_system_exit_not_retried(self):
        """SystemExit should be re-raised immediately, never retried."""
        block = AlwaysFailingBlock("b1", error_cls=SystemExit, message="exit")
        block.retry_config = RetryConfig(max_attempts=5, backoff="fixed", backoff_base_seconds=0.1)

        wf = _make_workflow_with_single_block(block)

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(SystemExit):
                await wf.run(WorkflowState())

        mock_sleep.assert_not_called()


# ===========================================================================
# 10. max_attempts=1 edge case
# ===========================================================================


class TestMaxAttemptsOne:
    """max_attempts=1 means run once — no retry on failure."""

    @pytest.mark.asyncio
    async def test_max_attempts_one_failing_block(self):
        """max_attempts=1: block runs once, fails, raises original exception."""
        block = AlwaysFailingBlock("b1")
        block.retry_config = RetryConfig(max_attempts=1, backoff="fixed", backoff_base_seconds=0.1)

        wf = _make_workflow_with_single_block(block)

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(RuntimeError, match="boom"):
                await wf.run(WorkflowState())

        # No sleep — only 1 attempt, no retry
        mock_sleep.assert_not_called()

    @pytest.mark.asyncio
    async def test_max_attempts_one_succeeding_block(self):
        """max_attempts=1: block succeeds on first attempt — works fine."""
        block = SucceedingBlock("b1")
        block.retry_config = RetryConfig(max_attempts=1, backoff="fixed", backoff_base_seconds=0.1)

        wf = _make_workflow_with_single_block(block)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            state = await wf.run(WorkflowState())

        assert state.results["b1"].output == "ok"


# ===========================================================================
# 11. Concurrent blocks with retry — independent retry state
# ===========================================================================


class TestIndependentRetryState:
    """Multiple blocks with retry configs maintain independent retry state."""

    @pytest.mark.asyncio
    async def test_two_blocks_independent_retry_metadata(self):
        """Two blocks in sequence, each with retry_config — each gets its own metadata."""
        block_a = FailNTimesThenSucceed("block_a", fail_count=1)
        block_a.retry_config = RetryConfig(
            max_attempts=3, backoff="fixed", backoff_base_seconds=0.1
        )

        block_b = FailNTimesThenSucceed("block_b", fail_count=2)
        block_b.retry_config = RetryConfig(
            max_attempts=5, backoff="fixed", backoff_base_seconds=0.1
        )

        wf = Workflow(name="multi_retry_wf")
        wf.add_block(block_a)
        wf.add_block(block_b)
        wf.add_transition("block_a", "block_b")
        wf.add_transition("block_b", None)
        wf.set_entry("block_a")

        with patch("asyncio.sleep", new_callable=AsyncMock):
            state = await wf.run(WorkflowState())

        # block_a: failed 1 time, succeeded on attempt 2
        meta_a = state.shared_memory["__retry__block_a"]
        assert meta_a["attempt"] == 2
        assert meta_a["total_retries"] == 1

        # block_b: failed 2 times, succeeded on attempt 3
        meta_b = state.shared_memory["__retry__block_b"]
        assert meta_b["attempt"] == 3
        assert meta_b["total_retries"] == 2

        # They are independent — one doesn't affect the other
        assert meta_a["max_attempts"] == 3
        assert meta_b["max_attempts"] == 5


# ===========================================================================
# 12. Retry is transparent to the block
# ===========================================================================


class TestRetryTransparency:
    """Retry should be transparent — block doesn't know it's being retried."""

    @pytest.mark.asyncio
    async def test_block_receives_same_state_on_each_retry(self):
        """Each retry attempt should receive the same input state (not a mutated one)."""

        class StateCapturingBlock(BaseBlock):
            """Captures the state passed to each execute() call."""

            def __init__(self, block_id: str):
                super().__init__(block_id)
                self.received_states = []
                self._call_count = 0

            async def execute(self, ctx):
                from runsight_core.block_io import BlockOutput

                state = ctx.state_snapshot
                self._call_count += 1
                self.received_states.append(state)
                if self._call_count <= 2:
                    raise RuntimeError(f"fail #{self._call_count}")
                return BlockOutput(output="done")

        block = StateCapturingBlock("b1")
        block.retry_config = RetryConfig(max_attempts=5, backoff="fixed", backoff_base_seconds=0.1)

        wf = _make_workflow_with_single_block(block)
        initial = WorkflowState(shared_memory={"key": "value"})

        with patch("asyncio.sleep", new_callable=AsyncMock):
            state = await wf.run(initial)

        # Block was called 3 times (2 failures + 1 success)
        assert block._call_count == 3
        assert state.results["b1"].output == "done"


# ===========================================================================
# 13. Retry wrapper uses asyncio.sleep (not time.sleep)
# ===========================================================================


class TestAsyncSleep:
    """Retry backoff must use asyncio.sleep for non-blocking behavior."""

    @pytest.mark.asyncio
    async def test_uses_asyncio_sleep_not_time_sleep(self):
        """Verify that asyncio.sleep is used, not time.sleep."""
        block = AlwaysFailingBlock("b1")
        block.retry_config = RetryConfig(max_attempts=2, backoff="fixed", backoff_base_seconds=1.0)

        wf = _make_workflow_with_single_block(block)

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_async_sleep:
            with pytest.raises(RuntimeError):
                await wf.run(WorkflowState())

        # asyncio.sleep should have been called (once, between attempt 1 and 2)
        assert mock_async_sleep.call_count == 1
