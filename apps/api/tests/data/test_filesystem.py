import json

import pytest

from runsight_api.data.filesystem.soul_repo import SoulRepository
from runsight_api.data.filesystem.workflow_repo import WorkflowRepository
from runsight_api.domain.errors import InputValidationError


def _workflow_yaml(wf_id: str, name: str) -> str:
    return (
        f"id: {wf_id}\n"
        "kind: workflow\n"
        "version: '1.0'\n"
        "blocks: {}\n"
        "workflow:\n"
        f"  name: {name}\n"
        "  entry: start\n"
        "  transitions: []\n"
    )


def test_workflow_repository(tmp_path):
    tmpdir = str(tmp_path)
    repo = WorkflowRepository(base_path=tmpdir)

    # Create stores the embedded id in the YAML.
    wf_id = "repository-round-trip"
    workflow_data = {
        "name": "Repository Round Trip",
        "yaml": _workflow_yaml(wf_id, "Repository Round Trip"),
    }
    entity = repo.create(workflow_data)
    assert entity.id == wf_id
    assert entity.name == "Repository Round Trip"

    # Get looks up by embedded id.
    fetched = repo.get_by_id(wf_id)
    assert fetched is not None
    assert fetched.id == wf_id
    assert fetched.name == "Repository Round Trip"

    # Update persists a new workflow name.
    updated_data = {
        "name": "Updated Workflow",
        "yaml": _workflow_yaml(wf_id, "Updated Workflow"),
    }
    repo.update(wf_id, updated_data)
    fetched_updated = repo.get_by_id(wf_id)
    assert fetched_updated.name == "Updated Workflow"
    assert fetched_updated.id == wf_id

    # Non-YAML structured fields are not synthesized back into the file.
    repo.update(
        wf_id,
        {
            "description": "Keeps existing name",
            "yaml": _workflow_yaml(wf_id, "Updated Workflow"),
        },
    )
    fetched_partial = repo.get_by_id(wf_id)
    assert fetched_partial.name == "Updated Workflow"
    assert not hasattr(fetched_partial, "description")

    # List returns the single stored workflow.
    all_wfs = repo.list_all()
    assert len(all_wfs) == 1

    # Delete removes the workflow.
    assert repo.delete(wf_id) is True
    assert repo.get_by_id(wf_id) is None


def test_workflow_repository_rejects_create_without_yaml(tmp_path):
    tmpdir = str(tmp_path)
    repo = WorkflowRepository(base_path=tmpdir)

    with pytest.raises(InputValidationError, match="yaml is required"):
        repo.create({"name": "No YAML"})


def test_workflow_repository_rejects_create_without_kind(tmp_path):
    tmpdir = str(tmp_path)
    repo = WorkflowRepository(base_path=tmpdir)

    with pytest.raises(InputValidationError, match="kind"):
        repo.create(
            {
                "name": "Missing Kind",
                "yaml": (
                    "id: missing-kind\n"
                    "version: '1.0'\n"
                    "blocks: {}\n"
                    "workflow:\n"
                    "  name: Missing Kind\n"
                    "  entry: start\n"
                    "  transitions: []\n"
                ),
            }
        )

    assert not (repo.workflows_dir / "missing-kind.yaml").exists()


def test_workflow_repository_rejects_update_without_yaml(tmp_path):
    tmpdir = str(tmp_path)
    repo = WorkflowRepository(base_path=tmpdir)
    entity = repo.create(
        {
            "name": "Validation Workflow",
            "yaml": _workflow_yaml("validation-workflow", "Validation Workflow"),
        }
    )

    with pytest.raises(InputValidationError, match="yaml is required"):
        repo.update(entity.id, {"name": "Updated Workflow"})


def test_workflow_repository_rejects_update_without_kind(tmp_path):
    tmpdir = str(tmp_path)
    repo = WorkflowRepository(base_path=tmpdir)
    entity = repo.create(
        {
            "name": "Kind Validation Workflow",
            "yaml": _workflow_yaml("kind-validation-workflow", "Kind Validation Workflow"),
        }
    )
    original_yaml = repo._get_path(entity.id).read_text()

    with pytest.raises(InputValidationError, match="kind"):
        repo.update(
            entity.id,
            {
                "yaml": (
                    "id: kind-validation-workflow\n"
                    "version: '1.0'\n"
                    "blocks: {}\n"
                    "workflow:\n"
                    "  name: Missing Kind\n"
                    "  entry: start\n"
                    "  transitions: []\n"
                )
            },
        )

    assert repo._get_path(entity.id).read_text() == original_yaml


def test_workflow_repository_persists_name_updates_into_valid_yaml(tmp_path):
    tmpdir = str(tmp_path)
    repo = WorkflowRepository(base_path=tmpdir)
    entity = repo.create({"yaml": _workflow_yaml("rename-me", "Original")})

    updated = repo.update(
        entity.id,
        {"name": "Renamed Workflow", "yaml": _workflow_yaml("rename-me", "Original")},
    )

    assert updated.name == "Renamed Workflow"

    fetched = repo.get_by_id(entity.id)
    assert fetched is not None
    assert fetched.name == "Renamed Workflow"


