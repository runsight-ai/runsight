"""Tool catalog suite split governance.

Owner: packages/core tool catalog test owners.
Boundary: ToolInstance/builtin registry tests, custom Python tool sandbox tests,
and request-tool HTTP/security tests must live in owner-specific suites with
package-local metadata/code builders instead of one inline god-object suite.
Exit criteria: delete this governance guard once the split suites and shared
fixture builders are the durable behavior owners.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.governance

CORE_TEST_ROOT = Path(__file__).resolve().parents[1]
UNIT_TEST_ROOT = Path(__file__).resolve().parent
LEGACY_TOOL_CATALOG_SUITE = UNIT_TEST_ROOT / "test_tool_catalog.py"

EXPECTED_OWNER_SUITES = {
    UNIT_TEST_ROOT / "test_tool_catalog_builtin_registry.py": (
        "ToolInstance schema and builtin registry behavior"
    ),
    UNIT_TEST_ROOT / "test_tool_catalog_custom_python.py": (
        "custom Python tool sandbox and execution contract"
    ),
    UNIT_TEST_ROOT / "test_tool_catalog_request_tools.py": (
        "request tool rendering, HTTP boundary, and SSRF/security behavior"
    ),
}
EXPECTED_FIXTURE_HELPERS = {
    CORE_TEST_ROOT / "tool_catalog_fixtures.py": (
        "package-local builders for custom tool YAML/code/request metadata"
    )
}

LEGACY_MAX_LINES = 350
LEGACY_MAX_TEST_FUNCTIONS = 12
LEGACY_MAX_TEST_CLASSES = 3
INLINE_LITERAL_MAX_NONBLANK_LINES = 8
INLINE_STRUCTURED_MARKERS = (
    "version:",
    "executor:",
    "parameters:",
    "request:",
    "code: |",
    "def main(",
    "body_template:",
)


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


def _large_inline_structured_literals(path: Path) -> list[str]:
    tree = _parse_source(path)
    violations: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue

        nonblank_lines = [line for line in node.value.splitlines() if line.strip()]
        if len(nonblank_lines) <= INLINE_LITERAL_MAX_NONBLANK_LINES:
            continue

        if not any(marker in node.value for marker in INLINE_STRUCTURED_MARKERS):
            continue

        line_number = getattr(node, "lineno", "?")
        violations.append(
            f"{path.relative_to(CORE_TEST_ROOT)}:{line_number}: "
            f"{len(nonblank_lines)} inline metadata/code lines"
        )

    return violations


def test_tool_catalog_governance_owner_suites_externalize_legacy_fixture_concerns() -> None:
    """Owner: packages/core tool catalog tests. Exit: split owner suites replace this guard."""
    violations: list[str] = []

    for path, owner in EXPECTED_OWNER_SUITES.items():
        if not path.exists():
            violations.append(
                f"missing owner suite for {owner}: {path.relative_to(CORE_TEST_ROOT)}"
            )

    for path, owner in EXPECTED_FIXTURE_HELPERS.items():
        if not path.exists():
            violations.append(
                f"missing fixture helper for {owner}: {path.relative_to(CORE_TEST_ROOT)}"
            )

    legacy_source = LEGACY_TOOL_CATALOG_SUITE.read_text(encoding="utf-8")
    legacy_tree = _parse_source(LEGACY_TOOL_CATALOG_SUITE)
    legacy_line_count = len(legacy_source.splitlines())
    legacy_test_count = _test_function_count(legacy_tree)
    legacy_class_count = _test_class_count(legacy_tree)

    if legacy_line_count > LEGACY_MAX_LINES:
        violations.append(
            f"{LEGACY_TOOL_CATALOG_SUITE.relative_to(CORE_TEST_ROOT)} has "
            f"{legacy_line_count} lines; expected <= {LEGACY_MAX_LINES}"
        )
    if legacy_test_count > LEGACY_MAX_TEST_FUNCTIONS:
        violations.append(
            f"{LEGACY_TOOL_CATALOG_SUITE.relative_to(CORE_TEST_ROOT)} has "
            f"{legacy_test_count} test functions; expected <= {LEGACY_MAX_TEST_FUNCTIONS}"
        )
    if legacy_class_count > LEGACY_MAX_TEST_CLASSES:
        violations.append(
            f"{LEGACY_TOOL_CATALOG_SUITE.relative_to(CORE_TEST_ROOT)} has "
            f"{legacy_class_count} test classes; expected <= {LEGACY_MAX_TEST_CLASSES}"
        )

    files_to_scan = [LEGACY_TOOL_CATALOG_SUITE]
    files_to_scan.extend(path for path in EXPECTED_OWNER_SUITES if path.exists())
    inline_literals = [
        violation for path in files_to_scan for violation in _large_inline_structured_literals(path)
    ]
    if inline_literals:
        violations.append(
            "large inline YAML/code/request metadata should move to package-local "
            "builders or fixture files:\n" + "\n".join(inline_literals)
        )

    assert violations == [], (
        "Tool catalog governance requires owner-specific suites, a small legacy "
        "suite, and externalized custom tool metadata/code fixtures.\n" + "\n".join(violations)
    )
