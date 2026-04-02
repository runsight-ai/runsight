"""RUN-548 red tests for the filesystem settings repository foundation."""

from __future__ import annotations

import importlib

import pytest
import yaml

from runsight_api.data.filesystem.settings_repo import FileSystemSettingsRepo
from runsight_api.domain.entities.settings import AppSettingsConfig, ModelDefaultEntry


def _settings_module():
    return importlib.import_module("runsight_api.domain.entities.settings")


def _entities_module():
    return importlib.import_module("runsight_api.domain.entities")


@pytest.fixture
def repo(tmp_path):
    return FileSystemSettingsRepo(base_path=str(tmp_path))


@pytest.fixture
def settings_file(tmp_path):
    return tmp_path / ".runsight" / "settings.yaml"


class TestDomainFoundation:
    def test_fallback_chain_entry_removed_from_settings_module(self):
        settings_module = _settings_module()

        assert not hasattr(settings_module, "FallbackChainEntry")

    def test_fallback_chain_entry_removed_from_entities_module(self):
        entities_module = _entities_module()

        assert not hasattr(entities_module, "FallbackChainEntry")

    def test_fallback_target_entry_exported_from_domain_modules(self):
        settings_module = _settings_module()
        entities_module = _entities_module()

        assert hasattr(settings_module, "FallbackTargetEntry")
        assert hasattr(entities_module, "FallbackTargetEntry")

    def test_fallback_target_entry_uses_per_provider_target_fields(self):
        entry_cls = getattr(_settings_module(), "FallbackTargetEntry")

        entry = entry_cls(
            provider_id="openai",
            fallback_provider_id="anthropic",
            fallback_model_id="claude-sonnet-4",
        )

        assert entry.model_dump() == {
            "provider_id": "openai",
            "fallback_provider_id": "anthropic",
            "fallback_model_id": "claude-sonnet-4",
        }

    def test_app_settings_config_defaults_fallback_enabled_false(self):
        settings = AppSettingsConfig()

        assert settings.fallback_enabled is False
        assert not hasattr(settings, "fallback_chain_enabled")


class TestFreshInstallDefaults:
    def test_get_settings_returns_fallback_enabled_false_for_new_install(self, repo):
        settings = repo.get_settings()

        assert isinstance(settings, AppSettingsConfig)
        assert settings.fallback_enabled is False

    def test_legacy_fallback_chain_repo_methods_are_removed(self, repo):
        assert not hasattr(repo, "get_fallback_chain")
        assert not hasattr(repo, "update_fallback_chain")

    def test_get_fallback_map_returns_empty_list_for_new_install(self, repo):
        assert repo.get_fallback_map() == []


class TestFallbackMapPersistence:
    def test_set_fallback_target_upserts_by_provider_id(self, repo):
        entry_cls = getattr(_settings_module(), "FallbackTargetEntry")

        repo.set_fallback_target(
            entry_cls(
                provider_id="openai",
                fallback_provider_id="anthropic",
                fallback_model_id="claude-sonnet-4",
            )
        )
        updated = repo.set_fallback_target(
            entry_cls(
                provider_id="openai",
                fallback_provider_id="google",
                fallback_model_id="gemini-2.5-pro",
            )
        )

        assert updated.provider_id == "openai"
        assert updated.fallback_provider_id == "google"
        assert updated.fallback_model_id == "gemini-2.5-pro"

        fallback_map = repo.get_fallback_map()
        assert len(fallback_map) == 1
        assert fallback_map[0].provider_id == "openai"
        assert fallback_map[0].fallback_provider_id == "google"
        assert fallback_map[0].fallback_model_id == "gemini-2.5-pro"

    def test_remove_fallback_target_returns_true_when_removed(self, repo):
        entry_cls = getattr(_settings_module(), "FallbackTargetEntry")
        repo.set_fallback_target(
            entry_cls(
                provider_id="openai",
                fallback_provider_id="anthropic",
                fallback_model_id="claude-sonnet-4",
            )
        )

        removed = repo.remove_fallback_target("openai")

        assert removed is True
        assert repo.get_fallback_map() == []

    def test_remove_fallback_target_returns_false_when_provider_is_missing(self, repo):
        assert repo.remove_fallback_target("missing-provider") is False


class TestLegacyYamlMigration:
    def test_first_read_renames_legacy_flag_and_deletes_fallback_chain(self, repo, settings_file):
        settings_file.parent.mkdir(parents=True, exist_ok=True)
        settings_file.write_text(
            yaml.safe_dump(
                {
                    "default_provider": "openai",
                    "fallback_chain_enabled": True,
                    "fallback_chain": [
                        {"provider_id": "openai", "model_id": "gpt-4o"},
                        {
                            "provider_id": "anthropic",
                            "model_id": "claude-sonnet-4",
                        },
                    ],
                    "model_defaults": [
                        {
                            "provider_id": "openai",
                            "model_id": "gpt-4o",
                            "is_default": True,
                        }
                    ],
                },
                sort_keys=False,
            )
        )

        settings = repo.get_settings()

        assert settings.fallback_enabled is True

        on_disk = yaml.safe_load(settings_file.read_text())
        assert on_disk["fallback_enabled"] is True
        assert "fallback_chain_enabled" not in on_disk
        assert "fallback_chain" not in on_disk
        assert on_disk["model_defaults"] == [
            ModelDefaultEntry(
                provider_id="openai",
                model_id="gpt-4o",
                is_default=True,
            ).model_dump()
        ]
        assert repo.get_fallback_map() == []

    def test_first_read_defaults_fallback_enabled_to_false_when_legacy_flag_is_missing(
        self, repo, settings_file
    ):
        settings_file.parent.mkdir(parents=True, exist_ok=True)
        settings_file.write_text(
            yaml.safe_dump(
                {
                    "default_provider": "openai",
                    "fallback_chain": [
                        {"provider_id": "openai", "model_id": "gpt-4o"},
                    ],
                },
                sort_keys=False,
            )
        )

        settings = repo.get_settings()

        assert settings.fallback_enabled is False

        on_disk = yaml.safe_load(settings_file.read_text())
        assert on_disk["fallback_enabled"] is False
        assert "fallback_chain_enabled" not in on_disk
        assert "fallback_chain" not in on_disk
