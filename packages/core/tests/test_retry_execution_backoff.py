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


class TestFixedBackoff:
    """Fixed backoff: constant wait between retries."""

    @pytest.mark.asyncio
    async def test_fixed_backoff_waits_constant_duration(self):
        """Fixed backoff should sleep for backoff_base_seconds between each retry."""
        block = AlwaysFailingBlock("retrying_block")
        block.retry_config = RetryConfig(
            max_attempts=4,
            backoff="fixed",
            backoff_base_seconds=2.0,
        )

        workflow = _make_workflow_with_single_block(block)

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(RuntimeError):
                await workflow.run(WorkflowState())

        # 4 attempts = 3 retry sleeps (after attempt 1, 2, 3; not after last)
        assert mock_sleep.call_count == 3
        for call in mock_sleep.call_args_list:
            assert call.args[0] == pytest.approx(2.0)

    @pytest.mark.asyncio
    async def test_fixed_backoff_no_sleep_on_success(self):
        """If block succeeds on first attempt, no sleep should occur."""
        block = SucceedingBlock("retrying_block")
        block.retry_config = RetryConfig(
            max_attempts=3,
            backoff="fixed",
            backoff_base_seconds=1.0,
        )

        workflow = _make_workflow_with_single_block(block)

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await workflow.run(WorkflowState())

        mock_sleep.assert_not_called()


# Exponential backoff


class TestExponentialBackoff:
    """Exponential backoff: base * 2^attempt."""

    @pytest.mark.asyncio
    async def test_exponential_backoff_durations(self):
        """Exponential backoff: sleep durations should be base * 2^0, base * 2^1, base * 2^2, ..."""
        block = AlwaysFailingBlock("retrying_block")
        block.retry_config = RetryConfig(
            max_attempts=4,
            backoff="exponential",
            backoff_base_seconds=1.0,
        )

        workflow = _make_workflow_with_single_block(block)

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(RuntimeError):
                await workflow.run(WorkflowState())

        # 4 attempts = 3 sleeps
        assert mock_sleep.call_count == 3
        # Exponential: base * 2^0, base * 2^1, base * 2^2
        expected_durations = [1.0, 2.0, 4.0]
        actual_durations = [call.args[0] for call in mock_sleep.call_args_list]
        assert actual_durations == pytest.approx(expected_durations)

    @pytest.mark.asyncio
    async def test_exponential_backoff_with_custom_base(self):
        """Exponential backoff with base=0.5: 0.5, 1.0, 2.0."""
        block = AlwaysFailingBlock("retrying_block")
        block.retry_config = RetryConfig(
            max_attempts=4,
            backoff="exponential",
            backoff_base_seconds=0.5,
        )

        workflow = _make_workflow_with_single_block(block)

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(RuntimeError):
                await workflow.run(WorkflowState())

        expected_durations = [0.5, 1.0, 2.0]
        actual_durations = [call.args[0] for call in mock_sleep.call_args_list]
        assert actual_durations == pytest.approx(expected_durations)


# Retry metadata


class TestAsyncSleep:
    """Retry backoff must use asyncio.sleep for non-blocking behavior."""

    @pytest.mark.asyncio
    async def test_uses_asyncio_sleep_not_time_sleep(self):
        """Verify that asyncio.sleep is used, not time.sleep."""
        block = AlwaysFailingBlock("retrying_block")
        block.retry_config = RetryConfig(max_attempts=2, backoff="fixed", backoff_base_seconds=1.0)

        workflow = _make_workflow_with_single_block(block)

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_async_sleep:
            with pytest.raises(RuntimeError):
                await workflow.run(WorkflowState())

        # asyncio.sleep should have been called (once, between attempt 1 and 2)
        assert mock_async_sleep.call_count == 1
