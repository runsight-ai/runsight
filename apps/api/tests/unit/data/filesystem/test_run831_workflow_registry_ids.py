from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from runsight_api.data.filesystem.workflow_repo import WorkflowRepository


def _write_workflow(
    path: Path,
    *,
    workflow_id: str,
    workflow_name: str,
    child_ref: str | None = None,
) -> None:
    blocks: dict[str, dict[str, object]] = {
        "finish": {
            "type": "code",
            "code": "def main(data):\n    return {}\n",
        }
    }
    transitions = [{"from": "finish", "to": None}]
    entry = "finish"

    if child_ref is not None:
        blocks = {"call_child": {"type": "workflow", "workflow_ref": child_ref}}
        transitions = [{"from": "call_child", "to": None}]
        entry = "call_child"

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            {
                "version": "1.0",
                "id": workflow_id,
                "kind": "workflow",
                "interface": {"inputs": [], "outputs": []},
                "blocks": blocks,
                "workflow": {
                    "name": workflow_name,
                    "entry": entry,
                    "transitions": transitions,
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


@pytest.mark.parametrize(
    "alias",
    [
        "Parent Flow",
        "custom/workflows/parent.yaml",
        "Child Flow",
        "custom/workflows/child.yaml",
    ],
)
def test_build_runnable_workflow_registry_resolves_embedded_ids_only(
    tmp_path: Path, alias: str
) -> None:
    parent_path = tmp_path / "custom" / "workflows" / "parent.yaml"
    child_path = tmp_path / "custom" / "workflows" / "child.yaml"

    _write_workflow(
        child_path,
        workflow_id="child",
        workflow_name="Child Flow",
    )
    _write_workflow(
        parent_path,
        workflow_id="parent",
        workflow_name="Parent Flow",
        child_ref="child",
    )

    registry = WorkflowRepository(base_path=str(tmp_path)).build_runnable_workflow_registry(
        "parent",
        parent_path.read_text(encoding="utf-8"),
    )

    assert registry.get("parent").workflow.name == "Parent Flow"
    assert registry.get("child").workflow.name == "Child Flow"

    with pytest.raises(ValueError, match="cannot resolve ref"):
        registry.get(alias)


def test_workflow_repository_source_does_not_keep_child_stem_fallback() -> None:
    root = Path(__file__).resolve().parents[6]
    source = (
        root / "apps" / "api" / "src" / "runsight_api" / "data" / "filesystem" / "workflow_repo.py"
    ).read_text(encoding="utf-8")

    assert "entity_id or resolved_child.stem" not in source
    assert "resolved_child.entity_id or resolved_child.stem" not in source
    assert "workflow_results_by_id[result.relative_path]" not in source
    assert "workflow_results_by_id[result.item.workflow.name]" not in source
    assert "validation_index[resolved_child.relative_path]" not in source
    assert "validation_index[wf_name]" not in source
