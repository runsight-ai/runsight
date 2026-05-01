"""Governance tests for API budget run status fixture ownership.

Owner: tools/tests owns temporary static checks for API test fixture ownership
migrations.
Boundary: reusable workflow payloads for the API budget run status suite belong
under apps/api/tests/fixtures. This suite inspects only repo-owned API test
source, not runtime/user-authored state.
Exit criteria: delete this suite once reusable budget run status workflow
payloads have been externalized with direct API package coverage for fixture
ownership.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
BUDGET_RUN_STATUS_TEST = (
    REPO_ROOT / "apps" / "api" / "tests" / "logic" / "test_budget_run_status.py"
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


def test_api_budget_run_status_suite_uses_package_owned_workflow_fixtures() -> None:
    """Reusable API budget run status workflows should live in API-owned fixtures."""
    constants = _module_level_workflow_constants(BUDGET_RUN_STATUS_TEST)

    assert constants == [], (
        f"{_relative(BUDGET_RUN_STATUS_TEST)} must not define reusable "
        "module-level workflow YAML constants. Move reusable budget run status "
        f"workflow payloads to {_relative(API_FIXTURE_ROOT)}/budget_run_status/ "
        "or a similarly behavior-named API fixture directory, then load them "
        "through a small helper or fixture in the test module. Found: "
        + ", ".join(
            f"{constant.name} at line {constant.line_number} (workflow id: {constant.workflow_id})"
            for constant in constants
        )
    )
