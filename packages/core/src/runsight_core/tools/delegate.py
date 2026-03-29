"""Built-in delegate tool: runsight/delegate."""

from __future__ import annotations

import json
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
            "task": {
                "type": "string",
                "description": "The task instruction to delegate to this port.",
            },
        },
        "required": ["port", "task"],
    }

    async def _execute(args: dict) -> str:
        port = args["port"]
        task = args.get("task")
        if exit_ids and port not in exit_ids:
            valid = ", ".join(exit_ids)
            return f"Error: invalid port '{port}'. Valid ports: {valid}"
        if not task:
            return port
        return json.dumps({"port": port, "task": task})

    return ToolInstance(
        name="delegate",
        description="Delegate execution to an exit port.",
        parameters=parameters,
        execute=_execute,
    )


register_builtin("runsight/delegate", create_delegate_tool)
