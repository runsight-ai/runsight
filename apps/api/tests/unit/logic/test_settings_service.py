"""Tests for the backend fallback settings service."""

from __future__ import annotations

import inspect
from unittest.mock import Mock, call

import pytest

from runsight_api.data.filesystem.provider_repo import FileSystemProviderRepo
from runsight_api.data.filesystem.settings_repo import FileSystemSettingsRepo
from runsight_api.domain.errors import InputValidationError, ProviderNotFound
from runsight_api.transport import deps as deps_module
from tests.unit.logic.settings_service_helpers import (
    fallback_entry,
    load_settings_service,
    load_settings_service_module,
    provider,
    service as make_service,
)


class TestSettingsServiceConstructor:
    def test_constructor_accepts_settings_repo_and_provider_repo(self):
        signature = inspect.signature(load_settings_service().__init__)
        assert list(signature.parameters) == ["self", "settings_repo", "provider_repo"]

    def test_get_settings_service_returns_settings_service(self):
        settings_repo = Mock(spec=FileSystemSettingsRepo)
        provider_repo = Mock(spec=FileSystemProviderRepo)

        service = deps_module.get_settings_service(
            settings_repo=settings_repo,
            provider_repo=provider_repo,
        )

        assert isinstance(service, load_settings_service())


class TestFallbackFoundation:
    def test_settings_service_only_uses_fallback_types_and_repo_methods(self):
        source = inspect.getsource(load_settings_service_module())

        assert "FallbackTargetEntry" in source
        assert "get_fallback_map" in source
        assert "set_fallback_target" in source
        assert "remove_fallback_target" in source
        assert "ModelDefaultEntry" not in source
        assert "list_model_defaults" not in source
        assert "update_model_default" not in source
        assert "fallback_chain" not in source

    def test_update_fallback_target_signature_is_pair_only(self):
        signature = inspect.signature(load_settings_service().update_fallback_target)
        assert list(signature.parameters) == [
            "self",
            "provider_id",
            "fallback_provider_id",
            "fallback_model_id",
        ]


class TestSettingsServiceReadFallbackTargets:
    def test_get_fallback_targets_returns_one_row_per_enabled_provider(self):
        settings_repo = Mock()
        provider_repo = Mock()
        provider_repo.list_all.return_value = [
            provider(
                provider_id="primary-provider",
                provider_type="primary-provider",
                name="Primary Provider",
                is_active=True,
                models=["primary-fixture-model"],
                status="connection_failed",
            ),
            provider(
                provider_id="fallback-provider",
                provider_type="fallback-provider",
                name="Fallback Provider",
                is_active=True,
                models=["fallback-fixture-model"],
            ),
            provider(
                provider_id="disabled-provider",
                provider_type="disabled-provider",
                name="Disabled Provider",
                is_active=False,
                models=["disabled-fixture-model"],
            ),
        ]
        settings_repo.get_fallback_map.return_value = [
            fallback_entry(
                provider_id="primary-provider",
                fallback_provider_id="fallback-provider",
                fallback_model_id="fallback-fixture-model",
            ),
            fallback_entry(
                provider_id="fallback-provider",
                fallback_provider_id="primary-provider",
                fallback_model_id="primary-fixture-model",
            ),
            fallback_entry(
                provider_id="disabled-provider",
                fallback_provider_id="primary-provider",
                fallback_model_id="primary-fixture-model",
            ),
        ]

        result = make_service(
            settings_repo=settings_repo, provider_repo=provider_repo
        ).get_fallback_targets()

        assert result == [
            {
                "id": "primary-provider",
                "provider_id": "primary-provider",
                "provider_name": "Primary Provider",
                "fallback_provider_id": "fallback-provider",
                "fallback_model_id": "fallback-fixture-model",
            },
            {
                "id": "fallback-provider",
                "provider_id": "fallback-provider",
                "provider_name": "Fallback Provider",
                "fallback_provider_id": "primary-provider",
                "fallback_model_id": "primary-fixture-model",
            },
        ]

    def test_get_fallback_targets_suppresses_missing_or_disabled_targets_without_rewriting_storage(
        self,
    ):
        settings_repo = Mock()
        provider_repo = Mock()
        provider_repo.list_all.return_value = [
            provider(
                provider_id="primary-provider",
                provider_type="primary-provider",
                name="Primary Provider",
                is_active=True,
                models=["primary-fixture-model"],
            ),
            provider(
                provider_id="disabled-provider",
                provider_type="disabled-provider",
                name="Disabled Provider",
                is_active=False,
                models=["disabled-fixture-model"],
            ),
        ]
        stored_fallback_map = [
            fallback_entry(
                provider_id="primary-provider",
                fallback_provider_id="disabled-provider",
                fallback_model_id="disabled-fixture-model",
            ),
            fallback_entry(
                provider_id="missing-provider",
                fallback_provider_id="primary-provider",
                fallback_model_id="primary-fixture-model",
            ),
        ]
        settings_repo.get_fallback_map.return_value = stored_fallback_map

        result = make_service(
            settings_repo=settings_repo, provider_repo=provider_repo
        ).get_fallback_targets()

        assert result == [
            {
                "id": "primary-provider",
                "provider_id": "primary-provider",
                "provider_name": "Primary Provider",
                "fallback_provider_id": None,
                "fallback_model_id": None,
            }
        ]
        settings_repo.set_fallback_target.assert_not_called()
        settings_repo.remove_fallback_target.assert_not_called()


