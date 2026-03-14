import tempfile
from runsight_api.data.filesystem.workflow_repo import WorkflowRepository
from runsight_api.data.filesystem.soul_repo import SoulRepository
from runsight_api.data.filesystem.task_repo import TaskRepository
from runsight_api.data.filesystem.step_repo import StepRepository


def test_workflow_repository():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = WorkflowRepository(base_path=tmpdir)

        # Test Create
        workflow_data = {"id": "wf-1", "name": "Test Workflow"}
        entity = repo.create(workflow_data)
        assert entity.id == "wf-1"
        assert entity.name == "Test Workflow"

        # Test Get
        fetched = repo.get_by_id("wf-1")
        assert fetched is not None
        assert fetched.id == "wf-1"
        assert fetched.name == "Test Workflow"

        # Test Update
        updated_data = {"id": "wf-1", "name": "Updated Workflow"}
        repo.update("wf-1", updated_data)
        fetched_updated = repo.get_by_id("wf-1")
        assert fetched_updated.name == "Updated Workflow"
        assert getattr(fetched_updated, "id") == "wf-1"

        # Test partial update preserves existing fields
        repo.update("wf-1", {"description": "Keeps existing name"})
        fetched_partial = repo.get_by_id("wf-1")
        assert fetched_partial.name == "Updated Workflow"
        assert getattr(fetched_partial, "description") == "Keeps existing name"

        # Test List
        all_wfs = repo.list_all()
        assert len(all_wfs) == 1

        # Test Delete
        assert repo.delete("wf-1") is True
        assert repo.get_by_id("wf-1") is None


def test_soul_repository():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = SoulRepository(base_path=tmpdir)

        soul_data = {"id": "sl-1", "name": "Test Soul"}
        entity = repo.create(soul_data)
        assert entity.id == "sl-1"
        assert entity.name == "Test Soul"

        fetched = repo.get_by_id("sl-1")
        assert fetched is not None
        assert fetched.name == "Test Soul"

        updated_data = {"id": "sl-1", "name": "Updated Soul"}
        repo.update("sl-1", updated_data)
        assert repo.get_by_id("sl-1").name == "Updated Soul"

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
