"""
Red tests for RUN-232: FileSystemProviderRepo — YAML-backed provider storage.

Tests the public API of FileSystemProviderRepo:
  list_all, get_by_id, get_by_type, create, update, delete

All tests should FAIL (ImportError) until the implementation is written.

Acceptance criteria covered:
  - FileSystemProviderRepo implements all CRUD methods
  - Provider ID is filename stem (no ID stored inside YAML)
  - Path traversal protection rejects ../ in provider IDs
  - Atomic writes via temp file + rename
  - list_all skips malformed YAML files with logged warning
  - custom/providers/ directory auto-created on repo init
  - Unit tests for CRUD, path traversal rejection, malformed file handling
  - Two providers with same name: create raises ValueError
"""

import logging
import os

import pytest
import yaml

from runsight_api.data.filesystem.provider_repo import FileSystemProviderRepo
from runsight_api.domain.errors import ProviderNotFound
from runsight_api.domain.value_objects import ProviderEntity

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_PROVIDER_DATA = {
    "name": "OpenAI",
    "type": "openai",
    "api_key": "${OPENAI_API_KEY}",
    "base_url": "https://api.openai.com/v1",
    "is_active": True,
    "status": "connected",
    "models": ["gpt-4o", "gpt-4o-mini"],
}


def _make_provider_data(**overrides):
    """Return a valid provider data dict with optional overrides."""
    data = dict(VALID_PROVIDER_DATA)
    data.update(overrides)
    return data


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def repo(tmp_path):
    """Create a FileSystemProviderRepo rooted at a temporary directory."""
    return FileSystemProviderRepo(base_path=str(tmp_path))


@pytest.fixture
def providers_dir(tmp_path):
    """Return the expected providers directory path."""
    return tmp_path / "custom" / "providers"


# ===========================================================================
# AC: custom/providers/ directory auto-created on repo init
# ===========================================================================


class TestDirectoryAutoCreation:
    def test_providers_dir_created_on_init(self, tmp_path):
        """Initialising the repo must create custom/providers/ automatically."""
        providers_dir = tmp_path / "custom" / "providers"
        assert not providers_dir.exists()

        FileSystemProviderRepo(base_path=str(tmp_path))

        assert providers_dir.exists()
        assert providers_dir.is_dir()


# ===========================================================================
# AC: FileSystemProviderRepo implements all CRUD methods
# ===========================================================================


class TestCreate:
    def test_create_returns_provider_entity(self, repo):
        """create() must return a ProviderEntity."""
        entity = repo.create(_make_provider_data())
        assert isinstance(entity, ProviderEntity)

    def test_create_sets_id_from_slugified_name(self, repo):
        """Provider ID should be the slugified version of the name."""
        entity = repo.create(_make_provider_data(name="OpenAI"))
        assert entity.id == "openai"

    def test_create_writes_yaml_file(self, repo, providers_dir):
        """create() must persist a .yaml file in custom/providers/."""
        entity = repo.create(_make_provider_data(name="OpenAI"))
        yaml_path = providers_dir / f"{entity.id}.yaml"
        assert yaml_path.exists()

    def test_create_preserves_all_fields_in_yaml(self, repo, providers_dir):
        """All provider fields must be written to the YAML file."""
        data = _make_provider_data()
        entity = repo.create(data)
        yaml_path = providers_dir / f"{entity.id}.yaml"

        with open(yaml_path) as f:
            on_disk = yaml.safe_load(f)

        assert on_disk["name"] == "OpenAI"
        assert on_disk["type"] == "openai"
        assert on_disk["api_key"] == "${OPENAI_API_KEY}"
        assert on_disk["base_url"] == "https://api.openai.com/v1"
        assert on_disk["is_active"] is True
        assert on_disk["status"] == "connected"
        assert on_disk["models"] == ["gpt-4o", "gpt-4o-mini"]

    def test_create_entity_has_correct_fields(self, repo):
        """Returned entity must carry all fields from the input data."""
        entity = repo.create(_make_provider_data())
        assert entity.name == "OpenAI"
        assert entity.type == "openai"
        assert entity.is_active is True
        assert entity.status == "connected"
        assert entity.models == ["gpt-4o", "gpt-4o-mini"]

    def test_create_slugifies_name_with_special_chars(self, repo):
        """Names with special characters must produce safe filesystem slugs."""
        entity = repo.create(_make_provider_data(name="My OpenAI Provider!"))
        # Slug should be lowercase, alphanumeric + hyphens
        assert entity.id == "my-openai-provider"

    def test_create_empty_name_gets_slug(self, repo):
        """An empty name should still produce a usable slug."""
        entity = repo.create(_make_provider_data(name=""))
        assert entity.id  # must not be empty


