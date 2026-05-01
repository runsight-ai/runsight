"""DispatchBlock migration suite split governance.

Owner: packages/core DispatchBlock behavior test owners.
Boundary: DispatchBlock v2 behavior, stateful history behavior, workflow
execution wiring, and shared dispatch fixtures must live in owner suites with
package-local helpers instead of the temporary BlockContext/BlockOutput
migration suite.
Exit criteria: delete this guard once test_dispatchblock_migration.py is small
or removed, duplicated behavior lives in owner suites, and shared dispatch
builders are externalized.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.governance

CORE_TEST_ROOT = Path(__file__).resolve().parent
MIGRATION_SUITE = CORE_TEST_ROOT / "test_dispatchblock_migration.py"

EXPECTED_OWNER_SUITES = {
    CORE_TEST_ROOT / "test_dispatch_v2.py": (
        "DispatchBlock v2 per-exit task/result, combined output, context, "
        "schema, and cost/token behavior"
    ),
    CORE_TEST_ROOT / "test_dispatch_block_stateful.py": (
        "DispatchBlock stateful and non-stateful conversation history behavior"
    ),
}
EXPECTED_HELPER_MODULES = {
    CORE_TEST_ROOT / "dispatch_block_helpers.py": (
        "package-local dispatch Soul, DispatchBranch, runner, ExecutionResult, "
        "budget patch, and workflow-state builders"
    )
}

MIGRATION_MAX_LINES = 350
MIGRATION_MAX_TEST_FUNCTIONS = 10
MIGRATION_MAX_INLINE_FIXTURE_OR_BUILDER_FUNCTIONS = 2
MIGRATION_ONLY_ALLOWED_SECTION_KEYWORDS = {
    "BlockContext",
    "BlockOutput",
    "migration",
    "migrate",
    "compatibility",
}
OWNER_BEHAVIOR_SECTION_KEYWORDS = {
    "Budget isolation",
    "combined output",
    "context building",
    "conversation_updates",
    "cost",
    "execute_block",
    "extra_results",
    "stateful conversation",
    "workflow dispatch",
}
INLINE_DISPATCH_BUILDER_NAMES = {
    "_make_branches",
    "_make_dispatch_ctx",
    "_make_result",
    "_patch_dispatch_budget_passthrough",
    "_setup_runner_side_effect",
    "block_execution_ctx",
    "dispatch_task",
    "mock_runner",
    "soul_alpha",
    "soul_beta",
}


def _parse_source(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _test_function_count(tree: ast.Module) -> int:
    return sum(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_")
        for node in ast.walk(tree)
    )


def _defined_function_names(tree: ast.Module) -> set[str]:
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _module_docstring(path: Path) -> str:
    return ast.get_docstring(_parse_source(path)) or ""


def _comment_lines(path: Path) -> list[str]:
    return [
        line.strip("#").strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.lstrip().startswith("#")
    ]


def _migration_docstring_violations() -> list[str]:
    docstring = _module_docstring(MIGRATION_SUITE)
    required_fragments = ["Owner:", "Boundary:", "Exit criteria:"]
    violations = [
        f"{MIGRATION_SUITE.name} module docstring is missing {fragment}"
        for fragment in required_fragments
        if fragment not in docstring
    ]
    if "migration" not in docstring.lower():
        violations.append(f"{MIGRATION_SUITE.name} docstring must name the migration boundary")
    if "remove" not in docstring.lower():
        violations.append(f"{MIGRATION_SUITE.name} docstring must state a removal exit path")
    return violations


def _legacy_migration_suite_violations() -> list[str]:
    source = MIGRATION_SUITE.read_text(encoding="utf-8")
    tree = _parse_source(MIGRATION_SUITE)
    line_count = len(source.splitlines())
    test_count = _test_function_count(tree)
    inline_builders = sorted(_defined_function_names(tree) & INLINE_DISPATCH_BUILDER_NAMES)
    comments = _comment_lines(MIGRATION_SUITE)
    owner_behavior_sections = sorted(
        keyword
        for keyword in OWNER_BEHAVIOR_SECTION_KEYWORDS
        if any(keyword in line for line in comments)
    )
    migration_only_sections = [
        line
        for line in comments
        if line and not set(line.split()).isdisjoint(MIGRATION_ONLY_ALLOWED_SECTION_KEYWORDS)
    ]

    violations: list[str] = []
    legacy_label = MIGRATION_SUITE.relative_to(CORE_TEST_ROOT)

    if line_count > MIGRATION_MAX_LINES:
        violations.append(
            f"{legacy_label} has {line_count} lines; expected <= {MIGRATION_MAX_LINES}"
        )
    if test_count > MIGRATION_MAX_TEST_FUNCTIONS:
        violations.append(
            f"{legacy_label} has {test_count} test functions; "
            f"expected <= {MIGRATION_MAX_TEST_FUNCTIONS}"
        )
    if len(inline_builders) > MIGRATION_MAX_INLINE_FIXTURE_OR_BUILDER_FUNCTIONS:
        violations.append(
            f"{legacy_label} still defines inline dispatch fixture/builders: "
            + ", ".join(inline_builders)
        )
    if owner_behavior_sections:
        violations.append(
            f"{legacy_label} still has owner-behavior sections that should move "
            "to DispatchBlock v2/stateful owner suites: " + ", ".join(owner_behavior_sections)
        )
    if not migration_only_sections:
        violations.append(
            f"{legacy_label} should retain only explicit BlockContext/BlockOutput "
            "migration compatibility sections until deletion"
        )

    return violations


def test_dispatchblock_migration_governance_externalizes_behavior_and_helpers() -> None:
    """Owner: DispatchBlock tests. Exit: split owner suites replace this guard."""
    violations: list[str] = []

    for path, owner in EXPECTED_OWNER_SUITES.items():
        if not path.exists():
            violations.append(
                f"missing owner suite for {owner}: {path.relative_to(CORE_TEST_ROOT)}"
            )

    for path, owner in EXPECTED_HELPER_MODULES.items():
        if not path.exists():
            violations.append(
                f"missing fixture helper for {owner}: {path.relative_to(CORE_TEST_ROOT)}"
            )

    violations.extend(_migration_docstring_violations())
    violations.extend(_legacy_migration_suite_violations())

    assert violations == [], (
        "DispatchBlock migration governance requires behavior-owner suites, a "
        "small explicitly migration-only legacy suite, documented owner/boundary/"
        "exit criteria, and externalized package-local dispatch builders.\n" + "\n".join(violations)
    )
