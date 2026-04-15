"""
RUN-278 — Red tests: Agentic tool loop in RunsightTeamRunner.execute_task().

These tests verify that execute_task() implements an agentic tool-use loop when
the soul has resolved_tools, including:
  AC1: Single-shot path unchanged when no tools
  AC2: Tool loop — LLM calls tool -> executed -> result fed back -> LLM responds
  AC3: Max iterations enforced, last iteration strips tools
  AC4: Cost/tokens accumulated correctly across iterations
  AC5: Tool errors fed back as strings (loop continues)
  AC6: Unknown tool name -> error message to LLM
  AC7: ExecutionResult.tool_iterations and tool_calls_made populated

All tests mock LiteLLMClient.achat() to avoid real API calls.
"""

from unittest.mock import AsyncMock, patch

import pytest
from runsight_core.primitives import Soul
from runsight_core.runner import ExecutionResult, RunsightTeamRunner

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_soul(
    resolved_tools=None,
    max_tool_iterations: int = 5,
    **kwargs,
) -> Soul:
    """Build a Soul with optional resolved_tools."""
    defaults = {
        "id": "test_soul",
        "kind": "soul",
        "name": "Test Agent",
        "role": "Test Agent",
        "system_prompt": "You are a test agent.",
        "provider": "openai",
        "model_name": "gpt-4o",
    }
    defaults.update(kwargs)
    soul = Soul(**defaults, max_tool_iterations=max_tool_iterations)
    soul.resolved_tools = resolved_tools
    return soul


def _make_tool_instance(name: str = "get_weather", execute_fn=None):
    """Create a mock ToolInstance-like object with name, execute, to_openai_schema."""
    from unittest.mock import MagicMock

    tool = MagicMock()
    tool.name = name
    tool.description = f"A tool called {name}"
    tool.parameters = {"type": "object", "properties": {}}

    if execute_fn is not None:
        tool.execute = execute_fn
    else:
        tool.execute = AsyncMock(return_value="tool result for " + name)

    tool.to_openai_schema.return_value = {
        "type": "function",
        "function": {
            "name": name,
            "description": f"A tool called {name}",
            "parameters": {"type": "object", "properties": {}},
        },
    }
    return tool


def _achat_text_response(
    content: str = "Final answer.",
    cost_usd: float = 0.001,
    total_tokens: int = 10,
):
    """A plain text response with no tool_calls."""
    return {
        "content": content,
        "cost_usd": cost_usd,
        "prompt_tokens": 5,
        "completion_tokens": 5,
        "total_tokens": total_tokens,
        "tool_calls": None,
        "finish_reason": "stop",
        "raw_message": {"role": "assistant", "content": content},
    }


def _achat_tool_response(
    tool_name: str = "get_weather",
    call_id: str = "call_001",
    arguments: str = '{"location": "Paris"}',
    cost_usd: float = 0.002,
    total_tokens: int = 20,
):
    """A response where the LLM calls a tool."""
    tool_call = {
        "id": call_id,
        "type": "function",
        "function": {
            "name": tool_name,
            "arguments": arguments,
        },
    }
    return {
        "content": "",
        "cost_usd": cost_usd,
        "prompt_tokens": 10,
        "completion_tokens": 10,
        "total_tokens": total_tokens,
        "tool_calls": [tool_call],
        "finish_reason": "tool_calls",
        "raw_message": {
            "role": "assistant",
            "content": "",
            "tool_calls": [tool_call],
        },
    }


# ---------------------------------------------------------------------------
# AC1: Single-shot path unchanged when no tools
# ---------------------------------------------------------------------------


class TestSingleShotNoTools:
    """When soul has no resolved_tools (None or empty), execute_task must
    behave exactly as before — single achat() call, no tool loop."""

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_no_resolved_tools_single_call(self, mock_achat):
        """Soul without resolved_tools: achat called once, returns text."""
        mock_achat.return_value = _achat_text_response(content="Hello!")
        soul = _make_soul(resolved_tools=None)

        runner = RunsightTeamRunner(model_name="test-model")
        result = await runner.execute("Do something.", None, soul)

        assert isinstance(result, ExecutionResult)
        assert result.output == "Hello!"
        mock_achat.assert_called_once()

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_empty_resolved_tools_single_call(self, mock_achat):
        """Soul with empty resolved_tools list: same as no tools."""
        mock_achat.return_value = _achat_text_response(content="Hello!")
        soul = _make_soul(resolved_tools=[])

        runner = RunsightTeamRunner(model_name="test-model")
        result = await runner.execute("Do something.", None, soul)

        assert isinstance(result, ExecutionResult)
        assert result.output == "Hello!"
        mock_achat.assert_called_once()

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_no_tools_does_not_pass_tools_to_achat(self, mock_achat):
        """Without resolved_tools, achat must NOT receive tools kwarg."""
        mock_achat.return_value = _achat_text_response()
        soul = _make_soul(resolved_tools=None)

        runner = RunsightTeamRunner(model_name="test-model")
        await runner.execute("Do something.", None, soul)

        call_kwargs = mock_achat.call_args.kwargs
        assert "tools" not in call_kwargs or call_kwargs.get("tools") is None


