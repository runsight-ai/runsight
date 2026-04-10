from __future__ import annotations

import ast
import logging
import subprocess
from pathlib import Path
from typing import Annotated, Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, StringConstraints, ValidationError

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

    version: NonEmptyString
    type: Literal["custom"]
    executor: NonEmptyString
    name: NonEmptyString
    description: NonEmptyString
    parameters: dict[str, Any]
    code: str | None = None
    code_file: str | None = None
    request: RequestConfig | None = None
    timeout_seconds: int | None = None


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

        try:
            manifest = ToolManifest.model_validate(raw)
        except ValidationError as exc:
            raise _fail_tool_file(yaml_file, str(exc)) from exc

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
            tool_id=tool_id,
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
