"""Smoke coverage for dispatch branch budget accounting through parsed workflows."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from runsight_core.budget_enforcement import _active_budget
from runsight_core.state import WorkflowState
from runsight_core.yaml.parser import parse_workflow_yaml

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "workflows"
_COST_CAP_WORKFLOW_FIXTURE = "dispatch-budget-cost-cap.yaml"
_DISPATCH_KEY = "budgeted_dispatch"
_BRANCH_KEYS = [
    "budgeted_dispatch.budget_branch_alpha",
    "budgeted_dispatch.budget_branch_beta",
    "budgeted_dispatch.budget_branch_gamma",
]


def _parse_fixture_workflow(fixture_name: str):
    return parse_workflow_yaml((_FIXTURE_DIR / fixture_name).read_text(encoding="utf-8"))


def _make_completion_response(content: str, total_tokens: int):
    message = MagicMock()
    message.content = content
    message.tool_calls = None

    choice = MagicMock()
    choice.message = message
    choice.finish_reason = "stop"

    usage = MagicMock()
    usage.prompt_tokens = total_tokens // 2
    usage.completion_tokens = total_tokens - usage.prompt_tokens
    usage.total_tokens = total_tokens

    response = MagicMock()
    response.choices = [choice]
    response.usage = usage
    return response


@pytest.mark.asyncio
@patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
@patch("runsight_core.llm.client.completion_cost")
async def test_parsed_dispatch_workflow_tracks_branch_results_and_budget_context(
    patched_cost_calculator, patched_completion_call
):
    responses = [
        _make_completion_response("alpha result", 100),
        _make_completion_response("beta result", 120),
        _make_completion_response("gamma result", 80),
    ]
    captured_sessions = []

    async def _capturing_completion(**kwargs):
        captured_sessions.append(_active_budget.get(None))
        return responses[len(captured_sessions) - 1]

    patched_completion_call.side_effect = _capturing_completion
    patched_cost_calculator.side_effect = [0.50, 0.60, 0.40]

    wf = _parse_fixture_workflow(_COST_CAP_WORKFLOW_FIXTURE)
    result = await wf.run(WorkflowState())

    assert _DISPATCH_KEY in result.results
    for key in _BRANCH_KEYS:
        assert key in result.results
    assert result.total_cost_usd == pytest.approx(1.50)
    assert result.total_tokens == 300
    assert captured_sessions == [None, None, None]
    assert _active_budget.get(None) is None
