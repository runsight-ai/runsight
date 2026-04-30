from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from runsight_api.domain.entities.settings import FallbackTargetEntry
from runsight_api.domain.errors import InputValidationError
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
        kind="provider",
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
            SimpleNamespace(
                provider="primary-provider", model_id="primary-fixture-model", mode="chat"
            ),
            SimpleNamespace(
                provider="backup-provider", model_id="backup-fixture-model", mode="chat"
            ),
        ]
        provider_repo = Mock()
        provider_repo.list_all.return_value = [
            _provider(
                provider_id="primary-provider",
                provider_type="primary-provider",
                name="Primary Provider",
                is_active=True,
            ),
            _provider(
                provider_id="backup-provider",
                provider_type="backup-provider",
                name="Backup Provider",
                is_active=False,
            ),
        ]

        service = ModelService(catalog=catalog, provider_repo=provider_repo)

        result = service.get_available_models()

        assert [model.provider for model in result] == ["primary-provider"]


class TestSettingsServiceDisabledProviders:
    def test_omits_inactive_source_rows_and_suppresses_disabled_targets(self):
        settings_repo = Mock()
        provider_repo = Mock()
        provider_repo.list_all.return_value = [
            _provider(
                provider_id="primary-provider",
                provider_type="primary-provider",
                name="Primary Provider",
                is_active=True,
                models=["primary-fixture-model"],
            ),
            _provider(
                provider_id="backup-provider",
                provider_type="backup-provider",
                name="Backup Provider",
                is_active=False,
                models=["backup-fixture-model"],
            ),
        ]
        settings_repo.get_fallback_map.return_value = [
            FallbackTargetEntry(
                provider_id="primary-provider",
                fallback_provider_id="backup-provider",
                fallback_model_id="backup-fixture-model",
            ),
            FallbackTargetEntry(
                provider_id="backup-provider",
                fallback_provider_id="primary-provider",
                fallback_model_id="primary-fixture-model",
            ),
        ]

        service = SettingsService(settings_repo=settings_repo, provider_repo=provider_repo)

        result = service.get_fallback_targets()

        assert result == [
            {
                "id": "primary-provider",
                "provider_id": "primary-provider",
                "provider_name": "Primary Provider",
                "fallback_provider_id": None,
                "fallback_model_id": None,
            }
        ]

    def test_update_fallback_target_rejects_inactive_source_provider(self):
        settings_repo = Mock()
        provider_repo = Mock()
        provider_repo.get_by_id.return_value = _provider(
            provider_id="backup-provider",
            provider_type="backup-provider",
            name="Backup Provider",
            is_active=False,
            models=["backup-fixture-model"],
        )

        service = SettingsService(settings_repo=settings_repo, provider_repo=provider_repo)

        with pytest.raises(InputValidationError, match="disabled"):
            service.update_fallback_target(
                provider_id="backup-provider",
                fallback_provider_id="primary-provider",
                fallback_model_id="primary-fixture-model",
            )


class TestExecutionServiceDisabledProviders:
    def test_resolve_api_keys_skips_inactive_provider_env_fallback(self):
        provider_repo = Mock()
        provider_repo.list_all.return_value = [
            _provider(
                provider_id="primary-provider",
                # The provider type is behavior-bearing: env fallback is hard-coded
                # for openai/anthropic and must be skipped when that type is disabled.
                provider_type="openai",
                name="Primary Provider",
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

        with patch.dict("os.environ", {"OPENAI_API_KEY": "dummy-disabled-openai-key"}, clear=True):
            result = service._resolve_api_keys()

        assert "openai" not in result
