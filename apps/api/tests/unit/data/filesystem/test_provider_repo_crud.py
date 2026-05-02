"""FileSystemProviderRepo lazily creates storage and supports provider CRUD."""

import pytest
import yaml
from pydantic import ValidationError

from runsight_api.data.filesystem.provider_repo import FileSystemProviderRepo
from runsight_api.domain.errors import ProviderNotFound
from runsight_api.domain.value_objects import ProviderEntity
from tests.unit.data.filesystem.provider_repo_builders import (
    _ensure_providers_dir,
    _make_provider_data,
)

pytest_plugins = ("tests.unit.data.filesystem.provider_repo_fixtures",)


class TestDirectoryCreationContract:
    def test_repo_init_does_not_create_providers_dir(self, tmp_path):
        """Blank-workspace startup must not create custom/providers/ just by wiring the repo."""
        providers_dir = tmp_path / "custom" / "providers"
        assert not providers_dir.exists()

        FileSystemProviderRepo(base_path=str(tmp_path))

        assert not providers_dir.exists()

    def test_create_lazily_creates_providers_dir(self, tmp_path):
        """Provider persistence must still work when custom/providers/ is absent at init time."""
        providers_dir = tmp_path / "custom" / "providers"
        repo = FileSystemProviderRepo(base_path=str(tmp_path))

        entity = repo.create(_make_provider_data(name="Fixture Provider"))

        assert providers_dir.exists()
        assert providers_dir.is_dir()
        assert (providers_dir / f"{entity.id}.yaml").exists()


# ===========================================================================
# FileSystemProviderRepo implements all CRUD methods
# ===========================================================================


class TestCreate:
    def test_create_returns_provider_entity(self, repo):
        """create() must return a ProviderEntity."""
        entity = repo.create(_make_provider_data())
        assert isinstance(entity, ProviderEntity)

    def test_create_sets_id_from_slugified_name(self, repo):
        """Provider ID should be the slugified version of the name."""
        entity = repo.create(_make_provider_data(name="Fixture Provider"))
        assert entity.id == "fixture-provider"

    def test_create_writes_yaml_file(self, repo, providers_dir):
        """create() must persist a .yaml file in custom/providers/."""
        entity = repo.create(_make_provider_data(name="Fixture Provider"))
        yaml_path = providers_dir / f"{entity.id}.yaml"
        assert yaml_path.exists()

    def test_create_preserves_all_fields_in_yaml(self, repo, providers_dir):
        """All provider fields must be written to the YAML file."""
        data = _make_provider_data()
        entity = repo.create(data)
        yaml_path = providers_dir / f"{entity.id}.yaml"

        with open(yaml_path) as f:
            on_disk = yaml.safe_load(f)

        assert on_disk["name"] == "Fixture Provider"
        assert on_disk["type"] == "fixture-provider"
        assert on_disk["api_key"] == "${DUMMY_PROVIDER_KEY}"
        assert on_disk["base_url"] == "http://localhost/fixture-provider/v1"
        assert on_disk["is_active"] is True
        assert on_disk["status"] == "connected"
        assert on_disk["models"] == ["fixture-chat-model", "fixture-small-model"]

    def test_create_entity_has_correct_fields(self, repo):
        """Returned entity must carry all fields from the input data."""
        entity = repo.create(_make_provider_data())
        assert entity.name == "Fixture Provider"
        assert entity.type == "fixture-provider"
        assert entity.is_active is True
        assert entity.status == "connected"
        assert entity.models == ["fixture-chat-model", "fixture-small-model"]

    def test_create_slugifies_name_with_special_chars(self, repo):
        """Names with special characters must produce safe filesystem slugs."""
        entity = repo.create(_make_provider_data(name="My Fixture Provider!"))
        # Slug should be lowercase, alphanumeric + hyphens
        assert entity.id == "my-fixture-provider"

    def test_create_empty_name_gets_slug(self, repo):
        """An empty name should still produce a usable slug."""
        entity = repo.create(_make_provider_data(name=""))
        assert entity.id  # must not be empty

    def test_create_rejects_unknown_fields_and_does_not_persist_yaml(self, repo, providers_dir):
        data = _make_provider_data(custom_notes="unsupported")

        with pytest.raises(ValidationError):
            repo.create(data)

        assert not (providers_dir / "fixture-provider.yaml").exists()


class TestCreateDuplicates:
    """Two providers with the same name cannot be created."""

    def test_create_duplicate_name_raises_value_error(self, repo):
        """Creating two providers with the same name must raise ValueError."""
        repo.create(_make_provider_data(name="Fixture Provider"))
        with pytest.raises(ValueError):
            repo.create(_make_provider_data(name="Fixture Provider"))

    def test_create_duplicate_slug_different_case_raises(self, repo):
        """Names that slugify to the same value must also collide."""
        repo.create(_make_provider_data(name="Duplicate Provider"))
        with pytest.raises(ValueError):
            repo.create(_make_provider_data(name="duplicate-provider"))


class TestGetById:
    def test_get_by_id_returns_entity(self, repo):
        """get_by_id must return the previously created provider."""
        created = repo.create(_make_provider_data(name="Backup Provider"))
        fetched = repo.get_by_id(created.id)
        assert fetched is not None
        assert isinstance(fetched, ProviderEntity)
        assert fetched.id == created.id
        assert fetched.name == "Backup Provider"

    def test_get_by_id_returns_none_for_missing(self, repo):
        """get_by_id must return None when the provider does not exist."""
        result = repo.get_by_id("nonexistent")
        assert result is None

    def test_get_by_id_derives_id_from_filename(self, repo, providers_dir):
        """ID must be stored in YAML and match the filename stem."""
        # Write a YAML file with the id field matching the filename stem
        _ensure_providers_dir(providers_dir)
        yaml_path = providers_dir / "my-provider.yaml"
        yaml_path.write_text(
            yaml.dump(
                {"id": "my-provider", "kind": "provider", "name": "My Provider", "type": "custom"}
            )
        )

        entity = repo.get_by_id("my-provider")
        assert entity is not None
        assert entity.id == "my-provider"


