"""Custom Python tool sandbox and execution contract tests."""

from __future__ import annotations

import json

import pytest

from packages.core.tests.tool_catalog_fixtures import (
    write_blocked_builtin_python_tool,
    write_blocked_import_python_tool,
    write_echo_json_python_tool,
    write_file_backed_python_tool,
    write_slow_python_tool,
)


class TestResolveCanonicalPythonTools:
    """Canonical Python custom IDs are the only custom runtime path."""

    @pytest.mark.asyncio
    async def test_execute_round_trips_args_through_json_subprocess_contract(
        self, tmp_path
    ) -> None:
        from runsight_core.tools import resolve_tool

        write_echo_json_python_tool(tmp_path)

        tool = resolve_tool("echo_json", base_dir=tmp_path)
        result = await tool.execute({"name": "alice"})

        assert json.loads(result) == {"message": "hello alice"}

    def test_blocked_imports_are_rejected_at_resolve_time(self, tmp_path) -> None:
        from runsight_core.tools import resolve_tool

        write_blocked_import_python_tool(tmp_path)

        with pytest.raises(ValueError, match="not allowed"):
            resolve_tool("blocked_import_tool", base_dir=tmp_path)

    def test_blocked_builtins_are_rejected_at_resolve_time(self, tmp_path) -> None:
        from runsight_core.tools import resolve_tool

        write_blocked_builtin_python_tool(tmp_path)

        with pytest.raises(ValueError, match="not allowed"):
            resolve_tool("blocked_builtin_tool", base_dir=tmp_path)

    @pytest.mark.asyncio
    async def test_timeout_returns_error_string(self, tmp_path) -> None:
        from runsight_core.tools import resolve_tool

        write_slow_python_tool(tmp_path)

        tool = resolve_tool("slow_tool", base_dir=tmp_path, timeout_seconds=1)
        result = await tool.execute({})

        assert "timed out" in result.lower()

    @pytest.mark.asyncio
    async def test_code_file_variant_loads_external_python_file(self, tmp_path) -> None:
        from runsight_core.tools import resolve_tool

        write_file_backed_python_tool(tmp_path)

        tool = resolve_tool("file_backed", base_dir=tmp_path)
        result = await tool.execute({"port": "done"})

        assert json.loads(result) == {"port": "done"}