class TestCreateDuplicates:
    """AC: Two providers with same name: create raises ValueError."""

    def test_create_duplicate_name_raises_value_error(self, repo):
        """Creating two providers with the same name must raise ValueError."""
        repo.create(_make_provider_data(name="OpenAI"))
        with pytest.raises(ValueError):
            repo.create(_make_provider_data(name="OpenAI"))

    def test_create_duplicate_slug_different_case_raises(self, repo):
        """Names that slugify to the same value must also collide."""
        repo.create(_make_provider_data(name="Open AI"))
        with pytest.raises(ValueError):
            repo.create(_make_provider_data(name="open-ai"))


class TestGetById:
    def test_get_by_id_returns_entity(self, repo):
        """get_by_id must return the previously created provider."""
        created = repo.create(_make_provider_data(name="Anthropic"))
        fetched = repo.get_by_id(created.id)
        assert fetched is not None
        assert isinstance(fetched, ProviderEntity)
        assert fetched.id == created.id
        assert fetched.name == "Anthropic"

    def test_get_by_id_returns_none_for_missing(self, repo):
        """get_by_id must return None when the provider does not exist."""
        result = repo.get_by_id("nonexistent")
        assert result is None

    def test_get_by_id_derives_id_from_filename(self, repo, providers_dir):
        """ID must come from the filename stem, not from inside the YAML."""
        # Manually write a YAML file (no id field inside)
        yaml_path = providers_dir / "my-provider.yaml"
        yaml_path.write_text(yaml.dump({"name": "My Provider", "type": "custom"}))

        entity = repo.get_by_id("my-provider")
        assert entity is not None
        assert entity.id == "my-provider"


class TestGetByType:
    def test_get_by_type_returns_matching_providers(self, repo):
        """get_by_type must return providers matching the given type."""
        repo.create(_make_provider_data(name="OpenAI Primary", type="openai"))
        repo.create(_make_provider_data(name="OpenAI Secondary", type="openai"))
        repo.create(_make_provider_data(name="Anthropic", type="anthropic"))

        results = repo.get_by_type("openai")
        assert len(results) == 2
        assert all(p.type == "openai" for p in results)

    def test_get_by_type_returns_empty_list_for_no_match(self, repo):
        """get_by_type must return an empty list when no providers match."""
        repo.create(_make_provider_data(name="OpenAI", type="openai"))
        results = repo.get_by_type("anthropic")
        assert results == []

    def test_get_by_type_returns_only_providers_of_type(self, repo):
        """get_by_type must not return providers of other types."""
        repo.create(_make_provider_data(name="OpenAI", type="openai"))
        repo.create(_make_provider_data(name="Anthropic", type="anthropic"))

        results = repo.get_by_type("anthropic")
        assert len(results) == 1
        assert results[0].name == "Anthropic"


class TestListAll:
    def test_list_all_returns_empty_for_empty_dir(self, repo):
        """list_all must return an empty list when no providers exist."""
        assert repo.list_all() == []

    def test_list_all_returns_all_providers(self, repo):
        """list_all must return every provider in the directory."""
        repo.create(_make_provider_data(name="OpenAI", type="openai"))
        repo.create(_make_provider_data(name="Anthropic", type="anthropic"))
        repo.create(_make_provider_data(name="Google", type="google"))

        result = repo.list_all()
        assert len(result) == 3
        names = {p.name for p in result}
        assert names == {"OpenAI", "Anthropic", "Google"}

    def test_list_all_returns_provider_entities(self, repo):
        """Each item from list_all must be a ProviderEntity."""
        repo.create(_make_provider_data(name="OpenAI"))
        result = repo.list_all()
        assert all(isinstance(p, ProviderEntity) for p in result)

    def test_list_all_includes_hand_authored_files(self, repo, providers_dir):
        """Hand-authored YAML files (without id) must be picked up by list_all."""
        yaml_path = providers_dir / "manual-provider.yaml"
        yaml_path.write_text(yaml.dump({"name": "Manual", "type": "custom"}))

        result = repo.list_all()
        assert len(result) == 1
        assert result[0].id == "manual-provider"
        assert result[0].name == "Manual"


