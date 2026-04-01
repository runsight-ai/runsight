"""Built-in tool catalog: ToolInstance, registration, and resolution."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from dataclasses import dataclass
from typing import Callable, Dict

from runsight_core.blocks.code import (
    _HARNESS_PREFIX,
    _HARNESS_SUFFIX,
    DEFAULT_ALLOWED_IMPORTS,
    _validate_code_ast,
)
from runsight_core.yaml.discovery import discover_custom_tools
from runsight_core.yaml.schema import BuiltinToolDef, CustomToolDef, HTTPToolDef, ToolDef

# ---------------------------------------------------------------------------
# Module-level registry
# ---------------------------------------------------------------------------

BUILTIN_TOOL_CATALOG: Dict[str, Callable] = {}


# ---------------------------------------------------------------------------
# ToolInstance
# ---------------------------------------------------------------------------


@dataclass
class ToolInstance:
    """A fully-resolved tool ready for execution."""

    name: str
    description: str
    parameters: dict
    execute: Callable

    def to_openai_schema(self) -> dict:
        """Return the OpenAI function-calling tool format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


# ---------------------------------------------------------------------------
# Registration helpers
# ---------------------------------------------------------------------------


def register_builtin(source: str, factory: Callable) -> None:
    """Register a factory function under *source* in the builtin catalog."""
    BUILTIN_TOOL_CATALOG[source] = factory


def get_builtin(source: str) -> Callable | None:
    """Retrieve a factory by *source*, or ``None`` if not registered."""
    return BUILTIN_TOOL_CATALOG.get(source)


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------


def _resolve_builtin_tool(tool_def: BuiltinToolDef, **kwargs: object) -> ToolInstance:
    """Resolve a built-in tool through the registered factory catalog."""
    factory = BUILTIN_TOOL_CATALOG.get(tool_def.source)
    if factory is None:
        raise ValueError(f"Unknown tool source: {tool_def.source!r}")
    return factory(**kwargs)


def resolve_custom_tool(tool_def: CustomToolDef, **kwargs: object) -> ToolInstance:
    """Resolve a custom tool from ``custom/tools/*.yaml`` metadata."""
    base_dir = kwargs.get("base_dir", ".")
    timeout_seconds = kwargs.get("timeout_seconds", 30)
    if not isinstance(timeout_seconds, int):
        raise TypeError("timeout_seconds must be an int")

    tool_meta = discover_custom_tools(base_dir).get(tool_def.source)
    if tool_meta is None:
        raise ValueError(f"Unknown custom tool source: {tool_def.source!r}")
    if tool_meta.code is None:
        raise ValueError(f"Custom tool {tool_def.source!r} has no executable code")

    _validate_code_ast(tool_meta.code, list(DEFAULT_ALLOWED_IMPORTS))
    harness = _HARNESS_PREFIX + tool_meta.code + _HARNESS_SUFFIX

    async def _execute(args: dict) -> str:
        stdin_data = json.dumps(args).encode()
        minimal_env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin:/usr/sbin:/sbin")}
        for key in ("HOME", "DYLD_LIBRARY_PATH", "DYLD_FALLBACK_LIBRARY_PATH"):
            if key in os.environ:
                minimal_env[key] = os.environ[key]

        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            harness,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=minimal_env,
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(input=stdin_data), timeout=timeout_seconds
            )
        except asyncio.TimeoutError:
            try:
                proc.kill()
                await proc.wait()
            except ProcessLookupError:
                pass
            return f"Error: custom tool '{tool_def.source}' timed out after {timeout_seconds}s"

        if proc.returncode != 0:
            error_msg = stderr_bytes.decode(errors="replace").strip()
            return f"Error: {error_msg}"

        return stdout_bytes.decode(errors="replace").strip()

    return ToolInstance(
        name=tool_def.source,
        description=f"Custom tool '{tool_def.source}'",
        parameters={"type": "object", "properties": {}},
        execute=_execute,
    )


def _resolve_http_tool(tool_def: HTTPToolDef, **kwargs: object) -> ToolInstance:
    """Stub dispatcher for HTTP tools until RUN-527 lands."""
    raise NotImplementedError(
        f"HTTP tool resolution is not implemented yet for {tool_def.source!r}"
    )


def resolve_tool(tool_def: ToolDef, **kwargs: object) -> ToolInstance:
    """Dispatch to the appropriate resolver for the validated ToolDef variant.

    Raises:
        ValueError: If the builtin source is not registered in BUILTIN_TOOL_CATALOG.
        NotImplementedError: If custom/http resolution has not been implemented yet.
    """
    if isinstance(tool_def, BuiltinToolDef):
        return _resolve_builtin_tool(tool_def, **kwargs)
    if isinstance(tool_def, CustomToolDef):
        return resolve_custom_tool(tool_def, **kwargs)
    if isinstance(tool_def, HTTPToolDef):
        return _resolve_http_tool(tool_def, **kwargs)

    raise TypeError(f"Unsupported tool definition type: {type(tool_def)!r}")
