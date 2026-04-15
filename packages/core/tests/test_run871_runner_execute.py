"""
Tests for RUN-871: Add execute() alongside execute_task() on RunsightTeamRunner.

Verifies:
  AC1: execute(instruction, context, soul) exists and returns ExecutionResult
  AC2: execute() handles both single-shot and agentic tool-loop paths
  AC3: execute_task() still works (delegates to execute() internally)
  AC4: execute_task() and execute() produce identical results for same inputs
  AC5: execute() builds prompt from instruction+context (same logic as _build_prompt)

These tests fail because RunsightTeamRunner.execute() does not exist yet.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from runsight_core.primitives import Soul
from runsight_core.runner import ExecutionResult, FallbackRoute, RunsightTeamRunner

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def soul():
    return Soul(
        id="soul-one",
        kind="soul",
        name="Agent",
        role="Agent",
        system_prompt="You are helpful.",
        provider="openai",
        model_name="gpt-4o",
    )


@pytest.fixture
def soul_with_temp():
    return Soul(
        id="soul-two",
        kind="soul",
        name="Configured Agent",
        role="Configured Agent",
        system_prompt="You are a configured agent.",
        provider="openai",
        model_name="gpt-4o",
        temperature=0.0,
        max_tokens=128,
    )


INSTRUCTION = "Say hello."
CONTEXT = "This is a test context."

HISTORY_MESSAGES = [
    {"role": "user", "content": "Previous turn."},
    {"role": "assistant", "content": "Understood."},
]


def _make_soul_with_tools(resolved_tools, max_tool_iterations: int = 5) -> Soul:
    soul = Soul(
        id="tool_soul",
        kind="soul",
        name="Tool Agent",
        role="Tool Agent",
        system_prompt="You use tools.",
        provider="openai",
        model_name="gpt-4o",
        max_tool_iterations=max_tool_iterations,
    )
    soul.resolved_tools = resolved_tools
    return soul


def _make_tool_instance(name: str = "get_weather"):
    from unittest.mock import MagicMock

    tool = MagicMock()
    tool.name = name
    tool.description = f"A tool called {name}"
    tool.parameters = {"type": "object", "properties": {}}
    tool.execute = AsyncMock(return_value=f"result from {name}")
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
    content: str = "Hello!",
    cost_usd: float = 0.001,
    total_tokens: int = 10,
) -> dict:
    return {
        "content": content,
        "cost_usd": cost_usd,
        "total_tokens": total_tokens,
        "tool_calls": None,
        "raw_message": {"role": "assistant", "content": content},
    }


def _achat_tool_response(
    tool_name: str = "get_weather",
    call_id: str = "call_001",
    arguments: str = "{}",
    cost_usd: float = 0.002,
    total_tokens: int = 20,
) -> dict:
    tool_call = {
        "id": call_id,
        "type": "function",
        "function": {"name": tool_name, "arguments": arguments},
    }
    return {
        "content": "",
        "cost_usd": cost_usd,
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
# AC1: execute() method exists and returns ExecutionResult
# ---------------------------------------------------------------------------


class TestExecuteMethodExists:
    """execute() must exist on RunsightTeamRunner and return ExecutionResult."""

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_execute_method_exists_on_runner(self, mock_achat, soul):
        """RunsightTeamRunner must have an execute() method."""
        mock_achat.return_value = _achat_text_response()
        runner = RunsightTeamRunner(model_name="gpt-4o")
        assert hasattr(runner, "execute"), "RunsightTeamRunner must have an execute() method"

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_execute_is_coroutine(self, mock_achat, soul):
        """execute() must be async (coroutine function)."""
        import inspect

        mock_achat.return_value = _achat_text_response()
        runner = RunsightTeamRunner(model_name="gpt-4o")
        assert inspect.iscoroutinefunction(runner.execute), (
            "execute() must be an async coroutine function"
        )

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_execute_returns_execution_result(self, mock_achat, soul):
        """execute(instruction, context, soul) must return an ExecutionResult."""
        mock_achat.return_value = _achat_text_response(content="Hello!")

        runner = RunsightTeamRunner(model_name="gpt-4o")
        result = await runner.execute(INSTRUCTION, CONTEXT, soul)

        assert isinstance(result, ExecutionResult)

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_execute_returns_correct_output(self, mock_achat, soul):
        """execute() output field must match LLM response content."""
        mock_achat.return_value = _achat_text_response(content="Hello!")

        runner = RunsightTeamRunner(model_name="gpt-4o")
        result = await runner.execute(INSTRUCTION, CONTEXT, soul)

        assert result.output == "Hello!"

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_execute_returns_correct_soul_id(self, mock_achat, soul):
        """execute() result soul_id must be the active soul's id."""
        mock_achat.return_value = _achat_text_response()

        runner = RunsightTeamRunner(model_name="gpt-4o")
        result = await runner.execute(INSTRUCTION, CONTEXT, soul)

        assert result.soul_id == "soul-one"

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_execute_returns_cost_and_tokens(self, mock_achat, soul):
        """execute() result must include cost_usd and total_tokens from LLM response."""
        mock_achat.return_value = _achat_text_response(cost_usd=0.005, total_tokens=50)

        runner = RunsightTeamRunner(model_name="gpt-4o")
        result = await runner.execute(INSTRUCTION, CONTEXT, soul)

        assert result.cost_usd == pytest.approx(0.005)
        assert result.total_tokens == 50

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_execute_accepts_none_context(self, mock_achat, soul):
        """execute() must accept context=None (no context)."""
        mock_achat.return_value = _achat_text_response(content="No context.")

        runner = RunsightTeamRunner(model_name="gpt-4o")
        result = await runner.execute(INSTRUCTION, None, soul)

        assert isinstance(result, ExecutionResult)
        assert result.output == "No context."

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_execute_accepts_optional_messages(self, mock_achat, soul):
        """execute() must accept an optional messages parameter (history)."""
        mock_achat.return_value = _achat_text_response(content="With history.")

        runner = RunsightTeamRunner(model_name="gpt-4o")
        result = await runner.execute(INSTRUCTION, CONTEXT, soul, messages=HISTORY_MESSAGES)

        assert isinstance(result, ExecutionResult)
        assert result.output == "With history."


