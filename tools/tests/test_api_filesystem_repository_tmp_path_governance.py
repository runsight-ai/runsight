"""Governance tests for API filesystem repository workspace ownership.

Owner: tools/tests owns temporary static checks for API filesystem repository
test isolation.
Boundary: API filesystem repository behavior suites must build repository
workspaces under pytest-owned tmp_path, not unmanaged tempfile directories. This
suite inspects only the repo-owned API tests listed below, and intentionally
does not scan conftest, central pytest isolation fixtures, or unrelated
governance tests.
Exit criteria: delete this suite once the targeted API filesystem repository
tests use pytest tmp_path-owned workspaces while preserving their behavior
coverage.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TARGET_API_FILESYSTEM_REPOSITORY_TESTS = (
    REPO_ROOT / "apps" / "api" / "tests" / "data" / "test_base_yaml_identity.py",
    REPO_ROOT
    / "apps"
    / "api"
    / "tests"
    / "unit"
    / "data"
    / "filesystem"
    / "test_provider_repo_identity.py",
    REPO_ROOT / "apps" / "api" / "tests" / "data" / "test_base_yaml_repository.py",
    REPO_ROOT / "apps" / "api" / "tests" / "data" / "test_filesystem.py",
    REPO_ROOT / "apps" / "api" / "tests" / "data" / "test_soul_repo.py",
)

pytestmark = pytest.mark.governance


@dataclass(frozen=True)
class TemporaryDirectoryImport:
    path: Path
    line_number: int
    imported_name: str
    import_style: str


@dataclass(frozen=True)
class TemporaryDirectoryCall:
    path: Path
    line_number: int
    function_name: str
    called_name: str


def _relative(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _source_tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _temporary_directory_imports(
    tree: ast.Module, path: Path
) -> tuple[TemporaryDirectoryImport, ...]:
    imports: list[TemporaryDirectoryImport] = []
    for statement in tree.body:
        if isinstance(statement, ast.Import):
            imports.extend(
                TemporaryDirectoryImport(
                    path=path,
                    line_number=statement.lineno,
                    imported_name=alias.asname or alias.name,
                    import_style="import tempfile",
                )
                for alias in statement.names
                if alias.name == "tempfile"
            )
        elif isinstance(statement, ast.ImportFrom) and statement.module == "tempfile":
            imports.extend(
                TemporaryDirectoryImport(
                    path=path,
                    line_number=statement.lineno,
                    imported_name=alias.asname or alias.name,
                    import_style="from tempfile import TemporaryDirectory",
                )
                for alias in statement.names
                if alias.name == "TemporaryDirectory"
            )
    return tuple(imports)


def _called_temporary_directory_name(
    call: ast.Call,
    temporary_directory_imports: tuple[TemporaryDirectoryImport, ...],
) -> str | None:
    module_aliases = {
        imported.imported_name
        for imported in temporary_directory_imports
        if imported.import_style == "import tempfile"
    }
    direct_aliases = {
        imported.imported_name
        for imported in temporary_directory_imports
        if imported.import_style == "from tempfile import TemporaryDirectory"
    }

    if isinstance(call.func, ast.Attribute):
        if not isinstance(call.func.value, ast.Name):
            return None
        if call.func.value.id in module_aliases and call.func.attr == "TemporaryDirectory":
            return f"{call.func.value.id}.TemporaryDirectory"

    if isinstance(call.func, ast.Name) and call.func.id in direct_aliases:
        return call.func.id

    return None


def _with_parent_links(tree: ast.Module) -> ast.Module:
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            child_parents = getattr(parent, "_parents", ())
            child._parents = (*child_parents, parent)  # type: ignore[attr-defined]
    return tree


def _containing_function_name(node: ast.AST) -> str:
    parents = getattr(node, "_parents", ())
    for parent in reversed(parents):
        if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return parent.name
    return "<module>"


def _temporary_directory_calls(
    tree: ast.Module,
    path: Path,
    temporary_directory_imports: tuple[TemporaryDirectoryImport, ...],
) -> tuple[TemporaryDirectoryCall, ...]:
    calls: list[TemporaryDirectoryCall] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        called_name = _called_temporary_directory_name(node, temporary_directory_imports)
        if called_name is None:
            continue
        calls.append(
            TemporaryDirectoryCall(
                path=path,
                line_number=node.lineno,
                function_name=_containing_function_name(node),
                called_name=called_name,
            )
        )
    return tuple(calls)


def _temporary_directory_findings() -> tuple[
    tuple[TemporaryDirectoryImport, ...],
    tuple[TemporaryDirectoryCall, ...],
]:
    imports: list[TemporaryDirectoryImport] = []
    calls: list[TemporaryDirectoryCall] = []

    for path in TARGET_API_FILESYSTEM_REPOSITORY_TESTS:
        tree = _with_parent_links(_source_tree(path))
        file_imports = _temporary_directory_imports(tree, path)
        imports.extend(file_imports)
        calls.extend(_temporary_directory_calls(tree, path, file_imports))

    return tuple(imports), tuple(calls)


def test_api_filesystem_repository_workspaces_use_pytest_owned_tmp_path() -> None:
    """Owner/boundary/exit: repository workspaces must be owned by pytest tmp_path."""
    imports, calls = _temporary_directory_findings()

    import_details = "\n".join(
        f"  - {_relative(imported.path)} imports {imported.import_style} "
        f"as {imported.imported_name} at line {imported.line_number}"
        for imported in imports
    )
    call_details = "\n".join(
        f"  - {_relative(call.path)}::{call.function_name} calls {call.called_name} "
        f"at line {call.line_number}"
        for call in calls
    )

    assert imports == () and calls == (), (
        "API filesystem repository behavior suites must not import or use "
        "tempfile.TemporaryDirectory for repository workspaces. Accept pytest's "
        "tmp_path fixture in the target tests and build repository workspaces "
        "under that pytest-owned path so cleanup and fixture ownership remain "
        "visible to pytest. This static governance check is intentionally scoped "
        "only to the five API filesystem repository test files listed in "
        "TARGET_API_FILESYSTEM_REPOSITORY_TESTS.\n"
        "TemporaryDirectory imports found:\n"
        f"{import_details or '  - none'}\n"
        "TemporaryDirectory calls found:\n"
        f"{call_details or '  - none'}"
    )
