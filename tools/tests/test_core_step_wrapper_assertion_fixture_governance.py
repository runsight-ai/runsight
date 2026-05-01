"""Governance tests for core step wrapper assertion fixture ownership.

Owner: tools/tests owns temporary static checks for core test fixture ownership
migrations.
Boundary: reusable workflow-shaped YAML payloads for step wrapper assertion
parser behavior belong under packages/core/tests/fixtures/workflows and should
be loaded through packages/core/tests/workflow_fixture_helpers.py or the
existing core fixture helper pattern. Parser runtime workspaces in the behavior
suite must be owned by pytest tmp_path rather than unmanaged tempfile contexts.
This suite inspects only repo-owned source, not runtime or user state. Small
inline soul snippets local to parser setup are intentionally outside this check.
Exit criteria: delete this suite once the step wrapper assertion workflow
payloads have been externalized and the behavior tests preserve assertion
delegation plus parser coverage through package-owned fixtures and tmp_path.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
STEP_WRAPPER_ASSERTION_TEST = (
    REPO_ROOT / "packages" / "core" / "tests" / "test_step_wrapper_assertions.py"
)

pytestmark = pytest.mark.governance


@dataclass(frozen=True)
class ModuleWorkflowYamlConstant:
    name: str
    line_number: int
    workflow_id: str
    workflow_name: str
    step_wrapped_blocks: tuple[str, ...]


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


def _workflow_details(text: str) -> tuple[str, str, tuple[str, ...]] | None:
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

    step_wrapped_blocks = sorted(
        block_name
        for block_name, block_def in blocks.items()
        if isinstance(block_name, str)
        and isinstance(block_def, dict)
        and isinstance(block_def.get("inputs"), dict)
    )
    if not step_wrapped_blocks:
        return None

    workflow_id = parsed.get("id")
    workflow_name = workflow.get("name")
    if not isinstance(workflow_id, str):
        workflow_id = "<missing id>"
    if not isinstance(workflow_name, str):
        workflow_name = "<missing workflow.name>"

    return workflow_id, workflow_name, tuple(step_wrapped_blocks)


def _module_level_step_wrapper_workflow_constants(
    path: Path,
) -> list[ModuleWorkflowYamlConstant]:
    constants: list[ModuleWorkflowYamlConstant] = []
    for statement in _source_tree(path).body:
        value = _string_assignment_value(statement)
        if value is None:
            continue

        details = _workflow_details(value)
        if details is None:
            continue

        workflow_id, workflow_name, step_wrapped_blocks = details
        constants.extend(
            ModuleWorkflowYamlConstant(
                name=name,
                line_number=statement.lineno,
                workflow_id=workflow_id,
                workflow_name=workflow_name,
                step_wrapped_blocks=step_wrapped_blocks,
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


def _temporary_directory_calls(tree: ast.AST) -> list[int]:
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and _call_name(node) == "tempfile.TemporaryDirectory"
    ]


def test_step_wrapper_assertion_workflow_fixtures_are_not_module_level_constants() -> None:
    """Reusable step wrapper assertion workflows should live in core fixtures."""
    constants = _module_level_step_wrapper_workflow_constants(STEP_WRAPPER_ASSERTION_TEST)

    assert constants == [], (
        f"{_relative(STEP_WRAPPER_ASSERTION_TEST)} must not define reusable "
        "module-level workflow-shaped YAML constants for step wrapper assertion "
        "parser cases. Move these payloads to packages/core/tests/fixtures/workflows "
        "with behavior-focused names and load them through workflow_fixture_helpers.py "
        "or the existing core fixture helper pattern. Small inline soul snippets "
        "inside parser setup may remain local. Found:\n"
        + "\n".join(
            "  - "
            f"{constant.name} at line {constant.line_number} "
            f"(id={constant.workflow_id}, workflow={constant.workflow_name}, "
            f"step_wrapped_blocks={', '.join(constant.step_wrapped_blocks)})"
            for constant in constants
        )
    )


def test_step_wrapper_assertion_parser_workspace_uses_pytest_tmp_path() -> None:
    """Parser workspace setup should be visible to pytest-owned tmp_path cleanup."""
    tree = _source_tree(STEP_WRAPPER_ASSERTION_TEST)
    temporary_directory_lines = _temporary_directory_calls(tree)

    assert temporary_directory_lines == [], (
        f"{_relative(STEP_WRAPPER_ASSERTION_TEST)} must not create parser runtime "
        "workspaces with tempfile.TemporaryDirectory. Use pytest's tmp_path fixture "
        "and build custom/souls plus workflow files under that pytest-owned path. "
        "Found TemporaryDirectory calls at lines: "
        + ", ".join(str(line) for line in temporary_directory_lines)
    )

    parse_with_souls = _function_named(tree, "_parse_with_souls")
    if parse_with_souls is None:
        return

    argument_names = [argument.arg for argument in parse_with_souls.args.args]
    assert "tmp_path" in argument_names, (
        f"{_relative(STEP_WRAPPER_ASSERTION_TEST)} _parse_with_souls should accept "
        "pytest's tmp_path fixture path, so parser workspace ownership is explicit "
        "in the behavior suite."
    )
