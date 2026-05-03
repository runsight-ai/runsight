"""ProviderService test builders."""

from __future__ import annotations

from unittest.mock import Mock

from runsight_api.domain.value_objects import ProviderEntity
from runsight_api.logic.services.provider_service import ProviderService


def provider_entity(
    *,
    provider_id: str,
    name: str,
    provider_type: str,
    kind: str = "provider",
    api_key: str | None = None,
    base_url: str | None = None,
) -> ProviderEntity:
    return ProviderEntity(
        id=provider_id,
        kind=kind,
        name=name,
        type=provider_type,
        api_key=api_key,
        base_url=base_url,
    )


def provider_service(repo: Mock | None = None, secrets: Mock | None = None) -> ProviderService:
    return ProviderService(repo or Mock(), secrets or Mock())


def repo_and_secrets() -> tuple[Mock, Mock]:
    return Mock(), Mock()


def provider_create_side_effect(data: dict) -> ProviderEntity:
    return ProviderEntity(
        id=data["id"],
        kind=data["kind"],
        name=data["name"],
        type=data["type"],
        api_key=data.get("api_key"),
        base_url=data.get("base_url"),
    )


def provider_identity_side_effect(data: dict) -> ProviderEntity:
    return ProviderEntity(
        id=data["id"],
        kind=data["kind"],
        name=data["name"],
        type=data["type"],
    )
