"""Smoke coverage that block execution writes BlockResult values."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from runsight_core.block_io import apply_block_output, build_block_context
from runsight_core.primitives import Soul
from runsight_core.runner import ExecutionResult
from runsight_core.state import BlockResult, WorkflowState


async def _exec(block, state):
    ctx = build_block_context(block, state)
    output = await block.execute(ctx)
    return apply_block_output(state, block.block_id, output)


class NoCoercionWorkflowState(WorkflowState):
    """Reject raw strings written through model_copy(results=...)."""

    def model_copy(self, *, update: dict[str, Any] | None = None, **kwargs):
        if update and "results" in update:
            for key, value in update["results"].items():
                if isinstance(value, str):
                    raise TypeError(f"raw string written to results[{key!r}]")
        return super().model_copy(update=update, **kwargs)


def _make_state(**kwargs) -> NoCoercionWorkflowState:
    return NoCoercionWorkflowState.model_validate(WorkflowState(**kwargs).model_dump())


def _soul() -> Soul:
    return Soul(
        id="block_result_soul",
        kind="soul",
        name="Block Result Soul",
        role="Write Site Tester",
        system_prompt="Verify outputs.",
    )


def _execution_result(output: str) -> ExecutionResult:
    return ExecutionResult(
        task_id="write-site-task",
        soul_id="block_result_soul",
        output=output,
        cost_usd=0.001,
        total_tokens=10,
    )


@pytest.mark.asyncio
async def test_mixed_block_execution_leaves_only_block_result_values() -> None:
    from runsight_core import CodeBlock, LinearBlock, SynthesizeBlock

    runner = MagicMock()
    runner.model_name = "gpt-4o"
    runner.execute = AsyncMock(
        side_effect=[
            _execution_result("linear output"),
            _execution_result("synthesized output"),
        ]
    )
    soul = _soul()
    state = _make_state()

    state = await _exec(LinearBlock("linear_write_site", soul, runner), state)
    state = await _exec(
        SynthesizeBlock("synthesis_write_site", ["linear_write_site"], soul, runner),
        state,
    )
    state = await _exec(
        CodeBlock("code_write_site", code='def main(data):\n    return "code output"\n'),
        state,
    )

    assert set(state.results) == {
        "linear_write_site",
        "synthesis_write_site",
        "code_write_site",
    }
    assert state.results["linear_write_site"].output == "linear output"
    assert state.results["synthesis_write_site"].output == "synthesized output"
    assert state.results["code_write_site"].output == "code output"
    assert all(isinstance(result, BlockResult) for result in state.results.values())
