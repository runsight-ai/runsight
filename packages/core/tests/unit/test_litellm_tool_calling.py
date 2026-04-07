"""
RUN-277 — Red tests: LiteLLMClient.achat() tool calling support.

These tests verify that achat() can:
1. Accept tools and tool_choice parameters (AC2)
2. Return tool_calls, finish_reason, and raw_message in the response dict (AC2, AC3, AC4)
3. Maintain backward compatibility when called without tools (AC1)

All tests mock litellm.acompletion to avoid real API calls.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from runsight_core.llm.client import LiteLLMClient

# ---------------------------------------------------------------------------
# Helpers: mock litellm response objects
# ---------------------------------------------------------------------------

SAMPLE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "City name"},
                },
                "required": ["location"],
            },
        },
    }
]


def _make_tool_call(
    call_id: str = "call_abc123",
    name: str = "get_weather",
    arguments: str = '{"location": "Paris"}',
):
    """Build a mock tool_call object matching litellm's response shape."""
    tc = MagicMock()
    tc.id = call_id
    tc.type = "function"
    tc.function = MagicMock()
    tc.function.name = name
    tc.function.arguments = arguments
    return tc


def _make_response(
    content: str = "hello",
    tool_calls=None,
    finish_reason: str = "stop",
    prompt_tokens: int = 10,
    completion_tokens: int = 5,
    total_tokens: int = 15,
):
    """Build a mock litellm acompletion response."""
    message = MagicMock()
    message.content = content
    message.tool_calls = tool_calls
    message.role = "assistant"

    choice = MagicMock()
    choice.message = message
    choice.finish_reason = finish_reason

    usage = MagicMock()
    usage.prompt_tokens = prompt_tokens
    usage.completion_tokens = completion_tokens
    usage.total_tokens = total_tokens

    response = MagicMock()
    response.choices = [choice]
    response.usage = usage
    return response


# ---------------------------------------------------------------------------
# AC1: Backward compatibility — achat() without tools
# ---------------------------------------------------------------------------


class TestAchatBackwardCompatWithToolFields:
    """When called WITHOUT tools, achat() must still return the original keys
    plus the new tool_calls, finish_reason, and raw_message fields."""

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost", return_value=0.002)
    async def test_no_tools_returns_original_keys(self, mock_cost, mock_acompletion):
        """All five original keys must still be present."""
        mock_acompletion.return_value = _make_response(content="hi there")

        client = LiteLLMClient(model_name="gpt-4o")
        result = await client.achat(messages=[{"role": "user", "content": "hello"}])

        assert "content" in result
        assert "cost_usd" in result
        assert "prompt_tokens" in result
        assert "completion_tokens" in result
        assert "total_tokens" in result

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost", return_value=0.002)
    async def test_no_tools_tool_calls_is_none(self, mock_cost, mock_acompletion):
        """tool_calls must be None when no tools requested."""
        mock_acompletion.return_value = _make_response(content="hi", tool_calls=None)

        client = LiteLLMClient(model_name="gpt-4o")
        result = await client.achat(messages=[{"role": "user", "content": "hello"}])

        assert "tool_calls" in result
        assert result["tool_calls"] is None

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost", return_value=0.002)
    async def test_no_tools_finish_reason_present(self, mock_cost, mock_acompletion):
        """finish_reason must be present even without tools."""
        mock_acompletion.return_value = _make_response(finish_reason="stop")

        client = LiteLLMClient(model_name="gpt-4o")
        result = await client.achat(messages=[{"role": "user", "content": "hello"}])

        assert "finish_reason" in result
        assert result["finish_reason"] == "stop"

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost", return_value=0.002)
    async def test_no_tools_raw_message_present(self, mock_cost, mock_acompletion):
        """raw_message must be present even without tools."""
        mock_acompletion.return_value = _make_response(content="hello")

        client = LiteLLMClient(model_name="gpt-4o")
        result = await client.achat(messages=[{"role": "user", "content": "hello"}])

        assert "raw_message" in result

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost", return_value=0.002)
    async def test_no_tools_does_not_pass_tools_to_acompletion(self, mock_cost, mock_acompletion):
        """When tools is not provided, acompletion must NOT receive tools/tool_choice kwargs."""
        mock_acompletion.return_value = _make_response()

        client = LiteLLMClient(model_name="gpt-4o")
        await client.achat(messages=[{"role": "user", "content": "hello"}])

        call_kwargs = mock_acompletion.call_args.kwargs
        assert "tools" not in call_kwargs
        assert "tool_choice" not in call_kwargs

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost", return_value=0.002)
    async def test_no_tools_does_not_pass_temperature_when_unset(
        self, mock_cost, mock_acompletion
    ):
        """Unspecified temperature must stay unset so provider defaults can apply."""
        mock_acompletion.return_value = _make_response()

        client = LiteLLMClient(model_name="gpt-5.4-nano")
        await client.achat(messages=[{"role": "user", "content": "hello"}])

        call_kwargs = mock_acompletion.call_args.kwargs
        assert "temperature" not in call_kwargs

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost", return_value=0.002)
    async def test_explicit_temperature_is_forwarded(self, mock_cost, mock_acompletion):
        """Explicit temperature overrides must still be forwarded."""
        mock_acompletion.return_value = _make_response()

        client = LiteLLMClient(model_name="gpt-4o")
        await client.achat(
            messages=[{"role": "user", "content": "hello"}],
            temperature=0.2,
        )

        call_kwargs = mock_acompletion.call_args.kwargs
        assert call_kwargs["temperature"] == 0.2


