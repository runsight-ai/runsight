"""Built-in file I/O tool."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

from runsight_core.tools._catalog import ToolInstance, register_builtin

_PARAMETERS_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["read", "write"]},
        "path": {"type": "string"},
        "content": {"type": "string"},
    },
    "required": ["action", "path"],
}


def _validate_path(base_dir: Path, relative_path: str) -> Path:
    """Resolve and validate that *relative_path* stays inside *base_dir*."""
    if os.path.isabs(relative_path):
        raise PermissionError(f"Absolute paths are not allowed: {relative_path}")

    if ".." in Path(relative_path).parts:
        raise PermissionError(f"Path traversal is not allowed: {relative_path}")

    resolved = (base_dir / relative_path).resolve()
    if not str(resolved).startswith(str(base_dir.resolve())):
        raise PermissionError(f"Path escapes base directory: {relative_path}")

    return resolved


def create_file_io_tool(base_dir: str = ".") -> ToolInstance:
    """Factory that returns a ToolInstance for file read/write operations."""
    base = Path(base_dir)

    async def _execute(args: dict) -> str:
        action = args["action"]
        path = args["path"]

        target = _validate_path(base, path)

        if action == "read":
            if not target.exists():
                raise FileNotFoundError(f"File not found: {path}")
            return target.read_text()

        if action == "write":
            content = args.get("content", "")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
            return f"Written {len(content)} bytes to {path}"

        return f"Error: unknown action '{action}'"

    return ToolInstance(
        name="file_io",
        description="Read or write files within a sandboxed directory.",
        parameters=_PARAMETERS_SCHEMA,
        execute=_execute,
    )


register_builtin("file_io", create_file_io_tool)
