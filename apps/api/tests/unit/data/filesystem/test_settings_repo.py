"""
Red tests for RUN-233: FileSystemSettingsRepo — YAML-backed app settings.

Tests the public API of FileSystemSettingsRepo:
  get_settings, update_settings, get_fallback_chain, update_fallback_chain,
  list_model_defaults, set_model_default

All tests should FAIL (ImportError) until the implementation is written.

Acceptance criteria covered:
  - Reads/writes .runsight/settings.yaml
  - Missing file returns default AppSettingsConfig() with all None/empty
  - update_settings merges partial updates correctly (shallow merge)
  - update_fallback_chain replaces the entire fallback chain list (full replacement)
  - set_model_default upserts by (provider_id, model_id) composite key
  - Atomic writes prevent corruption
  - Invalid YAML in settings file: log warning, return defaults
  - Unit tests for all methods including missing-file and partial-update scenarios
"""

import logging
import os

import pytest
import yaml

from runsight_api.data.filesystem.settings_repo import FileSystemSettingsRepo
from runsight_api.domain.entities.settings import (
    AppSettingsConfig,
    FallbackChainEntry,
    ModelDefaultEntry,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def repo(tmp_path):
    """Create a FileSystemSettingsRepo rooted at a temporary directory."""
    return FileSystemSettingsRepo(base_path=str(tmp_path))


@pytest.fixture
def settings_file(tmp_path):
    """Return the expected settings file path."""
    return tmp_path / ".runsight" / "settings.yaml"


# ===========================================================================
# AC: Missing file returns default AppSettingsConfig() with all None/empty
# ===========================================================================


class TestMissingFileDefaults:
    def test_get_settings_returns_default_when_no_file(self, repo):
        """get_settings must return a default AppSettingsConfig when no file exists."""
        result = repo.get_settings()
        assert isinstance(result, AppSettingsConfig)

    def test_default_settings_has_none_default_provider(self, repo):
        """Default AppSettingsConfig must have default_provider as None."""
        result = repo.get_settings()
        assert result.default_provider is None

    def test_default_settings_has_none_auto_save(self, repo):
        """Default AppSettingsConfig must have auto_save as None."""
        result = repo.get_settings()
        assert result.auto_save is None

    def test_default_settings_has_false_onboarding_completed(self, repo):
        """Default AppSettingsConfig must have onboarding_completed as False."""
        result = repo.get_settings()
        assert result.onboarding_completed is False

    def test_get_fallback_chain_returns_empty_when_no_file(self, repo):
        """get_fallback_chain must return an empty list when no file exists."""
        result = repo.get_fallback_chain()
        assert result == []

    def test_list_model_defaults_returns_empty_when_no_file(self, repo):
        """list_model_defaults must return an empty list when no file exists."""
        result = repo.list_model_defaults()
        assert result == []


# ===========================================================================
# AC: Reads/writes .runsight/settings.yaml
# ===========================================================================


class TestSettingsFileLocation:
    def test_settings_dir_created_on_init(self, tmp_path):
        """Initialising the repo must create .runsight/ directory automatically."""
        runsight_dir = tmp_path / ".runsight"
        assert not runsight_dir.exists()

        FileSystemSettingsRepo(base_path=str(tmp_path))

        assert runsight_dir.exists()
        assert runsight_dir.is_dir()

    def test_update_settings_creates_yaml_file(self, repo, settings_file):
        """update_settings must persist a settings.yaml file in .runsight/."""
        repo.update_settings({"default_provider": "openai"})
        assert settings_file.exists()

    def test_settings_file_is_valid_yaml(self, repo, settings_file):
        """The settings file must contain valid YAML."""
        repo.update_settings({"default_provider": "openai"})

        with open(settings_file) as f:
            data = yaml.safe_load(f)

        assert isinstance(data, dict)
        assert data["default_provider"] == "openai"


# ===========================================================================
# AC: update_settings merges partial updates correctly (shallow merge)
# ===========================================================================


class TestUpdateSettingsPartialMerge:
    def test_update_returns_app_settings_config(self, repo):
        """update_settings must return an AppSettingsConfig."""
        result = repo.update_settings({"default_provider": "openai"})
        assert isinstance(result, AppSettingsConfig)

    def test_update_sets_single_field(self, repo):
        """Setting a single field must persist it."""
        repo.update_settings({"default_provider": "openai"})
        result = repo.get_settings()
        assert result.default_provider == "openai"

    def test_update_preserves_existing_fields(self, repo):
        """Updating one field must NOT clobber other existing fields."""
        repo.update_settings({"default_provider": "openai", "auto_save": True})
        repo.update_settings({"default_provider": "anthropic"})

        result = repo.get_settings()
        assert result.default_provider == "anthropic"
        assert result.auto_save is True  # must be preserved

    def test_update_only_overwrites_provided_fields(self, repo):
        """Only fields present in the update dict should be changed."""
        repo.update_settings(
            {
                "default_provider": "openai",
                "auto_save": True,
                "onboarding_completed": False,
            }
        )
        repo.update_settings({"onboarding_completed": True})

        result = repo.get_settings()
        assert result.default_provider == "openai"  # unchanged
        assert result.auto_save is True  # unchanged
        assert result.onboarding_completed is True  # updated

    def test_update_can_set_all_flat_fields(self, repo):
        """All flat settings fields must be writable."""
        repo.update_settings(
            {
                "default_provider": "google",
                "auto_save": False,
                "onboarding_completed": True,
            }
        )

        result = repo.get_settings()
        assert result.default_provider == "google"
        assert result.auto_save is False
        assert result.onboarding_completed is True

    def test_update_with_empty_dict_changes_nothing(self, repo):
        """An empty update dict must leave settings unchanged."""
        repo.update_settings({"default_provider": "openai"})
        repo.update_settings({})

        result = repo.get_settings()
        assert result.default_provider == "openai"

    def test_update_can_set_field_to_none(self, repo):
        """Setting a field to None explicitly must store None."""
        repo.update_settings({"default_provider": "openai"})
        repo.update_settings({"default_provider": None})

        result = repo.get_settings()
        assert result.default_provider is None


# ===========================================================================
# AC: get_fallback_chain / update_fallback_chain
# ===========================================================================


class TestFallbackChain:
    def test_update_fallback_chain_returns_list(self, repo):
        """update_fallback_chain must return a list."""
        chain = [
            FallbackChainEntry(provider_id="openai", model_id="gpt-4o"),
        ]
        result = repo.update_fallback_chain(chain)
        assert isinstance(result, list)

    def test_update_fallback_chain_returns_entries(self, repo):
        """Returned items must be FallbackChainEntry instances."""
        chain = [
            FallbackChainEntry(provider_id="openai", model_id="gpt-4o"),
        ]
        result = repo.update_fallback_chain(chain)
        assert len(result) == 1
        assert isinstance(result[0], FallbackChainEntry)

    def test_get_fallback_chain_returns_entries(self, repo):
        """get_fallback_chain must return FallbackChainEntry instances."""
        chain = [
            FallbackChainEntry(provider_id="openai", model_id="gpt-4o"),
            FallbackChainEntry(provider_id="anthropic", model_id="claude-sonnet-4-20250514"),
        ]
        repo.update_fallback_chain(chain)

        result = repo.get_fallback_chain()
        assert len(result) == 2
        assert all(isinstance(e, FallbackChainEntry) for e in result)

    def test_fallback_chain_preserves_order(self, repo):
        """The fallback chain must preserve insertion order."""
        chain = [
            FallbackChainEntry(provider_id="openai", model_id="gpt-4o"),
            FallbackChainEntry(provider_id="anthropic", model_id="claude-sonnet-4-20250514"),
            FallbackChainEntry(provider_id="google", model_id="gemini-pro"),
        ]
        repo.update_fallback_chain(chain)

        result = repo.get_fallback_chain()
        assert result[0].provider_id == "openai"
        assert result[1].provider_id == "anthropic"
        assert result[2].provider_id == "google"

    def test_fallback_chain_preserves_field_values(self, repo):
        """Each entry must have correct provider_id and model_id."""
        chain = [
            FallbackChainEntry(provider_id="openai", model_id="gpt-4o"),
        ]
        repo.update_fallback_chain(chain)

        result = repo.get_fallback_chain()
        assert result[0].provider_id == "openai"
        assert result[0].model_id == "gpt-4o"


class TestFallbackChainFullReplacement:
    """AC: update_fallback_chain replaces the entire fallback chain list."""

    def test_update_replaces_entire_chain(self, repo):
        """Second call to update_fallback_chain must fully replace the first."""
        chain_v1 = [
            FallbackChainEntry(provider_id="openai", model_id="gpt-4o"),
            FallbackChainEntry(provider_id="anthropic", model_id="claude-sonnet-4-20250514"),
        ]
        repo.update_fallback_chain(chain_v1)

        chain_v2 = [
            FallbackChainEntry(provider_id="google", model_id="gemini-pro"),
        ]
        repo.update_fallback_chain(chain_v2)

        result = repo.get_fallback_chain()
        assert len(result) == 1
        assert result[0].provider_id == "google"
        assert result[0].model_id == "gemini-pro"

    def test_update_with_empty_list_clears_chain(self, repo):
        """Passing an empty list must remove all entries."""
        chain = [
            FallbackChainEntry(provider_id="openai", model_id="gpt-4o"),
        ]
        repo.update_fallback_chain(chain)
        repo.update_fallback_chain([])

        result = repo.get_fallback_chain()
        assert result == []

    def test_update_does_not_merge_with_existing(self, repo):
        """New chain must NOT contain any entries from the previous chain."""
        chain_v1 = [
            FallbackChainEntry(provider_id="openai", model_id="gpt-4o"),
            FallbackChainEntry(provider_id="anthropic", model_id="claude-sonnet-4-20250514"),
        ]
        repo.update_fallback_chain(chain_v1)

        chain_v2 = [
            FallbackChainEntry(provider_id="anthropic", model_id="claude-sonnet-4-20250514"),
        ]
        repo.update_fallback_chain(chain_v2)

        result = repo.get_fallback_chain()
        assert len(result) == 1
        # Only the v2 entry should remain; openai from v1 must be gone
        provider_ids = [e.provider_id for e in result]
        assert "openai" not in provider_ids


# ===========================================================================
# AC: set_model_default upserts by (provider_id, model_id) composite key
# ===========================================================================


class TestSetModelDefault:
    def test_set_model_default_returns_entry(self, repo):
        """set_model_default must return a ModelDefaultEntry."""
        entry = ModelDefaultEntry(provider_id="openai", model_id="gpt-4o", is_default=True)
        result = repo.set_model_default(entry)
        assert isinstance(result, ModelDefaultEntry)

    def test_set_model_default_creates_new_entry(self, repo):
        """Setting a model default for a new composite key must create an entry."""
        entry = ModelDefaultEntry(provider_id="openai", model_id="gpt-4o", is_default=True)
        repo.set_model_default(entry)

        result = repo.list_model_defaults()
        assert len(result) == 1
        assert result[0].provider_id == "openai"
        assert result[0].model_id == "gpt-4o"
        assert result[0].is_default is True

    def test_set_model_default_upserts_existing(self, repo):
        """Setting a default for the same composite key must update, not duplicate."""
        entry_v1 = ModelDefaultEntry(provider_id="openai", model_id="gpt-4o", is_default=True)
        repo.set_model_default(entry_v1)

        entry_v2 = ModelDefaultEntry(provider_id="openai", model_id="gpt-4o", is_default=False)
        repo.set_model_default(entry_v2)

        result = repo.list_model_defaults()
        assert len(result) == 1  # Must NOT have duplicates
        assert result[0].is_default is False  # Updated value

    def test_set_model_default_different_models_coexist(self, repo):
        """Different (provider_id, model_id) pairs must coexist."""
        repo.set_model_default(
            ModelDefaultEntry(provider_id="openai", model_id="gpt-4o", is_default=True)
        )
        repo.set_model_default(
            ModelDefaultEntry(provider_id="openai", model_id="gpt-4o-mini", is_default=False)
        )
        repo.set_model_default(
            ModelDefaultEntry(
                provider_id="anthropic", model_id="claude-sonnet-4-20250514", is_default=True
            )
        )

        result = repo.list_model_defaults()
        assert len(result) == 3

    def test_set_model_default_upserts_only_matching_key(self, repo):
        """Upsert must only affect the entry with matching composite key."""
        repo.set_model_default(
            ModelDefaultEntry(provider_id="openai", model_id="gpt-4o", is_default=True)
        )
        repo.set_model_default(
            ModelDefaultEntry(provider_id="openai", model_id="gpt-4o-mini", is_default=True)
        )

        # Upsert gpt-4o to is_default=False
        repo.set_model_default(
            ModelDefaultEntry(provider_id="openai", model_id="gpt-4o", is_default=False)
        )

        result = repo.list_model_defaults()
        assert len(result) == 2

        by_key = {(e.provider_id, e.model_id): e for e in result}
        assert by_key[("openai", "gpt-4o")].is_default is False
        assert by_key[("openai", "gpt-4o-mini")].is_default is True  # untouched


class TestListModelDefaults:
    def test_list_returns_all_entries(self, repo):
        """list_model_defaults must return every saved entry."""
        repo.set_model_default(
            ModelDefaultEntry(provider_id="openai", model_id="gpt-4o", is_default=True)
        )
        repo.set_model_default(
            ModelDefaultEntry(
                provider_id="anthropic", model_id="claude-sonnet-4-20250514", is_default=True
            )
        )

        result = repo.list_model_defaults()
        assert len(result) == 2
        assert all(isinstance(e, ModelDefaultEntry) for e in result)

    def test_list_returns_model_default_entries(self, repo):
        """Each item from list_model_defaults must be a ModelDefaultEntry."""
        repo.set_model_default(
            ModelDefaultEntry(provider_id="openai", model_id="gpt-4o", is_default=True)
        )

        result = repo.list_model_defaults()
        assert all(isinstance(e, ModelDefaultEntry) for e in result)


# ===========================================================================
# AC: Atomic writes prevent corruption
# ===========================================================================


class TestAtomicWrites:
    def test_update_settings_uses_atomic_write(self, repo, tmp_path, monkeypatch):
        """update_settings must write via temp file + os.rename."""
        renames = []
        original_rename = os.rename

        def tracking_rename(src, dst):
            renames.append((src, dst))
            return original_rename(src, dst)

        monkeypatch.setattr(os, "rename", tracking_rename)

        repo.update_settings({"default_provider": "openai"})

        assert len(renames) >= 1, "No os.rename calls detected — write is not atomic"
        runsight_dir = str(tmp_path / ".runsight")
        dst_paths = [dst for _, dst in renames]
        assert any(runsight_dir in str(p) for p in dst_paths), (
            f"Rename destination not in .runsight dir: {dst_paths}"
        )

    def test_update_fallback_chain_uses_atomic_write(self, repo, monkeypatch):
        """update_fallback_chain must also use atomic writes."""
        renames = []
        original_rename = os.rename

        def tracking_rename(src, dst):
            renames.append((src, dst))
            return original_rename(src, dst)

        monkeypatch.setattr(os, "rename", tracking_rename)

        chain = [FallbackChainEntry(provider_id="openai", model_id="gpt-4o")]
        repo.update_fallback_chain(chain)

        assert len(renames) >= 1, "No os.rename calls detected — write is not atomic"

    def test_set_model_default_uses_atomic_write(self, repo, monkeypatch):
        """set_model_default must also use atomic writes."""
        renames = []
        original_rename = os.rename

        def tracking_rename(src, dst):
            renames.append((src, dst))
            return original_rename(src, dst)

        monkeypatch.setattr(os, "rename", tracking_rename)

        entry = ModelDefaultEntry(provider_id="openai", model_id="gpt-4o", is_default=True)
        repo.set_model_default(entry)

        assert len(renames) >= 1, "No os.rename calls detected — write is not atomic"


# ===========================================================================
# AC: Invalid YAML in settings file: log warning, return defaults
# ===========================================================================


class TestInvalidYamlHandling:
    def test_get_settings_returns_defaults_for_invalid_yaml(self, repo, settings_file):
        """get_settings must return default AppSettingsConfig for invalid YAML."""
        settings_file.parent.mkdir(parents=True, exist_ok=True)
        settings_file.write_text(":\n  - :\n    invalid: [yaml{{{")

        result = repo.get_settings()
        assert isinstance(result, AppSettingsConfig)
        assert result.default_provider is None

    def test_get_settings_logs_warning_for_invalid_yaml(self, repo, settings_file, caplog):
        """get_settings must log a warning when the YAML file is invalid."""
        settings_file.parent.mkdir(parents=True, exist_ok=True)
        settings_file.write_text("not: valid: yaml: {{{}}")

        with caplog.at_level(logging.WARNING):
            repo.get_settings()

        assert any(
            "warning" in record.levelname.lower()
            or "failed" in record.message.lower()
            or "invalid" in record.message.lower()
            or "error" in record.message.lower()
            or "settings" in record.message.lower()
            for record in caplog.records
        ), f"Expected warning about invalid YAML, got: {[r.message for r in caplog.records]}"

    def test_get_fallback_chain_returns_empty_for_invalid_yaml(self, repo, settings_file):
        """get_fallback_chain must return empty list for invalid YAML."""
        settings_file.parent.mkdir(parents=True, exist_ok=True)
        settings_file.write_text("not valid yaml {{{}}")

        result = repo.get_fallback_chain()
        assert result == []

    def test_list_model_defaults_returns_empty_for_invalid_yaml(self, repo, settings_file):
        """list_model_defaults must return empty list for invalid YAML."""
        settings_file.parent.mkdir(parents=True, exist_ok=True)
        settings_file.write_text("not valid yaml {{{}}")

        result = repo.list_model_defaults()
        assert result == []


# ===========================================================================
# YAML schema matches epic spec
# ===========================================================================


class TestYamlSchema:
    def test_yaml_schema_matches_epic(self, repo, settings_file):
        """On-disk YAML must use the field names from the epic spec."""
        repo.update_settings(
            {
                "default_provider": "openai",
                "auto_save": True,
                "onboarding_completed": True,
            }
        )
        repo.update_fallback_chain(
            [
                FallbackChainEntry(provider_id="openai", model_id="gpt-4o"),
                FallbackChainEntry(provider_id="anthropic", model_id="claude-sonnet-4-20250514"),
            ]
        )
        repo.set_model_default(
            ModelDefaultEntry(provider_id="openai", model_id="gpt-4o", is_default=True)
        )

        with open(settings_file) as f:
            on_disk = yaml.safe_load(f)

        # Flat settings fields
        assert on_disk["default_provider"] == "openai"
        assert on_disk["auto_save"] is True
        assert on_disk["onboarding_completed"] is True

        # Fallback chain
        assert "fallback_chain" in on_disk
        assert len(on_disk["fallback_chain"]) == 2
        assert on_disk["fallback_chain"][0]["provider_id"] == "openai"
        assert on_disk["fallback_chain"][0]["model_id"] == "gpt-4o"

        # Model defaults
        assert "model_defaults" in on_disk
        assert len(on_disk["model_defaults"]) == 1
        assert on_disk["model_defaults"][0]["provider_id"] == "openai"
        assert on_disk["model_defaults"][0]["model_id"] == "gpt-4o"
        assert on_disk["model_defaults"][0]["is_default"] is True


# ===========================================================================
# Round-trip fidelity
# ===========================================================================


class TestRoundTrip:
    def test_settings_round_trip(self, repo):
        """Settings must survive update -> get round trip."""
        repo.update_settings(
            {
                "default_provider": "openai",
                "auto_save": True,
                "onboarding_completed": False,
            }
        )

        result = repo.get_settings()
        assert result.default_provider == "openai"
        assert result.auto_save is True
        assert result.onboarding_completed is False

    def test_fallback_chain_round_trip(self, repo):
        """Fallback chain must survive update -> get round trip."""
        chain = [
            FallbackChainEntry(provider_id="openai", model_id="gpt-4o"),
            FallbackChainEntry(provider_id="anthropic", model_id="claude-sonnet-4-20250514"),
        ]
        repo.update_fallback_chain(chain)

        result = repo.get_fallback_chain()
        assert len(result) == 2
        assert result[0].provider_id == "openai"
        assert result[0].model_id == "gpt-4o"
        assert result[1].provider_id == "anthropic"
        assert result[1].model_id == "claude-sonnet-4-20250514"

    def test_model_defaults_round_trip(self, repo):
        """Model defaults must survive set -> list round trip."""
        repo.set_model_default(
            ModelDefaultEntry(provider_id="openai", model_id="gpt-4o", is_default=True)
        )

        result = repo.list_model_defaults()
        assert len(result) == 1
        assert result[0].provider_id == "openai"
        assert result[0].model_id == "gpt-4o"
        assert result[0].is_default is True

    def test_all_sections_coexist_in_single_file(self, repo, settings_file):
        """Settings, fallback chain, and model defaults must all live in one file."""
        repo.update_settings({"default_provider": "openai"})
        repo.update_fallback_chain(
            [
                FallbackChainEntry(provider_id="openai", model_id="gpt-4o"),
            ]
        )
        repo.set_model_default(
            ModelDefaultEntry(provider_id="openai", model_id="gpt-4o", is_default=True)
        )

        # Verify there's exactly one file
        assert settings_file.exists()

        with open(settings_file) as f:
            on_disk = yaml.safe_load(f)

        # All three sections must be present
        assert "default_provider" in on_disk
        assert "fallback_chain" in on_disk
        assert "model_defaults" in on_disk


# ===========================================================================
# Edge cases: hand-authored YAML
# ===========================================================================


class TestHandAuthoredYaml:
    def test_reads_hand_authored_settings(self, repo, settings_file):
        """Must correctly read a hand-authored settings.yaml file."""
        settings_file.parent.mkdir(parents=True, exist_ok=True)
        settings_file.write_text(
            yaml.dump(
                {
                    "default_provider": "anthropic",
                    "auto_save": False,
                    "onboarding_completed": True,
                    "fallback_chain": [
                        {"provider_id": "openai", "model_id": "gpt-4o"},
                        {"provider_id": "anthropic", "model_id": "claude-sonnet-4-20250514"},
                    ],
                    "model_defaults": [
                        {"provider_id": "openai", "model_id": "gpt-4o", "is_default": True},
                    ],
                }
            )
        )

        settings = repo.get_settings()
        assert settings.default_provider == "anthropic"
        assert settings.auto_save is False
        assert settings.onboarding_completed is True

        chain = repo.get_fallback_chain()
        assert len(chain) == 2
        assert chain[0].provider_id == "openai"

        defaults = repo.list_model_defaults()
        assert len(defaults) == 1
        assert defaults[0].is_default is True

    def test_reads_minimal_hand_authored_file(self, repo, settings_file):
        """A hand-authored file with only some fields must work (others default)."""
        settings_file.parent.mkdir(parents=True, exist_ok=True)
        settings_file.write_text("default_provider: openai\n")

        settings = repo.get_settings()
        assert settings.default_provider == "openai"
        assert settings.auto_save is None
        assert settings.onboarding_completed is False

        # Missing sections default to empty lists
        assert repo.get_fallback_chain() == []
        assert repo.list_model_defaults() == []

    def test_reads_empty_file_as_defaults(self, repo, settings_file):
        """An empty settings file must return defaults (not crash)."""
        settings_file.parent.mkdir(parents=True, exist_ok=True)
        settings_file.write_text("")

        result = repo.get_settings()
        assert isinstance(result, AppSettingsConfig)
        assert result.default_provider is None


# ===========================================================================
# Pydantic models: AppSettingsConfig, FallbackChainEntry, ModelDefaultEntry
# ===========================================================================


class TestPydanticModels:
    def test_app_settings_config_is_pydantic_model(self):
        """AppSettingsConfig must be a Pydantic BaseModel."""
        config = AppSettingsConfig()
        assert hasattr(config, "model_dump")

    def test_app_settings_config_fields(self):
        """AppSettingsConfig must have the expected fields."""
        config = AppSettingsConfig()
        assert hasattr(config, "default_provider")
        assert hasattr(config, "auto_save")
        assert hasattr(config, "onboarding_completed")

    def test_fallback_chain_entry_fields(self):
        """FallbackChainEntry must have provider_id and model_id."""
        entry = FallbackChainEntry(provider_id="openai", model_id="gpt-4o")
        assert entry.provider_id == "openai"
        assert entry.model_id == "gpt-4o"

    def test_model_default_entry_fields(self):
        """ModelDefaultEntry must have provider_id, model_id, and is_default."""
        entry = ModelDefaultEntry(provider_id="openai", model_id="gpt-4o", is_default=True)
        assert entry.provider_id == "openai"
        assert entry.model_id == "gpt-4o"
        assert entry.is_default is True

    def test_model_default_entry_is_default_defaults_false(self):
        """ModelDefaultEntry.is_default must default to False."""
        entry = ModelDefaultEntry(provider_id="openai", model_id="gpt-4o")
        assert entry.is_default is False
