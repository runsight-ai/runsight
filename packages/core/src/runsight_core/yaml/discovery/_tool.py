from __future__ import annotations

import ast
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from runsight_core.yaml.discovery._base import BaseScanner, ScanIndex, ScanResult

logger = logging.getLogger(__name__)


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


def _fail_tool_file(yaml_file: Path, message: str) -> ValueError:
    return ValueError(f"{yaml_file.name}: {message}")


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


class ToolScanner(BaseScanner[ToolMeta]):
    """Scanner for custom tool metadata YAML files."""

    def __init__(
        self,
        base_dir: str | Path,
        *,
        tools_subdir: str = "custom/tools",
    ) -> None:
        super().__init__(base_dir)
        self._tools_subdir = tools_subdir

    @property
    def asset_subdir(self) -> str:
        return self._tools_subdir

    def _glob_yaml_files(self, directory: Path) -> list[Path]:
        # Keep historical behavior: tool discovery scans only *.yaml files.
        return sorted(directory.glob("*.yaml"), key=lambda path: path.name)

    def _parse_file(self, path: Path, raw_yaml: str) -> ToolMeta:
        parsed = yaml.safe_load(raw_yaml)
        if not isinstance(parsed, dict):
            raise _fail_tool_file(path, "invalid tool metadata")
        return self._parse_tool_mapping(path, parsed)

    def _scan_yaml_content(self, path: Path, raw_yaml: str) -> ScanResult[ToolMeta] | None:
        try:
            parsed = yaml.safe_load(raw_yaml)
        except yaml.YAMLError as exc:
            raise _fail_tool_file(path, "malformed YAML") from exc

        if not isinstance(parsed, dict):
            raise _fail_tool_file(path, "invalid tool metadata")

        item = self._parse_tool_mapping(path, parsed)
        aliases = self._compute_aliases(path, item)
        resolved = path.resolve()
        try:
            relative_path = resolved.relative_to(self.base_dir.resolve()).as_posix()
        except ValueError:
            relative_path = path.as_posix()
        aliases.add(resolved.as_posix())
        aliases.add(path.stem)
        aliases.add(relative_path)
        return ScanResult(
            path=resolved,
            stem=path.stem,
            relative_path=relative_path,
            item=item,
            aliases=frozenset(aliases),
        )

    def _scan_filesystem(self) -> ScanIndex[ToolMeta]:
        asset_dir = self.asset_dir
        if not asset_dir.exists():
            return ScanIndex()

        results: list[ScanResult[ToolMeta]] = []
        seen_stems: set[str] = set()
        for yaml_file in self._glob_yaml_files(asset_dir):
            if yaml_file.stem in seen_stems:
                raise _fail_tool_file(
                    yaml_file,
                    f"duplicate custom tool id collision for {yaml_file.stem!r}",
                )
            seen_stems.add(yaml_file.stem)
            result = self._scan_yaml_file(yaml_file)
            if result is not None:
                results.append(result)
        return ScanIndex(results)

    def _scan_git(self, git_ref: str, git_service: Any) -> ScanIndex[ToolMeta]:
        command = [
            "git",
            "ls-tree",
            "-r",
            "--name-only",
            git_ref,
            "--",
            f"{self.asset_subdir}/",
        ]
        result = subprocess.run(
            command,
            cwd=str(git_service.repo_path),
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return ScanIndex()

        results: list[ScanResult[ToolMeta]] = []
        seen_stems: set[str] = set()
        for line in result.stdout.splitlines():
            candidate = line.strip()
            if not candidate or not candidate.endswith(".yaml"):
                continue
            candidate_path = Path(candidate)
            if candidate_path.stem in seen_stems:
                raise _fail_tool_file(
                    candidate_path,
                    f"duplicate custom tool id collision for {candidate_path.stem!r}",
                )
            seen_stems.add(candidate_path.stem)
            try:
                raw_yaml = git_service.read_file(candidate, git_ref)
            except Exception:
                continue
            result_item = self._scan_yaml_content(candidate_path, raw_yaml)
            if result_item is not None:
                results.append(result_item)
        return ScanIndex(results)

    def _parse_tool_mapping(self, yaml_file: Path, raw: dict[str, Any]) -> ToolMeta:
        tool_id = yaml_file.stem
        if tool_id in RESERVED_BUILTIN_TOOL_IDS:
            collision_path: Path | str = yaml_file
            try:
                collision_path = yaml_file.relative_to(self.base_dir)
            except ValueError:
                try:
                    collision_path = yaml_file.resolve().relative_to(self.base_dir.resolve())
                except ValueError:
                    pass
            raise _fail_tool_file(
                yaml_file,
                f"reserved builtin tool id {tool_id!r} collides with custom tool metadata at "
                f"{collision_path}",
            )

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

        return ToolMeta(
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
