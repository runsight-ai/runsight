"""RunsightTeamRunner execute() result contract."""

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
from runsight_core.runner import ExecutionResult, RunsightTeamRunner


@pytest.mark.asyncio
@patch("runsight_core.runner.LiteLLMClient.achat")
async def test_execute_returns_canonical_execution_result(mock_achat) -> None:
    mock_achat.return_value = achat_text_response(
        content="Mapped response.", cost_usd=0.005, total_tokens=50
    )

    result = await RunsightTeamRunner(model_name="gpt-4o").execute(
        INSTRUCTION, CONTEXT, make_soul()
    )

    assert isinstance(result, ExecutionResult)
    assert result.task_id == "execute"
    assert result.soul_id == "soul-one"
    assert result.output == "Mapped response."
    assert result.cost_usd == pytest.approx(0.005)
    assert result.total_tokens == 50
    assert result.metadata == {}


@pytest.mark.asyncio
@patch("runsight_core.runner.LiteLLMClient.achat")
async def test_execute_accepts_missing_context_and_history_messages(mock_achat) -> None:
    mock_achat.return_value = achat_text_response(content="With history.")

    result = await RunsightTeamRunner(model_name="gpt-4o").execute(
        INSTRUCTION,
        None,
        make_soul(),
        messages=HISTORY_MESSAGES,
    )

    assert result.output == "With history."
    sent = mock_achat.call_args.kwargs["messages"]
    assert sent[:2] == HISTORY_MESSAGES
    assert sent[-1]["role"] == "user"
    assert "Context:" not in sent[-1]["content"]


@pytest.mark.asyncio
@patch("runsight_core.runner.LiteLLMClient.achat")
async def test_execute_rejects_soul_without_provider(mock_achat) -> None:
    mock_achat.return_value = achat_text_response()
    bad_soul = make_soul(id="bad-soul", provider=None)

    with pytest.raises(ValueError, match="explicit provider"):
        await RunsightTeamRunner(model_name="gpt-4o").execute(INSTRUCTION, CONTEXT, bad_soul)

    mock_achat.assert_not_called()
