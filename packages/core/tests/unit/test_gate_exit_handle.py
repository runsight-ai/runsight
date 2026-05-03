"""Smoke coverage for GateBlock exit handles."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

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
            task_id="gate-exit-task",
            soul_id="gate-exit-soul",
            output=output,
            cost_usd=cost,
            total_tokens=tokens,
        )
    )
    return runner


def _make_soul() -> Soul:
    return Soul(
        id="gate_soul",
        kind="soul",
        name="Gate",
        role="Gate",
        system_prompt="Evaluate quality.",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("runner_output", "expected_exit", "expected_output"),
    [
        ("PASS", "pass", "PASS"),
        ("FAIL: missing citations", "fail", "missing citations"),
    ],
)
async def test_gate_block_returns_pass_or_fail_exit_handle(
    runner_output: str,
    expected_exit: str,
    expected_output: str,
) -> None:
    from runsight_core.blocks.gate import GateBlock

    block = GateBlock(
        block_id="quality_gate",
        gate_soul=_make_soul(),
        eval_key="content",
        runner=_mock_runner(runner_output, cost=0.03, tokens=150),
    )
    state = WorkflowState(
        results={"content": BlockResult(output="Draft text")},
        total_cost_usd=1.0,
        total_tokens=500,
    )

    result_state = await execute_block_for_test(block, state)

    result = result_state.results["quality_gate"]
    assert result.exit_handle == expected_exit
    assert result.output == expected_output
    assert result_state.total_cost_usd == pytest.approx(1.03)
    assert result_state.total_tokens == 650


def test_gate_build_auto_injects_pass_fail_exits_when_omitted() -> None:
    from runsight_core.blocks.gate import GateBlockDef, build

    block_def = GateBlockDef(
        type="gate",
        soul_ref="gate_soul",
        eval_key="content",
        exits=None,
    )

    build("quality_gate", block_def, {"gate_soul": _make_soul()}, _mock_runner("PASS"), {})

    assert [(exit_def.id, exit_def.label) for exit_def in block_def.exits or []] == [
        ("pass", "Pass"),
        ("fail", "Fail"),
    ]
