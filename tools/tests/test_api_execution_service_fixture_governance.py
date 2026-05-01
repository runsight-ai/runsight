"""Governance tests for API execution service runtime workflow fixture ownership.

Owner: tools/tests owns temporary static checks for API test fixture ownership
migrations.
Boundary: reusable workflow payloads for the API execution service suite belong
under apps/api/tests/fixtures and must not remain as module-level inline YAML or
format-string constants in apps/api/tests/logic/test_execution_service.py. Small
scalar constants and YAML strings local to individual tests are intentionally
outside this check.
Exit criteria: delete this suite once the reusable execution service runtime
workflow payload has been externalized to API-owned test fixtures and is loaded
through a helper that preserves the execution workflow identity values.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
EXECUTION_SERVICE_TEST = (
    REPO_ROOT / "apps" / "api" / "tests" / "logic" / "test_execution_service.py"
)
API_EXECUTION_SERVICE_FIXTURE_ROOT = (
    REPO_ROOT / "apps" / "api" / "tests" / "fixtures" / "execution_service"
)

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


def _module_level_stringish_value(statement: ast.stmt) -> str | None:
    if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
        return None

    value = statement.value
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return value.value
    if isinstance(value, ast.JoinedStr):
        return "".join(_joined_string_part(part) for part in value.values)
    return None


def _joined_string_part(part: ast.expr) -> str:
    if isinstance(part, ast.Constant) and isinstance(part.value, str):
        return part.value
    if isinstance(part, ast.FormattedValue):
        return "__formatted_value__"
    return ""


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
        value = _module_level_stringish_value(statement)
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


def test_api_execution_service_suite_uses_api_owned_runtime_workflow_fixtures() -> None:
    """Reusable API execution service runtime workflows should live in API fixtures."""
    constants = _module_level_workflow_constants(EXECUTION_SERVICE_TEST)

    assert constants == [], (
        f"{_relative(EXECUTION_SERVICE_TEST)} must not define reusable module-level "
        "workflow-shaped YAML or f-string constants. Move reusable execution service "
        f"runtime workflow payloads to {_relative(API_EXECUTION_SERVICE_FIXTURE_ROOT)} "
        "and load/render them from the API package tests while preserving "
        "EXECUTION_WORKFLOW_ID and EXECUTION_WORKFLOW_NAME. This check only flags "
        "module-level workflow documents, so small scalar constants and inline YAML "
        "inside individual tests remain allowed. Found:\n"
        + "\n".join(
            f"  - {constant.name} at line {constant.line_number} "
            f"(workflow id: {constant.workflow_id})"
            for constant in constants
        )
    )
