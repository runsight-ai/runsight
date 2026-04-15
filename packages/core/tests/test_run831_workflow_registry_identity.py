from __future__ import annotations

import inspect
from pathlib import Path

import pytest
import yaml
from runsight_core.yaml.registry import WorkflowRegistry
from runsight_core.yaml.schema import RunsightWorkflowFile


def _write_workflow(path: Path, *, workflow_id: str, workflow_name: str) -> RunsightWorkflowFile:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": "1.0",
        "id": workflow_id,
        "kind": "workflow",
        "interface": {"inputs": [], "outputs": []},
        "blocks": {
            "finish": {
                "type": "code",
                "code": "def main(data):\n    return {}\n",
            }
        },
        "workflow": {
            "name": workflow_name,
            "entry": "finish",
            "transitions": [{"from": "finish", "to": None}],
        },
    }
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return RunsightWorkflowFile.model_validate(payload)


def test_workflow_registry_constructor_no_longer_accepts_compatibility_fallback_shim() -> None:
    signature = inspect.signature(WorkflowRegistry)

    assert "allow_filesystem_fallback" not in signature.parameters


def test_workflow_registry_rejects_filesystem_path_refs_even_when_embedded_id_is_registered(
    tmp_path: Path,
) -> None:
    workflow_path = tmp_path / "custom" / "workflows" / "child.yaml"
    workflow_file = _write_workflow(
        workflow_path,
        workflow_id="child",
        workflow_name="Child Flow",
    )

    registry = WorkflowRegistry()
    registry.register("child", workflow_file)

    assert registry.get("child") is workflow_file

    with pytest.raises(ValueError):
        registry.get(workflow_path.resolve().as_posix())


def test_workflow_registry_resolves_only_explicit_embedded_ids(tmp_path: Path) -> None:
    workflow_path = tmp_path / "custom" / "workflows" / "child.yaml"
    workflow_file = _write_workflow(
        workflow_path,
        workflow_id="child",
        workflow_name="Child Flow",
    )

    registry = WorkflowRegistry()
    registry.register("child", workflow_file)

    assert registry.get("child") is workflow_file
    with pytest.raises(ValueError):
        registry.get("Child Flow")
