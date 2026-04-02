import json
import tempfile

import pytest

from runsight_api.data.filesystem.soul_repo import SoulRepository
from runsight_api.data.filesystem.step_repo import StepRepository
from runsight_api.data.filesystem.task_repo import TaskRepository
from runsight_api.data.filesystem.workflow_repo import WorkflowRepository
from runsight_api.domain.errors import InputValidationError


def test_workflow_repository():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = WorkflowRepository(base_path=tmpdir)

        # Test Create — id is derived from filename stem (slug-shortid)
        workflow_data = {"name": "Test Workflow", "yaml": "workflow:\n  name: Test Workflow\n"}
        entity = repo.create(workflow_data)
        assert entity.id  # id is auto-generated slug-shortid
        assert entity.name == "Test Workflow"
        assert entity.id.startswith("test-workflow-")
        wf_id = entity.id

        # Test Get — look up by slug-shortid
        fetched = repo.get_by_id(wf_id)
        assert fetched is not None
        assert fetched.id == wf_id
        assert fetched.name == "Test Workflow"

        # Test Update
        updated_data = {"name": "Updated Workflow", "yaml": "workflow:\n  name: Updated Workflow\n"}
        repo.update(wf_id, updated_data)
        fetched_updated = repo.get_by_id(wf_id)
        assert fetched_updated.name == "Updated Workflow"
        assert fetched_updated.id == wf_id

        # Test non-YAML structured fields are not synthesized back into the file
        repo.update(
            wf_id,
            {
                "description": "Keeps existing name",
                "yaml": "workflow:\n  name: Updated Workflow\n",
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


def test_workflow_repository_rejects_update_without_yaml():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = WorkflowRepository(base_path=tmpdir)
        entity = repo.create(
            {"name": "Test Workflow", "yaml": "workflow:\n  name: Test Workflow\n"}
        )

        with pytest.raises(InputValidationError, match="yaml is required"):
            repo.update(entity.id, {"name": "Updated Workflow"})


def test_workflow_create_does_not_mutate_input():
    """create() must not mutate the caller's dict (Fix 2)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = WorkflowRepository(base_path=tmpdir)

        data = {
            "name": "Immutable",
            "yaml": "workflow:\n  name: Immutable\n",
            "canvas_state": {"nodes": []},
        }
        original_keys = set(data.keys())
        repo.create(data)
        assert set(data.keys()) == original_keys, "create() mutated the input dict"


def test_workflow_id_not_in_yaml_file():
    """ADR D3: id must NOT be stored inside the YAML file content."""
    import yaml

    with tempfile.TemporaryDirectory() as tmpdir:
        repo = WorkflowRepository(base_path=tmpdir)
        entity = repo.create({"name": "No ID Inside", "yaml": "workflow:\n  name: No ID Inside\n"})

        yaml_path = repo._get_path(entity.id)
        with open(yaml_path) as f:
            on_disk = yaml.safe_load(f)

        assert "id" not in on_disk, "id field must not be stored in YAML file"


def test_workflow_list_includes_hand_authored_files():
    """Files without an 'id' field inside must still be listed (Fix 4)."""
    import yaml

    with tempfile.TemporaryDirectory() as tmpdir:
        repo = WorkflowRepository(base_path=tmpdir)

        # Write a hand-authored YAML file directly (no 'id' inside)
        hand_file = repo.workflows_dir / "my-hand-authored.yaml"
        hand_file.write_text(yaml.dump({"name": "Hand Authored"}))

        all_wfs = repo.list_all()
        assert len(all_wfs) == 1
        assert all_wfs[0].id == "my-hand-authored"
        assert all_wfs[0].name == "Hand Authored"


def test_workflow_get_returns_invalid_entity_for_malformed_yaml():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = WorkflowRepository(base_path=tmpdir)
        yaml_path = repo.workflows_dir / "broken-workflow.yaml"
        yaml_path.write_text("not: valid: yaml: {{{}}")

        entity = repo.get_by_id("broken-workflow")

        assert entity is not None
        assert entity.id == "broken-workflow"
        assert entity.yaml == "not: valid: yaml: {{{}}"
        assert entity.valid is False
        assert entity.validation_error


def test_workflow_list_keeps_malformed_yaml_recoverable():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = WorkflowRepository(base_path=tmpdir)
        (repo.workflows_dir / "legacy-broken.yaml").write_text("not: valid: yaml: {{{}}")

        workflows = repo.list_all()

        assert len(workflows) == 1
        assert workflows[0].id == "legacy-broken"
        assert workflows[0].valid is False
        assert workflows[0].validation_error


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

        soul_data = {"id": "sl-1", "role": "Test Soul"}
        entity = repo.create(soul_data)
        assert entity.id == "sl-1"
        assert entity.role == "Test Soul"

        fetched = repo.get_by_id("sl-1")
        assert fetched is not None
        assert fetched.role == "Test Soul"

        updated_data = {"id": "sl-1", "role": "Updated Soul"}
        repo.update("sl-1", updated_data)
        assert repo.get_by_id("sl-1").role == "Updated Soul"

        assert len(repo.list_all()) == 1
        assert repo.delete("sl-1") is True


def test_task_repository():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = TaskRepository(base_path=tmpdir)

        task_data = {"id": "tk-1", "name": "Test Task"}
        entity = repo.create(task_data)
        assert entity.id == "tk-1"

        fetched = repo.get_by_id("tk-1")
        assert fetched is not None

        updated_data = {"id": "tk-1", "name": "Updated Task"}
        repo.update("tk-1", updated_data)
        assert repo.get_by_id("tk-1").name == "Updated Task"

        assert len(repo.list_all()) == 1
        assert repo.delete("tk-1") is True


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
