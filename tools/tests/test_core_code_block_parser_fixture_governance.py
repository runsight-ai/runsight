"""Governance tests for core code block parser workflow fixture ownership.

Owner: tools/tests owns temporary static checks for core test fixture ownership
migrations.
Boundary: reusable workflow-shaped YAML payloads for code block parser cases
belong under packages/core/tests/fixtures/workflows and should be loaded through
packages/core/tests/workflow_fixture_helpers.py or an existing local helper
pattern. This suite inspects only repo-owned source, not runtime or user state.
Exit criteria: delete this suite once the code block parser workflow payloads
have been externalized and the behavior tests preserve parser and achat token
coverage through package-owned fixtures.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CODE_BLOCK_PARSER_TEST = (
    REPO_ROOT / "packages" / "core" / "tests" / "test_code_block_parser_and_achat.py"
)

pytestmark = pytest.mark.governance


@dataclass(frozen=True)
class ModuleWorkflowYamlConstant:
    name: str
    line_number: int
    workflow_name: str
    code_block_names: tuple[str, ...]


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


def _code_block_workflow_details(text: str) -> tuple[str, tuple[str, ...]] | None:
    try:
        parsed = yaml.safe_load(text)
    except yaml.YAMLError:
        return None

    if not isinstance(parsed, dict):
        return None

    blocks = parsed.get("blocks")
    workflow = parsed.get("workflow")
    if not isinstance(blocks, dict) or not isinstance(workflow, dict):
        return None

    code_block_names = tuple(
        block_name
        for block_name, block_def in blocks.items()
        if isinstance(block_name, str)
        and isinstance(block_def, dict)
        and block_def.get("type") == "code"
    )
    if not code_block_names:
        return None

    workflow_name = workflow.get("name")
    if not isinstance(workflow_name, str):
        workflow_name = "<missing workflow.name>"
    return workflow_name, code_block_names


def _module_level_code_workflow_constants(path: Path) -> list[ModuleWorkflowYamlConstant]:
    constants: list[ModuleWorkflowYamlConstant] = []
    for statement in _source_tree(path).body:
        value = _string_assignment_value(statement)
        if value is None:
            continue

        details = _code_block_workflow_details(value)
        if details is None:
            continue

        workflow_name, code_block_names = details
        constants.extend(
            ModuleWorkflowYamlConstant(
                name=name,
                line_number=statement.lineno,
                workflow_name=workflow_name,
                code_block_names=code_block_names,
            )
            for name in _assignment_targets(statement)
        )
    return constants


def test_code_block_parser_workflow_fixtures_are_not_module_level_yaml_constants() -> None:
    constants = _module_level_code_workflow_constants(CODE_BLOCK_PARSER_TEST)

    assert constants == [], (
        f"{_relative(CODE_BLOCK_PARSER_TEST)} must not define reusable module-level "
        "workflow-shaped YAML constants for code block parser cases. Move these "
        "payloads to packages/core/tests/fixtures/workflows with behavior-focused "
        "names and load them through workflow_fixture_helpers.py or the local "
        "package fixture helper pattern. Found:\n"
        + "\n".join(
            "  - "
            f"{constant.name} at line {constant.line_number} "
            f"(workflow={constant.workflow_name}, "
            f"code_blocks={', '.join(constant.code_block_names)})"
            for constant in constants
        )
    )