def test_workflow_create_does_not_mutate_input(tmp_path):
    """create() must not mutate the caller's dict."""
    tmpdir = str(tmp_path)
    repo = WorkflowRepository(base_path=tmpdir)

    data = {
        "name": "Immutable",
        "yaml": _workflow_yaml("immutable-wf", "Immutable"),
        "canvas_state": {"nodes": []},
    }
    original_keys = set(data.keys())
    repo.create(data)
    assert set(data.keys()) == original_keys, "create() mutated the input dict"


def test_workflow_id_stored_in_yaml_file(tmp_path):
    """id IS stored inside the YAML file content as canonical identity."""
    import yaml

    tmpdir = str(tmp_path)
    repo = WorkflowRepository(base_path=tmpdir)
    entity = repo.create(
        {
            "name": "With ID Inside",
            "yaml": _workflow_yaml("with-id-inside", "With ID Inside"),
        }
    )

    yaml_path = repo._get_path(entity.id)
    with open(yaml_path) as f:
        on_disk = yaml.safe_load(f)

    assert "id" in on_disk, "id field must be stored in YAML file"
    assert on_disk["id"] == "with-id-inside"


def test_workflow_list_includes_hand_authored_files(tmp_path):
    """Files with a matching embedded id are listed."""
    import yaml

    tmpdir = str(tmp_path)
    repo = WorkflowRepository(base_path=tmpdir)

    # Write a hand-authored YAML file with embedded id matching the filename stem
    hand_file = repo.workflows_dir / "my-hand-authored.yaml"
    hand_file.write_text(
        yaml.dump(
            {
                "id": "my-hand-authored",
                "kind": "workflow",
                "version": "1.0",
                "blocks": {},
                "workflow": {
                    "name": "Hand Authored",
                    "entry": "start",
                    "transitions": [],
                },
            }
        )
    )

    all_wfs = repo.list_all()
    assert len(all_wfs) == 1
    assert all_wfs[0].id == "my-hand-authored"


def test_workflow_get_returns_none_for_malformed_yaml(tmp_path):
    """Malformed YAML cannot be parsed, so get_by_id returns None."""
    tmpdir = str(tmp_path)
    repo = WorkflowRepository(base_path=tmpdir)
    yaml_path = repo.workflows_dir / "broken-workflow.yaml"
    yaml_path.write_text("not: valid: yaml: {{{}}")

    entity = repo.get_by_id("broken-workflow")

    assert entity is None


def test_workflow_list_skips_malformed_yaml(tmp_path):
    """Malformed YAML files are silently skipped in list_all."""
    tmpdir = str(tmp_path)
    repo = WorkflowRepository(base_path=tmpdir)
    (repo.workflows_dir / "legacy-broken.yaml").write_text("not: valid: yaml: {{{}}")

    workflows = repo.list_all()

    assert len(workflows) == 0


def test_workflow_list_does_not_materialize_orphan_canvas_sidecar(tmp_path):
    tmpdir = str(tmp_path)
    workflows_dir = WorkflowRepository(base_path=tmpdir).workflows_dir
    canvas_dir = workflows_dir / ".canvas"
    canvas_path = canvas_dir / "legacy-orphan.canvas.json"
    canvas_path.write_text(
        json.dumps(
            {
                "nodes": [],
                "edges": [],
                "viewport": {"x": 0.0, "y": 0.0, "zoom": 1.0},
                "selected_node_id": None,
                "canvas_mode": "dag",
            }
        )
    )
    repo = WorkflowRepository(base_path=tmpdir)

    workflows = repo.list_all()

    assert not (repo.workflows_dir / "legacy-orphan.yaml").exists()
    assert workflows == []
    assert repo.get_by_id("legacy-orphan") is None


def test_workflow_get_does_not_materialize_orphan_canvas_sidecar(tmp_path):
    tmpdir = str(tmp_path)
    workflows_dir = WorkflowRepository(base_path=tmpdir).workflows_dir
    canvas_dir = workflows_dir / ".canvas"
    canvas_path = canvas_dir / "legacy-get.canvas.json"
    canvas_path.write_text(
        json.dumps(
            {
                "nodes": [],
                "edges": [],
                "viewport": {"x": 0.0, "y": 0.0, "zoom": 1.0},
                "selected_node_id": "orphan-canvas-selected-node",
                "canvas_mode": "state-machine",
            }
        )
    )
    repo = WorkflowRepository(base_path=tmpdir)

    entity = repo.get_by_id("legacy-get")

    assert entity is None
    assert not (repo.workflows_dir / "legacy-get.yaml").exists()


def test_soul_repository(tmp_path):
    tmpdir = str(tmp_path)
    repo = SoulRepository(base_path=tmpdir)

    soul_data = {"id": "sl-one", "kind": "soul", "name": "Review Soul", "role": "Review Soul"}
    entity = repo.create(soul_data)
    assert entity.id == "sl-one"
    assert entity.role == "Review Soul"

    fetched = repo.get_by_id("sl-one")
    assert fetched is not None
    assert fetched.role == "Review Soul"

    updated_data = {
        "id": "sl-one",
        "kind": "soul",
        "name": "Updated Soul",
        "role": "Updated Soul",
    }
    repo.update("sl-one", updated_data)
    assert repo.get_by_id("sl-one").role == "Updated Soul"

    assert len(repo.list_all()) == 1
    assert repo.delete("sl-one") is True