class TestUpdate:
    def test_update_modifies_existing_provider(self, repo):
        """update() must modify the provider data on disk."""
        created = repo.create(_make_provider_data(name="OpenAI"))
        updated = repo.update(created.id, {"status": "error", "is_active": False})

        assert updated.status == "error"
        assert updated.is_active is False
        # Original fields are preserved
        assert updated.name == "OpenAI"

    def test_update_returns_provider_entity(self, repo):
        """update() must return a ProviderEntity."""
        created = repo.create(_make_provider_data(name="OpenAI"))
        updated = repo.update(created.id, {"status": "offline"})
        assert isinstance(updated, ProviderEntity)

    def test_update_nonexistent_raises_provider_not_found(self, repo):
        """update() on a missing provider must raise ProviderNotFound."""
        with pytest.raises(ProviderNotFound):
            repo.update("nonexistent", {"status": "error"})

    def test_update_preserves_id_from_filename(self, repo):
        """After update, the entity ID must still match the filename stem."""
        created = repo.create(_make_provider_data(name="OpenAI"))
        updated = repo.update(created.id, {"status": "offline"})
        assert updated.id == created.id


class TestDelete:
    def test_delete_removes_yaml_file(self, repo, providers_dir):
        """delete() must remove the YAML file from disk."""
        created = repo.create(_make_provider_data(name="OpenAI"))
        yaml_path = providers_dir / f"{created.id}.yaml"
        assert yaml_path.exists()

        result = repo.delete(created.id)
        assert result is True
        assert not yaml_path.exists()

    def test_delete_returns_true_when_exists(self, repo):
        """delete() must return True when the file was actually deleted."""
        created = repo.create(_make_provider_data(name="OpenAI"))
        assert repo.delete(created.id) is True

    def test_delete_returns_false_when_missing(self, repo):
        """delete() must return False when the provider does not exist."""
        assert repo.delete("nonexistent") is False

    def test_delete_makes_get_by_id_return_none(self, repo):
        """After deletion, get_by_id must return None."""
        created = repo.create(_make_provider_data(name="OpenAI"))
        repo.delete(created.id)
        assert repo.get_by_id(created.id) is None


# ===========================================================================
# AC: Provider ID is filename stem (no ID stored inside YAML)
# ===========================================================================


class TestIdNotStoredInYaml:
    def test_id_not_written_to_yaml_file(self, repo, providers_dir):
        """ADR D3: The 'id' field must NOT be stored inside the YAML file."""
        entity = repo.create(_make_provider_data(name="OpenAI"))
        yaml_path = providers_dir / f"{entity.id}.yaml"

        with open(yaml_path) as f:
            on_disk = yaml.safe_load(f)

        assert "id" not in on_disk, "id field must not be stored in YAML file"

    def test_id_derived_from_filename_on_read(self, repo, providers_dir):
        """When reading back, the ID must be inferred from the filename stem."""
        # Write a file with no id field
        (providers_dir / "test-provider.yaml").write_text(
            yaml.dump({"name": "Test", "type": "custom"})
        )
        entity = repo.get_by_id("test-provider")
        assert entity.id == "test-provider"


# ===========================================================================
# AC: Path traversal protection rejects ../ in provider IDs
# ===========================================================================


class TestPathTraversalProtection:
    MALICIOUS_IDS = [
        "../etc/passwd",
        "../../etc/shadow",
        "foo/../../../etc/passwd",
        "..",
        "../",
        "..\\",
        "foo/bar",
        "foo\\bar",
        "/etc/passwd",
        "%2e%2e%2fetc%2fpasswd",
    ]

    @pytest.mark.parametrize("malicious_id", MALICIOUS_IDS)
    def test_get_by_id_rejects_traversal(self, repo, malicious_id):
        with pytest.raises(ValueError, match="[Pp]ath|[Ii]nvalid|[Tt]raversal"):
            repo.get_by_id(malicious_id)

    @pytest.mark.parametrize("malicious_id", MALICIOUS_IDS)
    def test_update_rejects_traversal(self, repo, malicious_id):
        with pytest.raises(ValueError, match="[Pp]ath|[Ii]nvalid|[Tt]raversal"):
            repo.update(malicious_id, {"status": "error"})

    @pytest.mark.parametrize("malicious_id", MALICIOUS_IDS)
    def test_delete_rejects_traversal(self, repo, malicious_id):
        with pytest.raises(ValueError, match="[Pp]ath|[Ii]nvalid|[Tt]raversal"):
            repo.delete(malicious_id)

    def test_normal_id_accepted(self, repo):
        """Safe IDs must not trigger path traversal errors."""
        # Should not raise — provider just doesn't exist
        result = repo.get_by_id("totally-safe-id")
        assert result is None


# ===========================================================================
# AC: Atomic writes via temp file + rename
# ===========================================================================


