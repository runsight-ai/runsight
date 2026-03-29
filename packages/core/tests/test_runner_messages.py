"""
Tests for RUN-188: Runner messages parameter for multi-turn conversations.

Verifies that execute_task() and stream_task() accept an optional
`messages` parameter (history) that is prepended to the current user message
before being sent to the LLM client.
"""

import pytest
from unittest.mock import patch

from runsight_core.primitives import Soul, Task
from runsight_core.runner import RunsightTeamRunner


@pytest.fixture
def soul():
    return Soul(id="s1", role="Agent", system_prompt="You are helpful.")


@pytest.fixture
def task():
    return Task(id="t1", instruction="What next?", context="Some context.")


HISTORY_MESSAGES = [
    {"role": "user", "content": "Hello"},
    {"role": "assistant", "content": "Hi there! How can I help?"},
]


# ---------------------------------------------------------------------------
# execute_task with history messages
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("runsight_core.runner.LiteLLMClient.achat")
async def test_execute_task_with_history_sends_merged_messages(mock_achat, soul, task):
    """When messages=[2 history msgs], client receives 3-message array
    (2 history + 1 new user). LLM will see 4 total (system prepended by client)."""
    mock_achat.return_value = {
        "content": "Sure!",
        "cost_usd": 0.0,
        "total_tokens": 5,
    }

    runner = RunsightTeamRunner(model_name="test-model")
    await runner.execute_task(task, soul, messages=HISTORY_MESSAGES)

    mock_achat.assert_called_once()
    sent_messages = mock_achat.call_args.kwargs["messages"]

    # 2 history + 1 new user = 3 messages sent to client
    assert len(sent_messages) == 3
    # First two are history, preserved in order
    assert sent_messages[0] == {"role": "user", "content": "Hello"}
    assert sent_messages[1] == {"role": "assistant", "content": "Hi there! How can I help?"}
    # Last is the new user message built from the task
    assert sent_messages[2]["role"] == "user"
    assert "What next?" in sent_messages[2]["content"]


# ---------------------------------------------------------------------------
# execute_task backward compatibility (no messages param)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("runsight_core.runner.LiteLLMClient.achat")
async def test_execute_task_without_messages_is_backward_compatible(mock_achat, soul, task):
    """Calling without messages param sends a single-message array (unchanged behavior)."""
    mock_achat.return_value = {
        "content": "Ok",
        "cost_usd": 0.0,
        "total_tokens": 3,
    }

    runner = RunsightTeamRunner(model_name="test-model")
    await runner.execute_task(task, soul)

    sent_messages = mock_achat.call_args.kwargs["messages"]
    assert len(sent_messages) == 1
    assert sent_messages[0]["role"] == "user"


# ---------------------------------------------------------------------------
# execute_task with empty messages list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("runsight_core.runner.LiteLLMClient.achat")
async def test_execute_task_with_empty_messages_same_as_none(mock_achat, soul, task):
    """messages=[] should behave the same as messages=None (single user message)."""
    mock_achat.return_value = {
        "content": "Ok",
        "cost_usd": 0.0,
        "total_tokens": 3,
    }

    runner = RunsightTeamRunner(model_name="test-model")
    await runner.execute_task(task, soul, messages=[])

    sent_messages = mock_achat.call_args.kwargs["messages"]
    assert len(sent_messages) == 1
    assert sent_messages[0]["role"] == "user"


# ---------------------------------------------------------------------------
# stream_task with history messages
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("runsight_core.runner.LiteLLMClient.astream_chat")
async def test_stream_task_with_history_sends_merged_messages(mock_astream, soul, task):
    """stream_task with messages=[2 history msgs] sends 3-message array to client."""

    async def mock_gen(*args, **kwargs):
        yield "token"

    mock_astream.side_effect = mock_gen

    runner = RunsightTeamRunner(model_name="test-model")
    chunks = []
    async for chunk in runner.stream_task(task, soul, messages=HISTORY_MESSAGES):
        chunks.append(chunk)

    assert chunks == ["token"]

    mock_astream.assert_called_once()
    sent_messages = mock_astream.call_args.kwargs["messages"]

    assert len(sent_messages) == 3
    assert sent_messages[0] == {"role": "user", "content": "Hello"}
    assert sent_messages[1] == {"role": "assistant", "content": "Hi there! How can I help?"}
    assert sent_messages[2]["role"] == "user"
    assert "What next?" in sent_messages[2]["content"]


# ---------------------------------------------------------------------------
# stream_task backward compatibility
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("runsight_core.runner.LiteLLMClient.astream_chat")
async def test_stream_task_without_messages_is_backward_compatible(mock_astream, soul, task):
    """Calling stream_task without messages sends single-message array."""

    async def mock_gen(*args, **kwargs):
        yield "ok"

    mock_astream.side_effect = mock_gen

    runner = RunsightTeamRunner(model_name="test-model")
    async for _ in runner.stream_task(task, soul):
        pass

    sent_messages = mock_astream.call_args.kwargs["messages"]
    assert len(sent_messages) == 1
    assert sent_messages[0]["role"] == "user"


# ---------------------------------------------------------------------------
# stream_task with empty messages list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("runsight_core.runner.LiteLLMClient.astream_chat")
async def test_stream_task_with_empty_messages_same_as_none(mock_astream, soul, task):
    """stream_task with messages=[] behaves same as None."""

    async def mock_gen(*args, **kwargs):
        yield "ok"

    mock_astream.side_effect = mock_gen

    runner = RunsightTeamRunner(model_name="test-model")
    async for _ in runner.stream_task(task, soul, messages=[]):
        pass

    sent_messages = mock_astream.call_args.kwargs["messages"]
    assert len(sent_messages) == 1
    assert sent_messages[0]["role"] == "user"
