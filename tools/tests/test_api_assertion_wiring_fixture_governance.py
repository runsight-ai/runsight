"""Governance tests for API assertion wiring fixture and builder ownership.

Owner: tools/tests owns temporary static checks for API test fixture ownership
migrations.
Boundary: reusable workflow payloads for apps/api/tests/logic/
test_wire_assertion_configs.py belong under apps/api/tests/fixtures, and parser
workspace setup in that suite must be owned by pytest tmp_path or an API-owned
fixture/builder helper. This suite inspects only repo-owned API test source, not
runtime/user-authored state.
Exit criteria: delete this suite once assertion wiring workflow payloads have
been externalized and parser workspace construction uses tmp_path-driven
fixture/builder setup while preserving the behavior coverage in the API suite.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
ASSERTION_WIRING_TEST = (
    REPO_ROOT / "apps" / "api" / "tests" / "logic" / "test_wire_assertion_configs.py"
)
API_ASSERTION_WIRING_FIXTURE_ROOT = (
    REPO_ROOT / "apps" / "api" / "tests" / "fixtures" / "assertion_wiring"
)
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
class TempfileUsage:
    function_name: str
    line_number: int
    factory_name: str


def _relative(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _source_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _source_tree(path: Path) -> ast.Module:
    return ast.parse(_source_text(path), filename=str(path))


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
        and isinstance(parsed.get("blocks"), dict)
        and isinstance(parsed.get("workflow"), dict)
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


def _containing_function_name(tree: ast.Module, node: ast.AST) -> str:
    parents = getattr(node, "_parents", ())
    for parent in reversed(parents):
        if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return parent.name
    return "<module>"


def _with_parent_links(tree: ast.Module) -> ast.Module:
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            child_parents = getattr(parent, "_parents", ())
            child._parents = (*child_parents, parent)  # type: ignore[attr-defined]
    return tree


def _tempfile_usages(path: Path) -> list[TempfileUsage]:
    tree = _with_parent_links(_source_tree(path))
    tempfile_imports = _tempfile_imports(tree)
    usages: list[TempfileUsage] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        factory_name = _called_tempfile_factory(node, tempfile_imports)
        if factory_name is None:
            continue
        usages.append(
            TempfileUsage(
                function_name=_containing_function_name(tree, node),
                line_number=node.lineno,
                factory_name=factory_name,
            )
        )
    return usages


def test_api_assertion_wiring_suite_uses_api_owned_fixtures_and_builders() -> None:
    """Owner/boundary/exit: assertion wiring workflows and parser builders are API-owned."""
    constants = _module_level_workflow_constants(ASSERTION_WIRING_TEST)
    usages = _tempfile_usages(ASSERTION_WIRING_TEST)
    failures: list[str] = []

    if constants:
        failures.append(
            f"{_relative(ASSERTION_WIRING_TEST)} must not define reusable module-level "
            "workflow YAML constants. Move reusable assertion wiring workflow payloads "
            f"to {_relative(API_ASSERTION_WIRING_FIXTURE_ROOT)} or another behavior-named "
            "API-owned fixture directory and load them from the API package tests. Found:\n"
            + "\n".join(
                f"  - {constant.name} at line {constant.line_number} "
                f"(workflow id: {constant.workflow_id})"
                for constant in constants
            )
        )

    if usages:
        failures.append(
            f"{_relative(ASSERTION_WIRING_TEST)} must not create parser workspaces with "
            "unmanaged tempfile factories inside helper functions. Use pytest tmp_path "
            "through an explicit fixture or API-owned builder so workspace cleanup and "
            "fixture setup are visible to pytest. Found:\n"
            + "\n".join(
                f"  - {usage.function_name} calls {usage.factory_name} at line {usage.line_number}"
                for usage in usages
            )
        )

    assert failures == [], "\n\n".join(failures)
