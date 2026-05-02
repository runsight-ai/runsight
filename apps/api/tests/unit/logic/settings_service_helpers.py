"""Settings service fixture builders."""

from __future__ import annotations

import importlib
from typing import Any

from runsight_api.domain.entities.settings import FallbackTargetEntry
from runsight_api.domain.value_objects import ProviderEntity

PRIMARY_PROVIDER_ID = "primary-provider"
FALLBACK_PROVIDER_ID = "fallback-provider"
DISABLED_PROVIDER_ID = "disabled-provider"
MISSING_PROVIDER_ID = "missing-provider"
PRIMARY_MODEL_ID = "primary-fixture-model"
FALLBACK_MODEL_ID = "fallback-fixture-model"
DISABLED_MODEL_ID = "disabled-fixture-model"
UNOWNED_MODEL_ID = "unowned-fixture-model"


def load_settings_service_module():
    return importlib.import_module("runsight_api.logic.services.settings_service")


def load_settings_service():
    return load_settings_service_module().SettingsService


def provider(
    *,
    provider_id: str,
    provider_type: str | None = None,
    name: str | None = None,
    is_active: bool = True,
    models: list[str] | None = None,
    status: str = "connected",
) -> ProviderEntity:
    return ProviderEntity(
        id=provider_id,
        kind="provider",
        type=provider_type or provider_id,
        name=name or provider_id.replace("-", " ").title(),
        status=status,
        is_active=is_active,
        models=models or [],
    )


def fallback_entry(**overrides) -> FallbackTargetEntry:
    payload = {
        "provider_id": PRIMARY_PROVIDER_ID,
        "fallback_provider_id": FALLBACK_PROVIDER_ID,
        "fallback_model_id": FALLBACK_MODEL_ID,
    }
    payload.update(overrides)
    return FallbackTargetEntry(**payload)


def service(*, settings_repo: Any, provider_repo: Any):
    return load_settings_service()(settings_repo=settings_repo, provider_repo=provider_repo)
