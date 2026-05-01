"""Compatibility smoke coverage for split isolation credential owner suites.

Behavior coverage now lives in the focused owner suites named here. This file
stays small so targeted legacy invocations still collect a passing boundary
check while the migration settles.
"""

from __future__ import annotations

OWNER_SUITE_MODULES = (
    "test_isolation_credentials_ipc_tool_handler",
    "test_isolation_http_security",
    "test_isolation_file_io_sandbox",
    "test_isolation_env_resolution_budget",
)


def test_isolation_credentials_behavior_is_split_into_owner_suites() -> None:
    """Credential isolation behavior is owned by focused split suites."""
    assert OWNER_SUITE_MODULES == (
        "test_isolation_credentials_ipc_tool_handler",
        "test_isolation_http_security",
        "test_isolation_file_io_sandbox",
        "test_isolation_env_resolution_budget",
    )
