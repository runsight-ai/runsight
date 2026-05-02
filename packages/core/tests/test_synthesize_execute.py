"""Smoke coverage for SynthesizeBlock runner execution wiring."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from conftest import execute_block_for_test
from runsight_core.primitives import Soul
from runsight_core.runner import ExecutionResult, RunsightTeamRunner
from runsight_core.state import BlockResult, WorkflowState


def _mock_runner(output: str, cost: float = 0.01, tokens: int = 100) -> RunsightTeamRunner:
    runner = MagicMock(spec=RunsightTeamRunner)
    runner.model_name = "gpt-4o"
    runner.execute = AsyncMock(
        return_value=ExecutionResult(
            task_id="synthesis",
            soul_id="synth_soul",
            output=output,
            cost_usd=cost,
            total_tokens=tokens,
        )
    )
    runner.execute_task = AsyncMock()
    return runner


def _make_soul() -> Soul:
    return Soul(
        id="synth_soul",
        kind="soul",
        name="Synthesizer",
        role="Synthesizer",
        system_prompt="Synthesize the inputs.",
    )


@pytest.mark.asyncio
async def test_synthesize_block_executes_with_string_prompt_and_stores_result() -> None:
    from runsight_core.blocks.synthesize import SynthesizeBlock

    runner = _mock_runner("Final synthesized report", cost=0.07, tokens=300)
    block = SynthesizeBlock(
        block_id="synth",
        input_block_ids=["alpha", "beta"],
        synthesizer_soul=_make_soul(),
        runner=runner,
    )
    state = WorkflowState(
        results={
            "alpha": BlockResult(output="Alpha output"),
            "beta": BlockResult(output="Beta output"),
        },
        total_cost_usd=1.0,
        total_tokens=50,
    )

    with patch.object(BlockResult, "__str__", return_value="PATCHED_STR"):
        result_state = await execute_block_for_test(block, state)

    args, _kwargs = runner.execute.call_args
    assert isinstance(args[0], str)
    assert isinstance(args[1], (str, type(None)))
    assert isinstance(args[2], Soul)
    assert "Alpha output" in (args[1] or "")
    assert "Beta output" in (args[1] or "")
    assert "PATCHED_STR" not in (args[1] or "")
    assert result_state.results["synth"].output == "Final synthesized report"
    assert result_state.total_cost_usd == pytest.approx(1.07)
    assert result_state.total_tokens == 350
    runner.execute_task.assert_not_called()
