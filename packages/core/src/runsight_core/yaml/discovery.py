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

import ast
import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple

import yaml

from runsight_core.blocks.base import BaseBlock
from runsight_core.primitives import Soul
from runsight_core.workflow import Workflow


@dataclass
class ToolMeta:
    """Metadata for a discovered custom tool definition file."""

    type: str
    source: str
    code: str | None = None
    code_file: str | None = None
    method: str | None = None
    url: str | None = None
    body_template: str | None = None
    response_path: str | None = None


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


def _validate_tool_main_contract(code: str) -> None:
    """Require a ``def main(args)`` function in custom tool code."""
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        raise ValueError(f"Tool code has a syntax error: {exc}") from exc

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "main":
            args = node.args.args
            if len(args) != 1 or args[0].arg != "args":
                raise ValueError("Tool code must define 'def main(args)'")
            return

    raise ValueError("Tool code must define 'def main(args)'")


def discover_custom_tools(base_dir: str | Path) -> Dict[str, ToolMeta]:
    """Discover custom tool metadata files from ``custom/tools/*.yaml``."""
    base_path = Path(base_dir)
    tools_dir = base_path / "custom" / "tools"

    if not tools_dir.exists():
        return {}

    discovered: Dict[str, ToolMeta] = {}

    for yaml_file in tools_dir.glob("*.yaml"):
        try:
            raw = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise ValueError(f"{yaml_file.name}: malformed YAML") from exc

        if not isinstance(raw, dict):
            raise ValueError(f"{yaml_file.name}: invalid tool metadata")

        tool_type = raw.get("type")
        if tool_type not in {"custom", "http"}:
            raise ValueError(f"{yaml_file.name}: unsupported tool type {tool_type!r}")

        code = raw.get("code")
        code_file = raw.get("code_file")
        method = raw.get("method")
        url = raw.get("url")
        body_template = raw.get("body_template")
        response_path = raw.get("response_path")
        allowed_fields = {
            "type",
            "source",
            "code",
            "code_file",
            "method",
            "url",
            "body_template",
            "response_path",
        }
        extra_fields = sorted(set(raw.keys()) - allowed_fields)
        if extra_fields:
            raise ValueError(f"{yaml_file.name}: invalid tool metadata")

        source = raw.get("source")
        if code is not None and not isinstance(code, str):
            raise ValueError(f"{yaml_file.name}: invalid tool metadata")
        if code_file is not None and not isinstance(code_file, str):
            raise ValueError(f"{yaml_file.name}: invalid tool metadata")
        if method is not None and not isinstance(method, str):
            raise ValueError(f"{yaml_file.name}: invalid tool metadata")
        if url is not None and not isinstance(url, str):
            raise ValueError(f"{yaml_file.name}: invalid tool metadata")
        if body_template is not None and not isinstance(body_template, str):
            raise ValueError(f"{yaml_file.name}: invalid tool metadata")
        if response_path is not None and not isinstance(response_path, str):
            raise ValueError(f"{yaml_file.name}: invalid tool metadata")

        if tool_type == "custom":
            if not isinstance(source, str) or not source.strip():
                raise ValueError(f"{yaml_file.name}: invalid tool metadata")
            if code and code_file:
                raise ValueError(
                    f"{yaml_file.name}: custom tools cannot declare both code and code_file"
                )
            if code_file:
                code_path = yaml_file.parent / code_file
                if not code_path.exists():
                    raise ValueError(f"{yaml_file.name}: referenced code_file does not exist")
                code = code_path.read_text(encoding="utf-8")
            elif not code:
                raise ValueError(f"{yaml_file.name}: custom tools require code or code_file")

            try:
                _validate_tool_main_contract(code)
            except ValueError as exc:
                raise ValueError(f"{yaml_file.name}: {exc}") from exc
        else:
            if code is not None or code_file is not None:
                raise ValueError(f"{yaml_file.name}: http tools cannot declare code or code_file")
            if source is not None and (not isinstance(source, str) or not source.strip()):
                raise ValueError(f"{yaml_file.name}: invalid tool metadata")
            if source is None and (not isinstance(url, str) or not url.strip()):
                raise ValueError(f"{yaml_file.name}: invalid tool metadata")
            source = source or yaml_file.stem

        discovered[yaml_file.stem] = ToolMeta(
            type=tool_type,
            source=source,
            code=code,
            code_file=code_file,
            method=method,
            url=url,
            body_template=body_template,
            response_path=response_path,
        )

    return discovered


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


def _discover_souls(souls_dir: Path) -> Dict[str, Soul]:
    """
    Discover and load all Soul definitions from YAML files in souls_dir.

    Expected YAML structure per file:
        id: soul_id
        role: Soul Role
        system_prompt: Prompt text
        tools: [...]  # optional

    Args:
        souls_dir: Path to custom/souls/ directory.

    Returns:
        Dict mapping soul key (from filename stem) to Soul object.
        Returns empty dict if souls_dir doesn't exist.
    """
    souls: Dict[str, Soul] = {}

    if not souls_dir.exists():
        return souls

    for yaml_file in souls_dir.glob("*.yaml"):
        soul_key = yaml_file.stem

        with open(yaml_file, "r", encoding="utf-8") as f:
            soul_data = yaml.safe_load(f)

        if soul_data is None:
            continue

        soul = Soul.model_validate(soul_data)
        souls[soul_key] = soul

    return souls


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
    souls = _discover_souls(custom_path / "souls")
    workflows = _discover_workflows(custom_path / "workflows")

    return blocks, souls, workflows