# ---------------------------------------------------------------------------
# AC2: execute() builds prompt from instruction+context (same as _build_prompt)
# ---------------------------------------------------------------------------


class TestExecutePromptBuilding:
    """execute() must build the prompt from instruction+context the same way
    _build_prompt does from a Task: instruction + "\\n\\nContext:\\n" + context."""

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_execute_includes_instruction_in_prompt(self, mock_achat, soul):
        """The instruction must appear in the user message sent to the LLM."""
        mock_achat.return_value = _achat_text_response()

        runner = RunsightTeamRunner(model_name="gpt-4o")
        await runner.execute("Do the thing.", CONTEXT, soul)

        kwargs = mock_achat.call_args.kwargs
        user_message = kwargs["messages"][-1]
        assert "Do the thing." in user_message["content"]

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_execute_includes_context_in_prompt(self, mock_achat, soul):
        """The context must appear in the user message sent to the LLM."""
        mock_achat.return_value = _achat_text_response()

        runner = RunsightTeamRunner(model_name="gpt-4o")
        await runner.execute(INSTRUCTION, "My special context.", soul)

        kwargs = mock_achat.call_args.kwargs
        user_message = kwargs["messages"][-1]
        assert "My special context." in user_message["content"]

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_execute_no_context_prompt_has_instruction_only(self, mock_achat, soul):
        """When context is None, the prompt must contain only the instruction
        (no spurious 'Context:' section)."""
        mock_achat.return_value = _achat_text_response()

        runner = RunsightTeamRunner(model_name="gpt-4o")
        await runner.execute("Only this.", None, soul)

        kwargs = mock_achat.call_args.kwargs
        user_message = kwargs["messages"][-1]
        assert "Only this." in user_message["content"]
        assert "Context:" not in user_message["content"]

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_execute_uses_soul_system_prompt(self, mock_achat, soul):
        """execute() must pass the soul's system_prompt to the LLM client."""
        mock_achat.return_value = _achat_text_response()

        runner = RunsightTeamRunner(model_name="gpt-4o")
        await runner.execute(INSTRUCTION, CONTEXT, soul)

        kwargs = mock_achat.call_args.kwargs
        assert kwargs["system_prompt"] == "You are helpful."

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_execute_forwards_temperature_and_max_tokens(self, mock_achat, soul_with_temp):
        """execute() must forward temperature and max_tokens from the soul."""
        mock_achat.return_value = _achat_text_response()

        runner = RunsightTeamRunner(model_name="gpt-4o")
        await runner.execute(INSTRUCTION, CONTEXT, soul_with_temp)

        kwargs = mock_achat.call_args.kwargs
        assert kwargs["temperature"] == 0.0
        assert kwargs["max_tokens"] == 128

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_execute_with_history_messages_prepended(self, mock_achat, soul):
        """When messages history is provided, it must be prepended before the
        new user message built from instruction+context."""
        mock_achat.return_value = _achat_text_response()

        runner = RunsightTeamRunner(model_name="gpt-4o")
        await runner.execute(INSTRUCTION, CONTEXT, soul, messages=HISTORY_MESSAGES)

        sent = mock_achat.call_args.kwargs["messages"]
        # 2 history + 1 new user
        assert len(sent) == 3
        assert sent[0] == HISTORY_MESSAGES[0]
        assert sent[1] == HISTORY_MESSAGES[1]
        assert sent[2]["role"] == "user"
        assert INSTRUCTION in sent[2]["content"]


