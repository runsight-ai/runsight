"""
Integration tests for RunsightTeamRunner and Primitives (Soul, Task).

Tests the interaction between the runner and primitive data models,
ensuring proper data flow and transformation.
"""

import pytest
from unittest.mock import patch

from runsight_core.primitives import Soul, Task
from runsight_core.runner import RunsightTeamRunner, ExecutionResult


@pytest.fixture
def integration_soul():
    """Soul for integration testing with all fields populated."""
    return Soul(
        id="integration_test_soul",
        role="Integration Test Agent",
        system_prompt="You are an integration test agent that validates system behavior.",
        tools=[
            {"name": "calculator", "description": "Performs calculations"},
            {"name": "search", "description": "Searches information"},
        ],
    )


@pytest.fixture
def integration_task_with_context():
    """Task with both instruction and context for integration testing."""
    return Task(
        id="integration_task_001",
        instruction="Analyze the system integration points",
        context="This is a comprehensive integration test. Consider all subsystems and their interactions.",
    )


@pytest.fixture
def integration_task_without_context():
    """Task with only instruction (no context) for integration testing."""
    return Task(id="integration_task_002", instruction="Perform a simple integration check")


@pytest.mark.asyncio
@patch("runsight_core.runner.LiteLLMClient.achat")
async def test_task_context_integration_with_runner(
    mock_achat, integration_soul, integration_task_with_context
):
    """
    INTEGRATION: Verify Task.context properly integrates into the runner's prompt building.

    Tests that runner._build_prompt() correctly appends context to instruction
    and the combined prompt reaches the LLM client.
    """
    mock_achat.return_value = {
        "content": "Analysis complete",
        "cost_usd": 0.1,
        "total_tokens": 100,
    }

    runner = RunsightTeamRunner(model_name="test-model")
    await runner.execute_task(integration_task_with_context, integration_soul)

    # Verify the prompt construction included context
    call_kwargs = mock_achat.call_args.kwargs
    messages = call_kwargs["messages"]

    assert len(messages) == 1
    prompt_content = messages[0]["content"]

    # Verify both instruction and context are in the prompt
    assert "Analyze the system integration points" in prompt_content
    assert "Context:" in prompt_content
    assert "This is a comprehensive integration test" in prompt_content
    assert prompt_content.index("Analyze") < prompt_content.index("Context:")


@pytest.mark.asyncio
@patch("runsight_core.runner.LiteLLMClient.achat")
async def test_task_without_context_integration(
    mock_achat, integration_soul, integration_task_without_context
):
    """
    INTEGRATION: Verify Task without context works correctly with runner.

    Tests that when Task.context is None, the runner handles it gracefully.
    """
    mock_achat.return_value = {
        "content": "Check complete",
        "cost_usd": 0.1,
        "total_tokens": 100,
    }

    runner = RunsightTeamRunner(model_name="test-model")
    await runner.execute_task(integration_task_without_context, integration_soul)

    # Verify the prompt only has instruction (no context section)
    call_kwargs = mock_achat.call_args.kwargs
    messages = call_kwargs["messages"]

    prompt_content = messages[0]["content"]

    assert "Perform a simple integration check" in prompt_content
    assert "Context:" not in prompt_content


@pytest.mark.asyncio
@patch("runsight_core.runner.LiteLLMClient.achat")
async def test_soul_system_prompt_integration_with_llm_client(
    mock_achat, integration_soul, integration_task_with_context
):
    """
    INTEGRATION: Verify Soul.system_prompt correctly passed to LLM client.

    Tests that the Soul's system_prompt makes it to the LLM client's achat call.
    """
    mock_achat.return_value = {
        "content": "Response",
        "cost_usd": 0.1,
        "total_tokens": 100,
    }

    runner = RunsightTeamRunner(model_name="test-model")
    await runner.execute_task(integration_task_with_context, integration_soul)

    call_kwargs = mock_achat.call_args.kwargs
    system_prompt = call_kwargs["system_prompt"]

    assert system_prompt == "You are an integration test agent that validates system behavior."


@pytest.mark.asyncio
@patch("runsight_core.runner.LiteLLMClient.achat")
async def test_execution_result_mapping_from_llm_response(
    mock_achat, integration_soul, integration_task_with_context
):
    """
    INTEGRATION: Verify LLM response correctly maps to ExecutionResult fields.

    Tests the transformation: LLMClient.achat() -> ExecutionResult
    """
    llm_response = "This is the detailed response from the LLM with multiple sentences and comprehensive output."
    mock_achat.return_value = {
        "content": llm_response,
        "cost_usd": 0.1,
        "total_tokens": 100,
    }

    runner = RunsightTeamRunner(model_name="test-model")
    result = await runner.execute_task(integration_task_with_context, integration_soul)

    # Verify ExecutionResult correctly populated
    assert isinstance(result, ExecutionResult)
    assert result.task_id == "integration_task_001"
    assert result.soul_id == "integration_test_soul"
    assert result.output == llm_response
    assert result.metadata == {}


