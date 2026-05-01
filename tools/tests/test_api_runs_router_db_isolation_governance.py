"""Governance tests for API runs router database path isolation.

Owner: tools/tests owns temporary static checks for API transport test isolation.
Boundary: apps/api/tests/transport/test_runs_router.py may verify the real runs
read model, but file-backed test databases must live under pytest-owned tmp_path
rather than unmanaged tempfile directories.
Exit criteria: delete this suite once the runs router real read-model test uses
tmp_path, or an explicitly in-memory database, and the API transport suite owns
that isolation directly.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNS_ROUTER_TEST = REPO_ROOT / "apps" / "api" / "tests" / "transport" / "test_runs_router.py"
FILE_BACKED_DB_NAMES = frozenset({"runsight.db"})
UNMANAGED_TEMPFILE_FACTORIES = frozenset({"mkdtemp", "TemporaryDirectory", "NamedTemporaryFile"})

pytestmark = pytest.mark.governance


@dataclass(frozen=True)
class TempfileImport:
    module_name: str
    imported_name: str


@dataclass(frozen=True)
class UnmanagedDbPathUsage:
    test_name: str
    line_number: int
    factory_name: str
    db_name: str


def _relative(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _source_tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _tempfile_imports(tree: ast.Module) -> tuple[TempfileImport, ...]:
    imports: list[TempfileImport] = []
    for statement in tree.body:
        if isinstance(statement, ast.Import):
            imports.extend(
                TempfileImport(module_name=alias.name, imported_name=alias.asname or alias.name)
                for alias in statement.names
                if alias.name == "tempfile"
            )
        elif isinstance(statement, ast.ImportFrom) and statement.module == "tempfile":
            imports.extend(
                TempfileImport(module_name=alias.name, imported_name=alias.asname or alias.name)
                for alias in statement.names
                if alias.name in UNMANAGED_TEMPFILE_FACTORIES
            )
    return tuple(imports)


def _called_tempfile_factory(
    call: ast.Call,
    tempfile_imports: tuple[TempfileImport, ...],
) -> str | None:
    module_aliases = {
        imported.imported_name
        for imported in tempfile_imports
        if imported.module_name == "tempfile"
    }
    direct_factory_aliases = {
        imported.imported_name: imported.module_name
        for imported in tempfile_imports
        if imported.module_name in UNMANAGED_TEMPFILE_FACTORIES
    }

    if isinstance(call.func, ast.Attribute):
        if not isinstance(call.func.value, ast.Name):
            return None
        if call.func.value.id in module_aliases and call.func.attr in UNMANAGED_TEMPFILE_FACTORIES:
            return f"{call.func.value.id}.{call.func.attr}"

    if isinstance(call.func, ast.Name):
        factory_name = direct_factory_aliases.get(call.func.id)
        if factory_name is not None:
            return (
                call.func.id if call.func.id == factory_name else f"{call.func.id} ({factory_name})"
            )

    return None


def _contains_tempfile_factory(
    node: ast.AST,
    tempfile_imports: tuple[TempfileImport, ...],
) -> str | None:
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            factory_name = _called_tempfile_factory(child, tempfile_imports)
            if factory_name is not None:
                return factory_name
    return None


def _file_backed_db_name(node: ast.AST) -> str | None:
    for child in ast.walk(node):
        if isinstance(child, ast.Constant) and isinstance(child.value, str):
            if child.value in FILE_BACKED_DB_NAMES:
                return child.value
    return None


def _test_function_unmanaged_db_path_usages(path: Path) -> list[UnmanagedDbPathUsage]:
    tree = _source_tree(path)
    tempfile_imports = _tempfile_imports(tree)
    usages: list[UnmanagedDbPathUsage] = []

    for statement in tree.body:
        if not isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not statement.name.startswith("test_"):
            continue

        for node in ast.walk(statement):
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            factory_name = _contains_tempfile_factory(node, tempfile_imports)
            db_name = _file_backed_db_name(node)
            if factory_name is None or db_name is None:
                continue
            usages.append(
                UnmanagedDbPathUsage(
                    test_name=statement.name,
                    line_number=node.lineno,
                    factory_name=factory_name,
                    db_name=db_name,
                )
            )

    return usages


def test_runs_router_real_read_model_db_path_uses_pytest_owned_isolation() -> None:
    """Owner/boundary/exit: real read-model DB paths must be tmp_path-owned."""
    usages = _test_function_unmanaged_db_path_usages(RUNS_ROUTER_TEST)

    assert usages == [], (
        f"{_relative(RUNS_ROUTER_TEST)} test functions must not create file-backed "
        "runs router databases from unmanaged tempfile factories. Pass tmp_path into "
        'the real read-model test and use tmp_path / "runsight.db" so pytest owns '
        "cleanup. Found:\n"
        + "\n".join(
            f"  - {usage.test_name} builds {usage.db_name} with {usage.factory_name} "
            f"at line {usage.line_number}"
            for usage in usages
        )
    )
