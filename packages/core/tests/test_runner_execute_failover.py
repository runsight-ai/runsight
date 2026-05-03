"""Provider failover behavior for RunsightTeamRunner.execute()."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest
from runner_execute_helpers import CONTEXT, INSTRUCTION, make_soul
from runsight_core.runner import FallbackRoute, RunsightTeamRunner


@pytest.mark.asyncio
async def test_execute_falls_back_on_retryable_provider_error() -> None:
    primary_client = Mock()
    primary_client.achat = AsyncMock(side_effect=RuntimeError("RateLimitError: openai overloaded"))
    fallback_client = Mock()
    fallback_client.achat = AsyncMock(
        return_value={
            "content": "Fallback answer.",
            "cost_usd": 0.002,
            "total_tokens": 20,
            "tool_calls": None,
            "raw_message": {"role": "assistant", "content": "Fallback answer."},
        }
    )

    with patch("runsight_core.runner.LiteLLMClient") as mock_client:
        mock_client.side_effect = lambda *, model_name, api_key=None: (
            primary_client if model_name == "gpt-4o" else fallback_client
        )
        runner = RunsightTeamRunner(
            model_name="gpt-4o",
            api_keys={"openai": "sk-openai", "anthropic": "sk-anthropic"},
            fallback_routes={
                "openai": FallbackRoute(
                    source_provider_id="openai",
                    target_provider_id="anthropic",
                    target_model_name="claude-3-opus-20240229",
                )
            },
        )
        result = await runner.execute(INSTRUCTION, CONTEXT, make_soul())

    assert result.output == "Fallback answer."
    primary_client.achat.assert_awaited_once()
    fallback_client.achat.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_does_not_fallback_on_authentication_error() -> None:
    primary_client = Mock()
    primary_client.achat = AsyncMock(
        side_effect=RuntimeError("AuthenticationError: invalid api key")
    )
    fallback_client = Mock()
    fallback_client.achat = AsyncMock(return_value={"content": "Should not run."})

    with patch("runsight_core.runner.LiteLLMClient") as mock_client:
        mock_client.side_effect = lambda *, model_name, api_key=None: (
            primary_client if model_name == "gpt-4o" else fallback_client
        )
        runner = RunsightTeamRunner(
            model_name="gpt-4o",
            api_keys={"openai": "sk-openai", "anthropic": "sk-anthropic"},
            fallback_routes={
                "openai": FallbackRoute(
                    source_provider_id="openai",
                    target_provider_id="anthropic",
                    target_model_name="claude-3-opus-20240229",
                )
            },
        )
        with pytest.raises(RuntimeError, match="AuthenticationError"):
            await runner.execute(INSTRUCTION, CONTEXT, make_soul())

    primary_client.achat.assert_awaited_once()
    fallback_client.achat.assert_not_awaited()
