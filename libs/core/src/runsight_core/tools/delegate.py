"""Built-in delegate tool: runsight/delegate."""

from __future__ import annotations

from typing import Any, Dict, List

from runsight_core.tools._catalog import ToolInstance, register_builtin
from runsight_core.yaml.schema import ExitDef


def create_delegate_tool(exits: List[ExitDef] | None = None) -> ToolInstance:
    """Factory that returns a ToolInstance for exit-port delegation."""
    if exits is None:
        exits = []

    exit_ids = [e.id for e in exits]

    port_schema: Dict[str, Any] = {"type": "string"}
    if exit_ids:
        port_schema["enum"] = exit_ids

    parameters: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "port": port_schema,
        },
        "required": ["port"],
    }

    async def _execute(args: dict) -> str:
        port = args["port"]
        if exit_ids and port not in exit_ids:
            valid = ", ".join(exit_ids)
            return f"Error: invalid port '{port}'. Valid ports: {valid}"
        return port

    return ToolInstance(
        name="delegate",
        description="Delegate execution to an exit port.",
        parameters=parameters,
        execute=_execute,
    )


register_builtin("runsight/delegate", create_delegate_tool)