# ---------------------------------------------------------------------------
# AC2: achat() with tools — passes tools to litellm, extracts tool_calls
# ---------------------------------------------------------------------------


class TestAchatToolCalling:
    """When called WITH tools, achat() must forward them to litellm.acompletion
    and extract tool_calls from the response."""

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost", return_value=0.003)
    async def test_tools_passed_to_acompletion(self, mock_cost, mock_acompletion):
        """tools list must be forwarded to litellm.acompletion()."""
        mock_acompletion.return_value = _make_response(
            content="",
            tool_calls=[_make_tool_call()],
            finish_reason="tool_calls",
        )

        client = LiteLLMClient(model_name="gpt-4o")
        await client.achat(
            messages=[{"role": "user", "content": "weather?"}],
            tools=SAMPLE_TOOLS,
        )

        call_kwargs = mock_acompletion.call_args.kwargs
        assert call_kwargs.get("tools") == SAMPLE_TOOLS

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost", return_value=0.003)
    async def test_tool_choice_passed_to_acompletion(self, mock_cost, mock_acompletion):
        """tool_choice must be forwarded to litellm.acompletion()."""
        mock_acompletion.return_value = _make_response(
            content="",
            tool_calls=[_make_tool_call()],
            finish_reason="tool_calls",
        )

        client = LiteLLMClient(model_name="gpt-4o")
        await client.achat(
            messages=[{"role": "user", "content": "weather?"}],
            tools=SAMPLE_TOOLS,
            tool_choice="auto",
        )

        call_kwargs = mock_acompletion.call_args.kwargs
        assert call_kwargs.get("tool_choice") == "auto"

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost", return_value=0.003)
    async def test_tool_calls_extracted_from_response(self, mock_cost, mock_acompletion):
        """tool_calls must be extracted from response and returned in result dict."""
        tc = _make_tool_call(
            call_id="call_xyz", name="get_weather", arguments='{"location": "NYC"}'
        )
        mock_acompletion.return_value = _make_response(
            content="",
            tool_calls=[tc],
            finish_reason="tool_calls",
        )

        client = LiteLLMClient(model_name="gpt-4o")
        result = await client.achat(
            messages=[{"role": "user", "content": "weather in NYC?"}],
            tools=SAMPLE_TOOLS,
        )

        assert "tool_calls" in result
        assert result["tool_calls"] is not None
        assert len(result["tool_calls"]) == 1

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost", return_value=0.003)
    async def test_tool_calls_structure_has_id_and_function(self, mock_cost, mock_acompletion):
        """Each tool_call must have id, function.name, and function.arguments."""
        tc = _make_tool_call(
            call_id="call_001", name="get_weather", arguments='{"location": "London"}'
        )
        mock_acompletion.return_value = _make_response(
            content="",
            tool_calls=[tc],
            finish_reason="tool_calls",
        )

        client = LiteLLMClient(model_name="gpt-4o")
        result = await client.achat(
            messages=[{"role": "user", "content": "weather?"}],
            tools=SAMPLE_TOOLS,
        )

        tool_call = result["tool_calls"][0]
        # Must have id
        assert hasattr(tool_call, "id") or "id" in tool_call
        # Must have function.name
        func = tool_call.function if hasattr(tool_call, "function") else tool_call["function"]
        name = func.name if hasattr(func, "name") else func["name"]
        assert name == "get_weather"
        # Must have function.arguments
        args = func.arguments if hasattr(func, "arguments") else func["arguments"]
        assert args == '{"location": "London"}'

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost", return_value=0.003)
    async def test_multiple_tool_calls(self, mock_cost, mock_acompletion):
        """When the LLM returns multiple tool_calls, all should be present in result."""
        tc1 = _make_tool_call(
            call_id="call_a", name="get_weather", arguments='{"location": "Paris"}'
        )
        tc2 = _make_tool_call(
            call_id="call_b", name="get_weather", arguments='{"location": "Tokyo"}'
        )
        mock_acompletion.return_value = _make_response(
            content="",
            tool_calls=[tc1, tc2],
            finish_reason="tool_calls",
        )

        client = LiteLLMClient(model_name="gpt-4o")
        result = await client.achat(
            messages=[{"role": "user", "content": "weather in Paris and Tokyo?"}],
            tools=SAMPLE_TOOLS,
        )

        assert result["tool_calls"] is not None
        assert len(result["tool_calls"]) == 2

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost", return_value=0.003)
    async def test_tools_provided_but_llm_responds_with_text(self, mock_cost, mock_acompletion):
        """When tools are provided but LLM chooses to respond with text, tool_calls is None."""
        mock_acompletion.return_value = _make_response(
            content="I can't help with that.",
            tool_calls=None,
            finish_reason="stop",
        )

        client = LiteLLMClient(model_name="gpt-4o")
        result = await client.achat(
            messages=[{"role": "user", "content": "hello"}],
            tools=SAMPLE_TOOLS,
        )

        assert result["tool_calls"] is None
        assert result["content"] == "I can't help with that."
        assert result["finish_reason"] == "stop"


