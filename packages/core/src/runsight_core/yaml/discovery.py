"""
Auto-discovery engine for custom blocks, souls, tasks, and workflows.

This module provides functionality to discover and load custom assets from a directory structure:
- custom/blocks/: Python files containing BaseBlock subclasses
- custom/souls/: YAML soul files
- custom/tasks/: YAML task files (future use)
- custom/workflows/: YAML workflow files

Usage:
    from runsight_core.yaml.discovery import discover_custom_assets
    blocks, souls, workflows = discover_custom_assets(custom_dir="./custom")
"""

from __future__ import annotations

import importlib.util
import logging
import sys
from pathlib import Path
from typing import Any, Collection, Dict, Tuple

import yaml
from pydantic import ValidationError

from runsight_core.blocks.base import BaseBlock
from runsight_core.primitives import Soul
from runsight_core.workflow import Workflow

__path__ = [str(Path(__file__).with_name("discovery"))]
if __spec__ is not None:
    __spec__.submodule_search_locations = __path__

from runsight_core.yaml.discovery._base import BaseScanner, ScanIndex
from runsight_core.yaml.discovery._tool import (
    RESERVED_BUILTIN_TOOL_IDS,
    ToolMeta,
    ToolScanner,
)

logger = logging.getLogger(__name__)

__all__ = [
    "RESERVED_BUILTIN_TOOL_IDS",
    "SoulScanner",
    "ToolMeta",
    "ToolScanner",
    "_to_snake_case",
    "discover_custom_assets",
]


def _to_snake_case(name: str) -> str:
    """
    Convert CamelCase class name to snake_case identifier.

    Examples:
        MyBlock -> my_block
        HTTPHandler -> h_t_t_p_handler
    """
    result = []
    for i, char in enumerate(name):
        if char.isupper() and i > 0:
            result.append("_")
        result.append(char.lower())
    return "".join(result)


def _fail_soul_file(yaml_file: Path, message: str) -> ValueError:
    return ValueError(f"{yaml_file.name}: {message}")


class SoulScanner(BaseScanner[Soul]):
    """Scanner for soul YAML files."""

    def __init__(
        self,
        base_dir: str | Path,
        *,
        souls_subdir: str = "custom/souls",
    ) -> None:
        super().__init__(base_dir)
        self._souls_subdir = souls_subdir

    @property
    def asset_subdir(self) -> str:
        return self._souls_subdir

    def _parse_file(self, path: Path, raw_yaml: str) -> Soul:
        try:
            soul_data = yaml.safe_load(raw_yaml)
        except yaml.YAMLError as exc:
            raise _fail_soul_file(path, "malformed YAML") from exc

        try:
            return Soul.model_validate(soul_data)
        except ValidationError as exc:
            raise _fail_soul_file(path, str(exc)) from exc

    def _glob_yaml_files(self, directory: Path) -> list[Path]:
        # Keep historical discovery behavior: souls are discovered only from *.yaml files.
        return sorted(directory.glob("*.yaml"), key=lambda path: path.name)

    def scan(
        self,
        *,
        ignore_keys: Collection[str] | None = None,
        git_ref: str | None = None,
        git_service: Any = None,
    ) -> ScanIndex[Soul]:
        index = super().scan(git_ref=git_ref, git_service=git_service)
        ignored_soul_keys = set(ignore_keys or ())
        if not ignored_soul_keys:
            return index

        for soul_key in sorted(ignored_soul_keys & set(index.stems())):
            logger.warning("Inline soul '%s' overrides external soul file", soul_key)
        return index.without_stems(ignored_soul_keys)


def _discover_blocks(blocks_dir: Path) -> Dict[str, type]:
    """
    Discover all BaseBlock subclasses in Python files under blocks_dir.

    Args:
        blocks_dir: Path to custom/blocks/ directory.

    Returns:
        Dict mapping snake_case block ID to BaseBlock subclass.
        Returns empty dict if blocks_dir doesn't exist.
    """
    blocks: Dict[str, type] = {}

    if not blocks_dir.exists():
        return blocks

    # Import all .py files in blocks_dir
    for py_file in blocks_dir.glob("*.py"):
        if py_file.name.startswith("_"):
            continue  # Skip __init__.py and _private.py

        # Dynamically load the module
        spec = importlib.util.spec_from_file_location(py_file.stem, py_file)
        if spec is None or spec.loader is None:
            continue

        module = importlib.util.module_from_spec(spec)
        sys.modules[py_file.stem] = module
        spec.loader.exec_module(module)

        # Find all BaseBlock subclasses in the module
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            # Check if it's a class, subclass of BaseBlock, and not BaseBlock itself
            if (
                isinstance(attr, type)
                and issubclass(attr, BaseBlock)
                and attr is not BaseBlock
                and attr.__module__ == module.__name__
            ):
                block_id = _to_snake_case(attr_name)
                blocks[block_id] = attr

    return blocks


def _discover_workflows(workflows_dir: Path) -> Dict[str, Workflow]:
    """
    Discover and parse all Workflow definitions from YAML files in workflows_dir.

    Args:
        workflows_dir: Path to custom/workflows/ directory.

    Returns:
        Dict mapping workflow key (from filename stem) to Workflow object.
        Returns empty dict if workflows_dir doesn't exist.

    Raises:
        ValueError: If workflow parsing fails.
        yaml.YAMLError: If YAML is malformed.
    """
    workflows: Dict[str, Workflow] = {}

    if not workflows_dir.exists():
        return workflows

    from runsight_core.yaml.parser import parse_workflow_yaml

    for yaml_file in workflows_dir.glob("*.yaml"):
        workflow_key = yaml_file.stem

        with open(yaml_file, "r", encoding="utf-8") as f:
            workflow_yaml = f.read()

        workflow = parse_workflow_yaml(workflow_yaml)
        workflows[workflow_key] = workflow

    return workflows


def discover_custom_assets(
    custom_dir: str | Path = "custom",
) -> Tuple[Dict[str, type], Dict[str, Soul], Dict[str, Workflow]]:
    """
    Auto-discover and load custom blocks, souls, and workflows from a directory.

    Expected directory structure:
        custom/
          blocks/         # Python files with BaseBlock subclasses
          souls/          # YAML soul definitions
          tasks/          # YAML task definitions (future use)
          workflows/      # YAML workflow definitions

    Args:
        custom_dir: Root directory containing custom assets (default: "custom").
                   Can be absolute or relative path.
                   Returns empty maps if directory doesn't exist.

    Returns:
        Tuple of three dicts:
        - blocks: {snake_case_id: BaseBlock subclass}
        - souls: {soul_key: Soul}
        - workflows: {workflow_key: Workflow}

        Each dict is empty if the corresponding subdirectory doesn't exist.

    Raises:
        ValueError: If workflow YAML parsing fails.
        yaml.YAMLError: If any YAML is malformed.
    """
    custom_path = Path(custom_dir)

    # Discover each asset type
    blocks = _discover_blocks(custom_path / "blocks")
    souls = SoulScanner(custom_path, souls_subdir="souls").scan().stems()
    workflows = _discover_workflows(custom_path / "workflows")

    return blocks, souls, workflows
