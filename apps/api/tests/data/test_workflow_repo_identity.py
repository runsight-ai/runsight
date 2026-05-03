"""Workflow repository must use embedded workflow ids."""

from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

import pytest

from runsight_api.data.filesystem.workflow_repo import WorkflowRepository
from runsight_api.domain.errors import InputValidationError


def _workflow_fixture_text() -> str:
    fixture_path = (
        Path(__file__).resolve().parents[1] / "fixtures" / "workflows" / "research-review.yaml"
    )
    return fixture_path.read_text(encoding="utf-8")


def _write_workflow_file(path: Path, yaml_text: str) -> None:
    path.write_text(dedent(yaml_text).strip() + "\n", encoding="utf-8")


def test_create_writes_workflow_filename_from_embedded_id_not_generated_slug(tmp_path) -> None:
    repo = WorkflowRepository(base_path=str(tmp_path))
    workflows_dir = tmp_path / "custom" / "workflows"
    raw_yaml = _workflow_fixture_text()

    entity = repo.create({"name": "Research & Review", "yaml": raw_yaml})

    assert entity.id == "research-review"
    assert (workflows_dir / "research-review.yaml").exists()
    assert not any(
        path.name.startswith("research-review-") for path in workflows_dir.glob("*.yaml")
    )


def test_list_all_does_not_infer_workflow_id_from_filename_stem_when_yaml_id_differs(
    tmp_path,
) -> None:
    repo = WorkflowRepository(base_path=str(tmp_path))
    workflows_dir = tmp_path / "custom" / "workflows"
    _write_workflow_file(workflows_dir / "legacy-workflow.yaml", _workflow_fixture_text())

    assert repo.list_all() == []


def test_get_by_id_rejects_workflow_id_stem_mismatch(tmp_path) -> None:
    repo = WorkflowRepository(base_path=str(tmp_path))
    workflows_dir = tmp_path / "custom" / "workflows"
    _write_workflow_file(workflows_dir / "legacy-workflow.yaml", _workflow_fixture_text())

    with pytest.raises(ValueError, match="id"):
        repo.get_by_id("legacy-workflow")


def test_update_rejects_workflow_id_stem_mismatch(tmp_path) -> None:
    repo = WorkflowRepository(base_path=str(tmp_path))
    workflows_dir = tmp_path / "custom" / "workflows"
    _write_workflow_file(workflows_dir / "legacy-workflow.yaml", _workflow_fixture_text())

    with pytest.raises(InputValidationError, match="id"):
        repo.update(
            "legacy-workflow",
            {"name": "Renamed Research Review", "yaml": _workflow_fixture_text()},
        )


def test_create_requires_embedded_workflow_id(tmp_path: Path) -> None:
    repo = WorkflowRepository(base_path=str(tmp_path))

    with pytest.raises(InputValidationError, match="Workflow must have an id"):
        repo.create(
            {
                "yaml": dedent(
                    """\
                    version: "1.0"
                    kind: workflow
                    workflow:
                      name: Research Review
                      entry: start
                      transitions: []
                    """
                )
            }
        )


def test_validate_yaml_rejects_missing_id_and_wrong_kind(tmp_path: Path) -> None:
    repo = WorkflowRepository(base_path=str(tmp_path))

    valid, validation_error, warnings = repo._validate_yaml_content(
        "research-review",
        dedent(
            """\
            version: "1.0"
            kind: workflow
            workflow:
              name: Research Review
              entry: start
              transitions: []
            """
        ),
    )
    assert valid is False
    assert validation_error is not None
    assert "id" in validation_error.lower()
    assert warnings == []

    valid, validation_error, warnings = repo._validate_yaml_content(
        "research-review",
        dedent(
            """\
            version: "1.0"
            id: research-review
            kind: pipeline
            workflow:
              name: Research Review
              entry: start
              transitions: []
            """
        ),
    )
    assert valid is False
    assert validation_error is not None
    assert "kind" in validation_error.lower()
    assert warnings == []


def test_build_entity_from_yaml_reports_snapshot_id_mismatch_as_validation_error(tmp_path) -> None:
    repo = WorkflowRepository(base_path=str(tmp_path))

    with pytest.raises(InputValidationError, match="embedded id"):
        repo.build_entity_from_yaml("legacy-workflow", _workflow_fixture_text())


def test_update_keeps_yaml_and_canvas_persistence_in_separate_workflow_contract_files(
    tmp_path,
) -> None:
    repo = WorkflowRepository(base_path=str(tmp_path))
    raw_yaml = (
        dedent(
            """
        version: "1.0"
        id: canvas_contract_workflow
        kind: workflow
        workflow:
          name: Canvas Contract
          entry: analyze
          transitions:
            - from: analyze
              to: null
        blocks:
          analyze:
            type: linear
            soul_ref: analyst
        souls:
          analyst:
            id: analyst
            kind: soul
            name: Analyst
            role: Analyst
            system_prompt: You are a careful analyst.
            provider: fixture-provider
            model_name: fixture-chat-model
        config: {}
        """
        ).strip()
        + "\n"
    )
    updated_yaml = raw_yaml.replace("Canvas Contract", "Canvas Contract Updated")
    canvas_state = {
        "nodes": [{"id": "analysis-node", "position": {"x": 12, "y": 34}}],
        "edges": [
            {
                "id": "analysis-to-review-edge",
                "source": "analysis-node",
                "target": "review-node",
            }
        ],
        "viewport": {"x": 1, "y": 2, "zoom": 0.75},
        "selected_node_id": "analysis-node",
        "canvas_mode": "dag",
    }

    repo.create({"yaml": raw_yaml})
    entity = repo.update(
        "canvas_contract_workflow",
        {
            "yaml": updated_yaml,
            "canvas_state": canvas_state,
        },
    )

    yaml_path = tmp_path / "custom" / "workflows" / "canvas_contract_workflow.yaml"
    canvas_path = (
        tmp_path / "custom" / "workflows" / ".canvas" / "canvas_contract_workflow.canvas.json"
    )
    assert yaml_path.read_text(encoding="utf-8") == updated_yaml
    assert "canvas_state" not in yaml_path.read_text(encoding="utf-8")
    assert json.loads(canvas_path.read_text(encoding="utf-8"))["selected_node_id"] == (
        "analysis-node"
    )

    reloaded = repo.get_by_id("canvas_contract_workflow")
    assert reloaded is not None
    reloaded_canvas = (
        reloaded.canvas_state.model_dump()
        if hasattr(reloaded.canvas_state, "model_dump")
        else reloaded.canvas_state
    )
    assert entity.yaml == updated_yaml
    assert reloaded.yaml == updated_yaml
    assert reloaded_canvas == canvas_state
