"""Governance tests for API execution preparation database fixture isolation.

Owner: tools/tests owns temporary static checks for API test isolation cleanup.
Boundary: the API execution preparation suite may use pytest-owned tmp_path
fixtures for git repository setup, but DB setup helpers must not allocate
unmanaged file-backed databases through tempfile helpers.
Exit criteria: delete this suite once execution preparation database state is
owned by pytest lifecycle fixtures, or by an explicit in-memory database, and
the API package suite covers that ownership directly.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
EXECUTION_PREPARATION_TEST = (
    REPO_ROOT / "apps" / "api" / "tests" / "logic" / "test_execution_preparation.py"
)
DB_SETUP_HELPERS = frozenset({"_db_engine"})
UNMANAGED_TEMPFILE_FACTORIES = frozenset({"mkdtemp", "TemporaryDirectory", "NamedTemporaryFile"})

pytestmark = pytest.mark.governance


@dataclass(frozen=True)
class TempfileImport:
    module_name: str
    imported_name: str


@dataclass(frozen=True)
class UnmanagedTempfileUsage:
    helper_name: str
    line_number: int
    factory_name: str


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


def _db_setup_tempfile_usages(path: Path) -> list[UnmanagedTempfileUsage]:
    tree = _source_tree(path)
    tempfile_imports = _tempfile_imports(tree)
    usages: list[UnmanagedTempfileUsage] = []

    for statement in tree.body:
        if not isinstance(statement, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        if statement.name not in DB_SETUP_HELPERS:
            continue

        for node in ast.walk(statement):
            if not isinstance(node, ast.Call):
                continue
            factory_name = _called_tempfile_factory(node, tempfile_imports)
            if factory_name is None:
                continue
            usages.append(
                UnmanagedTempfileUsage(
                    helper_name=statement.name,
                    line_number=node.lineno,
                    factory_name=factory_name,
                )
            )

    return usages


def test_api_execution_preparation_db_setup_uses_pytest_owned_isolation() -> None:
    """Owner/boundary/exit: DB setup must use pytest-owned or in-memory state."""
    usages = _db_setup_tempfile_usages(EXECUTION_PREPARATION_TEST)

    assert usages == [], (
        f"{_relative(EXECUTION_PREPARATION_TEST)} DB setup helpers must not create "
        "unmanaged file-backed test databases with tempfile factories. Pass tmp_path "
        "into the DB helper/test, or use an explicit in-memory DB when compatible. "
        "Pytest tmp_path fixtures used for git repository setup are allowed. Found:\n"
        + "\n".join(
            f"  - {usage.helper_name} calls {usage.factory_name} at line {usage.line_number}"
            for usage in usages
        )
    )
