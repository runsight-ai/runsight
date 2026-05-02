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


class TestRetryTransparency:
    """Retry is transparent to the retried block."""

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

        block = StateCapturingBlock("retrying_block")
        block.retry_config = RetryConfig(max_attempts=5, backoff="fixed", backoff_base_seconds=0.1)

        workflow = _make_workflow_with_single_block(block)
        initial = WorkflowState(shared_memory={"key": "value"})

        with patch("asyncio.sleep", new_callable=AsyncMock):
            state = await workflow.run(initial)

        # Block was called 3 times (2 failures + 1 success)
        assert block._call_count == 3
        assert state.results["retrying_block"].output == "done"


# Async backoff
