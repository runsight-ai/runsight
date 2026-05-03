"""Tests for the filesystem-backed settings repository."""

from __future__ import annotations

from unittest.mock import Mock

import pytest
import yaml

from runsight_api.domain.entities.settings import AppSettingsConfig
from tests.unit.data.filesystem.settings_repo_helpers import (  # noqa: F401
    AUXILIARY_MODEL_ID,
    AUXILIARY_PROVIDER_ID,
    BACKUP_MODEL_ID,
    BACKUP_PROVIDER_ID,
    PRIMARY_MODEL_ID,
    PRIMARY_PROVIDER_ID,
    entities_module,
    fallback_map_entry,
    fallback_target_entry,
    repo_fixture as _repo_fixture,
    settings_file_fixture as _settings_file_fixture,
    settings_module,
    write_settings_yaml,
)


class TestDomainFoundation:
    def test_legacy_fallback_entry_removed_from_settings_module(self):
        assert not hasattr(settings_module(), "FallbackChainEntry")

    def test_legacy_fallback_entry_removed_from_entities_module(self):
        assert not hasattr(entities_module(), "FallbackChainEntry")

    def test_fallback_target_entry_exported_from_domain_modules(self):
        settings_module_obj = settings_module()
        entities_module_obj = entities_module()

        assert hasattr(settings_module_obj, "FallbackTargetEntry")
        assert hasattr(entities_module_obj, "FallbackTargetEntry")
        assert not hasattr(settings_module_obj, "ModelDefaultEntry")
        assert not hasattr(entities_module_obj, "ModelDefaultEntry")

    def test_app_settings_config_defaults_fallback_enabled_false(self):
        settings = AppSettingsConfig()

        assert settings.fallback_enabled is False
        assert not hasattr(settings, "default_provider")
        assert not hasattr(settings, "fallback_chain_enabled")

    def test_app_settings_config_rejects_unknown_fields(self):
        with pytest.raises(Exception, match="auto_save"):
            AppSettingsConfig(auto_save=True)


class TestFreshInstallDefaults:
    def test_get_settings_returns_defaults_for_new_install(self, repo):
        settings = repo.get_settings()

        assert isinstance(settings, AppSettingsConfig)
        assert settings.fallback_enabled is False

    def test_present_settings_file_without_fallback_map_is_valid(self, repo, settings_file):
        write_settings_yaml(
            settings_file,
            {
                "onboarding_completed": True,
                "fallback_enabled": True,
            },
        )

        settings = repo.get_settings()

        assert isinstance(settings, AppSettingsConfig)
        assert settings.onboarding_completed is True
        assert settings.fallback_enabled is True
        assert repo.get_fallback_map() == []

    def test_legacy_fallback_repo_methods_are_removed(self, repo):
        assert not hasattr(repo, "get_fallback_chain")
        assert not hasattr(repo, "update_fallback_chain")
        assert not hasattr(repo, "list_model_defaults")
        assert not hasattr(repo, "set_model_default")

    def test_get_fallback_map_returns_empty_list_for_new_install(self, repo):
        assert repo.get_fallback_map() == []


class TestFallbackMapPersistence:
    def test_set_fallback_target_upserts_by_provider_id(self, repo):
        repo.set_fallback_target(fallback_target_entry())
        updated = repo.set_fallback_target(
            fallback_target_entry(
                fallback_provider_id=AUXILIARY_PROVIDER_ID,
                fallback_model_id=AUXILIARY_MODEL_ID,
            )
        )

        assert updated.provider_id == PRIMARY_PROVIDER_ID
        assert updated.fallback_provider_id == AUXILIARY_PROVIDER_ID
        assert updated.fallback_model_id == AUXILIARY_MODEL_ID

        fallback_map = repo.get_fallback_map()
        assert len(fallback_map) == 1
        assert fallback_map[0].provider_id == PRIMARY_PROVIDER_ID
        assert fallback_map[0].fallback_provider_id == AUXILIARY_PROVIDER_ID
        assert fallback_map[0].fallback_model_id == AUXILIARY_MODEL_ID

    def test_remove_fallback_target_returns_true_when_removed(self, repo):
        repo.set_fallback_target(fallback_target_entry())

        removed = repo.remove_fallback_target(PRIMARY_PROVIDER_ID)

        assert removed is True
        assert repo.get_fallback_map() == []

    def test_remove_fallback_target_is_side_effect_free_for_missing_provider(
        self, repo, settings_file, monkeypatch
    ):
        repo.set_fallback_target(fallback_target_entry())
        before = settings_file.read_text()
        write_mock = Mock()
        monkeypatch.setattr(repo, "_write_yaml", write_mock)

        assert repo.remove_fallback_target("missing-provider") is False
        assert settings_file.read_text() == before
        write_mock.assert_not_called()

    def test_set_fallback_target_preserves_app_settings_buckets(self, repo, settings_file):
        write_settings_yaml(
            settings_file,
            {
                "onboarding_completed": True,
                "fallback_enabled": True,
                "fallback_map": [fallback_map_entry()],
            },
        )

        updated = repo.set_fallback_target(
            fallback_target_entry(
                fallback_provider_id=AUXILIARY_PROVIDER_ID,
                fallback_model_id=AUXILIARY_MODEL_ID,
            )
        )

        assert updated.provider_id == PRIMARY_PROVIDER_ID
        assert updated.fallback_provider_id == AUXILIARY_PROVIDER_ID
        assert updated.fallback_model_id == AUXILIARY_MODEL_ID

        on_disk = yaml.safe_load(settings_file.read_text())
        assert on_disk["onboarding_completed"] is True
        assert on_disk["fallback_enabled"] is True
        assert on_disk["fallback_map"] == [
            fallback_map_entry(
                fallback_provider_id=AUXILIARY_PROVIDER_ID,
                fallback_model_id=AUXILIARY_MODEL_ID,
            )
        ]


