"""Custom asset tool contract governance.

Owner: packages/core custom asset fixtures.
Boundary: checked-in custom soul and workflow fixtures must use canonical tool
IDs and declare soul-required tools without depending on runtime custom assets.
Exit criteria: remove when fixture validation is handled by shared asset
contract checks.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml as pyyaml

pytestmark = pytest.mark.governance

FIXTURE_CUSTOM_ROOT = Path(__file__).resolve().parent / "fixtures" / "custom"
CUSTOM_SOULS = FIXTURE_CUSTOM_ROOT / "souls"
CUSTOM_WORKFLOWS = FIXTURE_CUSTOM_ROOT / "workflows"
LEGACY_BUILTIN_IDS = {"runsight/http", "runsight/file-io", "runsight/delegate"}


def _load_yaml(path: Path) -> dict:
    data = pyyaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _tool_ids(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [tool_id for tool_id in value if isinstance(tool_id, str)]


def _yaml_files(directory: Path) -> list[Path]:
    return sorted(directory.glob("*.yaml"))


def test_custom_asset_fixtures_exist():
    assert _yaml_files(CUSTOM_SOULS), f"No soul fixture YAML files found in {CUSTOM_SOULS}"
    assert _yaml_files(CUSTOM_WORKFLOWS), (
        f"No workflow fixture YAML files found in {CUSTOM_WORKFLOWS}"
    )


def test_custom_souls_use_canonical_builtin_tool_ids():
    for soul_path in _yaml_files(CUSTOM_SOULS):
        data = _load_yaml(soul_path)
        for tool_id in _tool_ids(data.get("tools")):
            assert tool_id not in LEGACY_BUILTIN_IDS, (
                f"{soul_path.name} still uses legacy builtin tool id {tool_id!r}"
            )


def test_example_workflows_use_canonical_tool_ids_and_declare_soul_tools():
    for workflow_path in _yaml_files(CUSTOM_WORKFLOWS):
        data = _load_yaml(workflow_path)
        declared_tool_ids = set(_tool_ids(data.get("tools")))

        for tool_id in declared_tool_ids:
            assert tool_id not in LEGACY_BUILTIN_IDS, (
                f"{workflow_path.name} still declares legacy builtin tool id {tool_id!r}"
            )

        souls = data.get("souls")
        if not isinstance(souls, dict):
            continue

        for soul_key, soul_def in souls.items():
            if not isinstance(soul_def, dict):
                continue

            for tool_id in _tool_ids(soul_def.get("tools")):
                assert tool_id not in LEGACY_BUILTIN_IDS, (
                    f"{workflow_path.name} soul {soul_key!r} still uses legacy builtin tool id "
                    f"{tool_id!r}"
                )
                assert tool_id in declared_tool_ids, (
                    f"{workflow_path.name} soul {soul_key!r} references undeclared tool id "
                    f"{tool_id!r}"
                )