# ---------------------------------------------------------------------------
# AC3: finish_reason correctly extracted
# ---------------------------------------------------------------------------


class TestAchatFinishReason:
    """finish_reason must be extracted from response.choices[0].finish_reason."""

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost", return_value=0.001)
    async def test_finish_reason_tool_calls(self, mock_cost, mock_acompletion):
        """finish_reason='tool_calls' when model invokes a tool."""
        mock_acompletion.return_value = _make_response(
            content="",
            tool_calls=[_make_tool_call()],
            finish_reason="tool_calls",
        )

        client = LiteLLMClient(model_name="gpt-4o")
        result = await client.achat(
            messages=[{"role": "user", "content": "weather?"}],
            tools=SAMPLE_TOOLS,
        )

        assert result["finish_reason"] == "tool_calls"

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost", return_value=0.001)
    async def test_finish_reason_stop(self, mock_cost, mock_acompletion):
        """finish_reason='stop' for normal text completion."""
        mock_acompletion.return_value = _make_response(
            content="Done.",
            finish_reason="stop",
        )

        client = LiteLLMClient(model_name="gpt-4o")
        result = await client.achat(messages=[{"role": "user", "content": "hi"}])

        assert result["finish_reason"] == "stop"

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost", return_value=0.001)
    async def test_finish_reason_length(self, mock_cost, mock_acompletion):
        """finish_reason='length' when output was truncated."""
        mock_acompletion.return_value = _make_response(
            content="partial output...",
            finish_reason="length",
        )

        client = LiteLLMClient(model_name="gpt-4o")
        result = await client.achat(messages=[{"role": "user", "content": "write a novel"}])

        assert result["finish_reason"] == "length"


# ---------------------------------------------------------------------------
# AC4: raw_message for re-feeding in agentic loop
# ---------------------------------------------------------------------------


class TestAchatRawMessage:
    """raw_message must contain the full assistant message dict for re-feeding
    into the conversation history in an agentic tool-use loop."""

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost", return_value=0.002)
    async def test_raw_message_contains_role(self, mock_cost, mock_acompletion):
        """raw_message must have role='assistant'."""
        mock_acompletion.return_value = _make_response(content="hello")

        client = LiteLLMClient(model_name="gpt-4o")
        result = await client.achat(messages=[{"role": "user", "content": "hi"}])

        raw = result["raw_message"]
        assert raw["role"] == "assistant"

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost", return_value=0.002)
    async def test_raw_message_contains_content(self, mock_cost, mock_acompletion):
        """raw_message must include the content field."""
        mock_acompletion.return_value = _make_response(content="the answer is 42")

        client = LiteLLMClient(model_name="gpt-4o")
        result = await client.achat(messages=[{"role": "user", "content": "what?"}])

        raw = result["raw_message"]
        assert raw["content"] == "the answer is 42"

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost", return_value=0.002)
    async def test_raw_message_contains_tool_calls_when_present(self, mock_cost, mock_acompletion):
        """raw_message must include tool_calls when the model invoked tools."""
        tc = _make_tool_call(call_id="call_raw", name="get_weather", arguments='{"location": "SF"}')
        mock_acompletion.return_value = _make_response(
            content="",
            tool_calls=[tc],
            finish_reason="tool_calls",
        )

        client = LiteLLMClient(model_name="gpt-4o")
        result = await client.achat(
            messages=[{"role": "user", "content": "weather?"}],
            tools=SAMPLE_TOOLS,
        )

        raw = result["raw_message"]
        assert "tool_calls" in raw
        assert raw["tool_calls"] is not None
        assert len(raw["tool_calls"]) == 1

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost", return_value=0.002)
    async def test_raw_message_no_tool_calls_when_absent(self, mock_cost, mock_acompletion):
        """raw_message must have tool_calls=None when no tools were called."""
        mock_acompletion.return_value = _make_response(content="just text")

        client = LiteLLMClient(model_name="gpt-4o")
        result = await client.achat(messages=[{"role": "user", "content": "hi"}])

        raw = result["raw_message"]
        assert raw.get("tool_calls") is None

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost", return_value=0.002)
    async def test_raw_message_is_dict(self, mock_cost, mock_acompletion):
        """raw_message must be a plain dict (not a litellm object) for serialization."""
        mock_acompletion.return_value = _make_response(content="hello")

        client = LiteLLMClient(model_name="gpt-4o")
        result = await client.achat(messages=[{"role": "user", "content": "hi"}])

        assert isinstance(result["raw_message"], dict)


