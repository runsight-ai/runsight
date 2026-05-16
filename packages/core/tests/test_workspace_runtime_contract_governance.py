"""Governance for workspace runtime contract ownership.

Owner: packages/core owns the workspace runtime isolation contract boundary.
Boundary: this suite may inspect checked-in Python source under packages/core
and apps/api. It must not inspect repo-root runtime state such as .runsight/,
runsight.db, custom/, secrets, or user configuration.
Exit criteria: delete this suite once import ownership is enforced by package
metadata or dedicated architectural tooling.
"""

from __future__ import annotations

import inspect
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.governance

REPO_ROOT = Path(__file__).resolve().parents[3]
CORE_SOURCE_ROOT = REPO_ROOT / "packages" / "core" / "src"
API_SOURCE_ROOT = REPO_ROOT / "apps" / "api"
LEGACY_CORE_ROOT = REPO_ROOT / "libs" / "core"

WORKSPACE_RUNTIME_CONTRACTS = (
    "WorkspaceHarness",
    "WorkspaceMaterialization",
    "WorkspaceManifest",
    "WorkspaceMaterializer",
    "WorkspacePolicy",
    "PolicyCapabilityReport",
    "WorkspaceSession",
    "WorkspaceSessionFactory",
    "WorkspaceHostBindings",
    "WorkspaceRunRequest",
    "IPCClientConfig",
    "IPCBinding",
    "IPCTransport",
    "WorkerLaunchSpec",
    "WorkerProcessHandle",
    "WorkerLauncher",
    "WorkerToolRegistry",
    "WorkerToolSchema",
    "HostToolExecutionRegistry",
    "HostToolExecutionRef",
)


def _relative(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


def test_workspace_runtime_contracts_are_exported_from_core_isolation_package() -> None:
    import runsight_core.isolation as isolation

    missing = [name for name in WORKSPACE_RUNTIME_CONTRACTS if not hasattr(isolation, name)]

    assert missing == []


def test_workspace_runtime_contract_definitions_live_under_packages_core() -> None:
    import runsight_core.isolation as isolation

    missing = [name for name in WORKSPACE_RUNTIME_CONTRACTS if not hasattr(isolation, name)]
    assert missing == []

    misplaced: list[str] = []
    for name in WORKSPACE_RUNTIME_CONTRACTS:
        source_path = Path(inspect.getfile(getattr(isolation, name))).resolve()
        if not source_path.is_relative_to(CORE_SOURCE_ROOT):
            misplaced.append(f"{name}: {_relative(source_path)}")

    assert misplaced == []


def test_workspace_runtime_contracts_are_not_defined_in_apps_api_or_legacy_core() -> None:
    definition_pattern = re.compile(
        r"^\s*(?:class|def)\s+(" + "|".join(WORKSPACE_RUNTIME_CONTRACTS) + r")\b",
        re.MULTILINE,
    )
    scanned_roots = [API_SOURCE_ROOT]
    if LEGACY_CORE_ROOT.exists():
        scanned_roots.append(LEGACY_CORE_ROOT)

    offenders: list[str] = []
    for root in scanned_roots:
        for path in root.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            matches = sorted(set(definition_pattern.findall(path.read_text(encoding="utf-8"))))
            if matches:
                offenders.append(f"{_relative(path)} defines {', '.join(matches)}")

    assert offenders == []
