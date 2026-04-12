import tempfile

import pytest
import yaml
from pydantic import ValidationError

from runsight_api.data.filesystem.soul_repo import SoulRepository
from runsight_api.domain.errors import SoulNotFound


def test_soul_repo():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = SoulRepository(base_path=tmpdir)

        assert repo.entity_dir.name == "souls"
        assert repo.entity_dir.parent.name == "custom"
        assert not hasattr(repo, "souls_dir")

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


def test_soul_repo_create_rejects_unknown_fields_and_does_not_persist():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = SoulRepository(base_path=tmpdir)
        soul_path = repo.entity_dir / "strict_soul.yaml"

        with pytest.raises(ValidationError):
            repo.create(
                {
                    "id": "strict_soul",
                    "role": "Strict Soul",
                    "system_prompt": "Prompt",
                    "custom_notes": "unsupported",
                }
            )

        assert not soul_path.exists()


def test_soul_repo_update_rejects_unknown_fields_and_keeps_existing_yaml():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = SoulRepository(base_path=tmpdir)
        repo.create(
            {
                "id": "strict_soul",
                "role": "Strict Soul",
                "system_prompt": "Prompt",
            }
        )

        with pytest.raises(ValidationError):
            repo.update(
                "strict_soul",
                {
                    "role": "Updated",
                    "system_prompt": "Updated prompt",
                    "custom_notes": "unsupported",
                },
            )

        with open(repo.entity_dir / "strict_soul.yaml", "r") as f:
            on_disk = yaml.safe_load(f)
        assert on_disk == {
            "id": "strict_soul",
            "role": "Strict Soul",
            "system_prompt": "Prompt",
        }


def test_soul_repo_get_by_id_rejects_unsupported_yaml_fields():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = SoulRepository(base_path=tmpdir)
        legacy_path = repo.entity_dir / "legacy.yaml"
        legacy_path.write_text(
            yaml.safe_dump(
                {
                    "id": "legacy",
                    "role": "Legacy Soul",
                    "system_prompt": "Prompt",
                    "assertions": [{"type": "contains", "value": "x"}],
                },
                sort_keys=False,
            )
        )

        with pytest.raises(ValidationError):
            repo.get_by_id("legacy")


def test_soul_repo_resolves_embedded_id_when_filename_differs():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = SoulRepository(base_path=tmpdir)
        legacy_path = repo.entity_dir / "gate_evaluator.yaml"
        legacy_path.write_text(
            yaml.safe_dump(
                {
                    "id": "gate_eval_1",
                    "role": "Quality Gate Evaluator",
                    "system_prompt": "Check quality",
                },
                sort_keys=False,
            )
        )

        fetched = repo.get_by_id("gate_eval_1")
        assert fetched is not None
        assert fetched.id == "gate_eval_1"
        assert fetched.role == "Quality Gate Evaluator"

        updated = repo.update(
            "gate_eval_1",
            {
                "role": "Updated Gate",
                "system_prompt": "Updated prompt",
            },
        )
        assert updated.id == "gate_eval_1"
        assert updated.role == "Updated Gate"
        assert legacy_path.exists()
        assert not (repo.entity_dir / "gate_eval_1.yaml").exists()

        with open(legacy_path, "r") as f:
            on_disk = yaml.safe_load(f)
        assert on_disk["id"] == "gate_eval_1"
        assert on_disk["role"] == "Updated Gate"

        assert repo.delete("gate_eval_1") is True
        assert not legacy_path.exists()