class TestGetByType:
    def test_get_by_type_returns_matching_providers(self, repo):
        """get_by_type must return providers matching the given type."""
        repo.create(_make_provider_data(name="Primary Provider", type="fixture-provider"))
        repo.create(_make_provider_data(name="Secondary Provider", type="fixture-provider"))
        repo.create(_make_provider_data(name="Backup Provider", type="backup-provider"))

        results = repo.get_by_type("fixture-provider")
        assert len(results) == 2
        assert all(p.type == "fixture-provider" for p in results)

    def test_get_by_type_returns_empty_list_for_no_match(self, repo):
        """get_by_type must return an empty list when no providers match."""
        repo.create(_make_provider_data(name="Fixture Provider", type="fixture-provider"))
        results = repo.get_by_type("backup-provider")
        assert results == []

    def test_get_by_type_returns_only_providers_of_type(self, repo):
        """get_by_type must not return providers of other types."""
        repo.create(_make_provider_data(name="Fixture Provider", type="fixture-provider"))
        repo.create(_make_provider_data(name="Backup Provider", type="backup-provider"))

        results = repo.get_by_type("backup-provider")
        assert len(results) == 1
        assert results[0].name == "Backup Provider"


class TestListAll:
    def test_list_all_returns_empty_for_empty_dir(self, repo):
        """list_all must return an empty list when no providers exist."""
        assert repo.list_all() == []

    def test_list_all_raises_for_non_directory_provider_path(self, repo, providers_dir):
        """An invalid custom/providers path must surface as a filesystem error."""
        providers_dir.parent.mkdir(parents=True, exist_ok=True)
        providers_dir.write_text("not a directory")

        with pytest.raises(NotADirectoryError, match="custom/providers"):
            repo.list_all()

    def test_list_all_returns_all_providers(self, repo):
        """list_all must return every provider in the directory."""
        repo.create(_make_provider_data(name="Fixture Provider", type="fixture-provider"))
        repo.create(_make_provider_data(name="Backup Provider", type="backup-provider"))
        repo.create(_make_provider_data(name="Auxiliary Provider", type="auxiliary-provider"))

        result = repo.list_all()
        assert len(result) == 3
        names = {p.name for p in result}
        assert names == {"Fixture Provider", "Backup Provider", "Auxiliary Provider"}

    def test_list_all_returns_provider_entities(self, repo):
        """Each item from list_all must be a ProviderEntity."""
        repo.create(_make_provider_data(name="Fixture Provider"))
        result = repo.list_all()
        assert all(isinstance(p, ProviderEntity) for p in result)

    def test_list_all_includes_hand_authored_files(self, repo, providers_dir):
        """Hand-authored YAML files with embedded id must be picked up by list_all."""
        _ensure_providers_dir(providers_dir)
        yaml_path = providers_dir / "manual-provider.yaml"
        yaml_path.write_text(
            yaml.dump(
                {"id": "manual-provider", "kind": "provider", "name": "Manual", "type": "custom"}
            )
        )

        result = repo.list_all()
        assert len(result) == 1
        assert result[0].id == "manual-provider"
        assert result[0].name == "Manual"


class TestUpdate:
    def test_update_modifies_existing_provider(self, repo):
        """update() must modify the provider data on disk."""
        created = repo.create(_make_provider_data(name="Fixture Provider"))
        updated = repo.update(
            created.id,
            {"id": created.id, "kind": "provider", "status": "error", "is_active": False},
        )

        assert updated.status == "error"
        assert updated.is_active is False
        # Original fields are preserved
        assert updated.name == "Fixture Provider"

    def test_update_returns_provider_entity(self, repo):
        """update() must return a ProviderEntity."""
        created = repo.create(_make_provider_data(name="Fixture Provider"))
        updated = repo.update(
            created.id, {"id": created.id, "kind": "provider", "status": "offline"}
        )
        assert isinstance(updated, ProviderEntity)

    def test_update_nonexistent_raises_provider_not_found(self, repo):
        """update() on a missing provider must raise ProviderNotFound."""
        with pytest.raises(ProviderNotFound):
            repo.update("nonexistent", {"status": "error"})

    def test_update_preserves_id_from_filename(self, repo):
        """After update, the entity ID must still match the filename stem."""
        created = repo.create(_make_provider_data(name="Fixture Provider"))
        updated = repo.update(
            created.id, {"id": created.id, "kind": "provider", "status": "offline"}
        )
        assert updated.id == created.id

    def test_update_rejects_unknown_fields_and_keeps_existing_yaml(self, repo, providers_dir):
        created = repo.create(_make_provider_data(name="Fixture Provider"))
        yaml_path = providers_dir / f"{created.id}.yaml"

        before = yaml.safe_load(yaml_path.read_text())
        with pytest.raises(ValidationError):
            repo.update(
                created.id,
                {"id": created.id, "kind": "provider", "custom_notes": "unsupported"},
            )
        after = yaml.safe_load(yaml_path.read_text())

        assert after == before
