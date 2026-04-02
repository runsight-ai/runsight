from types import SimpleNamespace
from unittest.mock import Mock, patch

from runsight_api.domain.entities.settings import ModelDefaultEntry
from runsight_api.domain.value_objects import ProviderEntity
from runsight_api.logic.services.execution_service import ExecutionService
from runsight_api.logic.services.model_service import ModelService
from runsight_api.logic.services.settings_service import SettingsService


def _provider(
    *,
    provider_id: str,
    provider_type: str,
    name: str,
    is_active: bool,
    models: list[str] | None = None,
    api_key: str | None = None,
) -> ProviderEntity:
    return ProviderEntity(
        id=provider_id,
        type=provider_type,
        name=name,
        status="connected",
        is_active=is_active,
        models=models or [],
        api_key=api_key,
    )


class TestModelServiceDisabledProviders:
    def test_excludes_inactive_providers_from_available_models(self):
        catalog = Mock()
        catalog.get_models.return_value = [
            SimpleNamespace(provider="openai", model_id="gpt-4o", mode="chat"),
            SimpleNamespace(provider="anthropic", model_id="claude-sonnet-4", mode="chat"),
        ]
        provider_repo = Mock()
        provider_repo.list_all.return_value = [
            _provider(
                provider_id="openai",
                provider_type="openai",
                name="OpenAI",
                is_active=True,
            ),
            _provider(
                provider_id="anthropic",
                provider_type="anthropic",
                name="Anthropic",
                is_active=False,
            ),
        ]

        service = ModelService(catalog=catalog, provider_repo=provider_repo)

        result = service.get_available_models()

        assert [model.provider for model in result] == ["openai"]


class TestSettingsServiceDisabledProviders:
    def test_omits_inactive_providers_from_model_defaults_and_fallback_chain(self):
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
                is_active=False,
                models=["claude-sonnet-4"],
            ),
        ]
        settings_repo.list_model_defaults.return_value = [
            ModelDefaultEntry(provider_id="openai", model_id="gpt-4o", is_default=True),
            ModelDefaultEntry(
                provider_id="anthropic",
                model_id="claude-sonnet-4",
                is_default=False,
            ),
        ]
        settings_repo.get_fallback_chain.return_value = [
            SimpleNamespace(provider_id="openai", model_id="gpt-4o"),
            SimpleNamespace(provider_id="anthropic", model_id="claude-sonnet-4"),
        ]

        service = SettingsService(settings_repo=settings_repo, provider_repo=provider_repo)

        result = service.get_model_defaults()

        assert result == [
            {
                "id": "openai",
                "provider_id": "openai",
                "provider_name": "OpenAI",
                "model_name": "gpt-4o",
                "is_default": True,
                "fallback_chain": ["gpt-4o"],
            }
        ]


class TestExecutionServiceDisabledProviders:
    def test_resolve_api_keys_skips_inactive_provider_env_fallback(self):
        provider_repo = Mock()
        provider_repo.list_all.return_value = [
            _provider(
                provider_id="openai",
                provider_type="openai",
                name="OpenAI",
                is_active=False,
                api_key=None,
            )
        ]
        secrets = Mock()
        service = ExecutionService(
            run_repo=Mock(),
            workflow_repo=Mock(),
            provider_repo=provider_repo,
            secrets=secrets,
        )

        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-env-disabled"}, clear=False):
            result = service._resolve_api_keys()

        assert "openai" not in result