class TestStrictSchemaValidation:
    @pytest.mark.parametrize(
        ("key", "value"),
        [
            ("auto_save", True),
            ("default_provider", "primary-provider"),
            ("fallback_chain_enabled", True),
            (
                "fallback_chain",
                [{"provider_id": PRIMARY_PROVIDER_ID, "model_id": PRIMARY_MODEL_ID}],
            ),
            (
                "model_defaults",
                [
                    {
                        "provider_id": PRIMARY_PROVIDER_ID,
                        "model_id": PRIMARY_MODEL_ID,
                        "is_default": True,
                    }
                ],
            ),
        ],
    )
    def test_get_settings_rejects_dead_top_level_keys(self, repo, settings_file, key, value):
        write_settings_yaml(settings_file, {key: value})

        with pytest.raises(Exception, match=key):
            repo.get_settings()

    def test_get_settings_rejects_malformed_yaml(self, repo, settings_file):
        settings_file.parent.mkdir(parents=True, exist_ok=True)
        settings_file.write_text("onboarding_completed: true\nfallback_map: [")

        with pytest.raises(Exception, match="fallback_map|YAML|parse|invalid"):
            repo.get_settings()

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("fallback_enabled", 1),
            ("onboarding_completed", "yes"),
        ],
    )
    def test_get_settings_rejects_wrong_type_for_supported_bool_fields(
        self, repo, settings_file, field, value
    ):
        write_settings_yaml(
            settings_file,
            {
                "onboarding_completed": False,
                "fallback_enabled": False,
                field: value,
            },
        )

        with pytest.raises(Exception, match=field):
            repo.get_settings()

    def test_get_fallback_map_rejects_non_list_fallback_map(self, repo, settings_file):
        write_settings_yaml(
            settings_file,
            {"fallback_map": fallback_map_entry()},
        )

        with pytest.raises(Exception, match="fallback_map"):
            repo.get_fallback_map()

    @pytest.mark.parametrize(
        ("missing_key", "entry"),
        [
            (
                "provider_id",
                {
                    "fallback_provider_id": BACKUP_PROVIDER_ID,
                    "fallback_model_id": BACKUP_MODEL_ID,
                },
            ),
            (
                "fallback_provider_id",
                {
                    "provider_id": PRIMARY_PROVIDER_ID,
                    "fallback_model_id": BACKUP_MODEL_ID,
                },
            ),
            (
                "fallback_model_id",
                {
                    "provider_id": PRIMARY_PROVIDER_ID,
                    "fallback_provider_id": BACKUP_PROVIDER_ID,
                },
            ),
        ],
    )
    def test_get_settings_rejects_fallback_map_entries_missing_required_fields(
        self, repo, settings_file, missing_key, entry
    ):
        write_settings_yaml(settings_file, {"fallback_map": [entry]})

        with pytest.raises(Exception, match=missing_key):
            repo.get_settings()


class TestStrictSettingsWrites:
    def test_update_settings_preserves_valid_fallback_data_when_mutating_app_settings(
        self, repo, settings_file
    ):
        write_settings_yaml(
            settings_file,
            {
                "onboarding_completed": False,
                "fallback_enabled": True,
                "fallback_map": [fallback_map_entry()],
            },
        )
        before = settings_file.read_text()

        updated = repo.update_settings({"onboarding_completed": True})

        assert updated.onboarding_completed is True
        assert updated.fallback_enabled is True

        on_disk = yaml.safe_load(settings_file.read_text())
        assert settings_file.read_text() != before
        assert on_disk["onboarding_completed"] is True
        assert on_disk["fallback_enabled"] is True
        assert on_disk["fallback_map"] == [fallback_map_entry()]

    def test_update_settings_rejects_auto_save_before_rewriting(
        self, repo, settings_file, monkeypatch
    ):
        write_settings_yaml(
            settings_file,
            {
                "auto_save": True,
                "onboarding_completed": False,
                "fallback_enabled": True,
            },
        )
        write_mock = Mock(wraps=repo._write_yaml)
        monkeypatch.setattr(repo, "_write_yaml", write_mock)

        with pytest.raises(Exception, match="auto_save"):
            repo.update_settings({"onboarding_completed": True})

        write_mock.assert_not_called()

    @pytest.mark.parametrize(
        ("updates", "field"),
        [
            ({"onboarding_completed": "yes"}, "onboarding_completed"),
            ({"fallback_enabled": 1}, "fallback_enabled"),
        ],
    )
    def test_update_settings_rejects_wrong_type_without_creating_settings_file(
        self, repo, settings_file, updates, field
    ):
        assert not settings_file.exists()

        with pytest.raises(Exception, match=field):
            repo.update_settings(updates)

        assert not settings_file.exists()

    def test_update_settings_rejects_wrong_type_without_rewriting_existing_file(
        self, repo, settings_file, monkeypatch
    ):
        write_settings_yaml(
            settings_file,
            {
                "onboarding_completed": False,
                "fallback_enabled": True,
            },
        )
        before = settings_file.read_text()
        write_mock = Mock(wraps=repo._write_yaml)
        monkeypatch.setattr(repo, "_write_yaml", write_mock)

        with pytest.raises(Exception, match="fallback_enabled"):
            repo.update_settings({"fallback_enabled": 1})

        assert settings_file.read_text() == before
        write_mock.assert_not_called()
