import tempfile

import pytest

from runsight_api.data.filesystem.step_repo import StepRepository
from runsight_api.domain.errors import StepNotFound


def test_step_repo():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = StepRepository(base_path=tmpdir)
        assert not hasattr(repo, "steps_dir")

        # Test create
        created = repo.create({"id": "test_step", "name": "Test Step"})
        assert created.id == "test_step"

        # Test get
        fetched = repo.get_by_id("test_step")
        assert fetched.name == "Test Step"

        # Test update
        repo.update("test_step", {"name": "Updated Step"})
        updated = repo.get_by_id("test_step")
        assert updated.name == "Updated Step"

        # Test delete
        repo.delete("test_step")
        assert repo.get_by_id("test_step") is None

        # Test not found
        with pytest.raises(StepNotFound):
            repo.update("missing", {"name": "Does not exist"})
