import json
import tempfile

import pytest

from runsight_api.data.filesystem.soul_repo import SoulRepository
from runsight_api.data.filesystem.step_repo import StepRepository
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


def test_workflow_repository():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = WorkflowRepository(base_path=tmpdir)

        # Test Create — id is embedded in the YAML (RUN-822)
        wf_id = "test-workflow"
        workflow_data = {
            "name": "Test Workflow",
            "yaml": _workflow_yaml(wf_id, "Test Workflow"),
        }
        entity = repo.create(workflow_data)
        assert entity.id == wf_id
        assert entity.name == "Test Workflow"

        # Test Get — look up by embedded id
        fetched = repo.get_by_id(wf_id)
        assert fetched is not None
        assert fetched.id == wf_id
        assert fetched.name == "Test Workflow"

        # Test Update
        updated_data = {
            "name": "Updated Workflow",
            "yaml": _workflow_yaml(wf_id, "Updated Workflow"),
        }
        repo.update(wf_id, updated_data)
        fetched_updated = repo.get_by_id(wf_id)
        assert fetched_updated.name == "Updated Workflow"
        assert fetched_updated.id == wf_id

        # Test non-YAML structured fields are not synthesized back into the file
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

        # Test List
        all_wfs = repo.list_all()
        assert len(all_wfs) == 1

        # Test Delete
        assert repo.delete(wf_id) is True
        assert repo.get_by_id(wf_id) is None


def test_workflow_repository_rejects_create_without_yaml():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = WorkflowRepository(base_path=tmpdir)

        with pytest.raises(InputValidationError, match="yaml is required"):
            repo.create({"name": "No YAML"})


def test_workflow_repository_rejects_create_without_kind():
    with tempfile.TemporaryDirectory() as tmpdir:
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


def test_workflow_repository_rejects_update_without_yaml():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = WorkflowRepository(base_path=tmpdir)
        entity = repo.create(
            {
                "name": "Test Workflow",
                "yaml": _workflow_yaml("test-workflow", "Test Workflow"),
            }
        )

        with pytest.raises(InputValidationError, match="yaml is required"):
            repo.update(entity.id, {"name": "Updated Workflow"})


def test_workflow_repository_rejects_update_without_kind():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = WorkflowRepository(base_path=tmpdir)
        entity = repo.create(
            {
                "name": "Test Workflow",
                "yaml": _workflow_yaml("test-workflow", "Test Workflow"),
            }
        )
        original_yaml = repo._get_path(entity.id).read_text()

        with pytest.raises(InputValidationError, match="kind"):
            repo.update(
                entity.id,
                {
                    "yaml": (
                        "id: test-workflow\n"
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


def test_workflow_repository_persists_name_updates_into_valid_yaml():
    with tempfile.TemporaryDirectory() as tmpdir:
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


def test_workflow_create_does_not_mutate_input():
    """create() must not mutate the caller's dict (Fix 2)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = WorkflowRepository(base_path=tmpdir)

        data = {
            "name": "Immutable",
            "yaml": _workflow_yaml("immutable-wf", "Immutable"),
            "canvas_state": {"nodes": []},
        }
        original_keys = set(data.keys())
        repo.create(data)
        assert set(data.keys()) == original_keys, "create() mutated the input dict"


def test_workflow_id_stored_in_yaml_file():
    """RUN-822: id IS stored inside the YAML file content as canonical identity."""
    import yaml

    with tempfile.TemporaryDirectory() as tmpdir:
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


def test_workflow_list_includes_hand_authored_files():
    """Files with a matching embedded id are listed (RUN-822)."""
    import yaml

    with tempfile.TemporaryDirectory() as tmpdir:
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


def test_workflow_get_returns_none_for_malformed_yaml():
    """Malformed YAML cannot be parsed, so get_by_id returns None (RUN-822)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = WorkflowRepository(base_path=tmpdir)
        yaml_path = repo.workflows_dir / "broken-workflow.yaml"
        yaml_path.write_text("not: valid: yaml: {{{}}")

        entity = repo.get_by_id("broken-workflow")

        assert entity is None


def test_workflow_list_skips_malformed_yaml():
    """Malformed YAML files are silently skipped in list_all (RUN-822)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = WorkflowRepository(base_path=tmpdir)
        (repo.workflows_dir / "legacy-broken.yaml").write_text("not: valid: yaml: {{{}}")

        workflows = repo.list_all()

        assert len(workflows) == 0


def test_workflow_list_does_not_materialize_orphan_canvas_sidecar():
    with tempfile.TemporaryDirectory() as tmpdir:
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


def test_workflow_get_does_not_materialize_orphan_canvas_sidecar():
    with tempfile.TemporaryDirectory() as tmpdir:
        workflows_dir = WorkflowRepository(base_path=tmpdir).workflows_dir
        canvas_dir = workflows_dir / ".canvas"
        canvas_path = canvas_dir / "legacy-get.canvas.json"
        canvas_path.write_text(
            json.dumps(
                {
                    "nodes": [],
                    "edges": [],
                    "viewport": {"x": 0.0, "y": 0.0, "zoom": 1.0},
                    "selected_node_id": "node-1",
                    "canvas_mode": "state-machine",
                }
            )
        )
        repo = WorkflowRepository(base_path=tmpdir)

        entity = repo.get_by_id("legacy-get")

        assert entity is None
        assert not (repo.workflows_dir / "legacy-get.yaml").exists()


def test_soul_repository():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = SoulRepository(base_path=tmpdir)

        soul_data = {"id": "sl-one", "kind": "soul", "name": "Test Soul", "role": "Test Soul"}
        entity = repo.create(soul_data)
        assert entity.id == "sl-one"
        assert entity.role == "Test Soul"

        fetched = repo.get_by_id("sl-one")
        assert fetched is not None
        assert fetched.role == "Test Soul"

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


def test_step_repository():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = StepRepository(base_path=tmpdir)

        step_data = {"id": "st-1", "name": "Test Step"}
        entity = repo.create(step_data)
        assert entity.id == "st-1"

        fetched = repo.get_by_id("st-1")
        assert fetched is not None

        updated_data = {"id": "st-1", "name": "Updated Step"}
        repo.update("st-1", updated_data)
        assert repo.get_by_id("st-1").name == "Updated Step"

        assert len(repo.list_all()) == 1
        assert repo.delete("st-1") is True
