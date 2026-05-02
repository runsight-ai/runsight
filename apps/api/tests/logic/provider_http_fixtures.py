"""Provider HTTP test fixtures."""

from __future__ import annotations

import importlib
from contextlib import contextmanager
from unittest.mock import AsyncMock, Mock, patch

import pytest

from runsight_api.domain.value_objects import ProviderEntity
from runsight_api.logic.services.provider_service import ProviderService


def make_provider(
    *,
    provider_id: str = "prov_async_health",
    name: str = "Test Provider",
    provider_type: str = "openai",
    api_key: str | None = "configured_key",
    base_url: str | None = None,
) -> ProviderEntity:
    return ProviderEntity(
        id=provider_id,
        kind="provider",
        name=name,
        type=provider_type,
        api_key=api_key,
        base_url=base_url,
    )


def make_service(provider: ProviderEntity) -> ProviderService:
    repo = Mock()
    repo.get_by_id.return_value = provider
    repo.update.return_value = provider
    secrets = Mock()
    secrets.is_configured.return_value = bool(provider.api_key)
    secrets.resolve.return_value = "dummy-xxx"
    return ProviderService(repo, secrets)


def provider_service_source() -> str:
    """Read the source code of provider_service.py."""
    spec = importlib.util.find_spec("runsight_api.logic.services.provider_service")
    assert spec and spec.origin, "Cannot locate provider_service.py"
    with open(spec.origin) as f:
        return f.read()


@pytest.fixture(autouse=True, name="_mock_ssrf_validation")
def mock_ssrf_validation():
    """Keep async HTTP client tests isolated from live DNS resolution."""
    with patch(
        "runsight_api.logic.services.provider_service.validate_ssrf",
        new_callable=AsyncMock,
    ) as mock_validate:
        yield mock_validate


def async_response(*, status_code: int = 200, json_data: dict | None = None) -> Mock:
    response = Mock()
    response.status_code = status_code
    if json_data is not None:
        response.json.return_value = json_data
    return response


def async_http_client(response: Mock | None = None) -> AsyncMock:
    client = AsyncMock()
    if response is not None:
        client.get.return_value = response
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


@contextmanager
def patched_provider_httpx(client: AsyncMock):
    with patch("runsight_api.logic.services.provider_service.httpx") as mock_httpx:
        mock_httpx.AsyncClient.return_value = client
        mock_httpx.get.side_effect = AssertionError(
            "Sync httpx.get() was called - must use httpx.AsyncClient"
        )
        yield mock_httpx
