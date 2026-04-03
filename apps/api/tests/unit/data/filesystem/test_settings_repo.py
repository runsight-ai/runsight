"""Tests for the filesystem-backed settings repository."""

from __future__ import annotations

import importlib

import pytest
import yaml

from runsight_api.data.filesystem.settings_repo import FileSystemSettingsRepo
from runsight_api.domain.entities.settings import AppSettingsConfig


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
    def test_legacy_fallback_entry_removed_from_settings_module(self):
        assert not hasattr(_settings_module(), "FallbackChainEntry")

    def test_legacy_fallback_entry_removed_from_entities_module(self):
        assert not hasattr(_entities_module(), "FallbackChainEntry")

    def test_fallback_target_entry_exported_from_domain_modules(self):
        settings_module = _settings_module()
        entities_module = _entities_module()

        assert hasattr(settings_module, "FallbackTargetEntry")
        assert hasattr(entities_module, "FallbackTargetEntry")
        assert not hasattr(settings_module, "ModelDefaultEntry")
        assert not hasattr(entities_module, "ModelDefaultEntry")

    def test_app_settings_config_defaults_fallback_enabled_false(self):
        settings = AppSettingsConfig()

        assert settings.fallback_enabled is False
        assert not hasattr(settings, "default_provider")
        assert not hasattr(settings, "fallback_chain_enabled")


class TestFreshInstallDefaults:
    def test_get_settings_returns_defaults_for_new_install(self, repo):
        settings = repo.get_settings()

        assert isinstance(settings, AppSettingsConfig)
        assert settings.fallback_enabled is False

    def test_legacy_fallback_repo_methods_are_removed(self, repo):
        assert not hasattr(repo, "get_fallback_chain")
        assert not hasattr(repo, "update_fallback_chain")
        assert not hasattr(repo, "list_model_defaults")
        assert not hasattr(repo, "set_model_default")

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


class TestCleanSchemaOnly:
    def test_get_settings_ignores_legacy_keys_without_rewriting_yaml(self, repo, settings_file):
        settings_file.parent.mkdir(parents=True, exist_ok=True)
        settings_file.write_text(
            yaml.safe_dump(
                {
                    "default_provider": "openai",
                    "fallback_chain_enabled": True,
                    "fallback_chain": [
                        {"provider_id": "openai", "model_id": "gpt-4o"},
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

        assert settings.fallback_enabled is False

        on_disk = yaml.safe_load(settings_file.read_text())
        assert on_disk["fallback_chain_enabled"] is True
        assert on_disk["fallback_chain"] == [{"provider_id": "openai", "model_id": "gpt-4o"}]
        assert on_disk["model_defaults"] == [
            {
                "provider_id": "openai",
                "model_id": "gpt-4o",
                "is_default": True,
            }
        ]
        assert repo.get_fallback_map() == []

    def test_get_settings_defaults_fallback_enabled_false_when_only_legacy_chain_exists(
        self, repo, settings_file
    ):
        settings_file.parent.mkdir(parents=True, exist_ok=True)
        settings_file.write_text(
            yaml.safe_dump(
                {
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
        assert "fallback_enabled" not in on_disk
        assert on_disk["fallback_chain"] == [{"provider_id": "openai", "model_id": "gpt-4o"}]