# ---------------------------------------------------------------------------
# Edge case: empty content when tool_calls present
# ---------------------------------------------------------------------------


class TestAchatContentWithToolCalls:
    """When the LLM returns tool_calls, content may be None or empty.
    achat() must default content to '' (empty string)."""

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost", return_value=0.001)
    async def test_none_content_defaults_to_empty_string(self, mock_cost, mock_acompletion):
        """When content is None (tool call), result['content'] must be ''."""
        mock_acompletion.return_value = _make_response(
            content=None,
            tool_calls=[_make_tool_call()],
            finish_reason="tool_calls",
        )

        client = LiteLLMClient(model_name="gpt-4o")
        result = await client.achat(
            messages=[{"role": "user", "content": "weather?"}],
            tools=SAMPLE_TOOLS,
        )

        assert result["content"] == ""

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost", return_value=0.001)
    async def test_empty_content_with_tool_calls(self, mock_cost, mock_acompletion):
        """When content is '' and tool_calls present, both fields must be correct."""
        mock_acompletion.return_value = _make_response(
            content="",
            tool_calls=[_make_tool_call()],
            finish_reason="tool_calls",
        )

        client = LiteLLMClient(model_name="gpt-4o")
        result = await client.achat(
            messages=[{"role": "user", "content": "weather?"}],
            tools=SAMPLE_TOOLS,
        )

        assert result["content"] == ""
        assert result["tool_calls"] is not None
        assert len(result["tool_calls"]) == 1


# ---------------------------------------------------------------------------
# Signature: achat() accepts tools and tool_choice parameters
# ---------------------------------------------------------------------------


class TestAchatSignature:
    """achat() must accept 'tools' and 'tool_choice' keyword arguments."""

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost", return_value=0.001)
    async def test_achat_accepts_tools_kwarg(self, mock_cost, mock_acompletion):
        """achat() must accept a 'tools' keyword argument without TypeError."""
        mock_acompletion.return_value = _make_response()

        client = LiteLLMClient(model_name="gpt-4o")
        # This must not raise TypeError
        result = await client.achat(
            messages=[{"role": "user", "content": "hi"}],
            tools=SAMPLE_TOOLS,
        )
        assert result is not None

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost", return_value=0.001)
    async def test_achat_accepts_tool_choice_kwarg(self, mock_cost, mock_acompletion):
        """achat() must accept a 'tool_choice' keyword argument without TypeError."""
        mock_acompletion.return_value = _make_response()

        client = LiteLLMClient(model_name="gpt-4o")
        result = await client.achat(
            messages=[{"role": "user", "content": "hi"}],
            tools=SAMPLE_TOOLS,
            tool_choice="required",
        )
        assert result is not None

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost", return_value=0.001)
    async def test_tool_choice_none_not_sent_to_acompletion(self, mock_cost, mock_acompletion):
        """When tool_choice is None (default), it must NOT be passed to acompletion."""
        mock_acompletion.return_value = _make_response()

        client = LiteLLMClient(model_name="gpt-4o")
        await client.achat(
            messages=[{"role": "user", "content": "hi"}],
            tools=SAMPLE_TOOLS,
            tool_choice=None,
        )

        call_kwargs = mock_acompletion.call_args.kwargs
        assert "tool_choice" not in call_kwargs
