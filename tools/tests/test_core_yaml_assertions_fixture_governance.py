"""Governance tests for core YAML assertions workflow fixture ownership.

Owner: tools/tests owns temporary static checks for core test fixture ownership
migrations.
Boundary: reusable workflow-shaped YAML payloads for assertion parser behavior
belong under packages/core/tests/fixtures/workflows and should be loaded through
packages/core/tests/workflow_fixture_helpers.py or the existing core fixture
helper pattern. This suite inspects only repo-owned source, not runtime or user
state.
Exit criteria: delete this suite once the YAML assertion parser workflow
payloads have been externalized and the behavior tests preserve assertion
removal and propagation coverage through package-owned fixtures.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
YAML_ASSERTIONS_CONFIG_TEST = (
    REPO_ROOT / "packages" / "core" / "tests" / "test_yaml_assertions_config.py"
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
    if not isinstance(parsed.get("souls"), dict) or not isinstance(parsed.get("blocks"), dict):
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


def test_yaml_assertion_parser_workflow_fixtures_are_not_module_level_constants() -> None:
    constants = _module_level_workflow_yaml_constants(YAML_ASSERTIONS_CONFIG_TEST)

    assert constants == [], (
        f"{_relative(YAML_ASSERTIONS_CONFIG_TEST)} must not define reusable "
        "module-level workflow-shaped YAML constants for assertion parser cases. "
        "Move these payloads to packages/core/tests/fixtures/workflows with "
        "behavior-focused names and load them through workflow_fixture_helpers.py "
        "or the existing core fixture helper pattern. Found:\n"
        + "\n".join(
            "  - "
            f"{constant.name} at line {constant.line_number} "
            f"(id={constant.workflow_id}, workflow={constant.workflow_name})"
            for constant in constants
        )
    )
