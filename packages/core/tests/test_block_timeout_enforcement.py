"""Red tests for RUN-713: asyncio.wait_for block timeout in execute_block().

Tests verify that execute_block() wraps _dispatch() with asyncio.wait_for when
block.max_duration_seconds is set, raising BudgetKilledException on timeout.
"""

from __future__ import annotations

import asyncio

import pytest
from runsight_core.blocks.base import BaseBlock
from runsight_core.budget_enforcement import BudgetKilledException
from runsight_core.state import WorkflowState
from runsight_core.workflow import BlockExecutionContext, execute_block

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class SlowBlock(BaseBlock):
    """Block whose execute() sleeps longer than any reasonable timeout."""

    def __init__(self, block_id: str, sleep_seconds: float) -> None:
        super().__init__(block_id)
        self.sleep_seconds = sleep_seconds

    async def execute(self, ctx):
        from runsight_core.block_io import BlockOutput

        await asyncio.sleep(self.sleep_seconds)
        return BlockOutput(output="slow done")


class FastBlock(BaseBlock):
    """Block that returns immediately."""

    def __init__(self, block_id: str) -> None:
        super().__init__(block_id)

    async def execute(self, ctx):
        from runsight_core.block_io import BlockOutput

        return BlockOutput(output="fast done")


class RecordingObserver:
    def __init__(self) -> None:
        self.events: list[tuple] = []

    def on_block_start(self, workflow_name, block_id, block_type, **kwargs) -> None:
        self.events.append(("start", workflow_name, block_id, block_type, kwargs))

    def on_block_complete(
        self, workflow_name, block_id, block_type, duration_s, state, **kwargs
    ) -> None:
        self.events.append(("complete", workflow_name, block_id, block_type))

    def on_block_error(self, workflow_name, block_id, block_type, duration_s, error) -> None:
        self.events.append(("error", workflow_name, block_id, block_type, error))


def _make_ctx(
    *,
    workflow_name: str = "test_workflow",
    blocks=None,
    call_stack=None,
    workflow_registry=None,
    observer=None,
) -> BlockExecutionContext:
    return BlockExecutionContext(
        workflow_name=workflow_name,
        blocks=blocks or {},
        call_stack=call_stack or ["root"],
        workflow_registry=workflow_registry,
        observer=observer,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBlockTimeoutEnforcement:
    """execute_block() wraps _dispatch with asyncio.wait_for when max_duration_seconds is set."""

    @pytest.mark.asyncio
    async def test_block_exceeding_timeout_raises_budget_killed_exception(self):
        """Given block with max_duration_seconds=0.1 that sleeps 0.5s,
        execute_block raises BudgetKilledException after ~0.1s."""
        block = SlowBlock("slow_block", sleep_seconds=0.5)
        block.max_duration_seconds = 0.1
        state = WorkflowState()
        ctx = _make_ctx()

        with pytest.raises(BudgetKilledException) as exc_info:
            await execute_block(block, state, ctx)

        exc = exc_info.value
        assert exc.scope == "block"
        assert exc.block_id == "slow_block"
        assert exc.limit_kind == "timeout"
        assert exc.limit_value == 0.1

    @pytest.mark.asyncio
    async def test_block_completing_within_timeout_returns_normal_result(self):
        """Given block with max_duration_seconds=5.0 that returns instantly,
        execute_block returns the normal result without error."""
        block = FastBlock("fast_block")
        block.max_duration_seconds = 5.0
        state = WorkflowState()
        ctx = _make_ctx()

        result = await execute_block(block, state, ctx)

        assert result.results["fast_block"].output == "fast done"

    @pytest.mark.asyncio
    async def test_no_max_duration_seconds_attribute_no_timeout_wrapping(self):
        """Given block without max_duration_seconds, execute_block does NOT
        wrap with asyncio.wait_for — behavior is identical to current."""
        block = FastBlock("plain_block")
        # Explicitly verify no max_duration_seconds
        assert not hasattr(block, "max_duration_seconds")
        state = WorkflowState()
        ctx = _make_ctx()

        result = await execute_block(block, state, ctx)

        assert result.results["plain_block"].output == "fast done"

    @pytest.mark.asyncio
    async def test_max_duration_seconds_none_treated_as_no_timeout(self):
        """Given block with max_duration_seconds=None, execute_block does NOT
        wrap with asyncio.wait_for — same as absent attribute."""
        block = FastBlock("none_timeout_block")
        block.max_duration_seconds = None
        state = WorkflowState()
        ctx = _make_ctx()

        result = await execute_block(block, state, ctx)

        assert result.results["none_timeout_block"].output == "fast done"

    @pytest.mark.asyncio
    async def test_timeout_exception_propagates_to_observer_error_handler(self):
        """BudgetKilledException from timeout triggers observer.on_block_error."""
        observer = RecordingObserver()
        block = SlowBlock("observed_slow", sleep_seconds=0.5)
        block.max_duration_seconds = 0.1
        state = WorkflowState()
        ctx = _make_ctx(observer=observer)

        with pytest.raises(BudgetKilledException):
            await execute_block(block, state, ctx)

        error_events = [e for e in observer.events if e[0] == "error"]
        assert len(error_events) == 1
        assert error_events[0][2] == "observed_slow"  # block_id
        assert isinstance(error_events[0][4], BudgetKilledException)

    @pytest.mark.asyncio
    async def test_timeout_actual_value_equals_timeout_setting(self):
        """BudgetKilledException.actual_value should be the timeout value itself
        (not elapsed wall-clock time), matching the contract."""
        block = SlowBlock("timeout_val_block", sleep_seconds=0.5)
        block.max_duration_seconds = 0.2
        state = WorkflowState()
        ctx = _make_ctx()

        with pytest.raises(BudgetKilledException) as exc_info:
            await execute_block(block, state, ctx)

        assert exc_info.value.actual_value == 0.2

    @pytest.mark.asyncio
    async def test_timeout_cancels_block_promptly(self):
        """Block timeout should fire after ~max_duration_seconds, not much longer."""
        block = SlowBlock("prompt_cancel_block", sleep_seconds=2.0)
        block.max_duration_seconds = 0.1
        state = WorkflowState()
        ctx = _make_ctx()

        import time

        t0 = time.monotonic()
        with pytest.raises(BudgetKilledException):
            await execute_block(block, state, ctx)
        elapsed = time.monotonic() - t0

        # Should complete in roughly 0.1s, definitely under 1s
        assert elapsed < 1.0, f"Timeout took {elapsed:.2f}s, expected ~0.1s"
