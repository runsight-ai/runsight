"""Prompt assembly for RunsightTeamRunner.execute()."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from runner_execute_helpers import (
    CONTEXT,
    HISTORY_MESSAGES,
    INSTRUCTION,
    achat_text_response,
    make_soul,
)
from runsight_core.runner import RunsightTeamRunner


@pytest.mark.asyncio
@patch("runsight_core.runner.LiteLLMClient.achat")
async def test_execute_combines_instruction_context_and_soul_settings(mock_achat) -> None:
    mock_achat.return_value = achat_text_response()
    soul = make_soul(system_prompt="System rules.", temperature=0.0, max_tokens=128)

    await RunsightTeamRunner(model_name="gpt-4o").execute("Do the thing.", "My context.", soul)

    kwargs = mock_achat.call_args.kwargs
    user_message = kwargs["messages"][-1]
    assert "Do the thing." in user_message["content"]
    assert "My context." in user_message["content"]
    assert kwargs["system_prompt"] == "System rules."
    assert kwargs["temperature"] == 0.0
    assert kwargs["max_tokens"] == 128


@pytest.mark.asyncio
@patch("runsight_core.runner.LiteLLMClient.achat")
async def test_execute_prepends_history_before_current_prompt(mock_achat) -> None:
    mock_achat.return_value = achat_text_response()

    await RunsightTeamRunner(model_name="gpt-4o").execute(
        INSTRUCTION,
        CONTEXT,
        make_soul(),
        messages=HISTORY_MESSAGES,
    )

    sent = mock_achat.call_args.kwargs["messages"]
    assert sent[0:2] == HISTORY_MESSAGES
    assert sent[2]["role"] == "user"
    assert INSTRUCTION in sent[2]["content"]
    assert CONTEXT in sent[2]["content"]


@pytest.mark.asyncio
@patch("runsight_core.runner.LiteLLMClient.achat")
async def test_execute_empty_history_has_single_user_prompt(mock_achat) -> None:
    mock_achat.return_value = achat_text_response()

    await RunsightTeamRunner(model_name="gpt-4o").execute(
        INSTRUCTION, None, make_soul(), messages=[]
    )

    sent = mock_achat.call_args.kwargs["messages"]
    assert sent == [{"role": "user", "content": INSTRUCTION}]
