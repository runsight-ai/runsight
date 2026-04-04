from __future__ import annotations

from pathlib import Path

import yaml as pyyaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
CUSTOM_SOULS = REPO_ROOT / "custom" / "souls"
CUSTOM_WORKFLOWS = REPO_ROOT / "custom" / "workflows"
LEGACY_BUILTIN_IDS = {"runsight/http", "runsight/file-io", "runsight/delegate"}


def _load_yaml(path: Path) -> dict:
    data = pyyaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _tool_ids(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [tool_id for tool_id in value if isinstance(tool_id, str)]


def test_custom_souls_use_canonical_builtin_tool_ids():
    for soul_path in sorted(CUSTOM_SOULS.glob("*.yaml")):
        data = _load_yaml(soul_path)
        for tool_id in _tool_ids(data.get("tools")):
            assert tool_id not in LEGACY_BUILTIN_IDS, (
                f"{soul_path.name} still uses legacy builtin tool id {tool_id!r}"
            )


def test_example_workflows_use_canonical_tool_ids_and_declare_soul_tools():
    for workflow_path in sorted(CUSTOM_WORKFLOWS.glob("*.yaml")):
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
