"""Tests for Step-wrapped workflow behavior.

These tests avoid source-shape assertions and instead lock down public behavior
that should remain the same when execution ownership is decomposed away from the
workflow facade.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from runsight_core.block_io import BlockContext, BlockOutput
from runsight_core.blocks.base import BaseBlock
from runsight_core.budget_enforcement import BudgetKilledException
from runsight_core.primitives import Step
from runsight_core.state import WorkflowState
from runsight_core.workflow import BlockExecutionContext, Workflow, execute_block
from runsight_core.yaml.schema import RetryConfig


class _DeclaredExit:
    def __init__(self, exit_id: str) -> None:
        self.id = exit_id


class _LeafBlock(BaseBlock):
    def __init__(self, block_id: str, output: str | None = None) -> None:
        super().__init__(block_id)
        self.output = output or block_id

    async def execute(self, ctx: BlockContext) -> BlockOutput:
        return BlockOutput(output=self.output)


class _FlakyBlock(BaseBlock):
    def __init__(self, block_id: str) -> None:
        super().__init__(block_id)
        self.calls = 0

    async def execute(self, ctx: BlockContext) -> BlockOutput:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("fail once before retrying")
        return BlockOutput(output=f"ok on attempt {self.calls}")


class _SlowBlock(BaseBlock):
    def __init__(self, block_id: str, *, sleep_seconds: float) -> None:
        super().__init__(block_id)
        self.sleep_seconds = sleep_seconds
        self.calls = 0

    async def execute(self, ctx: BlockContext) -> BlockOutput:
        self.calls += 1
        await asyncio.sleep(self.sleep_seconds)
        return BlockOutput(output="slow complete")


def _make_ctx(step: Step) -> BlockExecutionContext:
    return BlockExecutionContext(
        workflow_name="step_wrapped_workflow",
        blocks={step.block_id: step},
        call_stack=[],
        workflow_registry=None,
        observer=None,
    )


def test_validate_rejects_invalid_declared_exit_key_for_step_wrapped_block():
    """Step wrappers should not hide declared exits from Workflow.validate()."""
    router = _LeafBlock("router")
    router._declared_exits = [_DeclaredExit("approved"), _DeclaredExit("rejected")]

    workflow = Workflow("step_declared_exit_validation")
    workflow.add_block(Step(block=router))
    workflow.add_block(_LeafBlock("approved"))
    workflow.add_block(_LeafBlock("fallback"))
    workflow.set_entry("router")
    workflow.add_conditional_transition(
        "router",
        {
            "bogus": "approved",
            "default": "fallback",
        },
    )
    workflow.add_transition("approved", None)
    workflow.add_transition("fallback", None)

    errors = workflow.validate()

    assert any(
        "'router': transition key 'bogus' not in declared exits" in error for error in errors
    )


@pytest.mark.asyncio
async def test_workflow_run_retries_step_wrapped_block_using_wrapped_retry_config():
    """A Step-wrapped block should keep the wrapped block's retry behavior."""
    inner = _FlakyBlock("retry_step")
    inner.retry_config = RetryConfig(
        max_attempts=2,
        backoff="fixed",
        backoff_base_seconds=0.1,
    )

    workflow = Workflow("step_retry_workflow")
    workflow.add_block(Step(block=inner))
    workflow.set_entry("retry_step")
    workflow.add_transition("retry_step", None)

    with patch("asyncio.sleep", new_callable=AsyncMock) as sleep_mock:
        final_state = await workflow.run(WorkflowState())

    assert inner.calls == 2
    assert sleep_mock.await_count == 1
    assert final_state.results["retry_step"].output == "ok on attempt 2"


@pytest.mark.asyncio
async def test_execute_block_enforces_wrapped_block_timeout_for_step():
    """execute_block() should preserve max_duration_seconds for Step-wrapped blocks."""
    inner = _SlowBlock("slow_step", sleep_seconds=0.05)
    inner.max_duration_seconds = 0.01
    step = Step(block=inner)

    with pytest.raises(BudgetKilledException) as exc_info:
        await execute_block(step, WorkflowState(), _make_ctx(step))

    assert exc_info.value.scope == "block"
    assert exc_info.value.block_id == "slow_step"
    assert exc_info.value.limit_kind == "timeout"
