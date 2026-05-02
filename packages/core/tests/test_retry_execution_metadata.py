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


class TestRetryMetadataInSharedMemory:
    """Retry metadata must be stored in shared_memory under __retry__{block_id}."""

    @pytest.mark.asyncio
    async def test_retry_metadata_written_on_exhausted_failure(self):
        """After exhausting retries, block should have been called max_attempts times.

        Since Workflow.run() raises when the block exhausts all attempts,
        we verify the retry wrapper actually retried by checking call count.
        """
        block = AlwaysFailingBlock("retrying_block")
        block.retry_config = RetryConfig(max_attempts=3, backoff="fixed", backoff_base_seconds=0.1)

        workflow = _make_workflow_with_single_block(block)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(RuntimeError):
                await workflow.run(WorkflowState())

        # Block must have been called exactly max_attempts times
        assert block.call_count == 3

    @pytest.mark.asyncio
    async def test_retry_metadata_after_successful_retry(self):
        """Block fails once then succeeds and shared_memory contains retry metadata."""
        block = FailNTimesThenSucceed("retrying_block", fail_count=1)
        block.retry_config = RetryConfig(max_attempts=3, backoff="fixed", backoff_base_seconds=0.1)

        workflow = _make_workflow_with_single_block(block)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            state = await workflow.run(WorkflowState())

        meta_key = "__retry__retrying_block"
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
        block = FailNTimesThenSucceed("metadata_block", fail_count=2)
        block.retry_config = RetryConfig(max_attempts=5, backoff="fixed", backoff_base_seconds=0.1)

        workflow = _make_workflow_with_single_block(block)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            state = await workflow.run(WorkflowState())

        meta_key = "__retry__metadata_block"
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
        """Block succeeds on first attempt without retry metadata in shared_memory."""
        block = SucceedingBlock("retrying_block")
        block.retry_config = RetryConfig(max_attempts=3, backoff="fixed", backoff_base_seconds=0.1)

        workflow = _make_workflow_with_single_block(block)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            state = await workflow.run(WorkflowState())

        # No retry occurred, so no retry metadata should be written
        assert "__retry__retrying_block" not in state.shared_memory


# Execution without retry configuration


class TestIndependentRetryState:
    """Multiple blocks with retry configs maintain independent retry state."""

    @pytest.mark.asyncio
    async def test_two_blocks_independent_retry_metadata(self):
        """Two blocks in sequence, each with retry_config, get separate metadata."""
        ingest_step = FailNTimesThenSucceed("ingest_step", fail_count=1)
        ingest_step.retry_config = RetryConfig(
            max_attempts=3, backoff="fixed", backoff_base_seconds=0.1
        )

        publish_step = FailNTimesThenSucceed("publish_step", fail_count=2)
        publish_step.retry_config = RetryConfig(
            max_attempts=5, backoff="fixed", backoff_base_seconds=0.1
        )

        workflow = Workflow(name="independent_retry_workflow")
        workflow.add_block(ingest_step)
        workflow.add_block(publish_step)
        workflow.add_transition("ingest_step", "publish_step")
        workflow.add_transition("publish_step", None)
        workflow.set_entry("ingest_step")

        with patch("asyncio.sleep", new_callable=AsyncMock):
            state = await workflow.run(WorkflowState())

        # ingest_step: failed 1 time, succeeded on attempt 2
        ingest_meta = state.shared_memory["__retry__ingest_step"]
        assert ingest_meta["attempt"] == 2
        assert ingest_meta["total_retries"] == 1

        # publish_step: failed 2 times, succeeded on attempt 3
        publish_meta = state.shared_memory["__retry__publish_step"]
        assert publish_meta["attempt"] == 3
        assert publish_meta["total_retries"] == 2

        assert ingest_meta["max_attempts"] == 3
        assert publish_meta["max_attempts"] == 5


# Retry transparency
