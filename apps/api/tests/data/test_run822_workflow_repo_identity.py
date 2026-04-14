"""Red tests for RUN-822: workflow repository must use embedded workflow ids."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from runsight_api.data.filesystem.workflow_repo import WorkflowRepository


def _workflow_fixture_text() -> str:
    repo_root = Path(__file__).resolve().parents[4]
    fixture_path = (
        repo_root
        / "packages"
        / "core"
        / "tests"
        / "fixtures"
        / "custom"
        / "workflows"
        / "research-review.yaml"
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

    with pytest.raises(ValueError, match="id"):
        repo.update(
            "legacy-workflow",
            {"name": "Renamed Research Review", "yaml": _workflow_fixture_text()},
        )
