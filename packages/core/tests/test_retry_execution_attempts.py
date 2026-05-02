"""Workflow retry execution behavior coverage.

Tests cover:
- BaseBlock has retry_config attribute (set by parser, bridged from BlockDef)
- Retry wrapper in Workflow.run() retries blocks on exception up to max_attempts
- Block succeeds on 2nd attempt after 1 failure
- non_retryable_errors: ValueError bypasses retry, RuntimeError still retries
- Fixed backoff waits correct duration (mock asyncio.sleep)
- Exponential backoff waits correct durations (mock asyncio.sleep)
- Retry metadata written to shared_memory correctly
- Block without retry_config runs exactly once (no wrapper overhead)
- KeyboardInterrupt and SystemExit are never retried
- max_attempts=1 with failing block runs once and raises original exception
- Multiple retrying blocks keep independent retry state
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from runsight_core.blocks.base import BaseBlock
from runsight_core.state import WorkflowState
from runsight_core.workflow import Workflow
from runsight_core.yaml.schema import RetryConfig

# Test helpers


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
    workflow = Workflow(name="retry_behavior_workflow")
    workflow.add_block(block)
    workflow.add_transition(block.block_id, None)
    workflow.set_entry(block.block_id)
    return workflow


# BaseBlock retry configuration


class TestBaseBlockRetryConfigAttribute:
    """BaseBlock must have a retry_config attribute bridged from BlockDef."""

    def test_base_block_has_retry_config_attribute(self):
        """BaseBlock instances should have a retry_config attribute."""
        block = SucceedingBlock("retrying_block")
        assert hasattr(block, "retry_config")

    def test_base_block_retry_config_default_none(self):
        """BaseBlock.retry_config defaults to None when not explicitly set."""
        block = SucceedingBlock("retrying_block")
        assert block.retry_config is None

    def test_base_block_retry_config_can_be_set(self):
        """retry_config can be assigned to a BaseBlock instance."""
        block = SucceedingBlock("retrying_block")
        rc = RetryConfig(max_attempts=5, backoff="exponential")
        block.retry_config = rc
        assert block.retry_config is rc
        assert block.retry_config.max_attempts == 5

    def test_base_block_init_accepts_retry_config(self):
        """BaseBlock.__init__ should accept optional retry_config parameter."""
        rc = RetryConfig(max_attempts=3, backoff="fixed")
        # The constructor should accept retry_config as a keyword argument
        block = SucceedingBlock.__new__(SucceedingBlock)
        BaseBlock.__init__(block, "retrying_block", retry_config=rc)
        assert block.retry_config is rc


# Retry attempt limits


class TestRetryUpToMaxAttempts:
    """Blocks with retry_config retry on exception up to max_attempts."""

    @pytest.mark.asyncio
    async def test_retries_up_to_max_attempts_then_raises(self):
        """Block that always fails should be retried max_attempts times, then raise."""
        block = AlwaysFailingBlock("fail_block")
        block.retry_config = RetryConfig(max_attempts=3, backoff="fixed", backoff_base_seconds=0.1)

        workflow = _make_workflow_with_single_block(block)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(RuntimeError, match="boom"):
                await workflow.run(WorkflowState())

        # Must have been called exactly 3 times (initial + 2 retries)
        assert block.call_count == 3

    @pytest.mark.asyncio
    async def test_retries_exactly_max_attempts_times(self):
        """Block should be called exactly max_attempts times before giving up."""
        block = FailNTimesThenSucceed("retrying_block", fail_count=100)
        block.retry_config = RetryConfig(max_attempts=4, backoff="fixed", backoff_base_seconds=0.1)

        workflow = _make_workflow_with_single_block(block)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(RuntimeError):
                await workflow.run(WorkflowState())

        assert block._call_count == 4


# Retry eventual success


class TestRetrySucceedsAfterFailure:
    """Block that fails once then succeeds should complete successfully."""

    @pytest.mark.asyncio
    async def test_succeeds_on_second_attempt(self):
        """Block fails once, then succeeds and workflow completes normally."""
        block = FailNTimesThenSucceed("retrying_block", fail_count=1)
        block.retry_config = RetryConfig(max_attempts=3, backoff="fixed", backoff_base_seconds=0.1)

        workflow = _make_workflow_with_single_block(block)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            state = await workflow.run(WorkflowState())

        assert "retrying_block" in state.results
        assert "ok on attempt 2" in state.results["retrying_block"].output

    @pytest.mark.asyncio
    async def test_succeeds_on_third_attempt(self):
        """Block fails twice, then succeeds and workflow completes normally."""
        block = FailNTimesThenSucceed("retrying_block", fail_count=2)
        block.retry_config = RetryConfig(max_attempts=5, backoff="fixed", backoff_base_seconds=0.1)

        workflow = _make_workflow_with_single_block(block)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            state = await workflow.run(WorkflowState())

        assert "retrying_block" in state.results
        assert "ok on attempt 3" in state.results["retrying_block"].output


# Non-retryable errors


class TestNonRetryableErrors:
    """non_retryable_errors list controls which exceptions bypass retry."""

    @pytest.mark.asyncio
    async def test_non_retryable_error_not_retried(self):
        """ValueError in non_retryable_errors list bypasses retry."""
        block = AlwaysFailingBlock("retrying_block", error_cls=ValueError, message="bad value")
        block.retry_config = RetryConfig(
            max_attempts=5,
            backoff="fixed",
            backoff_base_seconds=0.1,
            non_retryable_errors=["ValueError"],
        )

        workflow = _make_workflow_with_single_block(block)

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(ValueError, match="bad value"):
                await workflow.run(WorkflowState())

        mock_sleep.assert_not_called()
        assert block.call_count == 1

    @pytest.mark.asyncio
    async def test_retryable_error_is_retried_when_non_retryable_list_exists(self):
        """RuntimeError not in non_retryable_errors is retried."""
        block = FailNTimesThenSucceed("retrying_block", fail_count=1, error_cls=RuntimeError)
        block.retry_config = RetryConfig(
            max_attempts=3,
            backoff="fixed",
            backoff_base_seconds=0.1,
            non_retryable_errors=["ValueError"],
        )

        workflow = _make_workflow_with_single_block(block)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            state = await workflow.run(WorkflowState())

        assert "retrying_block" in state.results

    @pytest.mark.asyncio
    async def test_non_retryable_error_raises_on_first_attempt(self):
        """A non-retryable error causes immediate failure with one attempt."""
        block = FailNTimesThenSucceed("retrying_block", fail_count=5, error_cls=ValueError)
        block.retry_config = RetryConfig(
            max_attempts=5,
            backoff="fixed",
            backoff_base_seconds=0.1,
            non_retryable_errors=["ValueError"],
        )

        workflow = _make_workflow_with_single_block(block)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(ValueError):
                await workflow.run(WorkflowState())

        assert block._call_count == 1


# Fixed backoff


class TestNoRetryConfig:
    """Blocks without retry_config should execute exactly once with no retry overhead."""

    @pytest.mark.asyncio
    async def test_block_without_retry_config_runs_once(self):
        """A block without retry_config that succeeds runs exactly once."""
        block = CountingBlock("retrying_block")

        workflow = _make_workflow_with_single_block(block)
        await workflow.run(WorkflowState())

        assert block.call_count == 1

    @pytest.mark.asyncio
    async def test_block_without_retry_config_error_propagates_immediately(self):
        """A block without retry_config that fails raises immediately."""
        block = AlwaysFailingBlock("retrying_block")

        workflow = _make_workflow_with_single_block(block)

        with pytest.raises(RuntimeError, match="boom"):
            await workflow.run(WorkflowState())

    @pytest.mark.asyncio
    async def test_no_sleep_called_for_block_without_retry_config(self):
        """No asyncio.sleep should be called for blocks without retry_config."""
        block = AlwaysFailingBlock("retrying_block")
        # No retry_config

        workflow = _make_workflow_with_single_block(block)

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(RuntimeError):
                await workflow.run(WorkflowState())

        mock_sleep.assert_not_called()


# System exception propagation


class TestNeverRetrySystemExceptions:
    """KeyboardInterrupt and SystemExit must never be retried, always re-raised."""

    @pytest.mark.asyncio
    async def test_keyboard_interrupt_not_retried(self):
        """KeyboardInterrupt should be re-raised immediately, never retried."""
        block = AlwaysFailingBlock("retrying_block", error_cls=KeyboardInterrupt, message="ctrl-c")
        block.retry_config = RetryConfig(max_attempts=5, backoff="fixed", backoff_base_seconds=0.1)

        workflow = _make_workflow_with_single_block(block)

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(KeyboardInterrupt):
                await workflow.run(WorkflowState())

        mock_sleep.assert_not_called()

    @pytest.mark.asyncio
    async def test_system_exit_not_retried(self):
        """SystemExit should be re-raised immediately, never retried."""
        block = AlwaysFailingBlock("retrying_block", error_cls=SystemExit, message="exit")
        block.retry_config = RetryConfig(max_attempts=5, backoff="fixed", backoff_base_seconds=0.1)

        workflow = _make_workflow_with_single_block(block)

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(SystemExit):
                await workflow.run(WorkflowState())

        mock_sleep.assert_not_called()


# Single-attempt retry configuration


class TestMaxAttemptsOne:
    """max_attempts=1 means run once with no retry on failure."""

    @pytest.mark.asyncio
    async def test_max_attempts_one_failing_block(self):
        """max_attempts=1: block runs once, fails, raises original exception."""
        block = AlwaysFailingBlock("retrying_block")
        block.retry_config = RetryConfig(max_attempts=1, backoff="fixed", backoff_base_seconds=0.1)

        workflow = _make_workflow_with_single_block(block)

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(RuntimeError, match="boom"):
                await workflow.run(WorkflowState())

        mock_sleep.assert_not_called()

    @pytest.mark.asyncio
    async def test_max_attempts_one_succeeding_block(self):
        """max_attempts=1: block succeeds on first attempt."""
        block = SucceedingBlock("retrying_block")
        block.retry_config = RetryConfig(max_attempts=1, backoff="fixed", backoff_base_seconds=0.1)

        workflow = _make_workflow_with_single_block(block)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            state = await workflow.run(WorkflowState())

        assert state.results["retrying_block"].output == "ok"


# Independent retry state
