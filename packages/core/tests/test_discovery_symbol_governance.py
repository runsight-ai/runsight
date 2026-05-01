"""Governance for removed core discovery symbols.

Boundary: core workflow/soul/tool discovery source.
Owner: core discovery tests until the legacy discovery helpers are fully
retired from production code and this guard can be deleted.
Exit criteria: remove this suite when behavior-owned scanner tests cover the
replacement path and the legacy symbols have stayed absent for one release
cycle.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.governance


def test_deleted_discovery_symbols_are_gone_from_core_production_code():
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
    root = Path(__file__).resolve().parents[1] / "src"
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
