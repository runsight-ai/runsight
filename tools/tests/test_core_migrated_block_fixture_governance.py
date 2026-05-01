"""Governance tests for migrated block round-trip workflow fixture ownership.

Owner: tools/tests owns temporary static checks for core test fixture ownership
migrations.
Boundary: reusable workflow-shaped YAML payloads for migrated block parser
round-trip coverage belong under packages/core/tests/fixtures/workflows and
should be loaded through packages/core/tests/workflow_fixture_helpers.py or the
existing core fixture helper pattern. This suite inspects only repo-owned
source, not runtime or user state.
Exit criteria: delete this suite once the migrated block parser round-trip
payloads have been externalized and the behavior tests preserve parser
round-trip plus schema/registry coverage through package-owned fixtures.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATED_BLOCK_TEST = REPO_ROOT / "packages" / "core" / "tests" / "test_migrate_blocks.py"
MIGRATED_ROUND_TRIP_BLOCK_TYPES = frozenset({"code", "linear", "loop"})

pytestmark = pytest.mark.governance


@dataclass(frozen=True)
class ModuleWorkflowYamlConstant:
    name: str
    line_number: int
    workflow_id: str
    workflow_name: str
    migrated_block_types: tuple[str, ...]


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


def _migrated_round_trip_workflow_details(text: str) -> tuple[str, str, tuple[str, ...]] | None:
    try:
        parsed = yaml.safe_load(text)
    except yaml.YAMLError:
        return None

    if not isinstance(parsed, dict):
        return None
    if parsed.get("kind") != "workflow":
        return None

    blocks = parsed.get("blocks")
    workflow = parsed.get("workflow")
    if not isinstance(blocks, dict) or not isinstance(workflow, dict):
        return None

    migrated_block_types = sorted(
        {
            block_def.get("type")
            for block_def in blocks.values()
            if isinstance(block_def, dict)
            and isinstance(block_def.get("type"), str)
            and block_def.get("type") in MIGRATED_ROUND_TRIP_BLOCK_TYPES
        }
    )
    if not migrated_block_types:
        return None

    workflow_id = parsed.get("id")
    workflow_name = workflow.get("name")
    if not isinstance(workflow_id, str):
        workflow_id = "<missing id>"
    if not isinstance(workflow_name, str):
        workflow_name = "<missing workflow.name>"

    return workflow_id, workflow_name, tuple(migrated_block_types)


def _module_level_migrated_workflow_yaml_constants(
    path: Path,
) -> list[ModuleWorkflowYamlConstant]:
    constants: list[ModuleWorkflowYamlConstant] = []
    for statement in _source_tree(path).body:
        value = _string_assignment_value(statement)
        if value is None:
            continue

        details = _migrated_round_trip_workflow_details(value)
        if details is None:
            continue

        workflow_id, workflow_name, migrated_block_types = details
        constants.extend(
            ModuleWorkflowYamlConstant(
                name=name,
                line_number=statement.lineno,
                workflow_id=workflow_id,
                workflow_name=workflow_name,
                migrated_block_types=migrated_block_types,
            )
            for name in _assignment_targets(statement)
        )
    return constants


def test_migrated_block_round_trip_workflow_fixtures_are_not_module_level_constants() -> None:
    constants = _module_level_migrated_workflow_yaml_constants(MIGRATED_BLOCK_TEST)

    assert constants == [], (
        f"{_relative(MIGRATED_BLOCK_TEST)} must not define reusable module-level "
        "workflow-shaped YAML constants for migrated block parser round trips. "
        "Move these payloads to packages/core/tests/fixtures/workflows with "
        "behavior-focused names and load them through workflow_fixture_helpers.py "
        "or the existing core fixture helper pattern. Scalar constants such as "
        "block-type sets and subprocess environment allowlists are still allowed. "
        "Found:\n"
        + "\n".join(
            "  - "
            f"{constant.name} at line {constant.line_number} "
            f"(id={constant.workflow_id}, workflow={constant.workflow_name}, "
            f"migrated_block_types={', '.join(constant.migrated_block_types)})"
            for constant in constants
        )
    )
