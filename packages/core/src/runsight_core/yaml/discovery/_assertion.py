from __future__ import annotations

import ast
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, StringConstraints, ValidationError

from runsight_core.assertions.contract import ASSERTION_FUNCTION_NAME, ASSERTION_FUNCTION_PARAMS
from runsight_core.assertions.deterministic import _ALL_ASSERTIONS
from runsight_core.yaml.discovery._base import BaseScanner, ScanIndex, ScanResult

RESERVED_BUILTIN_ASSERTION_IDS = frozenset(assertion.type for assertion in _ALL_ASSERTIONS)
NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
AssertionReturn = Literal["bool", "grading_result"]


class AssertionManifest(BaseModel):
    """Validated custom assertion manifest schema."""

    model_config = ConfigDict(extra="forbid")

    version: NonEmptyString
    name: NonEmptyString
    description: NonEmptyString
    returns: AssertionReturn
    source: NonEmptyString
    params: dict[str, Any] | None = None


@dataclass
class AssertionMeta:
    """Metadata for a discovered custom assertion manifest."""

    assertion_id: str
    file_path: Path
    manifest: AssertionManifest
    code: str | None = None


def _fail_assertion_file(yaml_file: Path, message: str) -> ValueError:
    return ValueError(f"{yaml_file.name}: {message}")


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


def _assertion_signature() -> str:
    params = ", ".join(ASSERTION_FUNCTION_PARAMS)
    return f"def {ASSERTION_FUNCTION_NAME}({params})"


def _validate_get_assert_contract(code: str) -> None:
    """Require the shared custom assertion entrypoint contract."""
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        raise ValueError(f"Assertion code has a syntax error: {exc}") from exc

    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == ASSERTION_FUNCTION_NAME:
            raise ValueError(f"Assertion code must define '{_assertion_signature()}'")

        if not isinstance(node, ast.FunctionDef) or node.name != ASSERTION_FUNCTION_NAME:
            continue

        if (
            len(node.args.posonlyargs) != 0
            or len(node.args.args) != len(ASSERTION_FUNCTION_PARAMS)
            or tuple(arg.arg for arg in node.args.args) != ASSERTION_FUNCTION_PARAMS
            or node.args.vararg is not None
            or len(node.args.kwonlyargs) != 0
            or node.args.kwarg is not None
        ):
            raise ValueError(f"Assertion code must define '{_assertion_signature()}'")
        return

    raise ValueError(f"Assertion code must define '{_assertion_signature()}'")


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

        try:
            manifest = AssertionManifest.model_validate(raw)
        except ValidationError as exc:
            raise _fail_assertion_file(yaml_file, str(exc)) from exc

        code = _read_assertion_source_file(yaml_file, manifest.source)
        try:
            _validate_get_assert_contract(code)
        except ValueError as exc:
            raise _fail_assertion_file(yaml_file, str(exc)) from exc

        return AssertionMeta(
            assertion_id=assertion_id,
            file_path=yaml_file,
            manifest=manifest,
            code=code,
        )
