import pytest
import tempfile
from runsight_api.data.filesystem.soul_repo import SoulRepository
from runsight_api.domain.errors import SoulNotFound


def test_soul_repo():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = SoulRepository(base_path=tmpdir)

        # Test create
        created = repo.create({"id": "test_soul", "name": "Test Soul"})
        assert created.id == "test_soul"

        # Test get
        fetched = repo.get_by_id("test_soul")
        assert fetched.name == "Test Soul"

        # Test update
        repo.update("test_soul", {"name": "Updated Soul"})
        updated = repo.get_by_id("test_soul")
        assert updated.name == "Updated Soul"

        # Test delete
        repo.delete("test_soul")
        assert repo.get_by_id("test_soul") is None

        # Test not found
        with pytest.raises(SoulNotFound):
            repo.update("missing", {"name": "Does not exist"})
