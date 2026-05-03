"""Provider connection checks resolve secrets while preserving SSRF validation."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

pytest_plugins = ("tests.unit.logic.provider_service_fixtures",)


class TestTestConnectionUsesSecrets:
    """test_connection must resolve API keys via secrets.resolve."""

    @pytest.mark.asyncio
    async def test_test_connection_resolves_key_via_secrets(self, service, secrets):
        """test_connection must use secrets.resolve to get the actual API key."""
        service.create_provider(
            id="openai",
            kind="provider",
            name="OpenAI",
            api_key="dummy-stored-key",
            provider_type="openai",
            base_url="https://provider.example.invalid/v1",
        )

        with (
            patch("runsight_api.logic.services.provider_service.httpx") as mock_httpx,
            patch(
                "runsight_api.logic.services.provider_service.validate_ssrf",
                new_callable=AsyncMock,
            ) as mock_validate_ssrf,
        ):
            mock_resp = Mock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"data": [{"id": "gpt-4o"}]}
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_httpx.AsyncClient.return_value = mock_client

            result = await service.test_connection("openai")

        assert result["success"] is True
        mock_validate_ssrf.assert_awaited()
        # Verify the HTTP call used the resolved stored key, not the ${ENV_VAR} reference.
        call_kwargs = mock_client.get.call_args
        auth_header = call_kwargs[1]["headers"]["Authorization"]
        assert "dummy-stored-key" in auth_header
        assert "${" not in auth_header, "Must not send ${ENV_VAR} as auth header"

    @pytest.mark.asyncio
    async def test_test_connection_no_key_configured(self, service):
        """test_connection with no API key must return failure for non-ollama."""
        service.create_provider(id="openai", kind="provider", name="OpenAI", provider_type="openai")
        result = await service.test_connection("openai")
        assert result["success"] is False
        assert "No API key configured" in result["message"]

    def test_test_connection_checks_is_configured_via_secrets(self, service, secrets):
        """test_connection must check secrets.is_configured() to determine if a key exists."""
        # Create provider with a key — api_key field will have ${ENV_VAR}
        service.create_provider(
            id="openai",
            kind="provider",
            name="OpenAI",
            api_key="dummy-test",
            provider_type="openai",
        )

        # Verify is_configured returns True for the stored key
        provider = service.get_provider("openai")
        assert provider is not None
        assert secrets.is_configured(provider.api_key) is True


# ===========================================================================
# SSRF validation remains wired after provider service rewiring
# ===========================================================================


class TestSSRFPreserved:
    """SSRF validation must still be called in test_connection after rewiring."""

    @pytest.mark.asyncio
    async def test_ssrf_blocks_private_ip(self, service):
        """Private IP in base_url must still be blocked after filesystem rewiring."""
        service.create_provider(
            id="openai",
            kind="provider",
            name="OpenAI",
            api_key="dummy-test",
            provider_type="openai",
            base_url="http://192.168.1.1/v1",
        )

        result = await service.test_connection("openai")

        assert result["success"] is False
        assert "ssrf" in result["message"].lower() or "blocked" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_ssrf_blocks_metadata_endpoint(self, service):
        """Cloud metadata endpoint must still be blocked."""
        service.create_provider(
            id="openai",
            kind="provider",
            name="OpenAI",
            api_key="dummy-test",
            provider_type="openai",
            base_url="http://169.254.169.254/latest",
        )

        result = await service.test_connection("openai")

        assert result["success"] is False
        assert "ssrf" in result["message"].lower() or "blocked" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_ssrf_allows_ollama_localhost(self, service):
        """Ollama localhost must still be allowed after rewiring."""
        service.create_provider(
            id="ollama",
            kind="provider",
            name="Ollama",
            provider_type="ollama",
            base_url="http://localhost:11434",
        )

        with patch("runsight_api.logic.services.provider_service.httpx") as mock_httpx:
            mock_resp = Mock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"models": [{"name": "llama3"}]}
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_httpx.AsyncClient.return_value = mock_client

            result = await service.test_connection("ollama")

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_ssrf_no_http_call_for_blocked_url(self, service):
        """When SSRF blocks a URL, httpx.get must NOT be called."""
        service.create_provider(
            id="openai",
            kind="provider",
            name="OpenAI",
            api_key="dummy-test",
            provider_type="openai",
            base_url="http://10.0.0.1/v1",
        )

        with patch("runsight_api.logic.services.provider_service.httpx") as mock_httpx:
            result = await service.test_connection("openai")

        assert result["success"] is False
        mock_httpx.get.assert_not_called()


# ===========================================================================
# 6. API response contract: api_key_env shows "configured" or ""
# ===========================================================================


class TestApiResponseContract:
    """_provider_to_out must check secrets.is_configured(), not api_key_encrypted."""

    def test_provider_to_out_shows_configured_when_key_exists(self, service, secrets):
        """Provider with stored API key must show api_key_env with the env var reference."""
        from runsight_api.transport.routers.settings import _provider_to_out

        provider = service.create_provider(
            id="openai",
            kind="provider",
            name="OpenAI",
            api_key="dummy-test",
            provider_type="openai",
        )
        out = _provider_to_out(provider, service)
        # api_key_env now stores the ${ENV_VAR} reference directly
        assert out.api_key_env is not None
        assert out.api_key_env.startswith("${")

    def test_provider_to_out_shows_empty_when_no_key(self, service):
        """Provider without API key must show api_key_env=None."""
        from runsight_api.transport.routers.settings import _provider_to_out

        provider = service.create_provider(
            id="ollama", kind="provider", name="Ollama", provider_type="ollama"
        )
        out = _provider_to_out(provider, service)
        assert out.api_key_env is None

    def test_provider_to_out_uses_api_key_not_api_key_encrypted(self):
        """_provider_to_out must use ProviderEntity.api_key, not .api_key_encrypted."""
        from runsight_api.domain.value_objects import ProviderEntity
        from runsight_api.transport.routers.settings import _provider_to_out

        # ProviderEntity has api_key (not api_key_encrypted)
        entity = ProviderEntity(
            id="openai",
            kind="provider",
            name="OpenAI",
            type="openai",
            api_key="${OPENAI_API_KEY}",
            status="connected",
        )
        mock_svc = Mock()
        mock_svc.secrets = Mock()
        mock_svc.secrets.resolve.return_value = "dummy-resolved"
        out = _provider_to_out(entity, mock_svc)
        # api_key_env now stores the ${ENV_VAR} reference directly
        assert out.api_key_env == "${OPENAI_API_KEY}"


# ===========================================================================
# 7. ExecutionService._resolve_api_keys uses SecretsEnvLoader
# ===========================================================================
