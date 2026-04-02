"""RUN-548 red tests for the backend settings service foundation."""

from __future__ import annotations

import importlib
import inspect
from typing import Any
from unittest.mock import Mock, call

import pytest

from runsight_api.data.filesystem.provider_repo import FileSystemProviderRepo
from runsight_api.data.filesystem.settings_repo import FileSystemSettingsRepo
from runsight_api.domain.entities.settings import FallbackTargetEntry, ModelDefaultEntry
from runsight_api.domain.errors import InputValidationError, ProviderNotFound
from runsight_api.domain.value_objects import ProviderEntity
from runsight_api.transport import deps as deps_module


def _load_settings_service_module():
    return importlib.import_module("runsight_api.logic.services.settings_service")


def _load_settings_service():
    return _load_settings_service_module().SettingsService


def _provider(
    *,
    provider_id: str,
    provider_type: str,
    name: str,
    is_active: bool,
    models: list[str] | None = None,
    status: str = "connected",
) -> ProviderEntity:
    return ProviderEntity(
        id=provider_id,
        type=provider_type,
        name=name,
        status=status,
        is_active=is_active,
        models=models or [],
    )


def _service(*, settings_repo: Any, provider_repo: Any):
    SettingsService = _load_settings_service()
    return SettingsService(settings_repo=settings_repo, provider_repo=provider_repo)


class TestSettingsServiceConstructor:
    def test_constructor_accepts_settings_repo_and_provider_repo(self):
        SettingsService = _load_settings_service()
        signature = inspect.signature(SettingsService.__init__)

        assert list(signature.parameters) == [
            "self",
            "settings_repo",
            "provider_repo",
        ]

    def test_get_settings_service_returns_settings_service(self):
        assert hasattr(deps_module, "get_settings_service"), (
            "deps.get_settings_service must exist to build SettingsService"
        )

        SettingsService = _load_settings_service()
        settings_repo = Mock(spec=FileSystemSettingsRepo)
        provider_repo = Mock(spec=FileSystemProviderRepo)

        service = deps_module.get_settings_service(
            settings_repo=settings_repo,
            provider_repo=provider_repo,
        )

        assert isinstance(service, SettingsService)


class TestFallbackFoundation:
    def test_settings_service_imports_fallback_target_entry_not_legacy_fallback_entry(self):
        module = _load_settings_service_module()
        source = inspect.getsource(module)

        assert "FallbackTargetEntry" in source
        assert "FallbackChainEntry" not in source

    def test_settings_service_uses_fallback_map_repo_methods(self):
        module = _load_settings_service_module()
        source = inspect.getsource(module)

        assert "get_fallback_map" in source
        assert "get_fallback_chain" not in source
        assert "update_fallback_chain" not in source

    def test_update_model_default_signature_uses_per_provider_fallback_fields(self):
        SettingsService = _load_settings_service()
        signature = inspect.signature(SettingsService.update_model_default)

        assert list(signature.parameters) == [
            "self",
            "provider_id",
            "model_name",
            "is_default",
            "fallback_provider_id",
            "fallback_model_id",
        ]

    def test_settings_service_removes_legacy_fallback_helper_names(self):
        module = _load_settings_service_module()
        source = inspect.getsource(module)

        assert "fallback_chain" not in source
        assert "_fallback_chain_for_provider" not in source
        assert "_fallback_chain_from_target" not in source


