from __future__ import annotations

import ast
import logging
import subprocess
from pathlib import Path
from typing import Annotated, Any

import yaml
from pydantic import BaseModel, ConfigDict, StringConstraints, ValidationError, field_validator

from runsight_core.identity import EntityKind, EntityRef, validate_entity_id
from runsight_core.tools.contract import TOOL_FUNCTION_NAME, TOOL_FUNCTION_PARAMS
from runsight_core.yaml.discovery._base import BaseScanner, ScanIndex, ScanResult

logger = logging.getLogger(__name__)

NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class RequestConfig(BaseModel):
    """Validated request config schema for HTTP-backed tools."""

    model_config = ConfigDict(extra="forbid")

    method: str = "GET"
    url: NonEmptyString
    headers: dict[str, str] | None = None
    body_template: str | None = None
    response_path: str | None = None


class ToolManifest(BaseModel):
    """Validated custom tool manifest schema."""

    model_config = ConfigDict(extra="forbid")

    id: NonEmptyString
    kind: NonEmptyString
    version: NonEmptyString
    type: NonEmptyString
    executor: NonEmptyString
    name: NonEmptyString
    description: NonEmptyString
    parameters: dict[str, Any]
    code: str | None = None
    code_file: str | None = None
    request: RequestConfig | None = None
    timeout_seconds: int | None = None

    @field_validator("kind")
    @classmethod
    def _validate_kind(cls, value: str) -> str:
        if value != "tool":
            raise ValueError("kind must be 'tool'")
        return value

    @field_validator("type")
    @classmethod
    def _validate_type(cls, value: str) -> str:
        if value != "custom":
            raise ValueError("type must be 'custom'")
        return value

    @field_validator("id")
    @classmethod
    def _validate_identity(cls, value: str) -> str:
        validate_entity_id(value, EntityKind.TOOL)
        return value


class ToolMeta(BaseModel):
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


def _tool_signature() -> str:
    params = ", ".join(TOOL_FUNCTION_PARAMS)
    return f"def {TOOL_FUNCTION_NAME}({params})"


def _validate_tool_main_contract(code: str) -> None:
    """Require a ``def main(args)`` function in custom tool code."""
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        raise ValueError(f"Tool code has a syntax error: {exc}") from exc

    for node in ast.walk(tree):
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == TOOL_FUNCTION_NAME
        ):
            args = node.args.args
            if (
                len(args) != len(TOOL_FUNCTION_PARAMS)
                or tuple(a.arg for a in args) != TOOL_FUNCTION_PARAMS
            ):
                raise ValueError(f"Tool code must define '{_tool_signature()}'")
            return

    raise ValueError(f"Tool code must define '{_tool_signature()}'")


def _read_tool_code_file(yaml_file: Path, code_file: str) -> str:
    raw_code_path = Path(code_file)
    if raw_code_path.is_absolute():
        raise _fail_tool_file(
            yaml_file, f"referenced code_file escapes tool directory: {code_file}"
        )

    tool_dir = yaml_file.parent.resolve()
    code_path = (yaml_file.parent / raw_code_path).resolve()
    try:
        code_path.relative_to(tool_dir)
    except ValueError as exc:
        raise _fail_tool_file(
            yaml_file, f"referenced code_file escapes tool directory: {code_file}"
        ) from exc

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
        resolved = path.resolve()
        relative_path = resolved.relative_to(self.base_dir.resolve()).as_posix()
        return ScanResult(
            path=resolved,
            stem=item.tool_id,
            relative_path=relative_path,
            item=item,
            aliases=frozenset({item.tool_id}),
            entity_id=item.tool_id,
        )

    def _scan_filesystem(self) -> ScanIndex[ToolMeta]:
        asset_dir = self.asset_dir
        if not asset_dir.exists():
            return ScanIndex()

        results: list[ScanResult[ToolMeta]] = []
        seen_ids: set[str] = set()
        for yaml_file in self._glob_yaml_files(asset_dir):
            result = self._scan_yaml_file(yaml_file)
            if result is not None:
                if result.entity_id in seen_ids:
                    raise _fail_tool_file(
                        yaml_file,
                        f"duplicate custom tool id collision for {result.entity_id!r}",
                    )
                seen_ids.add(result.entity_id)
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
        seen_ids: set[str] = set()
        for line in result.stdout.splitlines():
            candidate = line.strip()
            if not candidate or not candidate.endswith(".yaml"):
                continue
            candidate_path = Path(candidate)
            try:
                raw_yaml = git_service.read_file(candidate, git_ref)
            except Exception:
                continue
            result_item = self._scan_yaml_content(candidate_path, raw_yaml)
            if result_item is not None:
                if result_item.entity_id in seen_ids:
                    raise _fail_tool_file(
                        candidate_path,
                        f"duplicate custom tool id collision for {result_item.entity_id!r}",
                    )
                seen_ids.add(result_item.entity_id)
                results.append(result_item)
        return ScanIndex(results)

    def _parse_tool_mapping(self, yaml_file: Path, raw: dict[str, Any]) -> ToolMeta:
        raw_tool_id = raw.get("id")
        if isinstance(raw_tool_id, str) and raw_tool_id in RESERVED_BUILTIN_TOOL_IDS:
            tool_ref = str(EntityRef(EntityKind.TOOL, raw_tool_id))
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
                f"reserved builtin {tool_ref} collides with custom tool metadata at "
                f"{collision_path}",
            )

        try:
            manifest = ToolManifest.model_validate(raw)
        except ValidationError as exc:
            raise _fail_tool_file(yaml_file, str(exc)) from exc

        if manifest.id != yaml_file.stem:
            raise _fail_tool_file(
                yaml_file,
                f"embedded tool id {manifest.id!r} does not match filename stem {yaml_file.stem!r}",
            )

        if manifest.executor not in ("python", "request"):
            raise _fail_tool_file(yaml_file, f"unknown executor {manifest.executor!r}")

        code = manifest.code
        normalized_request: dict[str, Any] | None = None

        if manifest.executor == "python":
            if manifest.request is not None or manifest.timeout_seconds is not None:
                raise _fail_tool_file(yaml_file, "python executor cannot declare request fields")
            if code and manifest.code_file:
                raise _fail_tool_file(
                    yaml_file, "python executor cannot declare both code and code_file"
                )
            if manifest.code_file:
                code = _read_tool_code_file(yaml_file, manifest.code_file)
            elif not code:
                raise _fail_tool_file(yaml_file, "python executor requires code or code_file")

            try:
                _validate_tool_main_contract(code)
            except ValueError as exc:
                raise _fail_tool_file(yaml_file, str(exc)) from exc
        elif manifest.executor == "request":
            if code is not None or manifest.code_file is not None:
                raise _fail_tool_file(yaml_file, "request executor cannot declare python fields")
            if manifest.request is None:
                raise _fail_tool_file(yaml_file, "request executor requires a request mapping")
            normalized_request = manifest.request.model_dump()
            if normalized_request.get("headers") is None:
                normalized_request["headers"] = {}

        return ToolMeta(
            tool_id=manifest.id,
            file_path=yaml_file,
            version=manifest.version,
            type=manifest.type,
            executor=manifest.executor,
            name=manifest.name,
            description=manifest.description,
            parameters=manifest.parameters,
            code=code,
            code_file=manifest.code_file,
            request=normalized_request,
            timeout_seconds=manifest.timeout_seconds,
        )
