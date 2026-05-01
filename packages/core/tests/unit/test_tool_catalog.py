"""Legacy tool catalog smoke tests.

Owner suites for schema/registry, custom Python tools, and request-backed tools
live beside this file. This module stays intentionally small so existing
targeted commands still exercise the public catalog import surface.
"""

from __future__ import annotations


def test_tool_catalog_public_exports_are_importable() -> None:
    """The public tool catalog API remains importable from runsight_core.tools."""
    from runsight_core.tools import (
        BUILTIN_TOOL_CATALOG,
        ToolInstance,
        get_builtin,
        register_builtin,
        resolve_tool,
    )

    assert BUILTIN_TOOL_CATALOG is not None
    assert ToolInstance is not None
    assert get_builtin is not None
    assert register_builtin is not None
    assert resolve_tool is not None