class TestSettingsServiceReadFallbackTargets:
    def test_get_model_defaults_returns_per_provider_fallback_fields_and_allows_circular_reads(
        self,
    ):
        settings_repo = Mock()
        provider_repo = Mock()
        provider_repo.list_all.return_value = [
            _provider(
                provider_id="openai",
                provider_type="openai",
                name="OpenAI",
                is_active=True,
                models=["gpt-4o"],
                status="connection_failed",
            ),
            _provider(
                provider_id="anthropic",
                provider_type="anthropic",
                name="Anthropic",
                is_active=True,
                models=["claude-sonnet-4"],
            ),
            _provider(
                provider_id="google",
                provider_type="google",
                name="Google",
                is_active=False,
                models=["gemini-2.5-pro"],
            ),
        ]
        settings_repo.list_model_defaults.return_value = [
            ModelDefaultEntry(provider_id="openai", model_id="gpt-4o", is_default=True),
            ModelDefaultEntry(
                provider_id="anthropic",
                model_id="claude-sonnet-4",
                is_default=False,
            ),
            ModelDefaultEntry(
                provider_id="google",
                model_id="gemini-2.5-pro",
                is_default=False,
            ),
        ]
        settings_repo.get_fallback_map.return_value = [
            FallbackTargetEntry(
                provider_id="openai",
                fallback_provider_id="anthropic",
                fallback_model_id="claude-sonnet-4",
            ),
            FallbackTargetEntry(
                provider_id="anthropic",
                fallback_provider_id="openai",
                fallback_model_id="gpt-4o",
            ),
            FallbackTargetEntry(
                provider_id="google",
                fallback_provider_id="openai",
                fallback_model_id="gpt-4o",
            ),
        ]

        result = _service(
            settings_repo=settings_repo, provider_repo=provider_repo
        ).get_model_defaults()

        assert result == [
            {
                "id": "openai",
                "provider_id": "openai",
                "provider_name": "OpenAI",
                "model_name": "gpt-4o",
                "is_default": True,
                "fallback_provider_id": "anthropic",
                "fallback_model_id": "claude-sonnet-4",
            },
            {
                "id": "anthropic",
                "provider_id": "anthropic",
                "provider_name": "Anthropic",
                "model_name": "claude-sonnet-4",
                "is_default": False,
                "fallback_provider_id": "openai",
                "fallback_model_id": "gpt-4o",
            },
        ]

    def test_get_model_defaults_suppresses_missing_or_disabled_targets_without_dropping_rows(self):
        settings_repo = Mock()
        provider_repo = Mock()
        stored_fallback_map = [
            FallbackTargetEntry(
                provider_id="openai",
                fallback_provider_id="google",
                fallback_model_id="gemini-2.5-pro",
            ),
            FallbackTargetEntry(
                provider_id="missing-target",
                fallback_provider_id="openai",
                fallback_model_id="gpt-4o",
            ),
        ]
        provider_repo.list_all.return_value = [
            _provider(
                provider_id="openai",
                provider_type="openai",
                name="OpenAI",
                is_active=True,
                models=["gpt-4o"],
            ),
            _provider(
                provider_id="google",
                provider_type="google",
                name="Google",
                is_active=False,
                models=["gemini-2.5-pro"],
            ),
        ]
        settings_repo.list_model_defaults.return_value = [
            ModelDefaultEntry(provider_id="openai", model_id="gpt-4o", is_default=True),
        ]
        settings_repo.get_fallback_map.return_value = stored_fallback_map

        result = _service(
            settings_repo=settings_repo, provider_repo=provider_repo
        ).get_model_defaults()

        assert result == [
            {
                "id": "openai",
                "provider_id": "openai",
                "provider_name": "OpenAI",
                "model_name": "gpt-4o",
                "is_default": True,
                "fallback_provider_id": None,
                "fallback_model_id": None,
            }
        ]
        assert settings_repo.get_fallback_map.return_value == stored_fallback_map
        settings_repo.set_fallback_target.assert_not_called()
        settings_repo.remove_fallback_target.assert_not_called()

    def test_get_model_defaults_returns_stored_fallback_model_when_target_model_was_removed_later(
        self,
    ):
        settings_repo = Mock()
        provider_repo = Mock()
        provider_repo.list_all.return_value = [
            _provider(
                provider_id="openai",
                provider_type="openai",
                name="OpenAI",
                is_active=True,
                models=["gpt-4o"],
            ),
            _provider(
                provider_id="anthropic",
                provider_type="anthropic",
                name="Anthropic",
                is_active=True,
                models=["claude-3-opus"],
            ),
        ]
        settings_repo.list_model_defaults.return_value = [
            ModelDefaultEntry(provider_id="openai", model_id="gpt-4o", is_default=True),
        ]
        settings_repo.get_fallback_map.return_value = [
            FallbackTargetEntry(
                provider_id="openai",
                fallback_provider_id="anthropic",
                fallback_model_id="claude-sonnet-4",
            ),
        ]

        result = _service(
            settings_repo=settings_repo, provider_repo=provider_repo
        ).get_model_defaults()

        assert result == [
            {
                "id": "openai",
                "provider_id": "openai",
                "provider_name": "OpenAI",
                "model_name": "gpt-4o",
                "is_default": True,
                "fallback_provider_id": "anthropic",
                "fallback_model_id": "claude-sonnet-4",
            }
        ]


