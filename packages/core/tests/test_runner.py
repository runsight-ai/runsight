from unittest.mock import AsyncMock, Mock, patch

import pytest
from runsight_core.primitives import Soul, Task
from runsight_core.runner import ExecutionResult, FallbackRoute, RunsightTeamRunner


@pytest.fixture
def sample_soul():
    return Soul(
        id="test_soul",
        kind="soul",
        name="Test Agent",
        role="Test Agent",
        system_prompt="You are a helpful test agent.",
        provider="openai",
        model_name="gpt-4o",
    )


@pytest.fixture
def sample_task():
    return Task(id="test_task", instruction="Say hello.", context="This is a test context.")


def test_runner_requires_explicit_model_name():
    with pytest.raises(TypeError):
        RunsightTeamRunner()


@pytest.mark.asyncio
@patch("runsight_core.runner.LiteLLMClient.achat")
async def test_execute_task(mock_achat, sample_soul, sample_task):
    mock_achat.return_value = {
        "content": "Hello!",
        "cost_usd": 0.001,
        "total_tokens": 10,
    }

    runner = RunsightTeamRunner(model_name="gpt-4o")
    result = await runner.execute_task(sample_task, sample_soul)

    assert isinstance(result, ExecutionResult)
    assert result.task_id == "test_task"
    assert result.soul_id == "test_soul"
    assert result.output == "Hello!"
    assert result.cost_usd == 0.001
    assert result.total_tokens == 10

    mock_achat.assert_called_once()
    kwargs = mock_achat.call_args.kwargs
    assert kwargs["system_prompt"] == "You are a helpful test agent."
    assert len(kwargs["messages"]) == 1
    assert "Say hello." in kwargs["messages"][0]["content"]
    assert "This is a test context." in kwargs["messages"][0]["content"]


@pytest.mark.asyncio
@patch("runsight_core.runner.LiteLLMClient.achat")
async def test_execute_task_forwards_temperature_and_max_tokens(mock_achat, sample_task):
    mock_achat.return_value = {
        "content": "Hello!",
        "cost_usd": 0.001,
        "total_tokens": 10,
    }

    runner = RunsightTeamRunner(model_name="gpt-4o")
    soul = Soul(
        id="configured_soul",
        kind="soul",
        name="Configured Agent",
        role="Configured Agent",
        system_prompt="Use the configured runtime params.",
        provider="openai",
        model_name="gpt-4o",
        temperature=0.0,
        max_tokens=128,
    )
    await runner.execute_task(sample_task, soul)

    kwargs = mock_achat.call_args.kwargs
    assert kwargs["temperature"] == 0.0
    assert kwargs["max_tokens"] == 128


@pytest.mark.asyncio
@patch("runsight_core.runner.LiteLLMClient.achat")
async def test_execute_task_rejects_model_only_soul_without_provider(mock_achat, sample_task):
    mock_achat.return_value = {
        "content": "Hello!",
        "cost_usd": 0.001,
        "total_tokens": 10,
    }

    runner = RunsightTeamRunner(model_name="gpt-4o")
    soul = Soul(
        id="test_soul",
        kind="soul",
        name="Test Agent",
        role="Test Agent",
        system_prompt="You are a helpful test agent.",
        model_name="gpt-4o",
    )

    with pytest.raises(ValueError, match="explicit provider"):
        await runner.execute_task(sample_task, soul)

    mock_achat.assert_not_called()


@pytest.mark.asyncio
@patch("runsight_core.runner.LiteLLMClient.achat")
async def test_execute_task_rejects_provider_only_soul_without_model_name(mock_achat, sample_task):
    mock_achat.return_value = {
        "content": "Hello!",
        "cost_usd": 0.001,
        "total_tokens": 10,
    }

    runner = RunsightTeamRunner(model_name="gpt-4o")
    soul = Soul(
        id="test_soul",
        kind="soul",
        name="Test Agent",
        role="Test Agent",
        system_prompt="You are a helpful test agent.",
        provider="openai",
    )

    with pytest.raises(ValueError, match="explicit model_name"):
        await runner.execute_task(sample_task, soul)

    mock_achat.assert_not_called()


@pytest.mark.asyncio
@patch("runsight_core.runner.LiteLLMClient.achat")
async def test_execute_task_rejects_soul_without_provider_and_model_name(mock_achat, sample_task):
    mock_achat.return_value = {
        "content": "Hello!",
        "cost_usd": 0.001,
        "total_tokens": 10,
    }

    runner = RunsightTeamRunner(model_name="gpt-4o")
    soul = Soul(
        id="test_soul",
        kind="soul",
        name="Test Agent",
        role="Test Agent",
        system_prompt="You are a helpful test agent.",
    )

    with pytest.raises(ValueError, match="explicit provider and model_name"):
        await runner.execute_task(sample_task, soul)

    mock_achat.assert_not_called()


@pytest.mark.asyncio
async def test_execute_task_fails_over_to_configured_fallback_model(sample_task):
    primary_client = Mock()
    primary_client.achat = AsyncMock(side_effect=RuntimeError("RateLimitError: openai overloaded"))
    fallback_client = Mock()
    fallback_client.achat = AsyncMock(
        return_value={
            "content": "Recovered on fallback",
            "cost_usd": 0.002,
            "total_tokens": 20,
            "tool_calls": None,
            "raw_message": {"role": "assistant", "content": "Recovered on fallback"},
        }
    )

    def client_factory(*, model_name, api_key=None):
        if model_name == "gpt-4o":
            return primary_client
        if model_name == "claude-3-opus-20240229":
            return fallback_client
        raise AssertionError(f"Unexpected model_name: {model_name}")

    soul = Soul(
        id="test_soul",
        kind="soul",
        name="Test Agent",
        role="Test Agent",
        system_prompt="You are a helpful test agent.",
        model_name="gpt-4o",
        provider="openai",
    )

    with patch("runsight_core.runner.LiteLLMClient", side_effect=client_factory):
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
        result = await runner.execute_task(sample_task, soul)

    assert result.output == "Recovered on fallback"
    primary_client.achat.assert_awaited_once()
    fallback_client.achat.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_task_does_not_fail_over_on_authentication_error(sample_task):
    primary_client = Mock()
    primary_client.achat = AsyncMock(
        side_effect=RuntimeError("AuthenticationError: invalid api key")
    )
    fallback_client = Mock()
    fallback_client.achat = AsyncMock(
        return_value={
            "content": "Should not run",
            "cost_usd": 0.002,
            "total_tokens": 20,
            "tool_calls": None,
            "raw_message": {"role": "assistant", "content": "Should not run"},
        }
    )

    def client_factory(*, model_name, api_key=None):
        if model_name == "gpt-4o":
            return primary_client
        if model_name == "claude-3-opus-20240229":
            return fallback_client
        raise AssertionError(f"Unexpected model_name: {model_name}")

    soul = Soul(
        id="test_soul",
        kind="soul",
        name="Test Agent",
        role="Test Agent",
        system_prompt="You are a helpful test agent.",
        model_name="gpt-4o",
        provider="openai",
    )

    with patch("runsight_core.runner.LiteLLMClient", side_effect=client_factory):
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
            await runner.execute_task(sample_task, soul)

    primary_client.achat.assert_awaited_once()
    fallback_client.achat.assert_not_awaited()
