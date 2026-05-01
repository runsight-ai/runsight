"""LoopBlock carry-context suite split governance.

Owner: packages/core LoopBlock carry-context behavior owners.
Boundary: schema/config, carry propagation, runtime edge cases, and
writer-critic integration/formatting must live in owner-specific suites with
package-local fake block and loop-state helpers instead of one broad legacy
suite with inline fixture classes.
Exit criteria: delete this governance guard once the split owner suites and
shared helper module are the durable behavior owners.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.governance

CORE_TEST_ROOT = Path(__file__).resolve().parent
LEGACY_CARRY_CONTEXT_SUITE = CORE_TEST_ROOT / "test_loop_carry_context.py"

EXPECTED_OWNER_SUITES = {
    CORE_TEST_ROOT / "test_loop_carry_context_schema_config.py": (
        "CarryContextConfig and LoopBlockDef schema/config contracts"
    ),
    CORE_TEST_ROOT / "test_loop_carry_context_propagation.py": (
        "last/all carry modes, source block filtering, and inject key behavior"
    ),
    CORE_TEST_ROOT / "test_loop_carry_context_runtime_edges.py": (
        "round-one, disabled/none, validation, and empty-output runtime edge cases"
    ),
    CORE_TEST_ROOT / "test_loop_carry_context_writer_critic.py": (
        "writer-critic integration and carried-context formatting behavior"
    ),
}
EXPECTED_HELPER_MODULES = {
    CORE_TEST_ROOT / "loop_carry_context_helpers.py": (
        "package-local fake blocks plus seeded WorkflowState and loop runner builders"
    )
}

LEGACY_MAX_LINES = 350
LEGACY_MAX_TEST_FUNCTIONS = 12
LEGACY_MAX_TEST_CLASSES = 4
INLINE_FAKE_BLOCK_MAX_CLASSES = 1
INLINE_BUILDER_NAMES = {"_seeded_state", "_run_loop"}


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


def _baseblock_fake_class_count(tree: ast.Module) -> int:
    return sum(
        isinstance(node, ast.ClassDef)
        and any(
            (isinstance(base, ast.Name) and base.id == "BaseBlock")
            or (isinstance(base, ast.Attribute) and base.attr == "BaseBlock")
            for base in node.bases
        )
        for node in ast.walk(tree)
    )


def _defined_function_names(tree: ast.Module) -> set[str]:
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _legacy_suite_violations() -> list[str]:
    if not LEGACY_CARRY_CONTEXT_SUITE.exists():
        return []

    legacy_source = LEGACY_CARRY_CONTEXT_SUITE.read_text(encoding="utf-8")
    legacy_tree = _parse_source(LEGACY_CARRY_CONTEXT_SUITE)
    legacy_line_count = len(legacy_source.splitlines())
    legacy_test_count = _test_function_count(legacy_tree)
    legacy_class_count = _test_class_count(legacy_tree)
    fake_block_count = _baseblock_fake_class_count(legacy_tree)
    inline_builders = sorted(_defined_function_names(legacy_tree) & INLINE_BUILDER_NAMES)

    violations: list[str] = []
    legacy_label = LEGACY_CARRY_CONTEXT_SUITE.relative_to(CORE_TEST_ROOT)

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
    if fake_block_count > INLINE_FAKE_BLOCK_MAX_CLASSES:
        violations.append(
            f"{legacy_label} defines {fake_block_count} inline BaseBlock fake classes; "
            "move shared carry-context fake blocks to loop_carry_context_helpers.py"
        )
    if inline_builders:
        violations.append(
            f"{legacy_label} still defines inline loop-state builders: "
            + ", ".join(inline_builders)
        )

    return violations


def test_loop_carry_context_governance_owner_suites_externalize_legacy_helpers() -> None:
    """Owner: LoopBlock carry-context tests. Exit: split owner suites replace this guard."""
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

    violations.extend(_legacy_suite_violations())

    assert violations == [], (
        "LoopBlock carry-context governance requires behavior-owner suites, a "
        "small or removed legacy suite, and externalized fake block/state helpers.\n"
        + "\n".join(violations)
    )