# ---------------------------------------------------------------------------
# AC2: Tool loop — LLM calls tool -> executed -> result fed back -> LLM text
# ---------------------------------------------------------------------------


class TestToolLoopBasic:
    """When soul has resolved_tools, execute_task must enter an agentic loop:
    send tools to LLM, execute tool_calls, feed results back, repeat."""

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_one_tool_call_then_text(self, mock_achat):
        """LLM calls tool once, then responds with text. Two achat calls total."""
        tool = _make_tool_instance("get_weather")
        soul = _make_soul(resolved_tools=[tool])

        # First call: LLM requests tool; second call: LLM returns text
        mock_achat.side_effect = [
            _achat_tool_response(tool_name="get_weather", call_id="call_1"),
            _achat_text_response(content="The weather is sunny."),
        ]

        runner = RunsightTeamRunner(model_name="test-model")
        result = await runner.execute("Do something.", None, soul)

        assert result.output == "The weather is sunny."
        assert mock_achat.call_count == 2

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_tool_execute_called_with_parsed_args(self, mock_achat):
        """Tool's execute() must be called with parsed arguments from function.arguments."""
        tool = _make_tool_instance("get_weather")
        soul = _make_soul(resolved_tools=[tool])

        mock_achat.side_effect = [
            _achat_tool_response(
                tool_name="get_weather",
                arguments='{"location": "Paris"}',
            ),
            _achat_text_response(),
        ]

        runner = RunsightTeamRunner(model_name="test-model")
        await runner.execute("Do something.", None, soul)

        tool.execute.assert_called_once()
        call_args = tool.execute.call_args
        # The parsed arguments should be passed to execute
        passed_args = call_args[0][0] if call_args[0] else call_args[1]
        assert passed_args == {"location": "Paris"} or "location" in str(passed_args)

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_tool_result_fed_back_as_tool_message(self, mock_achat):
        """After tool execution, result must be fed back as a tool message."""
        tool = _make_tool_instance("get_weather")
        tool.execute = AsyncMock(return_value="Sunny, 25C")
        soul = _make_soul(resolved_tools=[tool])

        mock_achat.side_effect = [
            _achat_tool_response(tool_name="get_weather", call_id="call_abc"),
            _achat_text_response(),
        ]

        runner = RunsightTeamRunner(model_name="test-model")
        await runner.execute("Do something.", None, soul)

        # Second achat call should include the tool result message
        second_call_messages = mock_achat.call_args_list[1].kwargs.get(
            "messages",
            mock_achat.call_args_list[1][0][0] if mock_achat.call_args_list[1][0] else None,
        )
        assert second_call_messages is not None

        # Find the tool result message
        tool_messages = [m for m in second_call_messages if m.get("role") == "tool"]
        assert len(tool_messages) >= 1
        assert tool_messages[0]["tool_call_id"] == "call_abc"
        assert tool_messages[0]["content"] == "Sunny, 25C"

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_assistant_raw_message_appended_before_tool_result(self, mock_achat):
        """The raw assistant message (with tool_calls) must be appended to messages
        before the tool result message."""
        tool = _make_tool_instance("get_weather")
        soul = _make_soul(resolved_tools=[tool])

        tool_response = _achat_tool_response(tool_name="get_weather", call_id="call_x")
        mock_achat.side_effect = [tool_response, _achat_text_response()]

        runner = RunsightTeamRunner(model_name="test-model")
        await runner.execute("Do something.", None, soul)

        # Second call messages should include the raw_message from first response
        second_call_messages = mock_achat.call_args_list[1].kwargs.get(
            "messages",
            mock_achat.call_args_list[1][0][0] if mock_achat.call_args_list[1][0] else None,
        )
        # Find assistant message with tool_calls
        assistant_msgs = [m for m in second_call_messages if m.get("role") == "assistant"]
        assert len(assistant_msgs) >= 1
        assert "tool_calls" in assistant_msgs[-1]

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_tools_schema_passed_to_achat(self, mock_achat):
        """When tools are available, achat must receive the tool schemas."""
        tool = _make_tool_instance("get_weather")
        soul = _make_soul(resolved_tools=[tool])

        mock_achat.side_effect = [
            _achat_text_response(content="No tools needed."),
        ]

        runner = RunsightTeamRunner(model_name="test-model")
        await runner.execute("Do something.", None, soul)

        call_kwargs = mock_achat.call_args.kwargs
        assert "tools" in call_kwargs
        assert call_kwargs["tools"] == [tool.to_openai_schema()]