class TestAtomicWrites:
    def test_create_uses_atomic_write(self, repo, providers_dir, monkeypatch):
        """create() must write via temp file + os.rename, not direct write."""
        renames = []
        original_rename = os.rename

        def tracking_rename(src, dst):
            renames.append((src, dst))
            return original_rename(src, dst)

        monkeypatch.setattr(os, "rename", tracking_rename)

        repo.create(_make_provider_data(name="Atomic Test"))

        # At least one rename must have happened targeting the providers dir
        assert len(renames) >= 1, "No os.rename calls detected — write is not atomic"
        dst_paths = [dst for _, dst in renames]
        assert any(str(providers_dir) in str(p) for p in dst_paths), (
            f"Rename destination not in providers dir: {dst_paths}"
        )

    def test_update_uses_atomic_write(self, repo, providers_dir, monkeypatch):
        """update() must also use atomic writes."""
        created = repo.create(_make_provider_data(name="Atomic Update"))

        renames = []
        original_rename = os.rename

        def tracking_rename(src, dst):
            renames.append((src, dst))
            return original_rename(src, dst)

        monkeypatch.setattr(os, "rename", tracking_rename)

        repo.update(created.id, {"status": "offline"})

        assert len(renames) >= 1, "No os.rename calls detected — write is not atomic"


# ===========================================================================
# AC: list_all skips malformed YAML files with logged warning
# ===========================================================================


class TestMalformedYamlHandling:
    def test_list_all_skips_malformed_files(self, repo, providers_dir):
        """list_all must skip files that contain invalid YAML."""
        # Write a valid provider
        repo.create(_make_provider_data(name="Good Provider"))

        # Write a malformed YAML file
        malformed_path = providers_dir / "bad-provider.yaml"
        malformed_path.write_text(":\n  - :\n    invalid: [yaml{{{")

        result = repo.list_all()
        # Only the valid provider should be returned
        assert len(result) == 1
        assert result[0].name == "Good Provider"

    def test_list_all_logs_warning_for_malformed_files(self, repo, providers_dir, caplog):
        """list_all must log a warning when it skips a malformed file."""
        malformed_path = providers_dir / "broken.yaml"
        malformed_path.write_text("not: valid: yaml: {{{}}")

        with caplog.at_level(logging.WARNING):
            repo.list_all()

        assert any(
            "broken" in record.message.lower() or "failed" in record.message.lower()
            for record in caplog.records
        ), f"Expected warning about malformed file, got: {[r.message for r in caplog.records]}"

    def test_list_all_skips_non_yaml_files(self, repo, providers_dir):
        """list_all must ignore non-.yaml files in the directory."""
        repo.create(_make_provider_data(name="Good Provider"))

        # Write some non-YAML files
        (providers_dir / "readme.txt").write_text("not a provider")
        (providers_dir / ".DS_Store").write_text("macOS junk")

        result = repo.list_all()
        assert len(result) == 1


# ===========================================================================
# AC: YAML schema matches epic spec
# ===========================================================================


class TestYamlSchema:
    def test_yaml_matches_epic_schema(self, repo, providers_dir):
        """The on-disk YAML must match the schema from the epic."""
        data = _make_provider_data()
        entity = repo.create(data)
        yaml_path = providers_dir / f"{entity.id}.yaml"

        with open(yaml_path) as f:
            on_disk = yaml.safe_load(f)

        # All epic-defined fields must be present
        assert "name" in on_disk
        assert "type" in on_disk
        assert "api_key" in on_disk
        assert "base_url" in on_disk
        assert "is_active" in on_disk
        assert "status" in on_disk
        assert "models" in on_disk

        # id must NOT be in YAML (ADR D3)
        assert "id" not in on_disk


# ===========================================================================
# Edge case: round-trip fidelity
# ===========================================================================


class TestRoundTrip:
    def test_create_then_get_preserves_data(self, repo):
        """Data must survive a create -> get_by_id round trip."""
        data = _make_provider_data(name="Round Trip Provider")
        created = repo.create(data)
        fetched = repo.get_by_id(created.id)

        assert fetched.name == "Round Trip Provider"
        assert fetched.type == "openai"
        assert fetched.api_key == "${OPENAI_API_KEY}"
        assert fetched.base_url == "https://api.openai.com/v1"
        assert fetched.is_active is True
        assert fetched.status == "connected"
        assert fetched.models == ["gpt-4o", "gpt-4o-mini"]

    def test_update_then_get_reflects_changes(self, repo):
        """Changes from update() must be visible in a subsequent get_by_id()."""
        created = repo.create(_make_provider_data(name="Updatable"))
        repo.update(created.id, {"status": "error", "models": ["gpt-4o-mini"]})

        fetched = repo.get_by_id(created.id)
        assert fetched.status == "error"
        assert fetched.models == ["gpt-4o-mini"]
        # Unchanged fields are preserved
        assert fetched.name == "Updatable"
        assert fetched.type == "openai"
