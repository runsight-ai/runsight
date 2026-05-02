"""Built-in delegate tool behavior."""

from __future__ import annotations

import pytest
from runsight_core.tools import ToolInstance
from runsight_core.yaml.schema import ExitDef


def _exits(*ids: str) -> list[ExitDef]:
    return [ExitDef(id=exit_id, label=exit_id.title()) for exit_id in ids]


def test_delegate_factory_returns_named_tool_with_port_schema() -> None:
    from runsight_core.tools.delegate import create_delegate_tool

    tool = create_delegate_tool(exits=_exits("done", "retry"))

    assert isinstance(tool, ToolInstance)
    assert tool.name == "delegate"
    port_schema = tool.parameters["properties"]["port"]
    assert set(port_schema["enum"]) == {"done", "retry"}
    assert set(tool.to_openai_schema()["function"]["parameters"]["properties"]["port"]["enum"]) == {
        "done",
        "retry",
    }


def test_delegate_empty_exits_do_not_force_port_enum() -> None:
    from runsight_core.tools.delegate import create_delegate_tool

    port_schema = create_delegate_tool(exits=[]).parameters["properties"]["port"]

    assert port_schema.get("enum", []) == []


@pytest.mark.asyncio
async def test_delegate_returns_valid_port_string() -> None:
    from runsight_core.tools.delegate import create_delegate_tool

    tool = create_delegate_tool(exits=_exits("done", "retry"))

    assert await tool.execute({"port": "retry"}) == "retry"


@pytest.mark.asyncio
async def test_delegate_invalid_port_returns_error_string() -> None:
    from runsight_core.tools.delegate import create_delegate_tool

    tool = create_delegate_tool(exits=_exits("done"))
    result = await tool.execute({"port": "unknown_port"})

    assert isinstance(result, str)
    assert result != "unknown_port"
