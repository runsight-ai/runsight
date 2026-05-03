"""Built-in file I/O tool behavior."""

from __future__ import annotations

from pathlib import Path

import pytest
from runsight_core.tools import ToolInstance


def test_file_io_factory_returns_named_tool_with_schema() -> None:
    from runsight_core.tools.file_io import create_file_io_tool

    tool = create_file_io_tool()

    assert isinstance(tool, ToolInstance)
    assert tool.name == "file_io"
    assert {"action", "path", "content"}.issubset(tool.parameters["properties"])
    assert set(tool.parameters["properties"]["action"]["enum"]) == {"read", "write"}
    assert {"action", "path"}.issubset(tool.parameters["required"])


@pytest.mark.asyncio
async def test_file_io_reads_and_writes_inside_tmp_base(tmp_path: Path) -> None:
    from runsight_core.tools.file_io import create_file_io_tool

    tool = create_file_io_tool(base_dir=str(tmp_path))

    write_result = await tool.execute({"action": "write", "path": "output.txt", "content": "data"})
    read_result = await tool.execute({"action": "read", "path": "output.txt"})

    assert isinstance(write_result, str) and write_result
    assert (tmp_path / "output.txt").read_text() == "data"
    assert "data" in read_result


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["../../../etc/passwd", "/etc/passwd"])
async def test_file_io_rejects_path_traversal(tmp_path: Path, path: str) -> None:
    from runsight_core.tools.file_io import create_file_io_tool

    tool = create_file_io_tool(base_dir=str(tmp_path))

    with pytest.raises((ValueError, PermissionError)):
        await tool.execute({"action": "read", "path": path})


@pytest.mark.asyncio
async def test_file_io_rejects_symlink_escape_to_sibling_prefix(tmp_path: Path) -> None:
    from runsight_core.tools.file_io import create_file_io_tool

    base = tmp_path / "sandbox"
    sibling = tmp_path / "sandbox-escape"
    base.mkdir()
    sibling.mkdir()
    (sibling / "secret.txt").write_text("outside")
    (base / "escape-link").symlink_to(sibling, target_is_directory=True)
    tool = create_file_io_tool(base_dir=str(base))

    with pytest.raises((ValueError, PermissionError)):
        await tool.execute({"action": "read", "path": "escape-link/secret.txt"})


@pytest.mark.asyncio
async def test_file_io_missing_file_returns_error_or_filenotfound(tmp_path: Path) -> None:
    from runsight_core.tools.file_io import create_file_io_tool

    tool = create_file_io_tool(base_dir=str(tmp_path))

    try:
        result = await tool.execute({"action": "read", "path": "missing.txt"})
    except FileNotFoundError:
        return
    assert "error" in result.lower() or "not found" in result.lower()
