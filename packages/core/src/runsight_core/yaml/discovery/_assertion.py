from __future__ import annotations

import ast
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from runsight_core.assertions.deterministic import _ALL_ASSERTIONS
from runsight_core.yaml.discovery._base import BaseScanner, ScanIndex, ScanResult

ALLOWED_ASSERTION_RETURNS = frozenset({"bool", "grading_result"})
RESERVED_BUILTIN_ASSERTION_IDS = frozenset(assertion.type for assertion in _ALL_ASSERTIONS)


@dataclass
class AssertionMeta:
    """Metadata for a discovered custom assertion manifest."""

    assertion_id: str
    file_path: Path
    version: str
    name: str
    description: str
    returns: str
    source: str
    params: dict[str, Any] | None = None
    code: str | None = None


def _fail_assertion_file(yaml_file: Path, message: str) -> ValueError:
    return ValueError(f"{yaml_file.name}: {message}")


def _require_string(raw: dict[str, Any], key: str, *, yaml_file: Path) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise _fail_assertion_file(yaml_file, f"missing or invalid {key!r}")
    return value


def _require_optional_mapping(
    raw: dict[str, Any], key: str, *, yaml_file: Path
) -> dict[str, Any] | None:
    value = raw.get(key)
    if value is None:
        return None
    if not isinstance(value, dict):
        raise _fail_assertion_file(yaml_file, f"invalid {key!r}")
    return value


def _read_assertion_source_file(yaml_file: Path, source: str) -> str:
    source_path = yaml_file.parent / source
    if not source_path.exists():
        raise _fail_assertion_file(yaml_file, f"referenced source does not exist: {source}")
    if not source_path.is_file():
        raise _fail_assertion_file(yaml_file, f"referenced source is not readable: {source}")

    try:
        return source_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise _fail_assertion_file(
            yaml_file, f"referenced source is not readable: {source}"
        ) from exc


def _validate_get_assert_contract(code: str) -> None:
    """Require a strict ``def get_assert(args)`` function in custom assertion code."""
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        raise ValueError(f"Assertion code has a syntax error: {exc}") from exc

    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.name != "get_assert":
            continue

        if (
            len(node.args.posonlyargs) != 0
            or len(node.args.args) != 1
            or node.args.args[0].arg != "args"
            or node.args.vararg is not None
            or len(node.args.kwonlyargs) != 0
            or node.args.kwarg is not None
        ):
            raise ValueError("Assertion code must define 'def get_assert(args)'")
        return

    raise ValueError("Assertion code must define 'def get_assert(args)'")


class AssertionScanner(BaseScanner[AssertionMeta]):
    """Scanner for custom assertion metadata YAML files."""

    def __init__(
        self,
        base_dir: str | Path,
        *,
        assertions_subdir: str = "custom/assertions",
    ) -> None:
        super().__init__(base_dir)
        self._assertions_subdir = assertions_subdir

    @property
    def asset_subdir(self) -> str:
        return self._assertions_subdir

    def _glob_yaml_files(self, directory: Path) -> list[Path]:
        return sorted(directory.glob("*.yaml"), key=lambda path: path.name)

    def _parse_file(self, path: Path, raw_yaml: str) -> AssertionMeta:
        parsed = yaml.safe_load(raw_yaml)
        if not isinstance(parsed, dict):
            raise _fail_assertion_file(path, "invalid assertion metadata")
        return self._parse_assertion_mapping(path, parsed)

    def _scan_filesystem(self) -> ScanIndex[AssertionMeta]:
        asset_dir = self.asset_dir
        if not asset_dir.exists():
            return ScanIndex()

        results: list[ScanResult[AssertionMeta]] = []
        for yaml_file in self._glob_yaml_files(asset_dir):
            result = self._scan_yaml_file(yaml_file)
            if result is not None:
                results.append(result)
        return ScanIndex(results)

    def _scan_git(self, git_ref: str, git_service: Any) -> ScanIndex[AssertionMeta]:
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

        results: list[ScanResult[AssertionMeta]] = []
        for line in result.stdout.splitlines():
            candidate = line.strip()
            if not candidate or not candidate.endswith(".yaml"):
                continue
            try:
                raw_yaml = git_service.read_file(candidate, git_ref)
            except Exception:
                continue
            result_item = self._scan_yaml_content(Path(candidate), raw_yaml)
            if result_item is not None:
                results.append(result_item)
        return ScanIndex(results)

    def _parse_assertion_mapping(self, yaml_file: Path, raw: dict[str, Any]) -> AssertionMeta:
        assertion_id = yaml_file.stem
        if assertion_id in RESERVED_BUILTIN_ASSERTION_IDS:
            collision_path: Path | str = yaml_file
            try:
                collision_path = yaml_file.relative_to(self.base_dir)
            except ValueError:
                try:
                    collision_path = yaml_file.resolve().relative_to(self.base_dir.resolve())
                except ValueError:
                    pass
            raise _fail_assertion_file(
                yaml_file,
                f"reserved builtin assertion id {assertion_id!r} collides with custom assertion metadata at "
                f"{collision_path}",
            )

        allowed_fields = {"version", "name", "description", "returns", "source", "params"}
        extra_fields = sorted(set(raw.keys()) - allowed_fields)
        if extra_fields:
            joined = ", ".join(extra_fields)
            raise _fail_assertion_file(yaml_file, f"unsupported assertion fields: {joined}")

        version = _require_string(raw, "version", yaml_file=yaml_file)
        name = _require_string(raw, "name", yaml_file=yaml_file)
        description = _require_string(raw, "description", yaml_file=yaml_file)
        returns = _require_string(raw, "returns", yaml_file=yaml_file)
        source = _require_string(raw, "source", yaml_file=yaml_file)
        params = _require_optional_mapping(raw, "params", yaml_file=yaml_file)

        if returns not in ALLOWED_ASSERTION_RETURNS:
            allowed = ", ".join(sorted(ALLOWED_ASSERTION_RETURNS))
            raise _fail_assertion_file(
                yaml_file,
                f"invalid returns {returns!r}; expected one of: {allowed}",
            )

        code = _read_assertion_source_file(yaml_file, source)
        try:
            _validate_get_assert_contract(code)
        except ValueError as exc:
            raise _fail_assertion_file(yaml_file, str(exc)) from exc

        return AssertionMeta(
            assertion_id=assertion_id,
            file_path=yaml_file,
            version=version,
            name=name,
            description=description,
            returns=returns,
            source=source,
            params=params,
            code=code,
        )