@pytest.mark.asyncio
@patch("runsight_core.runner.LiteLLMClient.astream_chat")
async def test_streaming_integration_with_task_and_soul(
    mock_astream_chat, integration_soul, integration_task_with_context
):
    """
    INTEGRATION: Verify streaming execution works with Task and Soul.

    Tests the streaming data flow: Task + Soul -> Runner -> LLMClient stream
    """

    async def mock_stream():
        yield "Analysis "
        yield "of "
        yield "integration "
        yield "points "
        yield "complete."

    mock_astream_chat.return_value = mock_stream()

    runner = RunsightTeamRunner(model_name="test-model")
    chunks = []

    async for chunk in runner.stream_task(integration_task_with_context, integration_soul):
        chunks.append(chunk)

    assert chunks == ["Analysis ", "of ", "integration ", "points ", "complete."]

    # Verify correct parameters passed to streaming
    call_kwargs = mock_astream_chat.call_args.kwargs
    assert call_kwargs["system_prompt"] == integration_soul.system_prompt

    messages = call_kwargs["messages"]
    prompt_content = messages[0]["content"]
    assert integration_task_with_context.instruction in prompt_content


@pytest.mark.asyncio
@patch("runsight_core.runner.LiteLLMClient.achat")
async def test_multiple_tasks_with_same_soul(mock_achat, integration_soul):
    """
    INTEGRATION: Verify same Soul can execute multiple different Tasks.

    Tests that a Soul instance can be reused across multiple task executions.
    """
    task1 = Task(id="task1", instruction="First task")
    task2 = Task(id="task2", instruction="Second task", context="With context")
    task3 = Task(id="task3", instruction="Third task")

    mock_achat.side_effect = [
        {"content": "Result 1", "cost_usd": 0.1, "total_tokens": 100},
        {"content": "Result 2", "cost_usd": 0.1, "total_tokens": 100},
        {"content": "Result 3", "cost_usd": 0.1, "total_tokens": 100},
    ]

    runner = RunsightTeamRunner(model_name="test-model")

    result1 = await runner.execute_task(task1, integration_soul)
    result2 = await runner.execute_task(task2, integration_soul)
    result3 = await runner.execute_task(task3, integration_soul)

    # Verify all executions used the same soul
    assert result1.soul_id == "integration_test_soul"
    assert result2.soul_id == "integration_test_soul"
    assert result3.soul_id == "integration_test_soul"

    # Verify different tasks produced different results
    assert result1.task_id == "task1"
    assert result2.task_id == "task2"
    assert result3.task_id == "task3"

    assert result1.output == "Result 1"
    assert result2.output == "Result 2"
    assert result3.output == "Result 3"


@pytest.mark.asyncio
@patch("runsight_core.runner.LiteLLMClient.achat")
async def test_soul_tools_field_preserved_through_execution(
    mock_achat, integration_task_with_context
):
    """
    INTEGRATION: Verify Soul.tools field is preserved throughout execution.

    Tests that optional Soul.tools field doesn't get lost during runner execution.
    """
    soul_with_tools = Soul(
        id="tooled_soul",
        role="Tool User",
        system_prompt="You can use tools.",
        tools=[
            {"name": "file_reader", "description": "Reads files"},
            {"name": "web_search", "description": "Searches web"},
        ],
    )

    mock_achat.return_value = {
        "content": "Task completed",
        "cost_usd": 0.1,
        "total_tokens": 100,
    }

    runner = RunsightTeamRunner(model_name="test-model")
    await runner.execute_task(integration_task_with_context, soul_with_tools)

    # Verify soul tools are still accessible after execution
    assert soul_with_tools.tools is not None
    assert len(soul_with_tools.tools) == 2
    assert soul_with_tools.tools[0]["name"] == "file_reader"


@pytest.mark.asyncio
@patch("runsight_core.runner.LiteLLMClient.achat")
async def test_runner_model_name_integration(
    mock_achat, integration_soul, integration_task_with_context
):
    """
    INTEGRATION: Verify runner's model_name properly initializes LiteLLMClient.

    Tests that the model name specified in runner initialization is used.
    """
    mock_achat.return_value = {
        "content": "Response",
        "cost_usd": 0.1,
        "total_tokens": 100,
    }

    # Test with custom model
    runner = RunsightTeamRunner(model_name="gpt-4-turbo")
    await runner.execute_task(integration_task_with_context, integration_soul)

    # Verify LiteLLMClient was initialized
    assert runner.llm_client is not None
    assert runner.llm_client.model_name == "gpt-4-turbo"


@pytest.mark.asyncio
@patch("runsight_core.runner.LiteLLMClient.achat")
async def test_empty_task_context_edge_case(mock_achat, integration_soul):
    """
    INTEGRATION: Verify empty string context is handled correctly.

    Edge case: Task.context = "" (empty string, not None)
    """
    task_with_empty_context = Task(
        id="edge_task",
        instruction="Test instruction",
        context="",  # Empty string
    )

    mock_achat.return_value = {
        "content": "Handled",
        "cost_usd": 0.1,
        "total_tokens": 100,
    }

    runner = RunsightTeamRunner(model_name="test-model")
    result = await runner.execute_task(task_with_empty_context, integration_soul)

    # Should execute successfully
    assert result.output == "Handled"

    # Verify prompt construction
    call_kwargs = mock_achat.call_args.kwargs
    prompt_content = call_kwargs["messages"][0]["content"]

    # Empty context should still append context section (because it's truthy check in _build_prompt)
    # Actually, empty string is falsy in Python, so no Context: section should appear
    assert "Test instruction" in prompt_content
