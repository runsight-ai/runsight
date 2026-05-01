"""Governance for removed API workflow-discovery symbols.

Boundary: API filesystem workflow repository source.
Owner: API data/filesystem tests until the old discovery helpers are fully
retired from production code and this guard can be deleted.
Exit criteria: remove this suite when behavior-owned scanner collaboration tests
cover the replacement path and the legacy symbols have stayed absent for one
release cycle.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from runsight_api.data.filesystem.workflow_repo import WorkflowRepository

pytestmark = pytest.mark.governance


def test_deleted_discovery_symbols_are_gone_from_api_production_code():
    legacy_symbols = (
        "discover_custom_assets",
        "discover_custom_tools",
        "_discover_souls",
        "_discover_blocks",
        "_discover_workflows",
        "_to_snake_case",
        "_discovery_module",
        "_build_workflow_validation_index",
        "_resolve_workflow_call_contract_ref",
        "_build_name_index",
        "_read_workflow_from_source",
        "_register_workflow_aliases",
        "_candidate_workflow_paths",
    )
    root = Path(__file__).resolve().parents[4] / "src"
    patterns = {
        symbol: re.compile(rf"(?<!\w){re.escape(symbol)}(?!\w)") for symbol in legacy_symbols
    }

    matches: list[str] = []
    for py_file in root.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        for symbol, pattern in patterns.items():
            if pattern.search(content):
                matches.append(f"{py_file}:{symbol}")

    assert matches == []


def test_workflow_repository_legacy_scan_helpers_are_removed():
    assert not hasattr(WorkflowRepository, "_build_name_index")
    assert not hasattr(WorkflowRepository, "_read_workflow_from_source")
    assert not hasattr(WorkflowRepository, "_register_workflow_aliases")
    assert not hasattr(WorkflowRepository, "_candidate_workflow_paths")
