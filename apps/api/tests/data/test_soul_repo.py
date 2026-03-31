import tempfile

import pytest

from runsight_api.data.filesystem.soul_repo import SoulRepository
from runsight_api.domain.errors import SoulNotFound


def test_soul_repo():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = SoulRepository(base_path=tmpdir)

        assert repo.souls_dir.name == "souls"
        assert repo.souls_dir.parent.name == "custom"

        # Test create
        created = repo.create(
            {
                "id": "test_soul",
                "role": "Test Soul",
                "system_prompt": "Test prompt",
                "model_name": "gpt-4o",
            }
        )
        assert created.id == "test_soul"
        assert created.role == "Test Soul"
        assert created.system_prompt == "Test prompt"
        assert created.model_name == "gpt-4o"

        # Test get
        fetched = repo.get_by_id("test_soul")
        assert fetched.role == "Test Soul"
        assert fetched.system_prompt == "Test prompt"
        assert fetched.model_name == "gpt-4o"

        # Test update
        repo.update(
            "test_soul",
            {
                "role": "Updated Soul",
                "system_prompt": "Updated prompt",
                "model_name": "claude-sonnet",
            },
        )
        updated = repo.get_by_id("test_soul")
        assert updated.role == "Updated Soul"
        assert updated.system_prompt == "Updated prompt"
        assert updated.model_name == "claude-sonnet"

        # Test delete
        repo.delete("test_soul")
        assert repo.get_by_id("test_soul") is None

        # Test not found
        with pytest.raises(SoulNotFound):
            repo.update("missing", {"role": "Does not exist"})