# ---------------------------------------------------------------------------
# AC2: execute() handles agentic tool-loop path
# ---------------------------------------------------------------------------


class TestExecuteToolLoop:
    """execute() must enter the agentic tool loop when the soul has resolved_tools."""

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_execute_single_shot_no_tools(self, mock_achat):
        """execute() without resolved_tools: single achat call, returns text."""
        soul = Soul(
            id="no_tools",
            kind="soul",
            name="Agent",
            role="Agent",
            system_prompt="Simple.",
            provider="openai",
            model_name="gpt-4o",
        )
        soul.resolved_tools = None
        mock_achat.return_value = _achat_text_response(content="Simple answer.")

        runner = RunsightTeamRunner(model_name="gpt-4o")
        result = await runner.execute(INSTRUCTION, CONTEXT, soul)

        assert result.output == "Simple answer."
        mock_achat.assert_called_once()

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_execute_tool_loop_one_call_then_text(self, mock_achat):
        """execute() with resolved_tools: LLM calls tool once, then text. Two achat calls."""
        tool = _make_tool_instance("search")
        soul = _make_soul_with_tools([tool])

        mock_achat.side_effect = [
            _achat_tool_response(tool_name="search", call_id="c1"),
            _achat_text_response(content="Found it."),
        ]

        runner = RunsightTeamRunner(model_name="gpt-4o")
        result = await runner.execute(INSTRUCTION, CONTEXT, soul)

        assert result.output == "Found it."
        assert mock_achat.call_count == 2

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_execute_tool_loop_populates_tool_calls_made(self, mock_achat):
        """After tool loop, execute() result must have tool_calls_made populated."""
        tool = _make_tool_instance("search")
        soul = _make_soul_with_tools([tool])

        mock_achat.side_effect = [
            _achat_tool_response(tool_name="search", call_id="c1"),
            _achat_text_response(content="Done."),
        ]

        runner = RunsightTeamRunner(model_name="gpt-4o")
        result = await runner.execute(INSTRUCTION, CONTEXT, soul)

        assert "search" in result.tool_calls_made
        assert result.tool_iterations >= 1

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_execute_no_tools_zero_tool_iterations(self, mock_achat):
        """Single-shot execute() must return tool_iterations=0 and empty tool_calls_made."""
        soul = Soul(
            id="plain-soul",
            kind="soul",
            name="Agent",
            role="Agent",
            system_prompt="No tools.",
            provider="openai",
            model_name="gpt-4o",
        )
        soul.resolved_tools = None
        mock_achat.return_value = _achat_text_response()

        runner = RunsightTeamRunner(model_name="gpt-4o")
        result = await runner.execute(INSTRUCTION, CONTEXT, soul)

        assert result.tool_iterations == 0
        assert result.tool_calls_made == []

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_execute_tool_cost_accumulated(self, mock_achat):
        """execute() with tool loop must accumulate cost across all iterations."""
        tool = _make_tool_instance("calc")
        soul = _make_soul_with_tools([tool])

        mock_achat.side_effect = [
            _achat_tool_response(tool_name="calc", cost_usd=0.003, total_tokens=30),
            _achat_text_response(content="Result.", cost_usd=0.002, total_tokens=20),
        ]

        runner = RunsightTeamRunner(model_name="gpt-4o")
        result = await runner.execute(INSTRUCTION, CONTEXT, soul)

        assert result.cost_usd == pytest.approx(0.005)
        assert result.total_tokens == 50


# ---------------------------------------------------------------------------
# AC3 / AC4: execute() is the canonical API (execute_task was deleted in RUN-879)
# ---------------------------------------------------------------------------