class TestSettingsServiceUpdateFallbackTargets:
    def test_update_model_default_persists_valid_fallback_target_and_returns_fields(self):
        settings_repo = Mock()
        provider_repo = Mock()
        source_provider = _provider(
            provider_id="openai",
            provider_type="openai",
            name="OpenAI",
            is_active=True,
            models=["gpt-4o"],
        )
        target_provider = _provider(
            provider_id="anthropic",
            provider_type="anthropic",
            name="Anthropic",
            is_active=True,
            models=["claude-sonnet-4"],
        )
        provider_repo.get_by_id.side_effect = lambda provider_id: {
            "openai": source_provider,
            "anthropic": target_provider,
        }.get(provider_id)
        settings_repo.list_model_defaults.return_value = [
            ModelDefaultEntry(provider_id="openai", model_id="gpt-4o", is_default=True),
        ]
        settings_repo.get_fallback_map.return_value = []
        settings_repo.set_fallback_target.side_effect = lambda entry: entry

        service = _service(settings_repo=settings_repo, provider_repo=provider_repo)
        result = service.update_model_default(
            provider_id="openai",
            model_name="gpt-4o",
            is_default=True,
            fallback_provider_id="anthropic",
            fallback_model_id="claude-sonnet-4",
        )

        settings_repo.set_fallback_target.assert_called_once_with(
            FallbackTargetEntry(
                provider_id="openai",
                fallback_provider_id="anthropic",
                fallback_model_id="claude-sonnet-4",
            )
        )
        settings_repo.remove_fallback_target.assert_not_called()
        assert result["fallback_provider_id"] == "anthropic"
        assert result["fallback_model_id"] == "claude-sonnet-4"

    def test_update_model_default_allows_target_provider_with_connection_failure_status(self):
        settings_repo = Mock()
        provider_repo = Mock()
        source_provider = _provider(
            provider_id="openai",
            provider_type="openai",
            name="OpenAI",
            is_active=True,
            models=["gpt-4o"],
        )
        target_provider = _provider(
            provider_id="anthropic",
            provider_type="anthropic",
            name="Anthropic",
            is_active=True,
            models=["claude-sonnet-4"],
            status="connection_failed",
        )
        provider_repo.get_by_id.side_effect = lambda provider_id: {
            "openai": source_provider,
            "anthropic": target_provider,
        }.get(provider_id)
        settings_repo.list_model_defaults.return_value = [
            ModelDefaultEntry(provider_id="openai", model_id="gpt-4o", is_default=True),
        ]
        settings_repo.get_fallback_map.return_value = []
        settings_repo.set_fallback_target.side_effect = lambda entry: entry

        service = _service(settings_repo=settings_repo, provider_repo=provider_repo)
        result = service.update_model_default(
            provider_id="openai",
            model_name="gpt-4o",
            is_default=True,
            fallback_provider_id="anthropic",
            fallback_model_id="claude-sonnet-4",
        )

        settings_repo.set_fallback_target.assert_called_once_with(
            FallbackTargetEntry(
                provider_id="openai",
                fallback_provider_id="anthropic",
                fallback_model_id="claude-sonnet-4",
            )
        )
        assert result["fallback_provider_id"] == "anthropic"
        assert result["fallback_model_id"] == "claude-sonnet-4"

    def test_update_model_default_allows_circular_fallback_mappings(self):
        settings_repo = Mock()
        provider_repo = Mock()
        openai_provider = _provider(
            provider_id="openai",
            provider_type="openai",
            name="OpenAI",
            is_active=True,
            models=["gpt-4o"],
        )
        anthropic_provider = _provider(
            provider_id="anthropic",
            provider_type="anthropic",
            name="Anthropic",
            is_active=True,
            models=["claude-sonnet-4"],
        )
        provider_repo.get_by_id.side_effect = lambda provider_id: {
            "openai": openai_provider,
            "anthropic": anthropic_provider,
        }.get(provider_id)
        settings_repo.list_model_defaults.return_value = [
            ModelDefaultEntry(provider_id="openai", model_id="gpt-4o", is_default=True),
            ModelDefaultEntry(
                provider_id="anthropic",
                model_id="claude-sonnet-4",
                is_default=False,
            ),
        ]
        settings_repo.get_fallback_map.return_value = []
        settings_repo.set_fallback_target.side_effect = lambda entry: entry

        service = _service(settings_repo=settings_repo, provider_repo=provider_repo)
        first = service.update_model_default(
            provider_id="openai",
            model_name="gpt-4o",
            is_default=True,
            fallback_provider_id="anthropic",
            fallback_model_id="claude-sonnet-4",
        )
        second = service.update_model_default(
            provider_id="anthropic",
            model_name="claude-sonnet-4",
            is_default=False,
            fallback_provider_id="openai",
            fallback_model_id="gpt-4o",
        )

        assert settings_repo.set_fallback_target.call_args_list == [
            call(
                FallbackTargetEntry(
                    provider_id="openai",
                    fallback_provider_id="anthropic",
                    fallback_model_id="claude-sonnet-4",
                )
            ),
            call(
                FallbackTargetEntry(
                    provider_id="anthropic",
                    fallback_provider_id="openai",
                    fallback_model_id="gpt-4o",
                )
            ),
        ]
        assert first["fallback_provider_id"] == "anthropic"
        assert first["fallback_model_id"] == "claude-sonnet-4"
        assert second["fallback_provider_id"] == "openai"
        assert second["fallback_model_id"] == "gpt-4o"

    def test_update_model_default_rejects_partial_fallback_updates(self):
        settings_repo = Mock()
        provider_repo = Mock()
        provider_repo.get_by_id.side_effect = lambda provider_id: {
            "openai": _provider(
                provider_id="openai",
                provider_type="openai",
                name="OpenAI",
                is_active=True,
                models=["gpt-4o"],
            )
        }.get(provider_id)

        service = _service(settings_repo=settings_repo, provider_repo=provider_repo)

        with pytest.raises(InputValidationError, match="fallback_provider_id.*fallback_model_id"):
            service.update_model_default(
                provider_id="openai",
                model_name="gpt-4o",
                is_default=True,
                fallback_provider_id="anthropic",
                fallback_model_id=None,
            )

    def test_update_model_default_rejects_self_referencing_fallback_target(self):
        settings_repo = Mock()
        provider_repo = Mock()
        source_provider = _provider(
            provider_id="openai",
            provider_type="openai",
            name="OpenAI",
            is_active=True,
            models=["gpt-4o"],
        )
        provider_repo.get_by_id.side_effect = lambda provider_id: {
            "openai": source_provider,
        }.get(provider_id)

        service = _service(settings_repo=settings_repo, provider_repo=provider_repo)

        with pytest.raises(InputValidationError, match="self"):
            service.update_model_default(
                provider_id="openai",
                model_name="gpt-4o",
                is_default=True,
                fallback_provider_id="openai",
                fallback_model_id="gpt-4o",
            )

    def test_update_model_default_raises_provider_not_found_for_missing_target_provider(self):
        settings_repo = Mock()
        provider_repo = Mock()
        source_provider = _provider(
            provider_id="openai",
            provider_type="openai",
            name="OpenAI",
            is_active=True,
            models=["gpt-4o"],
        )
        provider_repo.get_by_id.side_effect = lambda provider_id: {
            "openai": source_provider,
        }.get(provider_id)

        service = _service(settings_repo=settings_repo, provider_repo=provider_repo)

        with pytest.raises(ProviderNotFound, match="anthropic"):
            service.update_model_default(
                provider_id="openai",
                model_name="gpt-4o",
                is_default=True,
                fallback_provider_id="anthropic",
                fallback_model_id="claude-sonnet-4",
            )

    def test_update_model_default_rejects_disabled_target_provider(self):
        settings_repo = Mock()
        provider_repo = Mock()
        source_provider = _provider(
            provider_id="openai",
            provider_type="openai",
            name="OpenAI",
            is_active=True,
            models=["gpt-4o"],
        )
        disabled_target = _provider(
            provider_id="anthropic",
            provider_type="anthropic",
            name="Anthropic",
            is_active=False,
            models=["claude-sonnet-4"],
        )
        provider_repo.get_by_id.side_effect = lambda provider_id: {
            "openai": source_provider,
            "anthropic": disabled_target,
        }.get(provider_id)

        service = _service(settings_repo=settings_repo, provider_repo=provider_repo)

        with pytest.raises(InputValidationError, match="disabled"):
            service.update_model_default(
                provider_id="openai",
                model_name="gpt-4o",
                is_default=True,
                fallback_provider_id="anthropic",
                fallback_model_id="claude-sonnet-4",
            )

    def test_update_model_default_rejects_target_model_not_owned_by_provider(self):
        settings_repo = Mock()
        provider_repo = Mock()
        source_provider = _provider(
            provider_id="openai",
            provider_type="openai",
            name="OpenAI",
            is_active=True,
            models=["gpt-4o"],
        )
        target_provider = _provider(
            provider_id="anthropic",
            provider_type="anthropic",
            name="Anthropic",
            is_active=True,
            models=["claude-3-opus"],
        )
        provider_repo.get_by_id.side_effect = lambda provider_id: {
            "openai": source_provider,
            "anthropic": target_provider,
        }.get(provider_id)

        service = _service(settings_repo=settings_repo, provider_repo=provider_repo)

        with pytest.raises(InputValidationError, match="claude-sonnet-4"):
            service.update_model_default(
                provider_id="openai",
                model_name="gpt-4o",
                is_default=True,
                fallback_provider_id="anthropic",
                fallback_model_id="claude-sonnet-4",
            )

    def test_update_model_default_clears_fallback_target_when_provider_id_is_empty_string(self):
        settings_repo = Mock()
        provider_repo = Mock()
        source_provider = _provider(
            provider_id="openai",
            provider_type="openai",
            name="OpenAI",
            is_active=True,
            models=["gpt-4o"],
        )
        provider_repo.get_by_id.side_effect = lambda provider_id: {
            "openai": source_provider,
        }.get(provider_id)
        settings_repo.list_model_defaults.return_value = [
            ModelDefaultEntry(provider_id="openai", model_id="gpt-4o", is_default=True),
        ]
        settings_repo.get_fallback_map.return_value = [
            FallbackTargetEntry(
                provider_id="openai",
                fallback_provider_id="anthropic",
                fallback_model_id="claude-sonnet-4",
            )
        ]

        service = _service(settings_repo=settings_repo, provider_repo=provider_repo)
        result = service.update_model_default(
            provider_id="openai",
            model_name="gpt-4o",
            is_default=True,
            fallback_provider_id="",
            fallback_model_id="",
        )

        settings_repo.remove_fallback_target.assert_called_once_with("openai")
        settings_repo.set_fallback_target.assert_not_called()
        assert result["fallback_provider_id"] is None
        assert result["fallback_model_id"] is None
