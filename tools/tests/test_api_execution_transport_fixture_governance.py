"""Governance tests for API execution transport fixture ownership.

Owner: tools/tests owns temporary static checks for API test fixture ownership
migrations.
Boundary: reusable workflow payloads for the API execution transport suite
belong under apps/api/tests/fixtures, and the suite runtime workspace fixture
must be owned by pytest tmp_path. This suite inspects only repo-owned API test
source, not runtime/user-authored state.
Exit criteria: delete this suite once reusable execution transport workflow
payloads have been externalized and the base_dir fixture uses pytest-owned
tmp_path lifecycle state with direct API package coverage for that ownership.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
EXECUTION_TRANSPORT_TEST = (
    REPO_ROOT / "apps" / "api" / "tests" / "test_execution_transport_integration.py"
)
API_FIXTURE_ROOT = REPO_ROOT / "apps" / "api" / "tests" / "fixtures"
RUNTIME_WORKSPACE_FIXTURE = "base_dir"
UNMANAGED_TEMPFILE_FACTORIES = frozenset({"mkdtemp", "TemporaryDirectory", "NamedTemporaryFile"})

pytestmark = pytest.mark.governance


@dataclass(frozen=True)
class ModuleWorkflowConstant:
    name: str
    line_number: int
    workflow_id: str


@dataclass(frozen=True)
class TempfileImport:
    module_name: str
    imported_name: str


@dataclass(frozen=True)
class RuntimeFixtureTempfileUsage:
    fixture_name: str
    line_number: int
    factory_name: str


def _relative(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _source_tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _assignment_targets(statement: ast.Assign | ast.AnnAssign) -> list[str]:
    if isinstance(statement, ast.Assign):
        return [target.id for target in statement.targets if isinstance(target, ast.Name)]
    if isinstance(statement.target, ast.Name):
        return [statement.target.id]
    return []


def _string_assignment_value(statement: ast.stmt) -> str | None:
    if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
        return None
    if not isinstance(statement.value, ast.Constant) or not isinstance(statement.value.value, str):
        return None
    return statement.value.value


def _workflow_document_id(text: str) -> str | None:
    try:
        parsed = yaml.safe_load(text)
    except yaml.YAMLError:
        return None

    if not isinstance(parsed, dict):
        return None

    has_workflow_shape = (
        parsed.get("kind") == "workflow"
        and isinstance(parsed.get("workflow"), dict)
        and isinstance(parsed.get("blocks"), dict)
    )
    if not has_workflow_shape:
        return None

    workflow_id = parsed.get("id")
    return workflow_id if isinstance(workflow_id, str) else "<missing id>"


def _module_level_workflow_constants(path: Path) -> list[ModuleWorkflowConstant]:
    constants: list[ModuleWorkflowConstant] = []
    for statement in _source_tree(path).body:
        value = _string_assignment_value(statement)
        if value is None:
            continue

        workflow_id = _workflow_document_id(value)
        if workflow_id is None:
            continue

        constants.extend(
            ModuleWorkflowConstant(
                name=name,
                line_number=statement.lineno,
                workflow_id=workflow_id,
            )
            for name in _assignment_targets(statement)
        )
    return constants


def _is_pytest_fixture(function: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for decorator in function.decorator_list:
        if isinstance(decorator, ast.Attribute):
            if isinstance(decorator.value, ast.Name) and decorator.value.id == "pytest":
                if decorator.attr == "fixture":
                    return True
        elif isinstance(decorator, ast.Call):
            called = decorator.func
            if isinstance(called, ast.Attribute):
                if isinstance(called.value, ast.Name) and called.value.id == "pytest":
                    if called.attr == "fixture":
                        return True
    return False


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


def _runtime_workspace_tempfile_usages(path: Path) -> list[RuntimeFixtureTempfileUsage]:
    tree = _source_tree(path)
    tempfile_imports = _tempfile_imports(tree)
    usages: list[RuntimeFixtureTempfileUsage] = []

    for statement in tree.body:
        if not isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if statement.name != RUNTIME_WORKSPACE_FIXTURE or not _is_pytest_fixture(statement):
            continue

        for node in ast.walk(statement):
            if not isinstance(node, ast.Call):
                continue
            factory_name = _called_tempfile_factory(node, tempfile_imports)
            if factory_name is None:
                continue
            usages.append(
                RuntimeFixtureTempfileUsage(
                    fixture_name=statement.name,
                    line_number=node.lineno,
                    factory_name=factory_name,
                )
            )

    return usages


def test_api_execution_transport_suite_uses_package_owned_workflow_fixtures() -> None:
    """Reusable API execution transport workflows should live in API-owned fixtures."""
    constants = _module_level_workflow_constants(EXECUTION_TRANSPORT_TEST)

    assert constants == [], (
        f"{_relative(EXECUTION_TRANSPORT_TEST)} must not define reusable "
        "module-level workflow YAML constants. Move reusable execution transport "
        f"workflow payloads to {_relative(API_FIXTURE_ROOT)} and load them from the "
        "API package tests. Found:\n"
        + "\n".join(
            f"  - {constant.name} at line {constant.line_number} "
            f"(workflow id: {constant.workflow_id})"
            for constant in constants
        )
    )


def test_api_execution_transport_runtime_workspace_fixture_uses_tmp_path() -> None:
    """Owner/boundary/exit: base_dir runtime workspace must use pytest tmp_path."""
    usages = _runtime_workspace_tempfile_usages(EXECUTION_TRANSPORT_TEST)

    assert usages == [], (
        f"{_relative(EXECUTION_TRANSPORT_TEST)} {RUNTIME_WORKSPACE_FIXTURE} fixture "
        "must not create unmanaged runtime workspaces with tempfile factories. "
        "Accept tmp_path in the base_dir fixture and build the API test workspace "
        "under that pytest-owned directory. This check is intentionally scoped to "
        "base_dir, so db_engine(tmp_path) and tiny inline request payloads remain "
        "outside the boundary. Found:\n"
        + "\n".join(
            f"  - {usage.fixture_name} calls {usage.factory_name} at line {usage.line_number}"
            for usage in usages
        )
    )
