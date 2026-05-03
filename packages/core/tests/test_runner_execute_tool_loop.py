"""Agentic tool-loop behavior for RunsightTeamRunner.execute()."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from runner_execute_helpers import (
    CONTEXT,
    INSTRUCTION,
    achat_text_response,
    achat_tool_response,
    make_soul,
    make_soul_with_tools,
    make_tool_instance,
)
from runsight_core.runner import RunsightTeamRunner


@pytest.mark.asyncio
@patch("runsight_core.runner.LiteLLMClient.achat")
async def test_execute_without_resolved_tools_uses_single_llm_call(mock_achat) -> None:
    soul = make_soul(id="no_tools")
    soul.resolved_tools = None
    mock_achat.return_value = achat_text_response(content="Simple answer.")

    result = await RunsightTeamRunner(model_name="gpt-4o").execute(INSTRUCTION, CONTEXT, soul)

    assert result.output == "Simple answer."
    assert result.tool_iterations == 0
    assert result.tool_calls_made == []
    mock_achat.assert_called_once()


@pytest.mark.asyncio
@patch("runsight_core.runner.LiteLLMClient.achat")
async def test_execute_tool_loop_runs_tool_then_returns_final_text(mock_achat) -> None:
    tool = make_tool_instance("search")
    soul = make_soul_with_tools([tool])
    mock_achat.side_effect = [
        achat_tool_response(tool_name="search", call_id="c1", cost_usd=0.003, total_tokens=30),
        achat_text_response(content="Found it.", cost_usd=0.002, total_tokens=20),
    ]

    result = await RunsightTeamRunner(model_name="gpt-4o").execute(INSTRUCTION, CONTEXT, soul)

    assert result.output == "Found it."
    assert result.cost_usd == pytest.approx(0.005)
    assert result.total_tokens == 50
    assert "search" in result.tool_calls_made
    assert result.tool_iterations >= 1
    assert mock_achat.call_count == 2
