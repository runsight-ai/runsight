"""Catalog registration for built-in tools."""

from __future__ import annotations

import pytest
from runsight_core.tools import BUILTIN_TOOL_CATALOG


@pytest.mark.parametrize("tool_id", ["http", "file_io", "delegate"])
def test_builtin_tool_id_is_registered(tool_id: str) -> None:
    import runsight_core.tools.delegate  # noqa: F401
    import runsight_core.tools.file_io  # noqa: F401
    import runsight_core.tools.http  # noqa: F401

    assert tool_id in BUILTIN_TOOL_CATALOG


@pytest.mark.parametrize(
    "legacy_source",
    ["runsight/http", "runsight/file-io", "runsight/delegate"],
)
def test_legacy_builtin_source_alias_is_not_registered(legacy_source: str) -> None:
    import runsight_core.tools.delegate  # noqa: F401
    import runsight_core.tools.file_io  # noqa: F401
    import runsight_core.tools.http  # noqa: F401

    assert legacy_source not in BUILTIN_TOOL_CATALOG
