"""Governance tests for core Docker entrypoint workspace ownership.

Owner: tools/tests owns temporary static checks for core test isolation.
Boundary: Docker entrypoint behavior tests must build subprocess workspace
paths under pytest-owned tmp_path, not unmanaged tempfile directories. This
suite inspects only packages/core/tests/test_docker_hardening.py and only the
TestEntrypointBehavior class, so central short-path isolation fixtures in
packages/core/tests/conftest.py remain outside this check.
Exit criteria: delete this suite once the Docker entrypoint behavior tests use
tmp_path-owned existing and missing workspace paths while preserving fail-fast
missing-path semantics.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCKER_HARDENING_TEST = REPO_ROOT / "packages" / "core" / "tests" / "test_docker_hardening.py"
ENTRYPOINT_BEHAVIOR_CLASS = "TestEntrypointBehavior"

pytestmark = pytest.mark.governance


@dataclass(frozen=True)
class TemporaryDirectoryCall:
    method_name: str
    line_number: int
    called_name: str


def _relative(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _source_tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _class_named(tree: ast.Module, name: str) -> ast.ClassDef:
    for statement in tree.body:
        if isinstance(statement, ast.ClassDef) and statement.name == name:
            return statement
    raise AssertionError(f"{_relative(DOCKER_HARDENING_TEST)} is missing {name}.")


def _tempfile_import_names(tree: ast.Module) -> tuple[str, ...]:
    names: list[str] = []
    for statement in tree.body:
        if isinstance(statement, ast.Import):
            names.extend(
                alias.asname or alias.name for alias in statement.names if alias.name == "tempfile"
            )
    return tuple(names)


def _direct_temporary_directory_import_names(tree: ast.Module) -> tuple[str, ...]:
    names: list[str] = []
    for statement in tree.body:
        if isinstance(statement, ast.ImportFrom) and statement.module == "tempfile":
            names.extend(
                alias.asname or alias.name
                for alias in statement.names
                if alias.name == "TemporaryDirectory"
            )
    return tuple(names)


def _called_temporary_directory_name(
    call: ast.Call,
    tempfile_module_names: tuple[str, ...],
    temporary_directory_names: tuple[str, ...],
) -> str | None:
    if isinstance(call.func, ast.Attribute):
        if not isinstance(call.func.value, ast.Name):
            return None
        if call.func.value.id in tempfile_module_names and call.func.attr == "TemporaryDirectory":
            return f"{call.func.value.id}.TemporaryDirectory"

    if isinstance(call.func, ast.Name) and call.func.id in temporary_directory_names:
        return call.func.id

    return None


def _entrypoint_temporary_directory_calls(path: Path) -> tuple[TemporaryDirectoryCall, ...]:
    tree = _source_tree(path)
    entrypoint_class = _class_named(tree, ENTRYPOINT_BEHAVIOR_CLASS)
    tempfile_module_names = _tempfile_import_names(tree)
    temporary_directory_names = _direct_temporary_directory_import_names(tree)
    calls: list[TemporaryDirectoryCall] = []

    for statement in entrypoint_class.body:
        if not isinstance(statement, ast.FunctionDef):
            continue
        for node in ast.walk(statement):
            if not isinstance(node, ast.Call):
                continue
            called_name = _called_temporary_directory_name(
                node,
                tempfile_module_names,
                temporary_directory_names,
            )
            if called_name is None:
                continue
            calls.append(
                TemporaryDirectoryCall(
                    method_name=statement.name,
                    line_number=node.lineno,
                    called_name=called_name,
                )
            )

    return tuple(calls)


def _entrypoint_method_argument_names(path: Path) -> dict[str, tuple[str, ...]]:
    entrypoint_class = _class_named(_source_tree(path), ENTRYPOINT_BEHAVIOR_CLASS)
    return {
        statement.name: tuple(argument.arg for argument in statement.args.args)
        for statement in entrypoint_class.body
        if isinstance(statement, ast.FunctionDef)
    }


def test_core_docker_entrypoint_subprocess_workspaces_use_pytest_tmp_path() -> None:
    """Boundary: entrypoint subprocess workspace paths must be pytest-owned."""
    temporary_directory_calls = _entrypoint_temporary_directory_calls(DOCKER_HARDENING_TEST)
    argument_names = _entrypoint_method_argument_names(DOCKER_HARDENING_TEST)
    missing_path_test_args = argument_names.get(
        "test_entrypoint_exits_nonzero_when_workspace_missing",
        (),
    )
    existing_path_test_args = {
        method_name: args
        for method_name, args in argument_names.items()
        if method_name
        in {
            "test_entrypoint_succeeds_when_workspace_exists",
            "test_entrypoint_prints_scaffold_message_for_empty_workspace",
        }
    }

    call_details = "\n".join(
        f"  - {ENTRYPOINT_BEHAVIOR_CLASS}.{call.method_name} calls "
        f"{call.called_name} at line {call.line_number}"
        for call in temporary_directory_calls
    )

    assert temporary_directory_calls == (), (
        f"{_relative(DOCKER_HARDENING_TEST)}::{ENTRYPOINT_BEHAVIOR_CLASS} must "
        "not create Docker entrypoint subprocess workspaces with "
        "tempfile.TemporaryDirectory. Accept pytest's tmp_path fixture in the "
        "entrypoint behavior tests instead. For existing-workspace cases, pass "
        "str(tmp_path) or a child directory created under tmp_path as "
        "RUNSIGHT_BASE_PATH. For the missing-workspace case, build a child path "
        "under tmp_path but do not create it, so the entrypoint fail-fast "
        "missing-path semantics stay covered. This static check intentionally "
        "does not inspect packages/core/tests/conftest.py or its central "
        "short-path isolation fixture.\n"
        "TemporaryDirectory calls found:\n"
        f"{call_details or '  - none'}"
    )

    assert "tmp_path" in missing_path_test_args, (
        f"{ENTRYPOINT_BEHAVIOR_CLASS}.test_entrypoint_exits_nonzero_when_workspace_missing "
        "should accept pytest's tmp_path fixture and derive a missing child path "
        "without creating it."
    )
    missing_existing_tmp_path = [
        method_name
        for method_name, args in existing_path_test_args.items()
        if "tmp_path" not in args
    ]
    assert missing_existing_tmp_path == [], (
        "Existing-workspace Docker entrypoint behavior tests should accept "
        "pytest's tmp_path fixture for subprocess RUNSIGHT_BASE_PATH setup. "
        "Missing tmp_path in: " + ", ".join(missing_existing_tmp_path)
    )
