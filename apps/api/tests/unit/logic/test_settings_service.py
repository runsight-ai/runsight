"""Red tests for RUN-455: SettingsService model-default joins and router DI."""

import importlib
import inspect
from unittest.mock import Mock

from runsight_api.data.filesystem.provider_repo import FileSystemProviderRepo
from runsight_api.data.filesystem.settings_repo import FileSystemSettingsRepo
from runsight_api.domain.entities.settings import FallbackChainEntry, ModelDefaultEntry
from runsight_api.domain.value_objects import ProviderEntity
from runsight_api.transport import deps as deps_module


def _load_settings_service():
    module = importlib.import_module("runsight_api.logic.services.settings_service")
    return module.SettingsService


def _provider(*, provider_id: str, name: str, models: list[str]) -> ProviderEntity:
    return ProviderEntity(
        id=provider_id,
        name=name,
        type=provider_id,
        status="connected",
        models=models,
    )


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


class TestGetModelDefaults:
    def test_returns_empty_list_when_no_providers_exist(self):
        SettingsService = _load_settings_service()
        settings_repo = Mock(spec=FileSystemSettingsRepo)
        provider_repo = Mock(spec=FileSystemProviderRepo)
        provider_repo.list_all.return_value = []
        settings_repo.list_model_defaults.return_value = [
            ModelDefaultEntry(provider_id="deleted-provider", model_id="ghost-model")
        ]
        settings_repo.get_fallback_chain.return_value = [
            FallbackChainEntry(provider_id="deleted-provider", model_id="ghost-model")
        ]

        service = SettingsService(settings_repo, provider_repo)
        result = service.get_model_defaults()

        assert result == []
        provider_repo.list_all.assert_called_once_with()
        settings_repo.list_model_defaults.assert_called_once_with()
        settings_repo.get_fallback_chain.assert_called_once_with()

    def test_returns_first_available_model_or_empty_string_without_saved_defaults(self):
        SettingsService = _load_settings_service()
        settings_repo = Mock(spec=FileSystemSettingsRepo)
        provider_repo = Mock(spec=FileSystemProviderRepo)
        provider_repo.list_all.return_value = [
            _provider(provider_id="openai", name="OpenAI", models=["gpt-4.1", "gpt-4o"]),
            _provider(provider_id="untested", name="Untested", models=[]),
        ]
        settings_repo.list_model_defaults.return_value = []
        settings_repo.get_fallback_chain.return_value = []

        service = SettingsService(settings_repo, provider_repo)
        result = service.get_model_defaults()

        assert result == [
            {
                "id": "openai",
                "provider_id": "openai",
                "provider_name": "OpenAI",
                "model_name": "gpt-4.1",
                "is_default": False,
                "fallback_chain": [],
            },
            {
                "id": "untested",
                "provider_id": "untested",
                "provider_name": "Untested",
                "model_name": "",
                "is_default": False,
                "fallback_chain": [],
            },
        ]

    def test_joins_saved_defaults_and_filters_stale_provider_entries(self):
        SettingsService = _load_settings_service()
        settings_repo = Mock(spec=FileSystemSettingsRepo)
        provider_repo = Mock(spec=FileSystemProviderRepo)
        provider_repo.list_all.return_value = [
            _provider(provider_id="openai", name="OpenAI", models=["gpt-4.1", "gpt-4o"]),
            _provider(
                provider_id="anthropic",
                name="Anthropic",
                models=["claude-3-5-sonnet"],
            ),
        ]
        settings_repo.list_model_defaults.return_value = [
            ModelDefaultEntry(provider_id="openai", model_id="gpt-4o", is_default=True),
            ModelDefaultEntry(
                provider_id="deleted-provider",
                model_id="ghost-model",
                is_default=True,
            ),
        ]
        settings_repo.get_fallback_chain.return_value = [
            FallbackChainEntry(provider_id="openai", model_id="gpt-4o"),
            FallbackChainEntry(
                provider_id="anthropic",
                model_id="claude-3-5-sonnet",
            ),
            FallbackChainEntry(provider_id="deleted-provider", model_id="ghost-model"),
        ]

        service = SettingsService(settings_repo, provider_repo)
        result = service.get_model_defaults()

        assert result == [
            {
                "id": "openai",
                "provider_id": "openai",
                "provider_name": "OpenAI",
                "model_name": "gpt-4o",
                "is_default": True,
                "fallback_chain": ["gpt-4o", "claude-3-5-sonnet"],
            },
            {
                "id": "anthropic",
                "provider_id": "anthropic",
                "provider_name": "Anthropic",
                "model_name": "claude-3-5-sonnet",
                "is_default": False,
                "fallback_chain": ["gpt-4o", "claude-3-5-sonnet"],
            },
        ]
