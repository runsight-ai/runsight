"""Governance tests for API execution assertion fixture ownership.

Owner: tools/tests owns temporary static checks for API test fixture ownership
migrations.
Boundary: reusable workflow payloads and runtime workspace ownership for the
API execution assertion evaluation suite belong to apps/api/tests. Reusable
workflow YAML must live under apps/api/tests/fixtures and must not remain as
module-level inline YAML constants in
apps/api/tests/test_execution_assertion_evaluation.py. The base_dir runtime
workspace fixture must be explicitly owned by pytest tmp_path rather than an
unmanaged tempfile.TemporaryDirectory context. Inline YAML inside an individual
test is local behavior setup and is intentionally outside this static check.
Exit criteria: delete this suite once those reusable workflow payloads have
been externalized and the API package suite has stable fixture-loading coverage
for execution assertion evaluation, and base_dir uses pytest-owned tmp_path for
its temporary runtime workspace.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
EXECUTION_ASSERTION_EVALUATION_TEST = (
    REPO_ROOT / "apps" / "api" / "tests" / "test_execution_assertion_evaluation.py"
)
API_FIXTURE_ROOT = REPO_ROOT / "apps" / "api" / "tests" / "fixtures"

pytestmark = pytest.mark.governance


@dataclass(frozen=True)
class ModuleWorkflowConstant:
    name: str
    line_number: int
    workflow_id: str


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


def _function_named(tree: ast.Module, name: str) -> ast.FunctionDef | None:
    for statement in tree.body:
        if isinstance(statement, ast.FunctionDef) and statement.name == name:
            return statement
    return None


def _call_name(call: ast.Call) -> str | None:
    function = call.func
    if isinstance(function, ast.Name):
        return function.id
    if isinstance(function, ast.Attribute) and isinstance(function.value, ast.Name):
        return f"{function.value.id}.{function.attr}"
    return None


def _uses_tempfile_temporary_directory(function: ast.FunctionDef) -> bool:
    return any(
        isinstance(node, ast.Call) and _call_name(node) == "tempfile.TemporaryDirectory"
        for node in ast.walk(function)
    )


def test_api_execution_assertion_suite_uses_package_owned_workflow_fixtures() -> None:
    """Reusable API execution assertion workflows should live in API-owned fixtures."""
    constants = _module_level_workflow_constants(EXECUTION_ASSERTION_EVALUATION_TEST)

    assert constants == [], (
        f"{_relative(EXECUTION_ASSERTION_EVALUATION_TEST)} must not define reusable "
        "module-level workflow YAML constants. Move reusable execution assertion "
        f"workflow payloads to {_relative(API_FIXTURE_ROOT)} and load them from the "
        "API package tests. Found:\n"
        + "\n".join(
            f"  - {constant.name} at line {constant.line_number} "
            f"(workflow id: {constant.workflow_id})"
            for constant in constants
        )
    )


def test_api_execution_assertion_base_dir_uses_pytest_owned_tmp_path() -> None:
    """base_dir should make runtime workspace ownership visible to pytest."""
    tree = _source_tree(EXECUTION_ASSERTION_EVALUATION_TEST)
    base_dir = _function_named(tree, "base_dir")

    assert base_dir is not None, (
        f"{_relative(EXECUTION_ASSERTION_EVALUATION_TEST)} must keep a base_dir "
        "fixture for execution assertion runtime workspace setup."
    )

    argument_names = [argument.arg for argument in base_dir.args.args]
    assert "tmp_path" in argument_names, (
        f"{_relative(EXECUTION_ASSERTION_EVALUATION_TEST)} base_dir fixture must "
        "accept pytest's tmp_path fixture so the API runtime workspace is owned "
        "and cleaned up by pytest."
    )

    assert not _uses_tempfile_temporary_directory(base_dir), (
        f"{_relative(EXECUTION_ASSERTION_EVALUATION_TEST)} base_dir fixture must "
        "not create its runtime workspace with tempfile.TemporaryDirectory. Use "
        "tmp_path and build custom/workflows under that pytest-owned path."
    )
