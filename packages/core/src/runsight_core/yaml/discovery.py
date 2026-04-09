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
import logging
import sys
from dataclasses import dataclass
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


@dataclass
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


RESERVED_BUILTIN_TOOL_IDS = frozenset({"http", "file_io", "delegate"})
logger = logging.getLogger(__name__)


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


def _fail_tool_file(yaml_file: Path, message: str) -> ValueError:
    return ValueError(f"{yaml_file.name}: {message}")


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


def _require_string(raw: dict[str, Any], key: str, *, yaml_file: Path) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise _fail_tool_file(yaml_file, f"missing or invalid {key!r}")
    return value


def _require_mapping(raw: dict[str, Any], key: str, *, yaml_file: Path) -> dict[str, Any]:
    value = raw.get(key)
    if not isinstance(value, dict):
        raise _fail_tool_file(yaml_file, f"missing or invalid {key!r}")
    return value


def _read_tool_code_file(yaml_file: Path, code_file: str) -> str:
    code_path = yaml_file.parent / code_file
    if not code_path.exists():
        raise _fail_tool_file(yaml_file, f"referenced code_file does not exist: {code_file}")
    if not code_path.is_file():
        raise _fail_tool_file(yaml_file, f"referenced code_file is not readable: {code_file}")

    try:
        return code_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise _fail_tool_file(
            yaml_file, f"referenced code_file is not readable: {code_file}"
        ) from exc


def _normalize_request_config(yaml_file: Path, raw_request: dict[str, Any]) -> dict[str, Any]:
    allowed_fields = {"method", "url", "headers", "body_template", "response_path"}
    extra_fields = sorted(set(raw_request.keys()) - allowed_fields)
    if extra_fields:
        joined = ", ".join(extra_fields)
        raise _fail_tool_file(yaml_file, f"unsupported request fields: {joined}")

    method = raw_request.get("method", "GET")
    url = raw_request.get("url")
    headers = raw_request.get("headers")
    body_template = raw_request.get("body_template")
    response_path = raw_request.get("response_path")

    if not isinstance(method, str) or not method.strip():
        raise _fail_tool_file(yaml_file, "missing or invalid request.method")
    if not isinstance(url, str) or not url.strip():
        raise _fail_tool_file(yaml_file, "missing or invalid request.url")
    if headers is not None:
        if not isinstance(headers, dict) or any(
            not isinstance(key, str) or not isinstance(value, str) for key, value in headers.items()
        ):
            raise _fail_tool_file(yaml_file, "request.headers must be a mapping of strings")
    if body_template is not None and not isinstance(body_template, str):
        raise _fail_tool_file(yaml_file, "request.body_template must be a string")
    if response_path is not None and not isinstance(response_path, str):
        raise _fail_tool_file(yaml_file, "request.response_path must be a string")

    return {
        "method": method,
        "url": url,
        "headers": headers or {},
        "body_template": body_template,
        "response_path": response_path,
    }


def discover_custom_tools(base_dir: str | Path) -> Dict[str, ToolMeta]:
    """Discover custom tool metadata files from ``custom/tools/*.yaml``."""
    base_path = Path(base_dir)
    tools_dir = base_path / "custom" / "tools"

    if not tools_dir.exists():
        return {}

    discovered: Dict[str, ToolMeta] = {}

    for yaml_file in tools_dir.glob("*.yaml"):
        tool_id = yaml_file.stem
        if tool_id in RESERVED_BUILTIN_TOOL_IDS:
            collision_path = yaml_file
            try:
                collision_path = yaml_file.relative_to(base_path)
            except ValueError:
                pass
            raise _fail_tool_file(
                yaml_file,
                f"reserved builtin tool id {tool_id!r} collides with custom tool metadata at "
                f"{collision_path}",
            )
        if tool_id in discovered:
            raise _fail_tool_file(yaml_file, f"duplicate custom tool id collision for {tool_id!r}")

        try:
            raw = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise _fail_tool_file(yaml_file, "malformed YAML") from exc

        if not isinstance(raw, dict):
            raise _fail_tool_file(yaml_file, "invalid tool metadata")

        allowed_fields = {
            "version",
            "type",
            "executor",
            "name",
            "description",
            "parameters",
            "code",
            "code_file",
            "request",
            "timeout_seconds",
        }
        extra_fields = sorted(set(raw.keys()) - allowed_fields)
        if extra_fields:
            joined = ", ".join(extra_fields)
            raise _fail_tool_file(yaml_file, f"unsupported fields: {joined}")

        version = _require_string(raw, "version", yaml_file=yaml_file)
        tool_type = _require_string(raw, "type", yaml_file=yaml_file)
        if tool_type != "custom":
            raise _fail_tool_file(yaml_file, "type must be 'custom'")

        executor = _require_string(raw, "executor", yaml_file=yaml_file)
        name = _require_string(raw, "name", yaml_file=yaml_file)
        description = _require_string(raw, "description", yaml_file=yaml_file)
        parameters = _require_mapping(raw, "parameters", yaml_file=yaml_file)
        code = raw.get("code")
        code_file = raw.get("code_file")
        request = raw.get("request")
        timeout_seconds = raw.get("timeout_seconds")
        if code is not None and not isinstance(code, str):
            raise _fail_tool_file(yaml_file, "code must be a string")
        if code_file is not None and not isinstance(code_file, str):
            raise _fail_tool_file(yaml_file, "code_file must be a string")
        if timeout_seconds is not None and (
            not isinstance(timeout_seconds, int)
            or isinstance(timeout_seconds, bool)
            or timeout_seconds < 1
        ):
            raise _fail_tool_file(yaml_file, "timeout_seconds must be a positive integer")

        normalized_request: dict[str, Any] | None = None
        if executor == "python":
            if request is not None or timeout_seconds is not None:
                raise _fail_tool_file(yaml_file, "python executor cannot declare request fields")
            if code and code_file:
                raise _fail_tool_file(
                    yaml_file, "python executor cannot declare both code and code_file"
                )
            if code_file:
                code = _read_tool_code_file(yaml_file, code_file)
            elif not code:
                raise _fail_tool_file(yaml_file, "python executor requires code or code_file")

            try:
                _validate_tool_main_contract(code)
            except ValueError as exc:
                raise _fail_tool_file(yaml_file, str(exc)) from exc
        elif executor == "request":
            if code is not None or code_file is not None:
                raise _fail_tool_file(yaml_file, "request executor cannot declare python fields")
            if not isinstance(request, dict):
                raise _fail_tool_file(yaml_file, "request executor requires a request mapping")
            normalized_request = _normalize_request_config(yaml_file, request)
        else:
            raise _fail_tool_file(yaml_file, f"unknown executor {executor!r}")

        discovered[tool_id] = ToolMeta(
            tool_id=tool_id,
            file_path=yaml_file,
            version=version,
            type=tool_type,
            executor=executor,
            name=name,
            description=description,
            parameters=parameters,
            code=code,
            code_file=code_file,
            request=normalized_request,
            timeout_seconds=timeout_seconds,
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
