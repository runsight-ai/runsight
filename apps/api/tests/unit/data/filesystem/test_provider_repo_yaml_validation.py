"""FileSystemProviderRepo validates YAML schema and malformed provider files."""

import logging

import pytest
import yaml
from pydantic import ValidationError

from tests.unit.data.filesystem.provider_repo_builders import (
    _ensure_providers_dir,
    _make_provider_data,
)

pytest_plugins = ("tests.unit.data.filesystem.provider_repo_fixtures",)


class TestReadValidation:
    def test_get_by_id_rejects_provider_yaml_with_unsupported_fields(self, repo, providers_dir):
        _ensure_providers_dir(providers_dir)
        yaml_path = providers_dir / "fixture-provider.yaml"
        yaml_path.write_text(
            yaml.safe_dump(
                {
                    "id": "fixture-provider",
                    "kind": "provider",
                    "name": "Fixture Provider",
                    "type": "fixture-provider",
                    "api_key": "${DUMMY_PROVIDER_KEY}",
                    "custom_notes": "unsupported",
                }
            )
        )

        assert repo.get_by_id("fixture-provider") is None

    def test_list_all_rejects_provider_yaml_with_unsupported_fields(self, repo, providers_dir):
        _ensure_providers_dir(providers_dir)
        yaml_path = providers_dir / "fixture-provider.yaml"
        yaml_path.write_text(
            yaml.safe_dump(
                {
                    "id": "fixture-provider",
                    "kind": "provider",
                    "name": "Fixture Provider",
                    "type": "fixture-provider",
                    "api_key": "${DUMMY_PROVIDER_KEY}",
                    "custom_notes": "unsupported",
                }
            )
        )

        with pytest.raises(ValidationError):
            repo.list_all()


class TestDelete:
    def test_delete_removes_yaml_file(self, repo, providers_dir):
        """delete() must remove the YAML file from disk."""
        created = repo.create(_make_provider_data(name="Fixture Provider"))
        yaml_path = providers_dir / f"{created.id}.yaml"
        assert yaml_path.exists()

        result = repo.delete(created.id)
        assert result is True
        assert not yaml_path.exists()

    def test_delete_returns_true_when_exists(self, repo):
        """delete() must return True when the file was actually deleted."""
        created = repo.create(_make_provider_data(name="Fixture Provider"))
        assert repo.delete(created.id) is True

    def test_delete_returns_false_when_missing(self, repo):
        """delete() must return False when the provider does not exist."""
        assert repo.delete("nonexistent") is False

    def test_delete_makes_get_by_id_return_none(self, repo):
        """After deletion, get_by_id must return None."""
        created = repo.create(_make_provider_data(name="Fixture Provider"))
        repo.delete(created.id)
        assert repo.get_by_id(created.id) is None


# ===========================================================================
# Provider ID is embedded in YAML and matches the filename stem
# ===========================================================================


class TestEmbeddedIdMatchesFilename:
    def test_id_is_written_to_yaml_file(self, repo, providers_dir):
        """The 'id' field is embedded in the YAML file and must match the filename stem."""
        entity = repo.create(_make_provider_data(name="Fixture Provider"))
        yaml_path = providers_dir / f"{entity.id}.yaml"

        with open(yaml_path) as f:
            on_disk = yaml.safe_load(f)

        assert "id" in on_disk, "id field must be stored in YAML file"
        assert on_disk["id"] == entity.id, "stored id must match the filename stem"

    def test_id_derived_from_filename_on_read(self, repo, providers_dir):
        """When reading back, the ID must match the embedded id field in the YAML."""
        # Write a file with the id field matching the filename stem
        _ensure_providers_dir(providers_dir)
        (providers_dir / "test-provider.yaml").write_text(
            yaml.dump({"id": "test-provider", "kind": "provider", "name": "Test", "type": "custom"})
        )
        entity = repo.get_by_id("test-provider")
        assert entity.id == "test-provider"


# ===========================================================================
# Path traversal protection rejects ../ in provider IDs
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
        _ensure_providers_dir(providers_dir)
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
        _ensure_providers_dir(providers_dir)
        (providers_dir / "readme.txt").write_text("not a provider")
        (providers_dir / ".DS_Store").write_text("macOS junk")

        result = repo.list_all()
        assert len(result) == 1


# ===========================================================================
# YAML schema matches the FileSystemProviderRepo contract
# ===========================================================================


class TestYamlSchema:
    def test_yaml_matches_provider_repo_schema(self, repo, providers_dir):
        """The on-disk YAML must match the provider repository schema."""
        data = _make_provider_data()
        entity = repo.create(data)
        yaml_path = providers_dir / f"{entity.id}.yaml"

        with open(yaml_path) as f:
            on_disk = yaml.safe_load(f)

        # All provider repository fields must be present.
        assert "name" in on_disk
        assert "type" in on_disk
        assert "api_key" in on_disk
        assert "base_url" in on_disk
        assert "is_active" in on_disk
        assert "status" in on_disk
        assert "models" in on_disk

        # id must be embedded in YAML and match the filename stem
        assert "id" in on_disk
        assert on_disk["id"] == entity.id


# ===========================================================================
# Edge case: round-trip fidelity
# ===========================================================================