class TestExecuteTaskBackwardCompat:
    """After RUN-879, execute_task() is deleted. execute() is the canonical API.
    These tests verify execute() covers what execute_task() used to do."""

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_execute_task_still_returns_execution_result(self, mock_achat, soul):
        """execute() must return an ExecutionResult."""
        mock_achat.return_value = _achat_text_response(content="Result via execute.")

        runner = RunsightTeamRunner(model_name="gpt-4o")
        result = await runner.execute(INSTRUCTION, CONTEXT, soul)

        assert isinstance(result, ExecutionResult)
        assert result.output == "Result via execute."

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_execute_task_soul_id_matches(self, mock_achat, soul):
        """execute() result soul_id must reflect the active soul."""
        mock_achat.return_value = _achat_text_response()

        runner = RunsightTeamRunner(model_name="gpt-4o")
        result = await runner.execute(INSTRUCTION, CONTEXT, soul)

        assert result.soul_id == "soul-one"

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_execute_and_execute_task_identical_outputs(self, mock_achat, soul):
        """execute() produces consistent results for same inputs called twice."""
        mock_achat.return_value = _achat_text_response(
            content="Identical.", cost_usd=0.003, total_tokens=30
        )

        runner = RunsightTeamRunner(model_name="gpt-4o")
        result1 = await runner.execute(INSTRUCTION, CONTEXT, soul)

        mock_achat.return_value = _achat_text_response(
            content="Identical.", cost_usd=0.003, total_tokens=30
        )
        result2 = await runner.execute(INSTRUCTION, CONTEXT, soul)

        assert result1.output == result2.output
        assert result1.cost_usd == pytest.approx(result2.cost_usd)
        assert result1.total_tokens == result2.total_tokens

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_execute_task_sends_same_prompt_as_execute(self, mock_achat, soul):
        """execute(instruction, context) must send combined prompt to LLM."""
        mock_achat.return_value = _achat_text_response()

        runner = RunsightTeamRunner(model_name="gpt-4o")
        await runner.execute(INSTRUCTION, CONTEXT, soul)
        execute_prompt = mock_achat.call_args.kwargs["messages"][-1]["content"]

        # Verify the combined prompt contains both instruction and context
        assert INSTRUCTION in execute_prompt
        assert CONTEXT in execute_prompt

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_execute_task_with_messages_still_works(self, mock_achat, soul):
        """execute() must work when called with messages parameter."""
        mock_achat.return_value = _achat_text_response(content="With history.")

        runner = RunsightTeamRunner(model_name="gpt-4o")
        result = await runner.execute(INSTRUCTION, CONTEXT, soul, messages=HISTORY_MESSAGES)

        assert result.output == "With history."
        sent = mock_achat.call_args.kwargs["messages"]
        assert len(sent) == 3  # 2 history + 1 new user


# ---------------------------------------------------------------------------
# AC2: execute() handles failover
# ---------------------------------------------------------------------------


class TestExecuteFailover:
    """execute() must support provider failover the same way execute_task() does."""

    @pytest.mark.asyncio
    async def test_execute_fails_over_to_fallback_model(self, soul):
        """When primary provider raises a retryable error, execute() must
        fall back to the configured fallback model."""
        primary_client = Mock()
        primary_client.achat = AsyncMock(
            side_effect=RuntimeError("RateLimitError: openai overloaded")
        )
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

        def client_factory(*, model_name, api_key=None):
            if model_name == "gpt-4o":
                return primary_client
            if model_name == "claude-3-opus-20240229":
                return fallback_client
            raise AssertionError(f"Unexpected model_name: {model_name}")

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
            result = await runner.execute(INSTRUCTION, CONTEXT, soul)

        assert result.output == "Fallback answer."
        primary_client.achat.assert_awaited_once()
        fallback_client.achat.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_execute_does_not_failover_on_authentication_error(self, soul):
        """execute() must not fail over on authentication errors (same as execute_task)."""
        primary_client = Mock()
        primary_client.achat = AsyncMock(
            side_effect=RuntimeError("AuthenticationError: invalid api key")
        )
        fallback_client = Mock()
        fallback_client.achat = AsyncMock(
            return_value={
                "content": "Should not run.",
                "cost_usd": 0.0,
                "total_tokens": 0,
                "tool_calls": None,
                "raw_message": {"role": "assistant", "content": "Should not run."},
            }
        )

        def client_factory(*, model_name, api_key=None):
            if model_name == "gpt-4o":
                return primary_client
            if model_name == "claude-3-opus-20240229":
                return fallback_client
            raise AssertionError(f"Unexpected model_name: {model_name}")

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
                await runner.execute(INSTRUCTION, CONTEXT, soul)

        primary_client.achat.assert_awaited_once()
        fallback_client.achat.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_execute_rejects_soul_without_provider(self, mock_achat):
        """execute() must raise ValueError for a soul missing provider (same validation)."""
        mock_achat.return_value = _achat_text_response()

        runner = RunsightTeamRunner(model_name="gpt-4o")
        bad_soul = Soul(
            id="bad-soul",
            kind="soul",
            name="Bad Soul",
            role="Bad Soul",
            system_prompt="No provider.",
            model_name="gpt-4o",
        )

        with pytest.raises(ValueError, match="explicit provider"):
            await runner.execute(INSTRUCTION, CONTEXT, bad_soul)

        mock_achat.assert_not_called()
