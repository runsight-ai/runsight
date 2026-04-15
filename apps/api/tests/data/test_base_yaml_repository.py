"""Tests for BaseYamlRepository generic base class."""

import tempfile
from typing import Optional

import pytest
import yaml
from pydantic import BaseModel, ValidationError

from runsight_api.data.filesystem._base_yaml_repo import BaseYamlRepository
from runsight_api.data.filesystem.step_repo import StepRepository
from runsight_api.domain.errors import RunsightError

# -- Fixtures: a minimal entity and concrete repo for testing ----------------


class DummyEntity(BaseModel):
    id: str
    name: Optional[str] = None
    model_config = {"extra": "allow"}


class DummyNotFound(RunsightError):
    pass


class DummyRepository(BaseYamlRepository[DummyEntity]):
    entity_type = DummyEntity
    subdir = "dummies"
    not_found_error = DummyNotFound
    entity_label = "Dummy"


class StrictDummyEntity(BaseModel):
    id: str
    name: Optional[str] = None
    model_config = {"extra": "forbid"}


class StrictDummyRepository(BaseYamlRepository[StrictDummyEntity]):
    entity_type = StrictDummyEntity
    subdir = "strict-dummies"
    not_found_error = DummyNotFound
    entity_label = "StrictDummy"


# -- Tests -------------------------------------------------------------------


class TestBaseYamlRepositoryInstantiation:
    """BaseYamlRepository can be instantiated with a type parameter."""

    def test_instantiation_creates_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = DummyRepository(base_path=tmpdir)
            assert repo.entity_dir.exists()
            assert repo.entity_dir.name == "dummies"

    def test_instantiation_sets_base_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = DummyRepository(base_path=tmpdir)
            assert str(repo.base_path) == tmpdir


