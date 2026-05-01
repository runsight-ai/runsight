"""Isolation worker suite split governance.

Owner: packages/core isolation worker test owners.
Boundary: worker IPC clients/tools, subprocess startup/env/exit/envelope
parsing, state/context reconstruction, and security/import/grant-token/
capability contracts must live in owner-specific suites with package-local
worker subprocess and envelope helpers instead of one broad legacy suite.
Exit criteria: delete this guard once the split owner suites and shared
isolation worker helper are the durable behavior owners, or when package-local
test safety tooling enforces the same suite-size and helper-placement rules.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.governance

CORE_TEST_ROOT = Path(__file__).resolve().parents[1]
LEGACY_WORKER_SUITE = CORE_TEST_ROOT / "test_isolation_worker.py"
WORKER_HELPER = CORE_TEST_ROOT / "isolation_worker_helpers.py"

EXPECTED_OWNER_SUITES = {
    CORE_TEST_ROOT / "test_isolation_worker_ipc_clients.py": (
        "proxied LLM client, IPC tool stubs, and shared IPC client contracts"
    ),
    CORE_TEST_ROOT / "test_isolation_worker_subprocess_startup.py": (
        "heartbeat, startup env, exit code, stdout envelope, and stdin parsing contracts"
    ),
    CORE_TEST_ROOT / "test_isolation_worker_state_context.py": (
        "fit-to-budget, history, block inputs, soul reconstruction, and scoped state"
    ),
    CORE_TEST_ROOT / "test_isolation_worker_security_capabilities.py": (
        "import boundaries, grant-token, capability negotiation, and assertion block guards"
    ),
}

EXPECTED_HELPER_FUNCTIONS = {
    "worker_socket_path": "test-owned IPC socket path builder",
    "minimal_worker_env": "whitelisted worker subprocess environment builder",
    "make_context_envelope": "minimal ContextEnvelope builder",
    "run_worker_subprocess": "single subprocess.run wrapper for worker execution",
    "parse_result_envelope": "stdout ResultEnvelope parsing helper",
}

LEGACY_MAX_LINES = 450
LEGACY_MAX_TEST_FUNCTIONS = 12
LEGACY_MAX_TEST_CLASSES = 4
INLINE_SCAFFOLD_NAME_RE = re.compile(
    r"("
    r"_SAFE_SUBPROCESS_ENV_KEYS|"
    r"_WORKER_SUBPROCESS_TIMEOUT_SECONDS|"
    r"_worker_socket_path|"
    r"_minimal_worker_env|"
    r"_make_context_envelope|"
    r"_run_worker"
    r")"
)
UNSAFE_HELPER_PATH_RE = re.compile(
    r"""Path\(["']\/["']\)\s*\/\s*["']tmp["']|["']\/tmp["']|"""
    r"""(?:REPO_ROOT|repo_root|Path\.cwd\(\))\s*/\s*["'](?:custom|\.runsight)["']"""
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


def _inline_scaffold_names(path: Path) -> list[str]:
    violations: list[str] = []

    for name, line_number in _defined_names(path).items():
        if INLINE_SCAFFOLD_NAME_RE.search(name):
            violations.append(f"{path.relative_to(CORE_TEST_ROOT)}:{line_number}: inline {name}")

    return violations


def _subprocess_run_calls(path: Path) -> list[str]:
    tree = _parse_source(path)
    calls: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if (
            isinstance(func, ast.Attribute)
            and func.attr == "run"
            and isinstance(func.value, ast.Name)
            and func.value.id == "subprocess"
        ):
            calls.append(f"{path.relative_to(CORE_TEST_ROOT)}:{node.lineno}: subprocess.run")

    return calls


def _legacy_suite_violations() -> list[str]:
    if not LEGACY_WORKER_SUITE.exists():
        return []

    legacy_source = LEGACY_WORKER_SUITE.read_text(encoding="utf-8")
    legacy_tree = _parse_source(LEGACY_WORKER_SUITE)
    legacy_line_count = len(legacy_source.splitlines())
    legacy_test_count = _test_function_count(legacy_tree)
    legacy_class_count = _test_class_count(legacy_tree)
    legacy_label = LEGACY_WORKER_SUITE.relative_to(CORE_TEST_ROOT)
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

    return violations


def test_isolation_worker_governance_owner_suites_externalize_subprocess_helpers() -> None:
    """Owner: isolation worker tests. Exit: split suites replace this governance guard."""
    violations: list[str] = []

    for path, owner in EXPECTED_OWNER_SUITES.items():
        if not path.exists():
            violations.append(
                f"missing owner suite for {owner}: {path.relative_to(CORE_TEST_ROOT)}"
            )

    if not WORKER_HELPER.exists():
        violations.append(
            "missing package-local helper for worker env/subprocess/envelope scaffolding: "
            f"{WORKER_HELPER.relative_to(CORE_TEST_ROOT)}"
        )
    else:
        helper_names = _defined_names(WORKER_HELPER)
        for name, purpose in EXPECTED_HELPER_FUNCTIONS.items():
            if name not in helper_names:
                violations.append(
                    f"{WORKER_HELPER.relative_to(CORE_TEST_ROOT)} is missing {name} for {purpose}"
                )
        if UNSAFE_HELPER_PATH_RE.search(WORKER_HELPER.read_text(encoding="utf-8")):
            violations.append(
                "isolation_worker_helpers.py should use tmp_path or test-owned state, "
                "not hard-coded /tmp or repo-root runtime assets"
            )

    violations.extend(_legacy_suite_violations())

    files_to_scan = [LEGACY_WORKER_SUITE]
    files_to_scan.extend(path for path in EXPECTED_OWNER_SUITES if path.exists())
    inline_scaffolds = [
        violation
        for path in files_to_scan
        if path.exists()
        for violation in _inline_scaffold_names(path)
    ]
    subprocess_calls = [
        violation
        for path in files_to_scan
        if path.exists()
        for violation in _subprocess_run_calls(path)
    ]

    if inline_scaffolds:
        violations.append(
            "worker env/subprocess/envelope scaffolding should live in "
            "isolation_worker_helpers.py:\n" + "\n".join(inline_scaffolds)
        )
    if subprocess_calls:
        violations.append(
            "worker subprocess execution should go through run_worker_subprocess() "
            "in isolation_worker_helpers.py:\n" + "\n".join(subprocess_calls)
        )

    assert violations == [], (
        "Isolation worker governance requires behavior-owner suites, a small or "
        "removed legacy suite, and externalized env/subprocess/envelope helpers.\n"
        + "\n".join(violations)
    )