# ---------------------------------------------------------------------------
# AC2 continued: Multi-iteration tool loop
# ---------------------------------------------------------------------------


class TestToolLoopMultiIteration:
    """LLM may call tools multiple times before responding with text."""

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_two_tool_iterations_then_text(self, mock_achat):
        """LLM calls tools twice before final text. Three achat calls total."""
        tool = _make_tool_instance("search")
        soul = _make_soul(resolved_tools=[tool])

        mock_achat.side_effect = [
            _achat_tool_response(tool_name="search", call_id="call_1"),
            _achat_tool_response(tool_name="search", call_id="call_2"),
            _achat_text_response(content="Found it."),
        ]

        runner = RunsightTeamRunner(model_name="test-model")
        result = await runner.execute("Do something.", None, soul)

        assert result.output == "Found it."
        assert mock_achat.call_count == 3


# ---------------------------------------------------------------------------
# AC3: Max iterations enforced, last iteration strips tools
# ---------------------------------------------------------------------------


class TestMaxIterations:
    """When the LLM keeps calling tools, the loop must stop at max_tool_iterations.
    On the last iteration, tools must be stripped to force a text response."""

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_max_iterations_stops_loop(self, mock_achat):
        """With max_tool_iterations=2, loop runs at most 2 iterations plus a
        final forced text call."""
        tool = _make_tool_instance("search")
        soul = _make_soul(resolved_tools=[tool], max_tool_iterations=2)

        # Two tool iterations, then the forced-text final call
        mock_achat.side_effect = [
            _achat_tool_response(tool_name="search", call_id="call_1"),
            _achat_tool_response(tool_name="search", call_id="call_2"),
            _achat_text_response(content="Gave up, here is what I have."),
        ]

        runner = RunsightTeamRunner(model_name="test-model")
        result = await runner.execute("Do something.", None, soul)

        assert result.output == "Gave up, here is what I have."

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_last_iteration_strips_tools(self, mock_achat):
        """On the last iteration (iteration == max - 1), tools must be passed
        as empty list to force a text response."""
        tool = _make_tool_instance("search")
        soul = _make_soul(resolved_tools=[tool], max_tool_iterations=1)

        # First call: iteration 0 (last iteration since max=1), tools stripped
        mock_achat.side_effect = [
            _achat_text_response(content="Direct answer."),
        ]

        runner = RunsightTeamRunner(model_name="test-model")
        await runner.execute("Do something.", None, soul)

        # The call on the last iteration should have tools=[]
        call_kwargs = mock_achat.call_args_list[0].kwargs
        assert call_kwargs.get("tools") == []

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_non_last_iteration_has_tools(self, mock_achat):
        """Before the last iteration, tools must be provided normally."""
        tool = _make_tool_instance("search")
        soul = _make_soul(resolved_tools=[tool], max_tool_iterations=3)

        mock_achat.side_effect = [
            _achat_tool_response(tool_name="search", call_id="call_1"),
            _achat_text_response(content="Done."),
        ]

        runner = RunsightTeamRunner(model_name="test-model")
        await runner.execute("Do something.", None, soul)

        # First call (iteration 0, not last) should have real tools
        first_call_kwargs = mock_achat.call_args_list[0].kwargs
        assert first_call_kwargs.get("tools") == [tool.to_openai_schema()]


# ---------------------------------------------------------------------------
# AC4: Cost/tokens accumulated across iterations
# ---------------------------------------------------------------------------