class TestListAll:
    """list_all returns all entities from YAML files."""

    def test_list_all_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = DummyRepository(base_path=tmpdir)
            assert repo.list_all() == []

    def test_list_all_returns_all_entities(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = DummyRepository(base_path=tmpdir)
            repo.create({"id": "d1", "name": "First"})
            repo.create({"id": "d2", "name": "Second"})
            results = repo.list_all()
            assert len(results) == 2
            ids = {e.id for e in results}
            assert ids == {"d1", "d2"}

    def test_list_all_injects_id_from_filename(self):
        """If the YAML file lacks an 'id' field, list_all uses the filename stem."""
        import yaml

        with tempfile.TemporaryDirectory() as tmpdir:
            repo = DummyRepository(base_path=tmpdir)
            # Write a YAML file without an 'id' key
            file_path = repo.entity_dir / "auto-id.yaml"
            with open(file_path, "w") as f:
                yaml.safe_dump({"name": "No ID"}, f)
            results = repo.list_all()
            assert len(results) == 1
            assert results[0].id == "auto-id"


class TestGetById:
    """get_by_id returns single entity."""

    def test_get_by_id_returns_entity(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = DummyRepository(base_path=tmpdir)
            repo.create({"id": "d1", "name": "Test"})
            entity = repo.get_by_id("d1")
            assert entity is not None
            assert entity.id == "d1"
            assert entity.name == "Test"

    def test_get_by_id_returns_none_for_missing(self):
        """get_by_id returns None for non-existent ID."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = DummyRepository(base_path=tmpdir)
            assert repo.get_by_id("nonexistent") is None

    def test_get_by_id_injects_id_from_filename(self):
        """If YAML lacks 'id', get_by_id uses the requested id."""
        import yaml

        with tempfile.TemporaryDirectory() as tmpdir:
            repo = DummyRepository(base_path=tmpdir)
            file_path = repo.entity_dir / "auto-id.yaml"
            with open(file_path, "w") as f:
                yaml.safe_dump({"name": "No ID"}, f)
            entity = repo.get_by_id("auto-id")
            assert entity.id == "auto-id"


class TestCreate:
    """create writes YAML file."""

    def test_create_writes_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = DummyRepository(base_path=tmpdir)
            entity = repo.create({"id": "d1", "name": "Created"})
            assert entity.id == "d1"
            assert entity.name == "Created"
            # Verify file exists on disk
            assert (repo.entity_dir / "d1.yaml").exists()

    def test_create_without_id_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = DummyRepository(base_path=tmpdir)
            with pytest.raises(ValueError, match="must have an id"):
                repo.create({"name": "No ID"})

    def test_create_preserves_extra_fields(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = DummyRepository(base_path=tmpdir)
            entity = repo.create({"id": "d1", "name": "Test", "extra_field": "value"})
            assert entity.id == "d1"
            # Verify round-trip via get_by_id
            fetched = repo.get_by_id("d1")
            assert fetched.extra_field == "value"


class TestUpdate:
    """update modifies YAML file."""

    def test_update_modifies_entity(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = DummyRepository(base_path=tmpdir)
            repo.create({"id": "d1", "name": "Original"})
            updated = repo.update("d1", {"name": "Updated"})
            assert updated.name == "Updated"
            assert updated.id == "d1"

    def test_update_nonexistent_raises_not_found(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = DummyRepository(base_path=tmpdir)
            with pytest.raises(DummyNotFound):
                repo.update("missing", {"name": "Nope"})


class TestStrictEntityWriteValidation:
    def test_create_rejects_unknown_fields_without_writing_yaml(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = StrictDummyRepository(base_path=tmpdir)
            file_path = repo.entity_dir / "d1.yaml"
            with pytest.raises(ValidationError):
                repo.create({"id": "d1", "name": "Test", "unsupported": "x"})
            assert not file_path.exists()

    def test_update_rejects_unknown_fields_without_mutating_yaml(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = StrictDummyRepository(base_path=tmpdir)
            repo.create({"id": "d1", "name": "Original"})

            with pytest.raises(ValidationError):
                repo.update("d1", {"name": "Updated", "unsupported": "x"})

            with open(repo.entity_dir / "d1.yaml", "r") as f:
                on_disk = yaml.safe_load(f)
            assert on_disk == {"id": "d1", "name": "Original"}


class TestTaskAndStepRepoStrictness:
    def test_step_repo_create_rejects_unknown_fields_and_does_not_persist(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = StepRepository(base_path=tmpdir)
            file_path = repo.entity_dir / "step-1.yaml"
            with pytest.raises(ValidationError):
                repo.create({"id": "step-1", "name": "Step", "unsupported": "x"})
            assert not file_path.exists()

    def test_step_repo_update_rejects_unknown_fields_and_keeps_original_yaml(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = StepRepository(base_path=tmpdir)
            repo.create({"id": "step-1", "name": "Step"})
            with pytest.raises(ValidationError):
                repo.update("step-1", {"name": "Updated", "unsupported": "x"})
            with open(repo.entity_dir / "step-1.yaml", "r") as f:
                on_disk = yaml.safe_load(f)
            assert on_disk == {"id": "step-1", "name": "Step"}

    def test_step_repo_get_by_id_rejects_unknown_fields_in_authored_yaml(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = StepRepository(base_path=tmpdir)
            step_path = repo.entity_dir / "step-1.yaml"
            step_path.write_text(
                yaml.safe_dump(
                    {
                        "id": "step-1",
                        "name": "Step",
                        "custom_notes": "unsupported",
                    },
                    sort_keys=False,
                )
            )

            with pytest.raises(ValidationError):
                repo.get_by_id("step-1")

    def test_step_repo_list_all_rejects_unknown_fields_in_authored_yaml(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = StepRepository(base_path=tmpdir)
            step_path = repo.entity_dir / "step-1.yaml"
            step_path.write_text(
                yaml.safe_dump(
                    {
                        "id": "step-1",
                        "name": "Step",
                        "unsupported": True,
                    },
                    sort_keys=False,
                )
            )

            with pytest.raises(ValidationError):
                repo.list_all()


class TestDelete:
    """delete removes YAML file."""

    def test_delete_removes_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = DummyRepository(base_path=tmpdir)
            repo.create({"id": "d1", "name": "Delete Me"})
            assert repo.delete("d1") is True
            assert not (repo.entity_dir / "d1.yaml").exists()
            assert repo.get_by_id("d1") is None

    def test_delete_nonexistent_returns_false(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = DummyRepository(base_path=tmpdir)
            assert repo.delete("nonexistent") is False


class TestPathTraversal:
    """Path traversal in IDs is rejected."""

    def test_create_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = DummyRepository(base_path=tmpdir)
            with pytest.raises(ValueError, match="[Ii]nvalid"):
                repo.create({"id": "../secret", "name": "Evil"})

    def test_get_by_id_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = DummyRepository(base_path=tmpdir)
            with pytest.raises(ValueError, match="[Ii]nvalid"):
                repo.get_by_id("../secret")

    def test_update_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = DummyRepository(base_path=tmpdir)
            with pytest.raises(ValueError, match="[Ii]nvalid"):
                repo.update("../secret", {"name": "Evil"})

    def test_delete_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = DummyRepository(base_path=tmpdir)
            with pytest.raises(ValueError, match="[Ii]nvalid"):
                repo.delete("../secret")

    def test_rejects_slash_in_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = DummyRepository(base_path=tmpdir)
            with pytest.raises(ValueError, match="[Ii]nvalid"):
                repo.create({"id": "sub/dir", "name": "Evil"})


class TestMalformedYaml:
    """Malformed YAML files are skipped in list_all."""

    def test_malformed_yaml_skipped(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = DummyRepository(base_path=tmpdir)
            # Create a valid entity
            repo.create({"id": "good", "name": "Good"})
            # Write a malformed YAML file
            bad_file = repo.entity_dir / "bad.yaml"
            bad_file.write_text(":\n  - :\n    invalid: [unclosed")
            results = repo.list_all()
            # Only the good entity should be returned
            assert len(results) == 1
            assert results[0].id == "good"

    def test_empty_yaml_file_skipped_or_handled(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = DummyRepository(base_path=tmpdir)
            # Write an empty file (yaml.safe_load returns None)
            empty_file = repo.entity_dir / "empty.yaml"
            empty_file.write_text("")
            # Should not crash — either skip or handle gracefully
            results = repo.list_all()
            # Empty YAML -> {} after `or {}` -> entity with id from stem
            assert len(results) == 1
            assert results[0].id == "empty"
