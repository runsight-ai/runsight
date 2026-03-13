import pytest
from unittest.mock import patch

from runsight_core.primitives import Soul, Task
from runsight_core.runner import RunsightTeamRunner, ExecutionResult


@pytest.fixture
def sample_soul():
    return Soul(id="test_soul", role="Test Agent", system_prompt="You are a helpful test agent.")


@pytest.fixture
def sample_task():
    return Task(id="test_task", instruction="Say hello.", context="This is a test context.")


@pytest.mark.asyncio
@patch("runsight_core.runner.LiteLLMClient.achat")
async def test_execute_task(mock_achat, sample_soul, sample_task):
    mock_achat.return_value = {
        "content": "Hello!",
        "cost_usd": 0.001,
        "total_tokens": 10,
    }

    runner = RunsightTeamRunner(model_name="test-model")
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
@patch("runsight_core.runner.LiteLLMClient.astream_chat")
async def test_stream_task(mock_astream_chat, sample_soul, sample_task):
    async def mock_stream_response(*args, **kwargs):
        yield "Hel"
        yield "lo!"

    mock_astream_chat.side_effect = mock_stream_response

    runner = RunsightTeamRunner(model_name="test-model")
    chunks = []
    async for chunk in runner.stream_task(sample_task, sample_soul):
        chunks.append(chunk)

    assert chunks == ["Hel", "lo!"]
    mock_astream_chat.assert_called_once()
