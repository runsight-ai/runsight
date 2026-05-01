"""Isolation credential suite split governance.

Owner: packages/core isolation credential and security-boundary test owners.
Boundary: credential-scoped IPC/tool handling, HTTP credential/security
behavior, file I/O sandbox behavior, and env/budget ownership must live in
owner-specific suites with package-local context, IPC-pair, and tool-call
helpers instead of one broad legacy suite.
Exit criteria: delete this guard once the split owner suites and shared helper
module are the durable behavior owners, or when package-local test safety
tooling enforces the same suite-size and helper-placement rules.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.governance

CORE_TEST_ROOT = Path(__file__).resolve().parent
LEGACY_CREDENTIAL_SUITE = CORE_TEST_ROOT / "test_isolation_credentials.py"
CREDENTIAL_HELPER = CORE_TEST_ROOT / "isolation_credentials_helpers.py"

EXPECTED_OWNER_SUITES = {
    CORE_TEST_ROOT / "test_isolation_credentials_ipc_tool_handler.py": (
        "subprocess credential scoping and generic IPC tool-call handler behavior"
    ),
    CORE_TEST_ROOT / "test_isolation_http_security.py": (
        "HTTP credential injection, URL allowlist, SSRF protection, and transport"
    ),
    CORE_TEST_ROOT / "test_isolation_file_io_sandbox.py": (
        "file base-dir and traversal sandbox behavior"
    ),
    CORE_TEST_ROOT / "test_isolation_env_resolution_budget.py": (
        "environment variable resolution and LLM budget ownership behavior"
    ),
}

LEGACY_MAX_LINES = 450
LEGACY_MAX_TEST_FUNCTIONS = 12
LEGACY_MAX_TEST_CLASSES = 4
EXPECTED_HELPER_NAMES = {
    "_make_context_envelope": "ContextEnvelope builder",
    "_setup_ipc_pair": "IPC server/client pair setup",
    "_teardown_ipc_pair": "IPC server/client pair teardown",
    "_tool_call_echo": "successful tool-call handler fake",
    "_tool_call_boom": "failing tool-call handler fake",
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


def _defined_helper_names(path: Path) -> dict[str, int]:
    tree = _parse_source(path)
    return {
        node.name: node.lineno
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in EXPECTED_HELPER_NAMES
    }


def test_isolation_credentials_governance_owner_suites_externalize_ipc_context_helpers() -> None:
    """Owner: isolation credential tests. Exit: split suites replace this guard."""
    violations: list[str] = []

    for path, owner in EXPECTED_OWNER_SUITES.items():
        if not path.exists():
            violations.append(
                f"missing owner suite for {owner}: {path.relative_to(CORE_TEST_ROOT)}"
            )

    if not CREDENTIAL_HELPER.exists():
        violations.append(
            "missing package-local helper for context, IPC-pair, and tool-call scaffolding: "
            f"{CREDENTIAL_HELPER.relative_to(CORE_TEST_ROOT)}"
        )
    else:
        helper_names = set(_defined_helper_names(CREDENTIAL_HELPER))
        for name, purpose in EXPECTED_HELPER_NAMES.items():
            if name not in helper_names:
                violations.append(
                    f"{CREDENTIAL_HELPER.relative_to(CORE_TEST_ROOT)} does not define "
                    f"{name} for {purpose}"
                )

    legacy_source = LEGACY_CREDENTIAL_SUITE.read_text(encoding="utf-8")
    legacy_tree = _parse_source(LEGACY_CREDENTIAL_SUITE)
    legacy_line_count = len(legacy_source.splitlines())
    legacy_test_count = _test_function_count(legacy_tree)
    legacy_class_count = _test_class_count(legacy_tree)

    if legacy_line_count > LEGACY_MAX_LINES:
        violations.append(
            f"{LEGACY_CREDENTIAL_SUITE.relative_to(CORE_TEST_ROOT)} has "
            f"{legacy_line_count} lines; expected <= {LEGACY_MAX_LINES}"
        )
    if legacy_test_count > LEGACY_MAX_TEST_FUNCTIONS:
        violations.append(
            f"{LEGACY_CREDENTIAL_SUITE.relative_to(CORE_TEST_ROOT)} has "
            f"{legacy_test_count} test functions; expected <= {LEGACY_MAX_TEST_FUNCTIONS}"
        )
    if legacy_class_count > LEGACY_MAX_TEST_CLASSES:
        violations.append(
            f"{LEGACY_CREDENTIAL_SUITE.relative_to(CORE_TEST_ROOT)} has "
            f"{legacy_class_count} test classes; expected <= {LEGACY_MAX_TEST_CLASSES}"
        )

    files_to_scan = [LEGACY_CREDENTIAL_SUITE]
    files_to_scan.extend(path for path in EXPECTED_OWNER_SUITES if path.exists())
    inline_helpers = [
        f"{path.relative_to(CORE_TEST_ROOT)}:{line_number}: inline {name}"
        for path in files_to_scan
        for name, line_number in _defined_helper_names(path).items()
    ]
    if inline_helpers:
        violations.append(
            "context, IPC-pair, and tool-call scaffolding should live in "
            "isolation_credentials_helpers.py:\n" + "\n".join(inline_helpers)
        )

    assert violations == [], (
        "Isolation credential governance requires owner-specific suites, a "
        "small legacy suite, and externalized context/IPC/tool-call helpers.\n"
        + "\n".join(violations)
    )
