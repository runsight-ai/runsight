"""Workflow service suite split governance.

Owner: apps/api workflow service test owners.
Boundary: WorkflowService list/get/detail, create/update, commit, and delete
behavior must live in owner-specific suites with package-local helper fixtures
instead of one import-stubbing god-object suite.
Exit criteria: delete this governance guard once the split behavior suites and
workflow_service_helpers.py are the durable owners of this coverage.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.governance

LOGIC_TEST_ROOT = Path(__file__).resolve().parent
API_TEST_ROOT = LOGIC_TEST_ROOT.parent
LEGACY_WORKFLOW_SERVICE_SUITE = LOGIC_TEST_ROOT / "test_workflow_service.py"

EXPECTED_OWNER_SUITES = {
    LOGIC_TEST_ROOT / "test_workflow_service_list_get_detail.py": (
        "list_workflows, get_workflow, and get_workflow_detail behavior"
    ),
    LOGIC_TEST_ROOT / "test_workflow_service_create_update.py": (
        "create_workflow and update_workflow behavior"
    ),
    LOGIC_TEST_ROOT / "test_workflow_service_commit.py": "commit_workflow behavior",
    LOGIC_TEST_ROOT / "test_workflow_service_delete.py": "delete_workflow behavior",
}
EXPECTED_FIXTURE_HELPER = LOGIC_TEST_ROOT / "workflow_service_helpers.py"
EXPECTED_HELPER_FIXTURES = {
    "workflow_repo",
    "run_repo",
    "run_read_model",
    "workflow_service",
}

LEGACY_MAX_LINES = 220
LEGACY_MAX_TEST_FUNCTIONS = 6


def _parse_source(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _test_function_count(tree: ast.Module) -> int:
    return sum(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_")
        for node in ast.walk(tree)
    )


def _function_names(tree: ast.Module) -> set[str]:
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _is_sys_modules_reference(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "modules"
        and isinstance(node.value, ast.Name)
        and node.value.id == "sys"
    )


def _top_level_sys_modules_lines(path: Path) -> list[int]:
    tree = _parse_source(path)
    line_numbers: set[int] = set()

    for statement in tree.body:
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        for node in ast.walk(statement):
            if _is_sys_modules_reference(node):
                line_numbers.add(node.lineno)

    return sorted(line_numbers)


def _workflow_service_behavior_suites() -> list[Path]:
    suites = [path for path in EXPECTED_OWNER_SUITES if path.exists()]
    if LEGACY_WORKFLOW_SERVICE_SUITE.exists():
        suites.append(LEGACY_WORKFLOW_SERVICE_SUITE)
    return suites


def test_workflow_service_governance_owner_suites_externalize_legacy_setup() -> None:
    """Owner: apps/api workflow service tests. Exit: split owner suites replace this guard."""
    violations: list[str] = []

    for path, owner in EXPECTED_OWNER_SUITES.items():
        if not path.exists():
            violations.append(f"missing owner suite for {owner}: {path.relative_to(API_TEST_ROOT)}")

    if not EXPECTED_FIXTURE_HELPER.exists():
        violations.append(
            "missing package-local helper for shared mock repo/service fixtures: "
            f"{EXPECTED_FIXTURE_HELPER.relative_to(API_TEST_ROOT)}"
        )
    else:
        helper_tree = _parse_source(EXPECTED_FIXTURE_HELPER)
        missing_fixtures = EXPECTED_HELPER_FIXTURES - _function_names(helper_tree)
        if missing_fixtures:
            violations.append(
                f"{EXPECTED_FIXTURE_HELPER.relative_to(API_TEST_ROOT)} is missing "
                "shared fixture/helper functions: " + ", ".join(sorted(missing_fixtures))
            )

    if LEGACY_WORKFLOW_SERVICE_SUITE.exists():
        legacy_source = LEGACY_WORKFLOW_SERVICE_SUITE.read_text(encoding="utf-8")
        legacy_tree = _parse_source(LEGACY_WORKFLOW_SERVICE_SUITE)
        legacy_line_count = len(legacy_source.splitlines())
        legacy_test_count = _test_function_count(legacy_tree)

        if legacy_line_count > LEGACY_MAX_LINES:
            violations.append(
                f"{LEGACY_WORKFLOW_SERVICE_SUITE.relative_to(API_TEST_ROOT)} has "
                f"{legacy_line_count} lines; expected <= {LEGACY_MAX_LINES}"
            )
        if legacy_test_count > LEGACY_MAX_TEST_FUNCTIONS:
            violations.append(
                f"{LEGACY_WORKFLOW_SERVICE_SUITE.relative_to(API_TEST_ROOT)} has "
                f"{legacy_test_count} test functions; expected <= {LEGACY_MAX_TEST_FUNCTIONS}"
            )

    behavior_suite_stubs = []
    for path in _workflow_service_behavior_suites():
        top_level_lines = _top_level_sys_modules_lines(path)
        if top_level_lines:
            behavior_suite_stubs.append(
                f"{path.relative_to(API_TEST_ROOT)} top-level sys.modules access on "
                f"lines {', '.join(str(line) for line in top_level_lines)}"
            )

    if behavior_suite_stubs:
        violations.append(
            "workflow service behavior suites must not stub or restore sys.modules at "
            "module import time; move import stubbing into workflow_service_helpers.py:\n"
            + "\n".join(behavior_suite_stubs)
        )

    assert violations == [], (
        "WorkflowService suite governance requires method-owned behavior suites, "
        "externalized shared fixtures/import stubs, and a small or deleted legacy suite.\n"
        + "\n".join(violations)
    )
