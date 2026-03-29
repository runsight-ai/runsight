"""Built-in tool catalog: ToolInstance, registration, and resolution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict

from runsight_core.yaml.schema import ToolDef

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


def resolve_tool(tool_def: ToolDef, **kwargs: object) -> ToolInstance:
    """Look up *tool_def.source* in the catalog, call its factory, and return a ToolInstance.

    Raises:
        ValueError: If the source is not registered in BUILTIN_TOOL_CATALOG.
    """
    factory = BUILTIN_TOOL_CATALOG.get(tool_def.source)
    if factory is None:
        raise ValueError(f"Unknown tool source: {tool_def.source!r}")
    return factory(**kwargs)
