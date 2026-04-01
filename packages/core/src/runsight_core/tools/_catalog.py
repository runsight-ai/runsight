"""Built-in tool catalog: ToolInstance, registration, and resolution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict

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


def _resolve_custom_tool(tool_def: CustomToolDef, **kwargs: object) -> ToolInstance:
    """Stub dispatcher for custom tools until RUN-526 lands."""
    raise NotImplementedError(
        f"Custom tool resolution is not implemented yet for {tool_def.source!r}"
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
        return _resolve_custom_tool(tool_def, **kwargs)
    if isinstance(tool_def, HTTPToolDef):
        return _resolve_http_tool(tool_def, **kwargs)

    raise TypeError(f"Unsupported tool definition type: {type(tool_def)!r}")
