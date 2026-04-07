from typing import Any, Dict, List, Optional

from litellm import acompletion, completion_cost  # type: ignore[import-not-found]
from pydantic import BaseModel

from runsight_core.budget_enforcement import _active_budget


class LLMMessage(BaseModel):
    role: str
    content: str


class LiteLLMClient:
    """
    A LiteLLM adapter matching the OpenAI SDK format. Supports standard (non-streaming) completion.
    """

    def __init__(
        self, model_name: str = "gpt-4o", timeout: float = 300.0, api_key: Optional[str] = None
    ):
        self.model_name = model_name
        self.timeout = timeout
        self.api_key = api_key

    async def achat(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        tools: Optional[List[dict]] = None,
        tool_choice: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Get the full response from the LLM without streaming.
        Returns a dict with keys: content, cost_usd, prompt_tokens,
        completion_tokens, total_tokens, tool_calls, finish_reason, raw_message.
        """
        formatted_messages: List[Dict[str, Any]] = []
        if system_prompt:
            formatted_messages.append({"role": "system", "content": system_prompt})

        formatted_messages.extend(messages)

        extra_kwargs = dict(kwargs)
        if self.api_key is not None:
            extra_kwargs["api_key"] = self.api_key
        if temperature is not None:
            extra_kwargs["temperature"] = temperature
        if tools is not None:
            extra_kwargs["tools"] = tools
        if tool_choice is not None:
            extra_kwargs["tool_choice"] = tool_choice

        response = await acompletion(
            model=self.model_name,
            messages=formatted_messages,
            stream=False,
            timeout=self.timeout,
            **extra_kwargs,
        )

        content = ""
        tool_calls_raw = None
        finish_reason = "stop"
        if response.choices and len(response.choices) > 0:
            message = response.choices[0].message
            content = message.content or ""
            tool_calls_raw = message.tool_calls
            finish_reason = response.choices[0].finish_reason

        # Calculate cost using litellm
        cost_usd = completion_cost(
            completion_response=response,
            model=self.model_name,
        )

        # Extract token breakdown from usage
        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0
        if hasattr(response, "usage") and response.usage:
            prompt_tokens = response.usage.prompt_tokens or 0
            completion_tokens = response.usage.completion_tokens or 0
            total_tokens = response.usage.total_tokens or 0

        # Convert tool_calls to plain dicts for serialization
        tool_calls_serialized = None
        if tool_calls_raw and isinstance(tool_calls_raw, list):
            tool_calls_serialized = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in tool_calls_raw
            ]

        # Build raw_message dict for re-feeding into conversation history
        raw_message: Dict[str, Any] = {
            "role": "assistant",
            "content": content,
        }
        if tool_calls_serialized is not None:
            raw_message["tool_calls"] = tool_calls_serialized

        # Budget enforcement via contextvars
        session = _active_budget.get(None)
        if session is not None:
            session.accrue(cost_usd=cost_usd, tokens=total_tokens)
            session.check_or_raise()

        return {
            "content": content,
            "cost_usd": cost_usd,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "tool_calls": tool_calls_serialized,
            "finish_reason": finish_reason,
            "raw_message": raw_message,
        }
