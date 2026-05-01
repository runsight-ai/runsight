"""Governance tests for API workflow input redaction fixture ownership.

Owner: tools/tests owns temporary static checks for API test fixture ownership
migrations.
Boundary: reusable workflow and provider payloads for
apps/api/tests/test_workflow_input_redaction_integration.py belong under
apps/api/tests/fixtures/workflow_input_redaction and should be loaded by a
small API-owned workspace builder or fixture, not cached as module-level text
aliases. The integration suite's runtime workspace must also be built under an
explicit pytest-owned tmp_path rather than by an unmanaged tempfile directory.
Exit criteria: delete this suite once workflow input redaction integration
fixtures are loaded on demand by the API-owned builder/fixture and base_dir
uses pytest tmp_path while preserving the integration behavior coverage.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_INPUT_REDACTION_TEST = (
    REPO_ROOT / "apps" / "api" / "tests" / "test_workflow_input_redaction_integration.py"
)
API_WORKFLOW_INPUT_REDACTION_FIXTURES = (
    REPO_ROOT / "apps" / "api" / "tests" / "fixtures" / "workflow_input_redaction"
)

pytestmark = pytest.mark.governance


@dataclass(frozen=True)
class ModuleFixtureTextAlias:
    name: str
    line_number: int
    fixture_path: str


def _relative(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _source_tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=_relative(path))


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        owner = _call_name(node.value)
        return f"{owner}.{node.attr}" if owner else node.attr
    return ""


def _assignment_targets(statement: ast.Assign | ast.AnnAssign) -> list[str]:
    if isinstance(statement, ast.Assign):
        return [target.id for target in statement.targets if isinstance(target, ast.Name)]
    if isinstance(statement.target, ast.Name):
        return [statement.target.id]
    return []


def _literal_string(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _fixture_text_call_path(node: ast.AST) -> str | None:
    if not isinstance(node, ast.Call):
        return None
    if _call_name(node.func) != "_fixture_text":
        return None
    if len(node.args) != 1:
        return "<dynamic path>"
    return _literal_string(node.args[0]) or "<dynamic path>"


def _module_fixture_text_aliases(path: Path) -> list[ModuleFixtureTextAlias]:
    aliases: list[ModuleFixtureTextAlias] = []

    for statement in _source_tree(path).body:
        if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
            continue

        fixture_path = _fixture_text_call_path(statement.value)
        if fixture_path is None:
            continue

        aliases.extend(
            ModuleFixtureTextAlias(
                name=name,
                line_number=statement.lineno,
                fixture_path=fixture_path,
            )
            for name in _assignment_targets(statement)
        )

    return aliases


def _decorator_name(node: ast.AST) -> str:
    if isinstance(node, ast.Call):
        return _decorator_name(node.func)
    return _call_name(node)


def _pytest_fixture_functions(path: Path) -> dict[str, ast.FunctionDef]:
    fixtures: dict[str, ast.FunctionDef] = {}

    for node in _source_tree(path).body:
        if not isinstance(node, ast.FunctionDef):
            continue
        if any(_decorator_name(decorator) == "pytest.fixture" for decorator in node.decorator_list):
            fixtures[node.name] = node

    return fixtures


def _uses_tempfile_temporary_directory(function: ast.FunctionDef) -> bool:
    return any(
        isinstance(node, ast.Call) and _call_name(node.func) == "tempfile.TemporaryDirectory"
        for node in ast.walk(function)
    )


def _argument_names(function: ast.FunctionDef) -> set[str]:
    return {argument.arg for argument in function.args.args}


def test_workflow_input_redaction_suite_uses_fixture_builder_and_tmp_path() -> None:
    """Owner/boundary/exit: redaction fixture data and workspace are API-owned."""
    aliases = _module_fixture_text_aliases(WORKFLOW_INPUT_REDACTION_TEST)
    base_dir = _pytest_fixture_functions(WORKFLOW_INPUT_REDACTION_TEST).get("base_dir")

    violations: list[str] = []
    if aliases:
        violations.append(
            "Module-level fixture text aliases loaded by _fixture_text(...) remain:\n"
            + "\n".join(
                f"  - {alias.name} at line {alias.line_number} (fixture: {alias.fixture_path})"
                for alias in aliases
            )
        )

    if base_dir is None:
        violations.append("The explicit base_dir pytest fixture is missing.")
    else:
        uses_tempfile_directory = _uses_tempfile_temporary_directory(base_dir)
        accepts_tmp_path = "tmp_path" in _argument_names(base_dir)

        if uses_tempfile_directory or not accepts_tmp_path:
            violations.append(
                "base_dir must accept pytest tmp_path and must not call "
                "tempfile.TemporaryDirectory for the runtime workspace. Found "
                f"TemporaryDirectory={uses_tempfile_directory}, tmp_path={accepts_tmp_path}."
            )

    assert violations == [], (
        f"{_relative(WORKFLOW_INPUT_REDACTION_TEST)} must load reusable workflow "
        "and provider payloads inside the API-owned workspace builder or fixture "
        "and build base_dir under pytest tmp_path. Keep files owned under "
        f"{_relative(API_WORKFLOW_INPUT_REDACTION_FIXTURES)}. Small scalar "
        "constants such as query strings or sentinel secrets remain allowed. Found:\n\n"
        + "\n\n".join(violations)
    )
