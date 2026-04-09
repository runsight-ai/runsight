from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from importlib import util
from pathlib import Path
from types import ModuleType
from typing import Any, Collection, Tuple

from runsight_core.primitives import Soul
from runsight_core.workflow import Workflow

from ._base import AssetType, BaseScanner, ScanError, ScanIndex, ScanResult

RESERVED_BUILTIN_TOOL_IDS = frozenset({"http", "file_io", "delegate"})


@dataclass(frozen=True, slots=True)
class ToolMeta:
    """Metadata for a discovered custom tool definition file."""

    tool_id: str
    file_path: Path
    version: str
    type: str
    executor: str
    name: str
    description: str
    parameters: dict[str, Any]
    code: str | None = None
    code_file: str | None = None
    request: dict[str, Any] | None = None
    timeout_seconds: int | None = None


def _to_snake_case(name: str) -> str:
    result = []
    for i, char in enumerate(name):
        if char.isupper() and i > 0:
            result.append("_")
        result.append(char.lower())
    return "".join(result)


@lru_cache(maxsize=1)
def _legacy_module() -> ModuleType:
    legacy_path = Path(__file__).resolve().parents[1] / "discovery.py"
    spec = util.spec_from_file_location("runsight_core.yaml._legacy_discovery", legacy_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load legacy discovery module from {legacy_path}")
    module = util.module_from_spec(spec)
    import sys

    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _coerce_tool_meta(tool_meta: Any) -> ToolMeta:
    if isinstance(tool_meta, ToolMeta):
        return tool_meta
    if hasattr(tool_meta, "__dict__"):
        data = dict(tool_meta.__dict__)
    else:
        data = {
            "tool_id": tool_meta.tool_id,
            "file_path": tool_meta.file_path,
            "version": tool_meta.version,
            "type": tool_meta.type,
            "executor": tool_meta.executor,
            "name": tool_meta.name,
            "description": tool_meta.description,
            "parameters": tool_meta.parameters,
            "code": getattr(tool_meta, "code", None),
            "code_file": getattr(tool_meta, "code_file", None),
            "request": getattr(tool_meta, "request", None),
            "timeout_seconds": getattr(tool_meta, "timeout_seconds", None),
        }
    return ToolMeta(**data)


def discover_custom_tools(base_dir: str | Path) -> dict[str, ToolMeta]:
    legacy = _legacy_module()
    discovered = legacy.discover_custom_tools(base_dir)
    return {tool_id: _coerce_tool_meta(tool_meta) for tool_id, tool_meta in discovered.items()}


def _discover_souls(
    souls_dir: Path,
    *,
    ignore_keys: Collection[str] | None = None,
) -> dict[str, Soul]:
    return _legacy_module()._discover_souls(souls_dir, ignore_keys=ignore_keys)


def _discover_blocks(blocks_dir: Path) -> dict[str, type]:
    return _legacy_module()._discover_blocks(blocks_dir)


def _discover_workflows(workflows_dir: Path) -> dict[str, Workflow]:
    return _legacy_module()._discover_workflows(workflows_dir)


def discover_custom_assets(
    custom_dir: str | Path = "custom",
) -> Tuple[dict[str, type], dict[str, Soul], dict[str, Workflow]]:
    return _legacy_module().discover_custom_assets(custom_dir)


def __getattr__(name: str) -> Any:
    return getattr(_legacy_module(), name)


__all__ = [
    "AssetType",
    "BaseScanner",
    "RESERVED_BUILTIN_TOOL_IDS",
    "ScanError",
    "ScanIndex",
    "ScanResult",
    "ToolMeta",
    "_discover_blocks",
    "_discover_souls",
    "_discover_workflows",
    "_to_snake_case",
    "discover_custom_assets",
    "discover_custom_tools",
]
