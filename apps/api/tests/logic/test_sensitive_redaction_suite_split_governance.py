"""Sensitive redaction suite split governance.

Owner: apps/api sensitive-redaction behavior test owners.
Boundary: ExecutionService input preparation, workflow input snapshot
serialization, ExecutionObserver persistence redaction, StreamingObserver SSE
redaction, and EvalObserver persistence/SSE redaction must live in focused
owner suites with package-local helper builders instead of one cross-boundary
fixture-heavy suite.
Exit criteria: delete this governance guard once the split owner suites and
sensitive_redaction_helpers.py are the durable behavior owners, or when repo
test safety tooling enforces equivalent suite-size and helper-placement rules.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.governance

API_LOGIC_TEST_ROOT = Path(__file__).resolve().parent
API_TEST_ROOT = API_LOGIC_TEST_ROOT.parent
LEGACY_SENSITIVE_REDACTION_SUITE = API_LOGIC_TEST_ROOT / "test_sensitive_redaction.py"
SENSITIVE_REDACTION_HELPER = API_LOGIC_TEST_ROOT / "sensitive_redaction_helpers.py"

EXPECTED_OWNER_SUITES = {
    API_LOGIC_TEST_ROOT / "test_execution_input_redaction.py": (
        "ExecutionService.prepare_run_inputs sensitive input normalization and runtime redactor"
    ),
    API_LOGIC_TEST_ROOT / "test_workflow_input_snapshot_redaction.py": (
        "workflow input snapshot serialization for runtime-sensitive values"
    ),
    API_LOGIC_TEST_ROOT / "test_execution_observer_redaction.py": (
        "ExecutionObserver persisted node, run, error, traceback, and log redaction"
    ),
    API_LOGIC_TEST_ROOT / "test_streaming_observer_redaction.py": (
        "StreamingObserver SSE error payload redaction"
    ),
    API_LOGIC_TEST_ROOT / "test_eval_observer_redaction.py": (
        "EvalObserver persisted eval result and SSE assertion redaction"
    ),
}

EXPECTED_HELPER_FUNCTIONS = {
    "make_sensitive_redactor": "shared registered sensitive-value redactor",
    "sensitive_workflow_yaml": "workflow YAML with sensitive and public inputs",
    "sensitive_default_workflow_yaml": "workflow YAML that rejects sensitive defaults",
    "sensitive_non_string_workflow_yaml": (
        "workflow YAML covering sensitive number, boolean, json, and array inputs"
    ),
    "mixed_structured_sensitive_workflow_yaml": (
        "workflow YAML covering structured sensitive string leaves"
    ),
    "make_sensitive_execution_service": "ExecutionService with a package-local workflow repo",
    "make_sensitive_db_engine": "test-owned in-memory SQLModel engine",
    "make_sensitive_eval_db_engine": "test-owned EvalObserver-compatible SQLModel engine",
    "seed_sensitive_run": "Run row builder for observer persistence tests",
    "seed_sensitive_eval_run": "Run and RunNode builder for EvalObserver redaction tests",
    "make_sensitive_state": "WorkflowState builder with registered input redactor",
    "make_sensitive_sse_queue": "SSE queue builder for observer redaction assertions",
    "collect_sensitive_log_messages": "LogEntry reader for observer persistence assertions",
}

LEGACY_MAX_LINES = 220
LEGACY_MAX_TEST_FUNCTIONS = 5

INLINE_SHARED_SETUP_NAMES = {
    "_redactor",
    "_workflow_yaml_with_sensitive_inputs",
    "_workflow_yaml_with_sensitive_default_input",
    "_workflow_yaml_with_sensitive_non_string_inputs",
    "_workflow_yaml_with_mixed_structured_sensitive_input",
    "_service",
    "_db_engine",
    "_eval_db_engine",
    "_seed_run",
    "_state_with_redactor",
    "_log_messages",
    "_seed_eval_run",
}


def _parse_source(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _test_function_count(tree: ast.Module) -> int:
    return sum(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_")
        for node in ast.walk(tree)
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


def _legacy_suite_violations() -> list[str]:
    if not LEGACY_SENSITIVE_REDACTION_SUITE.exists():
        return []

    legacy_source = LEGACY_SENSITIVE_REDACTION_SUITE.read_text(encoding="utf-8")
    legacy_tree = _parse_source(LEGACY_SENSITIVE_REDACTION_SUITE)
    legacy_line_count = len(legacy_source.splitlines())
    legacy_test_count = _test_function_count(legacy_tree)
    legacy_label = LEGACY_SENSITIVE_REDACTION_SUITE.relative_to(API_TEST_ROOT)
    legacy_names = _defined_names(LEGACY_SENSITIVE_REDACTION_SUITE)
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

    inline_setup = [
        f"{legacy_label}:{legacy_names[name]}: inline shared setup {name}"
        for name in sorted(INLINE_SHARED_SETUP_NAMES)
        if name in legacy_names
    ]
    if inline_setup:
        violations.append(
            "sensitive workflow/input/redaction DB and queue setup should move to "
            "sensitive_redaction_helpers.py:\n" + "\n".join(inline_setup)
        )

    return violations


def test_sensitive_redaction_governance_owner_suites_externalize_shared_setup() -> None:
    """Owner: sensitive redaction API tests. Exit: split owner suites replace this guard."""
    violations: list[str] = []

    for path, owner in EXPECTED_OWNER_SUITES.items():
        if not path.exists():
            violations.append(f"missing owner suite for {owner}: {path.relative_to(API_TEST_ROOT)}")

    if not SENSITIVE_REDACTION_HELPER.exists():
        violations.append(
            "missing API package-local helper for sensitive workflow/input/redaction "
            f"setup: {SENSITIVE_REDACTION_HELPER.relative_to(API_TEST_ROOT)}"
        )
    else:
        helper_names = _defined_names(SENSITIVE_REDACTION_HELPER)
        for name, purpose in EXPECTED_HELPER_FUNCTIONS.items():
            if name not in helper_names:
                violations.append(
                    f"{SENSITIVE_REDACTION_HELPER.relative_to(API_TEST_ROOT)} "
                    f"is missing {name} for {purpose}"
                )

    violations.extend(_legacy_suite_violations())

    assert violations == [], (
        "Sensitive redaction governance requires behavior-owner suites, a small "
        "or removed legacy suite, and externalized sensitive workflow/input/"
        "redaction DB and queue helpers.\n" + "\n".join(violations)
    )
