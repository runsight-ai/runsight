"""EvalObserver suite split governance.

Owner: apps/api EvalObserver behavior test owners.
Boundary: import/no-op/protocol, assertion execution, stream emission,
baseline/workflow aggregate, and child-run assertion/stream ownership must live
in focused owner suites with API package-local DB/run/SSE/state/assertion helper
builders instead of one broad legacy suite with inline shared fixtures.
Exit criteria: delete this governance guard once the split owner suites and
shared eval observer helper are the durable behavior owners, or when repo test
safety tooling enforces equivalent suite-size and helper-placement rules.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.governance

API_LOGIC_TEST_ROOT = Path(__file__).resolve().parent
API_TEST_ROOT = API_LOGIC_TEST_ROOT.parent
LEGACY_EVAL_OBSERVER_SUITE = API_LOGIC_TEST_ROOT / "test_eval_observer.py"
EVAL_OBSERVER_HELPER = API_LOGIC_TEST_ROOT / "eval_observer_helpers.py"

EXPECTED_OWNER_SUITES = {
    API_LOGIC_TEST_ROOT / "test_eval_observer_basics.py": (
        "import, no-op, defensive DB handling, and protocol basics"
    ),
    API_LOGIC_TEST_ROOT / "test_eval_observer_assertion_execution.py": (
        "assertion execution and RunNode eval field persistence"
    ),
    API_LOGIC_TEST_ROOT / "test_eval_observer_stream_emission.py": (
        "SSE node_eval_complete payloads and queue behavior"
    ),
    API_LOGIC_TEST_ROOT / "test_eval_observer_baseline_aggregate.py": (
        "baseline delta and workflow aggregate behavior"
    ),
    API_LOGIC_TEST_ROOT / "test_eval_observer_child_ownership.py": (
        "child stream isolation and child assertion ownership"
    ),
}

EXPECTED_HELPER_FUNCTIONS = {
    "make_eval_observer_engine": "test-owned in-memory SQLModel engine",
    "seed_eval_run": "Run row builder for isolated API tests",
    "seed_eval_run_node": "RunNode row builder for evaluated blocks",
    "seed_eval_baseline_nodes": "baseline RunNode builder for delta tests",
    "make_eval_sse_queue": "asyncio.Queue builder for SSE assertions",
    "make_eval_state": "WorkflowState builder with block results/cost/tokens",
    "make_eval_soul": "Soul builder with stable eval identity",
    "assertion_configs_for": "shared assertion config builder",
}

LEGACY_MAX_LINES = 450
LEGACY_MAX_TEST_FUNCTIONS = 12
LEGACY_MAX_TEST_CLASSES = 4

INLINE_SHARED_FIXTURE_NAMES = {
    "db_engine",
    "seed_run",
    "seed_run_with_node",
    "sse_queue",
    "sample_soul",
    "sample_state",
    "contains_assertion_configs",
    "multi_assertion_configs",
    "failing_assertion_configs",
    "cost_assertion_configs",
}


def _parse_source(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _test_function_count(tree: ast.Module) -> int:
    return sum(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_")
        for node in ast.walk(tree)
    )


def _test_class_count(tree: ast.Module) -> int:
    return sum(
        isinstance(node, ast.ClassDef) and node.name.startswith("Test") for node in ast.walk(tree)
    )


def _defined_names(path: Path) -> dict[str, int]:
    tree = _parse_source(path)
    names: dict[str, int] = {}

    for node in ast.walk(tree):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            names[node.name] = node.lineno
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names[target.id] = node.lineno

    return names


def _is_pytest_fixture(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for decorator in node.decorator_list:
        if isinstance(decorator, ast.Attribute) and decorator.attr == "fixture":
            return True
        if isinstance(decorator, ast.Call):
            func = decorator.func
            if isinstance(func, ast.Attribute) and func.attr == "fixture":
                return True
    return False


def _inline_shared_fixture_violations(path: Path) -> list[str]:
    tree = _parse_source(path)
    violations: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name not in INLINE_SHARED_FIXTURE_NAMES or not _is_pytest_fixture(node):
            continue
        violations.append(
            f"{path.relative_to(API_TEST_ROOT)}:{node.lineno}: inline fixture {node.name}"
        )

    return violations


def _legacy_suite_violations() -> list[str]:
    if not LEGACY_EVAL_OBSERVER_SUITE.exists():
        return []

    legacy_source = LEGACY_EVAL_OBSERVER_SUITE.read_text(encoding="utf-8")
    legacy_tree = _parse_source(LEGACY_EVAL_OBSERVER_SUITE)
    legacy_line_count = len(legacy_source.splitlines())
    legacy_test_count = _test_function_count(legacy_tree)
    legacy_class_count = _test_class_count(legacy_tree)
    legacy_label = LEGACY_EVAL_OBSERVER_SUITE.relative_to(API_TEST_ROOT)
    violations: list[str] = []

    if legacy_line_count > LEGACY_MAX_LINES:
        violations.append(
            f"{legacy_label} has {legacy_line_count} lines; expected <= {LEGACY_MAX_LINES}"
        )
    if legacy_test_count > LEGACY_MAX_TEST_FUNCTIONS:
        violations.append(
            f"{legacy_label} has {legacy_test_count} test functions; "
            f"expected <= {LEGACY_MAX_TEST_FUNCTIONS}"
        )
    if legacy_class_count > LEGACY_MAX_TEST_CLASSES:
        violations.append(
            f"{legacy_label} has {legacy_class_count} test classes; "
            f"expected <= {LEGACY_MAX_TEST_CLASSES}"
        )

    inline_fixtures = _inline_shared_fixture_violations(LEGACY_EVAL_OBSERVER_SUITE)
    if inline_fixtures:
        violations.append(
            "DB/run/SSE/state/assertion setup should move to "
            "eval_observer_helpers.py:\n" + "\n".join(inline_fixtures)
        )

    return violations


def test_eval_observer_governance_owner_suites_externalize_shared_fixtures() -> None:
    """Owner: EvalObserver API tests. Exit: split owner suites replace this guard."""
    violations: list[str] = []

    for path, owner in EXPECTED_OWNER_SUITES.items():
        if not path.exists():
            violations.append(f"missing owner suite for {owner}: {path.relative_to(API_TEST_ROOT)}")

    if not EVAL_OBSERVER_HELPER.exists():
        violations.append(
            "missing API package-local helper for DB/run/SSE/state/assertion setup: "
            f"{EVAL_OBSERVER_HELPER.relative_to(API_TEST_ROOT)}"
        )
    else:
        helper_names = _defined_names(EVAL_OBSERVER_HELPER)
        for name, purpose in EXPECTED_HELPER_FUNCTIONS.items():
            if name not in helper_names:
                violations.append(
                    f"{EVAL_OBSERVER_HELPER.relative_to(API_TEST_ROOT)} "
                    f"is missing {name} for {purpose}"
                )

    violations.extend(_legacy_suite_violations())

    assert violations == [], (
        "EvalObserver governance requires behavior-owner suites, a small or "
        "removed legacy suite, and externalized DB/run/SSE/state/assertion helpers.\n"
        + "\n".join(violations)
    )
