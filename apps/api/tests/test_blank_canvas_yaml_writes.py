"""Strict blank-canvas workflow YAML writes."""

import pytest

from runsight_api.data.filesystem.workflow_repo import WorkflowRepository
from runsight_api.data.filesystem.workflow_yaml_validation import assert_valid_yaml_for_write
from runsight_api.domain.errors import InputValidationError


@pytest.fixture
def repo(tmp_path):
    return WorkflowRepository(base_path=str(tmp_path))


@pytest.fixture
def workflows_dir(tmp_path):
    return tmp_path / "custom" / "workflows"


def _canonical_blank_canvas_yaml(
    workflow_id: str = "blank-canvas",
    workflow_name: str = "Blank Canvas",
) -> str:
    return (
        'version: "1.0"\n'
        f"id: {workflow_id}\n"
        "kind: workflow\n"
        "enabled: false\n"
        "blocks: {}\n"
        "workflow:\n"
        f"  name: {workflow_name}\n"
        "  entry: start\n"
        "  transitions: []\n"
    )


class TestCanonicalBlankCanvasYamlCreate:
    def test_create_accepts_current_gui_blank_canvas_payload(self, repo, workflows_dir):
        raw_yaml = _canonical_blank_canvas_yaml()

        entity = repo.create({"name": "Blank Canvas", "yaml": raw_yaml})
        yaml_path = workflows_dir / "blank-canvas.yaml"

        assert entity.id == "blank-canvas"
        assert entity.yaml == raw_yaml
        assert yaml_path.read_text() == raw_yaml

    def test_update_accepts_current_gui_blank_canvas_payload(self, repo, workflows_dir):
        initial_yaml = _canonical_blank_canvas_yaml("wf-update", "Original Canvas")
        entity = repo.create({"name": "Original Canvas", "yaml": initial_yaml})
        yaml_path = workflows_dir / "wf-update.yaml"
        updated_yaml = _canonical_blank_canvas_yaml("wf-update", "Renamed Canvas")

        updated = repo.update(entity.id, {"yaml": updated_yaml})

        assert updated.id == "wf-update"
        assert updated.yaml == updated_yaml
        assert yaml_path.read_text() == updated_yaml


class TestInvalidDraftYamlWrites:
    def test_create_rejects_empty_string_yaml(self, repo, workflows_dir):
        with pytest.raises(InputValidationError, match="YAML content is not a mapping"):
            repo.create({"name": "Blank Canvas", "yaml": ""})

        assert list(workflows_dir.glob("*.yaml")) == []

    def test_write_validator_rejects_partial_draft_yaml(self):
        partial_draft = "id: invalid-draft\nkind: workflow\nversion: '1.0'\n"

        with pytest.raises(InputValidationError):
            assert_valid_yaml_for_write("invalid-draft", partial_draft)

    def test_create_rejects_partial_draft_yaml_without_writing_file(self, repo, workflows_dir):
        partial_draft = "id: invalid-create\nkind: workflow\nversion: '1.0'\n"

        with pytest.raises(InputValidationError):
            repo.create({"name": "Invalid Create", "yaml": partial_draft})

        assert list(workflows_dir.glob("invalid-create.yaml")) == []

    def test_update_rejects_partial_draft_yaml_and_preserves_existing_file(
        self, repo, workflows_dir
    ):
        valid_yaml = _canonical_blank_canvas_yaml("strict-update", "Strict Update")
        entity = repo.create({"name": "Strict Update", "yaml": valid_yaml})
        yaml_path = workflows_dir / f"{entity.id}.yaml"
        partial_draft = "id: strict-update\nkind: workflow\nversion: '1.0'\n"

        with pytest.raises(InputValidationError):
            repo.update(entity.id, {"yaml": partial_draft})

        assert yaml_path.read_text() == valid_yaml


class TestMissingYamlIsRejected:
    def test_no_yaml_field_is_rejected(self, repo, workflows_dir):
        with pytest.raises(InputValidationError, match="yaml is required"):
            repo.create({"name": "Auto Generated"})

        assert list(workflows_dir.glob("*.yaml")) == []

    def test_none_yaml_field_is_rejected(self, repo, workflows_dir):
        with pytest.raises(InputValidationError, match="yaml is required"):
            repo.create({"name": "Explicit None", "yaml": None})

        assert list(workflows_dir.glob("*.yaml")) == []

    def test_update_without_yaml_is_rejected_instead_of_preserving_compat_fallback(
        self, repo, workflows_dir
    ):
        initial_yaml = _canonical_blank_canvas_yaml("to-update", "To Update")
        entity = repo.create({"name": "To Update", "yaml": initial_yaml})
        yaml_path = workflows_dir / f"{entity.id}.yaml"

        with pytest.raises(InputValidationError, match="yaml is required"):
            repo.update(entity.id, {"name": "Renamed"})

        assert yaml_path.read_text() == initial_yaml
