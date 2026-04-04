import tempfile

import pytest

from runsight_api.data.filesystem.task_repo import TaskRepository
from runsight_api.domain.errors import TaskNotFound


def test_task_repo():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = TaskRepository(base_path=tmpdir)
        assert not hasattr(repo, "tasks_dir")

        # Test create
        created = repo.create({"id": "test_task", "name": "Test Task"})
        assert created.id == "test_task"

        # Test get
        fetched = repo.get_by_id("test_task")
        assert fetched.name == "Test Task"

        # Test update
        repo.update("test_task", {"name": "Updated Task"})
        updated = repo.get_by_id("test_task")
        assert updated.name == "Updated Task"

        # Test delete
        repo.delete("test_task")
        assert repo.get_by_id("test_task") is None

        # Test not found
        with pytest.raises(TaskNotFound):
            repo.update("missing", {"name": "Does not exist"})
