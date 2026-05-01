"""Legacy entry point for SubprocessHarness isolation coverage.

Behavior ownership has moved to the IPC wiring, subprocess runtime, process
lifecycle, and result contract suites beside this file.
"""

from __future__ import annotations

from pathlib import Path

_OWNER_SUITES = (
    "test_isolation_harness_ipc_wiring.py",
    "test_isolation_harness_subprocess_runtime.py",
    "test_isolation_harness_process_lifecycle.py",
    "test_isolation_harness_result_contracts.py",
)


def test_isolation_harness_behavior_owner_suites_exist() -> None:
    owner_root = Path(__file__).resolve().parent

    missing = [suite for suite in _OWNER_SUITES if not (owner_root / suite).exists()]

    assert missing == []