class TestSettingsServiceUpdateFallbackTargets:
    def test_update_fallback_target_persists_valid_target(self):
        settings_repo = Mock()
        provider_repo = Mock()
        source_provider = provider(
            provider_id="primary-provider",
            provider_type="primary-provider",
            name="Primary Provider",
            is_active=True,
            models=["primary-fixture-model"],
        )
        target_provider = provider(
            provider_id="fallback-provider",
            provider_type="fallback-provider",
            name="Fallback Provider",
            is_active=True,
            models=["fallback-fixture-model"],
            status="connection_failed",
        )
        provider_repo.get_by_id.side_effect = lambda provider_id: {
            "primary-provider": source_provider,
            "fallback-provider": target_provider,
        }.get(provider_id)
        settings_repo.get_fallback_map.return_value = []
        settings_repo.set_fallback_target.side_effect = lambda entry: entry

        result = make_service(
            settings_repo=settings_repo, provider_repo=provider_repo
        ).update_fallback_target(
            provider_id="primary-provider",
            fallback_provider_id="fallback-provider",
            fallback_model_id="fallback-fixture-model",
        )

        settings_repo.set_fallback_target.assert_called_once_with(
            fallback_entry(
                provider_id="primary-provider",
                fallback_provider_id="fallback-provider",
                fallback_model_id="fallback-fixture-model",
            )
        )
        assert result["fallback_provider_id"] == "fallback-provider"
        assert result["fallback_model_id"] == "fallback-fixture-model"

    def test_update_fallback_target_allows_circular_reads(self):
        settings_repo = Mock()
        provider_repo = Mock()
        primary_provider = provider(
            provider_id="primary-provider",
            provider_type="primary-provider",
            name="Primary Provider",
            is_active=True,
            models=["primary-fixture-model"],
        )
        fallback_provider = provider(
            provider_id="fallback-provider",
            provider_type="fallback-provider",
            name="Fallback Provider",
            is_active=True,
            models=["fallback-fixture-model"],
        )
        provider_repo.get_by_id.side_effect = lambda provider_id: {
            "primary-provider": primary_provider,
            "fallback-provider": fallback_provider,
        }.get(provider_id)
        settings_repo.get_fallback_map.return_value = []
        settings_repo.set_fallback_target.side_effect = lambda entry: entry

        settings_service = make_service(settings_repo=settings_repo, provider_repo=provider_repo)
        first = settings_service.update_fallback_target(
            provider_id="primary-provider",
            fallback_provider_id="fallback-provider",
            fallback_model_id="fallback-fixture-model",
        )
        second = settings_service.update_fallback_target(
            provider_id="fallback-provider",
            fallback_provider_id="primary-provider",
            fallback_model_id="primary-fixture-model",
        )

        assert settings_repo.set_fallback_target.call_args_list == [
            call(
                fallback_entry(
                    provider_id="primary-provider",
                    fallback_provider_id="fallback-provider",
                    fallback_model_id="fallback-fixture-model",
                )
            ),
            call(
                fallback_entry(
                    provider_id="fallback-provider",
                    fallback_provider_id="primary-provider",
                    fallback_model_id="primary-fixture-model",
                )
            ),
        ]
        assert first["fallback_provider_id"] == "fallback-provider"
        assert second["fallback_provider_id"] == "primary-provider"

    def test_update_fallback_target_rejects_partial_updates(self):
        settings_repo = Mock()
        provider_repo = Mock()
        provider_repo.get_by_id.return_value = provider(
            provider_id="primary-provider",
            provider_type="primary-provider",
            name="Primary Provider",
            is_active=True,
            models=["primary-fixture-model"],
        )

        settings_service = make_service(settings_repo=settings_repo, provider_repo=provider_repo)

        with pytest.raises(InputValidationError, match="both be provided or both omitted"):
            settings_service.update_fallback_target(
                provider_id="primary-provider",
                fallback_provider_id="fallback-provider",
                fallback_model_id=None,
            )

    def test_update_fallback_target_rejects_self_reference(self):
        settings_repo = Mock()
        provider_repo = Mock()
        provider_repo.get_by_id.return_value = provider(
            provider_id="primary-provider",
            provider_type="primary-provider",
            name="Primary Provider",
            is_active=True,
            models=["primary-fixture-model"],
        )

        with pytest.raises(InputValidationError, match="self"):
            make_service(
                settings_repo=settings_repo, provider_repo=provider_repo
            ).update_fallback_target(
                provider_id="primary-provider",
                fallback_provider_id="primary-provider",
                fallback_model_id="primary-fixture-model",
            )

    def test_update_fallback_target_rejects_missing_or_disabled_target(self):
        settings_repo = Mock()
        provider_repo = Mock()
        source_provider = provider(
            provider_id="primary-provider",
            provider_type="primary-provider",
            name="Primary Provider",
            is_active=True,
            models=["primary-fixture-model"],
        )
        disabled_target = provider(
            provider_id="fallback-provider",
            provider_type="fallback-provider",
            name="Fallback Provider",
            is_active=False,
            models=["fallback-fixture-model"],
        )
        provider_repo.get_by_id.side_effect = lambda provider_id: {
            "primary-provider": source_provider,
            "fallback-provider": disabled_target,
        }.get(provider_id)

        settings_service = make_service(settings_repo=settings_repo, provider_repo=provider_repo)

        with pytest.raises(InputValidationError, match=r"provider:fallback-provider"):
            settings_service.update_fallback_target(
                provider_id="primary-provider",
                fallback_provider_id="fallback-provider",
                fallback_model_id="fallback-fixture-model",
            )

        provider_repo.get_by_id.side_effect = lambda provider_id: {
            "primary-provider": source_provider
        }.get(provider_id)
        with pytest.raises(ProviderNotFound, match=r"provider:fallback-provider"):
            settings_service.update_fallback_target(
                provider_id="primary-provider",
                fallback_provider_id="fallback-provider",
                fallback_model_id="fallback-fixture-model",
            )

    def test_update_fallback_target_rejects_model_not_owned_by_target(self):
        settings_repo = Mock()
        provider_repo = Mock()
        source_provider = provider(
            provider_id="primary-provider",
            provider_type="primary-provider",
            name="Primary Provider",
            is_active=True,
            models=["primary-fixture-model"],
        )
        target_provider = provider(
            provider_id="fallback-provider",
            provider_type="fallback-provider",
            name="Fallback Provider",
            is_active=True,
            models=["unowned-fixture-model"],
        )
        provider_repo.get_by_id.side_effect = lambda provider_id: {
            "primary-provider": source_provider,
            "fallback-provider": target_provider,
        }.get(provider_id)

        with pytest.raises(InputValidationError, match=r"provider:fallback-provider"):
            make_service(
                settings_repo=settings_repo, provider_repo=provider_repo
            ).update_fallback_target(
                provider_id="primary-provider",
                fallback_provider_id="fallback-provider",
                fallback_model_id="fallback-fixture-model",
            )

    def test_update_fallback_target_clears_mapping_when_both_fields_are_empty(self):
        settings_repo = Mock()
        provider_repo = Mock()
        source_provider = provider(
            provider_id="primary-provider",
            provider_type="primary-provider",
            name="Primary Provider",
            is_active=True,
            models=["primary-fixture-model"],
        )
        provider_repo.get_by_id.return_value = source_provider
        settings_repo.get_fallback_map.return_value = [
            fallback_entry(
                provider_id="primary-provider",
                fallback_provider_id="fallback-provider",
                fallback_model_id="fallback-fixture-model",
            )
        ]

        result = make_service(
            settings_repo=settings_repo, provider_repo=provider_repo
        ).update_fallback_target(
            provider_id="primary-provider",
            fallback_provider_id="",
            fallback_model_id="",
        )

        settings_repo.remove_fallback_target.assert_called_once_with("primary-provider")
        settings_repo.set_fallback_target.assert_not_called()
        assert result["fallback_provider_id"] is None
        assert result["fallback_model_id"] is None
