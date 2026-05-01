"""SubprocessHarness isolation suite split governance.

Owner: packages/core process-isolation test owners.
Boundary: SubprocessHarness IPC/wiring, subprocess runtime isolation,
process lifecycle/stall handling, result/cleanup contracts, and grant-token
coverage must live in owner-specific suites with package-local subprocess and
socket builders instead of one broad legacy suite.
Exit criteria: delete this guard once the split owner suites and shared
isolation harness helper are the durable behavior owners, or when package-local
test safety tooling enforces the same suite-size and fixture-placement rules.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.governance

CORE_TEST_ROOT = Path(__file__).resolve().parents[1]
LEGACY_HARNESS_SUITE = CORE_TEST_ROOT / "test_isolation_harness.py"
HARNESS_HELPER = CORE_TEST_ROOT / "isolation_harness_helpers.py"

EXPECTED_OWNER_SUITES = {
    CORE_TEST_ROOT / "test_isolation_harness_ipc_wiring.py": (
        "IPC handler registration plus LLM, budget, observer, and HTTP wiring"
    ),
    CORE_TEST_ROOT / "test_isolation_harness_subprocess_runtime.py": (
        "minimal subprocess env, cwd, socket path, and context-scope isolation"
    ),
    CORE_TEST_ROOT / "test_isolation_harness_process_lifecycle.py": (
        "timeout, heartbeat, phase-stall, and termination behavior"
    ),
    CORE_TEST_ROOT / "test_isolation_harness_result_contracts.py": (
        "result envelope, cleanup, Linear round trip, and grant-token contracts"
    ),
}

LEGACY_MAX_LINES = 450
LEGACY_MAX_TEST_FUNCTIONS = 12
LEGACY_MAX_TEST_CLASSES = 4
INLINE_SCAFFOLD_NAME_RE = re.compile(
    r"("
    r"HARNESS_SOCKET_ROOT|"
    r"_socket_fixture_path|"
    r"_patch_harness_(?:run|hanging)_subprocess|"
    r"_RecordingStdIn|"
    r"_StaticStdOut|"
    r"_HangingStdOut|"
    r"_EmptyStdErr|"
    r"_Fake(?:Run|Hanging)Process|"
    r"_NoopIPCServer"
    r")"
)
TMP_SOCKET_LITERAL_RE = re.compile(r"""Path\(["']\/["']\)\s*\/\s*["']tmp["']|["']\/tmp["']""")


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


def _defined_scaffold_names(path: Path) -> list[str]:
    tree = _parse_source(path)
    violations: list[str] = []

    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            names.append(node.name)
        elif isinstance(node, ast.Assign):
            names.extend(target.id for target in node.targets if isinstance(target, ast.Name))

        for name in names:
            if INLINE_SCAFFOLD_NAME_RE.search(name):
                violations.append(
                    f"{path.relative_to(CORE_TEST_ROOT)}:{node.lineno}: inline {name}"
                )

    return violations


def test_subprocess_harness_governance_split_externalizes_fixture_scaffolding() -> None:
    """Owner: process-isolation tests. Exit: split suites replace this migration guard."""
    violations: list[str] = []

    for path, owner in EXPECTED_OWNER_SUITES.items():
        if not path.exists():
            violations.append(
                f"missing owner suite for {owner}: {path.relative_to(CORE_TEST_ROOT)}"
            )

    if not HARNESS_HELPER.exists():
        violations.append(
            "missing package-local helper for fake subprocess/socket builders: "
            f"{HARNESS_HELPER.relative_to(CORE_TEST_ROOT)}"
        )

    legacy_source = LEGACY_HARNESS_SUITE.read_text(encoding="utf-8")
    legacy_tree = _parse_source(LEGACY_HARNESS_SUITE)
    legacy_line_count = len(legacy_source.splitlines())
    legacy_test_count = _test_function_count(legacy_tree)
    legacy_class_count = _test_class_count(legacy_tree)

    if legacy_line_count > LEGACY_MAX_LINES:
        violations.append(
            f"{LEGACY_HARNESS_SUITE.relative_to(CORE_TEST_ROOT)} has "
            f"{legacy_line_count} lines; expected <= {LEGACY_MAX_LINES}"
        )
    if legacy_test_count > LEGACY_MAX_TEST_FUNCTIONS:
        violations.append(
            f"{LEGACY_HARNESS_SUITE.relative_to(CORE_TEST_ROOT)} has "
            f"{legacy_test_count} test functions; expected <= {LEGACY_MAX_TEST_FUNCTIONS}"
        )
    if legacy_class_count > LEGACY_MAX_TEST_CLASSES:
        violations.append(
            f"{LEGACY_HARNESS_SUITE.relative_to(CORE_TEST_ROOT)} has "
            f"{legacy_class_count} test classes; expected <= {LEGACY_MAX_TEST_CLASSES}"
        )

    files_to_scan = [LEGACY_HARNESS_SUITE]
    files_to_scan.extend(path for path in EXPECTED_OWNER_SUITES if path.exists())
    inline_scaffolds = [
        violation for path in files_to_scan for violation in _defined_scaffold_names(path)
    ]
    if inline_scaffolds:
        violations.append(
            "fake process/socket scaffolding should live in isolation_harness_helpers.py:\n"
            + "\n".join(inline_scaffolds)
        )

    if HARNESS_HELPER.exists() and TMP_SOCKET_LITERAL_RE.search(
        HARNESS_HELPER.read_text(encoding="utf-8")
    ):
        violations.append(
            "isolation_harness_helpers.py should build socket paths from tmp_path or "
            "test-owned state, not a hard-coded /tmp root"
        )

    assert violations == [], (
        "SubprocessHarness isolation governance requires owner-specific suites, "
        "a small legacy suite, and externalized fake subprocess/socket helpers.\n"
        + "\n".join(violations)
    )
