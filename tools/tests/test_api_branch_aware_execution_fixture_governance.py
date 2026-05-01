"""Governance tests for API branch-aware execution workflow fixture ownership.

Owner: tools/tests owns temporary static checks for API test fixture ownership
migrations.
Boundary: reusable workflow payloads for the API branch-aware execution suite
belong under apps/api/tests/fixtures and must not remain as module-level inline
YAML constants in apps/api/tests/logic/test_branch_aware_exec.py. Smaller inline
YAML snippets inside individual tests may stay when they describe a
branch-vs-working-tree case.
Exit criteria: delete this suite once the reusable branch-aware execution
workflow payload has been externalized and loaded from API-owned test fixtures.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
BRANCH_AWARE_EXECUTION_TEST = (
    REPO_ROOT / "apps" / "api" / "tests" / "logic" / "test_branch_aware_exec.py"
)
API_FIXTURE_ROOT = REPO_ROOT / "apps" / "api" / "tests" / "fixtures"

pytestmark = pytest.mark.governance


@dataclass(frozen=True)
class ModuleWorkflowConstant:
    name: str
    line_number: int
    workflow_name: str


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


def _workflow_document_name(text: str) -> str | None:
    try:
        parsed = yaml.safe_load(text)
    except yaml.YAMLError:
        return None

    if not isinstance(parsed, dict):
        return None

    workflow = parsed.get("workflow")
    has_workflow_shape = (
        isinstance(workflow, dict)
        and isinstance(workflow.get("name"), str)
        and isinstance(workflow.get("entry"), str)
        and isinstance(parsed.get("blocks"), dict)
    )
    if not has_workflow_shape:
        return None

    return workflow["name"]


def _module_level_workflow_constants(path: Path) -> list[ModuleWorkflowConstant]:
    constants: list[ModuleWorkflowConstant] = []
    for statement in _source_tree(path).body:
        value = _string_assignment_value(statement)
        if value is None:
            continue

        workflow_name = _workflow_document_name(value)
        if workflow_name is None:
            continue

        constants.extend(
            ModuleWorkflowConstant(
                name=name,
                line_number=statement.lineno,
                workflow_name=workflow_name,
            )
            for name in _assignment_targets(statement)
        )
    return constants


def test_api_branch_aware_execution_suite_uses_api_owned_workflow_fixtures() -> None:
    """Reusable API branch-aware execution workflows should live in API fixtures."""
    constants = _module_level_workflow_constants(BRANCH_AWARE_EXECUTION_TEST)

    assert constants == [], (
        f"{_relative(BRANCH_AWARE_EXECUTION_TEST)} must not define reusable "
        "module-level workflow YAML constants. Move reusable branch-aware execution "
        f"workflow payloads to {_relative(API_FIXTURE_ROOT)} and load them from the "
        "API package tests. This check only flags module-level workflow documents, "
        "so smaller inline YAML strings inside individual branch-vs-working-tree "
        "tests remain allowed. Found:\n"
        + "\n".join(
            f"  - {constant.name} at line {constant.line_number} "
            f"(workflow name: {constant.workflow_name})"
            for constant in constants
        )
    )