class TestCostAccumulation:
    """Cost and token counts must sum across all achat() calls in the loop."""

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_cost_accumulated_across_iterations(self, mock_achat):
        """Two iterations: costs must sum."""
        tool = _make_tool_instance("search")
        soul = _make_soul(resolved_tools=[tool])

        mock_achat.side_effect = [
            _achat_tool_response(tool_name="search", cost_usd=0.003, total_tokens=30),
            _achat_text_response(content="Done.", cost_usd=0.002, total_tokens=20),
        ]

        runner = RunsightTeamRunner(model_name="test-model")
        result = await runner.execute("Do something.", None, soul)

        assert result.cost_usd == pytest.approx(0.005)
        assert result.total_tokens == 50

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_cost_accumulated_three_iterations(self, mock_achat):
        """Three iterations: costs must sum from all calls."""
        tool = _make_tool_instance("search")
        soul = _make_soul(resolved_tools=[tool])

        mock_achat.side_effect = [
            _achat_tool_response(tool_name="search", cost_usd=0.001, total_tokens=10),
            _achat_tool_response(tool_name="search", cost_usd=0.002, total_tokens=20),
            _achat_text_response(content="All done.", cost_usd=0.003, total_tokens=30),
        ]

        runner = RunsightTeamRunner(model_name="test-model")
        result = await runner.execute("Do something.", None, soul)

        assert result.cost_usd == pytest.approx(0.006)
        assert result.total_tokens == 60

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_single_shot_cost_unchanged(self, mock_achat):
        """Single-shot (no tools) cost must still work correctly."""
        mock_achat.return_value = _achat_text_response(cost_usd=0.005, total_tokens=100)
        soul = _make_soul(resolved_tools=None)

        runner = RunsightTeamRunner(model_name="test-model")
        result = await runner.execute("Do something.", None, soul)

        assert result.cost_usd == pytest.approx(0.005)
        assert result.total_tokens == 100


# ---------------------------------------------------------------------------
# AC5: Tool errors fed back as strings (loop continues)
# ---------------------------------------------------------------------------


class TestToolErrorHandling:
    """When tool.execute() raises an exception, the error must be fed back
    to the LLM as a string and the loop must continue."""

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_tool_exception_fed_back_as_string(self, mock_achat):
        """Tool raises RuntimeError -> error string sent as tool message, loop continues."""
        tool = _make_tool_instance("failing_tool")
        tool.execute = AsyncMock(side_effect=RuntimeError("Connection timeout"))
        soul = _make_soul(resolved_tools=[tool])

        mock_achat.side_effect = [
            _achat_tool_response(tool_name="failing_tool", call_id="call_err"),
            _achat_text_response(content="I encountered an error."),
        ]

        runner = RunsightTeamRunner(model_name="test-model")
        result = await runner.execute("Do something.", None, soul)

        # Loop should continue and return final text
        assert result.output == "I encountered an error."
        assert mock_achat.call_count == 2

        # The tool message fed back should contain the error
        second_call_messages = mock_achat.call_args_list[1].kwargs.get(
            "messages",
            mock_achat.call_args_list[1][0][0] if mock_achat.call_args_list[1][0] else None,
        )
        tool_messages = [m for m in second_call_messages if m.get("role") == "tool"]
        assert len(tool_messages) >= 1
        assert "Connection timeout" in tool_messages[0]["content"]

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_tool_error_does_not_crash_loop(self, mock_achat):
        """After tool error, LLM can call another tool successfully."""
        error_tool = _make_tool_instance("bad_tool")
        error_tool.execute = AsyncMock(side_effect=ValueError("Bad input"))

        good_tool = _make_tool_instance("good_tool")
        good_tool.execute = AsyncMock(return_value="Success!")

        soul = _make_soul(resolved_tools=[error_tool, good_tool])

        mock_achat.side_effect = [
            _achat_tool_response(tool_name="bad_tool", call_id="call_1"),
            _achat_tool_response(tool_name="good_tool", call_id="call_2"),
            _achat_text_response(content="Recovered."),
        ]

        runner = RunsightTeamRunner(model_name="test-model")
        result = await runner.execute("Do something.", None, soul)

        assert result.output == "Recovered."
        assert mock_achat.call_count == 3


# ---------------------------------------------------------------------------
# AC6: Unknown tool name -> error message to LLM
# ---------------------------------------------------------------------------


