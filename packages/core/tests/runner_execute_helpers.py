"""Shared fixtures for RunsightTeamRunner execute() tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from runsight_core.primitives import Soul

INSTRUCTION = "Say hello."
CONTEXT = "This is a test context."
HISTORY_MESSAGES = [
    {"role": "user", "content": "Previous turn."},
    {"role": "assistant", "content": "Understood."},
]


def make_soul(**overrides) -> Soul:
    values = {
        "id": "soul-one",
        "kind": "soul",
        "name": "Agent",
        "role": "Agent",
        "system_prompt": "You are helpful.",
        "provider": "openai",
        "model_name": "gpt-4o",
    }
    values.update(overrides)
    return Soul(**values)


def make_soul_with_tools(resolved_tools, max_tool_iterations: int = 5) -> Soul:
    soul = make_soul(
        id="tool_soul",
        name="Tool Agent",
        role="Tool Agent",
        system_prompt="You use tools.",
        max_tool_iterations=max_tool_iterations,
    )
    soul.resolved_tools = resolved_tools
    return soul


def make_tool_instance(name: str = "get_weather"):
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


def achat_text_response(
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


def achat_tool_response(
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
