"""Governance tests for API workflow repository tool-governance fixture ownership.

Owner: tools/tests owns temporary static checks for API test fixture ownership
migrations.
Boundary: reusable workflow payloads for the API workflow repository
tool-governance suite belong under apps/api/tests/fixtures and must not remain
as module-level inline YAML constants in the behavior suite. This suite inspects
only repo-owned API test source, not runtime/user-authored state.
Exit criteria: delete this suite once reusable workflow repository
tool-governance payloads have been externalized and loaded through an API-owned
fixture helper.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_REPO_TOOL_GOVERNANCE_TEST = (
    REPO_ROOT
    / "apps"
    / "api"
    / "tests"
    / "unit"
    / "data"
    / "filesystem"
    / "test_workflow_repo_tool_governance.py"
)
WORKFLOW_REPO_TOOL_GOVERNANCE_FIXTURE_ROOT = (
    REPO_ROOT / "apps" / "api" / "tests" / "fixtures" / "workflow_repo_tool_governance"
)

pytestmark = pytest.mark.governance


@dataclass(frozen=True)
class ModuleWorkflowYamlConstant:
    name: str
    line_number: int
    workflow_id: str
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


def _workflow_details(text: str) -> tuple[str, str] | None:
    try:
        parsed = yaml.safe_load(text)
    except yaml.YAMLError:
        return None

    if not isinstance(parsed, dict):
        return None
    if parsed.get("kind") != "workflow":
        return None
    if not isinstance(parsed.get("blocks"), dict):
        return None

    workflow = parsed.get("workflow")
    if not isinstance(workflow, dict):
        return None

    workflow_id = parsed.get("id")
    workflow_name = workflow.get("name")
    if not isinstance(workflow_id, str):
        workflow_id = "<missing id>"
    if not isinstance(workflow_name, str):
        workflow_name = "<missing workflow.name>"

    return workflow_id, workflow_name


def _module_level_workflow_yaml_constants(path: Path) -> list[ModuleWorkflowYamlConstant]:
    constants: list[ModuleWorkflowYamlConstant] = []
    for statement in _source_tree(path).body:
        value = _string_assignment_value(statement)
        if value is None:
            continue

        details = _workflow_details(value)
        if details is None:
            continue

        workflow_id, workflow_name = details
        constants.extend(
            ModuleWorkflowYamlConstant(
                name=name,
                line_number=statement.lineno,
                workflow_id=workflow_id,
                workflow_name=workflow_name,
            )
            for name in _assignment_targets(statement)
        )
    return constants


def test_api_workflow_repo_tool_governance_uses_owned_workflow_fixtures() -> None:
    """Reusable tool-governance workflows should live in API-owned fixtures."""
    constants = _module_level_workflow_yaml_constants(WORKFLOW_REPO_TOOL_GOVERNANCE_TEST)

    assert constants == [], (
        f"{_relative(WORKFLOW_REPO_TOOL_GOVERNANCE_TEST)} must not define reusable "
        "module-level workflow-shaped YAML constants for workflow repository "
        "tool-governance cases. Move these workflow payloads to "
        f"{_relative(WORKFLOW_REPO_TOOL_GOVERNANCE_FIXTURE_ROOT)} with "
        "behavior-focused names and load them through a helper owned by the API "
        "test workspace. This check only flags module-level workflow documents, "
        "so small inline custom soul/tool YAML snippets used as local behavior "
        "setup remain allowed. Found:\n"
        + "\n".join(
            "  - "
            f"{constant.name} at line {constant.line_number} "
            f"(id={constant.workflow_id}, workflow={constant.workflow_name})"
            for constant in constants
        )
    )