class TestUnknownTool:
    """When the LLM calls a tool name that is not in resolved_tools,
    an error message must be fed back (not a crash)."""

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_unknown_tool_error_fed_back(self, mock_achat):
        """LLM calls 'nonexistent_tool' not in resolved_tools -> error message."""
        tool = _make_tool_instance("get_weather")
        soul = _make_soul(resolved_tools=[tool])

        mock_achat.side_effect = [
            _achat_tool_response(tool_name="nonexistent_tool", call_id="call_unknown"),
            _achat_text_response(content="Sorry, I tried a wrong tool."),
        ]

        runner = RunsightTeamRunner(model_name="test-model")
        result = await runner.execute("Do something.", None, soul)

        assert result.output == "Sorry, I tried a wrong tool."
        assert mock_achat.call_count == 2

        # Verify error message was fed back
        second_call_messages = mock_achat.call_args_list[1].kwargs.get(
            "messages",
            mock_achat.call_args_list[1][0][0] if mock_achat.call_args_list[1][0] else None,
        )
        tool_messages = [m for m in second_call_messages if m.get("role") == "tool"]
        assert len(tool_messages) >= 1
        # Error should mention the unknown tool name
        assert (
            "nonexistent_tool" in tool_messages[0]["content"].lower()
            or "unknown" in tool_messages[0]["content"].lower()
        )

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_unknown_tool_does_not_crash(self, mock_achat):
        """Unknown tool must not raise an exception — loop continues."""
        tool = _make_tool_instance("real_tool")
        soul = _make_soul(resolved_tools=[tool])

        mock_achat.side_effect = [
            _achat_tool_response(tool_name="fake_tool", call_id="call_1"),
            _achat_text_response(content="Corrected."),
        ]

        runner = RunsightTeamRunner(model_name="test-model")
        # Must not raise
        result = await runner.execute("Do something.", None, soul)
        assert result.output == "Corrected."


# ---------------------------------------------------------------------------
# AC7: ExecutionResult.tool_iterations and tool_calls_made populated
# ---------------------------------------------------------------------------


class TestExecutionResultToolFields:
    """ExecutionResult must include tool_iterations (int) and
    tool_calls_made (list of tool names) fields."""

    def test_execution_result_has_tool_iterations_field(self):
        """ExecutionResult model must accept tool_iterations field."""
        result = ExecutionResult(
            task_id="t1",
            soul_id="s1",
            output="done",
            tool_iterations=3,
        )
        assert result.tool_iterations == 3

    def test_execution_result_has_tool_calls_made_field(self):
        """ExecutionResult model must accept tool_calls_made field."""
        result = ExecutionResult(
            task_id="t1",
            soul_id="s1",
            output="done",
            tool_calls_made=["get_weather", "search"],
        )
        assert result.tool_calls_made == ["get_weather", "search"]

    def test_execution_result_tool_iterations_default_zero(self):
        """tool_iterations must default to 0."""
        result = ExecutionResult(task_id="t1", soul_id="s1", output="done")
        assert result.tool_iterations == 0

    def test_execution_result_tool_calls_made_default_empty(self):
        """tool_calls_made must default to empty list."""
        result = ExecutionResult(task_id="t1", soul_id="s1", output="done")
        assert result.tool_calls_made == []

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_tool_iterations_count_populated(self, mock_achat):
        """After tool loop, tool_iterations must reflect actual iteration count."""
        tool = _make_tool_instance("search")
        soul = _make_soul(resolved_tools=[tool])

        mock_achat.side_effect = [
            _achat_tool_response(tool_name="search", call_id="call_1"),
            _achat_tool_response(tool_name="search", call_id="call_2"),
            _achat_text_response(content="Done."),
        ]

        runner = RunsightTeamRunner(model_name="test-model")
        result = await runner.execute("Do something.", None, soul)

        assert result.tool_iterations == 2

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_tool_calls_made_list_populated(self, mock_achat):
        """After tool loop, tool_calls_made must list all tool names called."""
        weather_tool = _make_tool_instance("get_weather")
        search_tool = _make_tool_instance("search")
        soul = _make_soul(resolved_tools=[weather_tool, search_tool])

        mock_achat.side_effect = [
            _achat_tool_response(tool_name="get_weather", call_id="call_1"),
            _achat_tool_response(tool_name="search", call_id="call_2"),
            _achat_text_response(content="Done."),
        ]

        runner = RunsightTeamRunner(model_name="test-model")
        result = await runner.execute("Do something.", None, soul)

        assert "get_weather" in result.tool_calls_made
        assert "search" in result.tool_calls_made
        assert len(result.tool_calls_made) == 2

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_no_tools_zero_iterations(self, mock_achat):
        """Single-shot (no tools) must have tool_iterations=0 and empty tool_calls_made."""
        mock_achat.return_value = _achat_text_response()
        soul = _make_soul(resolved_tools=None)

        runner = RunsightTeamRunner(model_name="test-model")
        result = await runner.execute("Do something.", None, soul)

        assert result.tool_iterations == 0
        assert result.tool_calls_made == []
