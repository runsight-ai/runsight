"""Tests for SSRF protection in ProviderService.test_connection().

RUN-225: The provider_service uses user-supplied base_url directly in
httpx.get() calls without SSRF validation. These tests verify that:
- Private IPs, loopback, link-local, and cloud metadata endpoints are blocked
- Normal public URLs continue to work
- Ollama providers are allowed to use localhost (intentional)
- A shared SSRF validation utility is extracted and importable
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from runsight_api.domain.value_objects import ProviderEntity
from runsight_api.logic.services.provider_service import ProviderService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_provider(
    *,
    provider_id: str = "prov_test123",
    name: str = "Test Provider",
    provider_type: str = "openai",
    api_key: str | None = "configured_key",
    base_url: str | None = None,
) -> ProviderEntity:
    """Create a ProviderEntity for testing."""
    return ProviderEntity(
        id=provider_id,
        kind="provider",
        name=name,
        type=provider_type,
        api_key=api_key,
        base_url=base_url,
    )


def _make_service_and_repo(provider: ProviderEntity) -> tuple[ProviderService, Mock]:
    """Create a ProviderService with mock repo and secrets that returns the given provider."""
    repo = Mock()
    repo.get_by_id.return_value = provider
    repo.update.return_value = provider
    secrets = Mock()
    secrets.is_configured.return_value = bool(provider.api_key)
    secrets.resolve.return_value = "sk-xxx"
    return ProviderService(repo, secrets), repo


# ===========================================================================
# 1. Shared SSRF utility exists and is importable
# ===========================================================================


class TestSharedSSRFUtilityExists:
    """The SSRF validation logic should be extracted into a shared utility
    that both HttpRequestBlock and ProviderService can use."""

    def test_shared_ssrf_validator_importable(self):
        """A shared SSRF validation function should exist in runsight_core."""
        from runsight_core.security import validate_ssrf  # noqa: F401

    def test_shared_ssrf_error_importable(self):
        """The SSRFError exception should be importable from the shared module."""
        from runsight_core.security import SSRFError  # noqa: F401

    @pytest.mark.asyncio
    async def test_shared_validator_blocks_private_ip(self):
        """The shared validator should raise SSRFError for private IPs."""
        from runsight_core.security import SSRFError, validate_ssrf

        with pytest.raises(SSRFError):
            await validate_ssrf("http://192.168.1.1/models")

    @pytest.mark.asyncio
    async def test_shared_validator_allows_public_url(self):
        """The shared validator should not raise for public URLs."""
        from runsight_core.security import validate_ssrf

        # Should not raise
        await validate_ssrf("https://api.openai.com/v1/models")

    @pytest.mark.asyncio
    async def test_shared_validator_respects_allow_private_flag(self):
        """The shared validator should accept an allow_private flag."""
        from runsight_core.security import validate_ssrf

        # Should not raise when private IPs are explicitly allowed
        await validate_ssrf("http://127.0.0.1/models", allow_private=True)

    @pytest.mark.asyncio
    async def test_shared_validator_blocks_dns_lookup_failures(self):
        """DNS resolution failures must fail closed instead of permitting the request."""
        from runsight_core.security import SSRFError, validate_ssrf

        fake_loop = Mock()
        fake_loop.getaddrinfo = AsyncMock(side_effect=OSError("dns lookup failed"))

        with patch("runsight_core.security.asyncio.get_running_loop", return_value=fake_loop):
            with pytest.raises(SSRFError):
                await validate_ssrf("https://provider.example/v1/models")


# ===========================================================================
# 2. SSRF-blocking tests — these should FAIL until protection is added
# ===========================================================================


class TestSSRFBlocksPrivateIPs:
    """test_connection() should reject URLs targeting private/internal networks."""

    @pytest.mark.asyncio
    async def test_blocks_private_ip_192_168(self):
        """Private IP 192.168.x.x must be blocked."""
        provider = _make_provider(base_url="http://192.168.1.1/v1")
        service, _ = _make_service_and_repo(provider)

        result = await service.test_connection("prov_test123")

        assert result["success"] is False
        assert "ssrf" in result["message"].lower() or "blocked" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_blocks_private_ip_10_network(self):
        """Private IP 10.x.x.x must be blocked."""
        provider = _make_provider(base_url="http://10.0.0.1:8080/admin")
        service, _ = _make_service_and_repo(provider)

        result = await service.test_connection("prov_test123")

        assert result["success"] is False
        assert "ssrf" in result["message"].lower() or "blocked" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_blocks_private_ip_172_16(self):
        """Private IP 172.16.x.x must be blocked."""
        provider = _make_provider(base_url="http://172.16.0.1/v1/models")
        service, _ = _make_service_and_repo(provider)

        result = await service.test_connection("prov_test123")

        assert result["success"] is False
        assert "ssrf" in result["message"].lower() or "blocked" in result["message"].lower()


class TestSSRFBlocksLoopback:
    """test_connection() should reject loopback addresses for non-Ollama providers."""

    @pytest.mark.asyncio
    async def test_blocks_loopback_127_0_0_1(self):
        """Loopback 127.0.0.1 must be blocked for non-Ollama providers."""
        provider = _make_provider(
            provider_type="openai",
            base_url="http://127.0.0.1:8080/v1",
        )
        service, _ = _make_service_and_repo(provider)

        result = await service.test_connection("prov_test123")

        assert result["success"] is False
        assert "ssrf" in result["message"].lower() or "blocked" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_blocks_loopback_localhost(self):
        """Loopback via 'localhost' hostname must be blocked for non-Ollama providers."""
        provider = _make_provider(
            provider_type="custom",
            base_url="http://localhost:9090/v1",
        )
        service, _ = _make_service_and_repo(provider)

        result = await service.test_connection("prov_test123")

        assert result["success"] is False
        assert "ssrf" in result["message"].lower() or "blocked" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_blocks_ipv6_loopback(self):
        """IPv6 loopback ::1 must be blocked for non-Ollama providers."""
        provider = _make_provider(
            provider_type="openai",
            base_url="http://[::1]:8080/v1",
        )
        service, _ = _make_service_and_repo(provider)

        result = await service.test_connection("prov_test123")

        assert result["success"] is False
        assert "ssrf" in result["message"].lower() or "blocked" in result["message"].lower()


class TestSSRFBlocksLinkLocal:
    """test_connection() should reject link-local addresses (cloud metadata endpoints)."""

    @pytest.mark.asyncio
    async def test_blocks_cloud_metadata_endpoint(self):
        """AWS/GCP metadata endpoint 169.254.169.254 must be blocked."""
        provider = _make_provider(
            base_url="http://169.254.169.254/latest/meta-data",
        )
        service, _ = _make_service_and_repo(provider)

        result = await service.test_connection("prov_test123")

        assert result["success"] is False
        assert "ssrf" in result["message"].lower() or "blocked" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_blocks_link_local_169_254(self):
        """Link-local range 169.254.x.x must be blocked."""
        provider = _make_provider(
            base_url="http://169.254.1.1/api",
        )
        service, _ = _make_service_and_repo(provider)

        result = await service.test_connection("prov_test123")

        assert result["success"] is False
        assert "ssrf" in result["message"].lower() or "blocked" in result["message"].lower()


# ===========================================================================
# 3. Ollama exception — localhost IS allowed for Ollama providers
# ===========================================================================


class TestOllamaLocalhostException:
    """Ollama providers intentionally run on localhost; SSRF should allow this."""

    @pytest.mark.asyncio
    async def test_ollama_localhost_allowed(self):
        """Ollama with localhost base_url should NOT be blocked by SSRF."""
        provider = _make_provider(
            name="Ollama",
            provider_type="ollama",
            api_key=None,
            base_url="http://localhost:11434",
        )
        service, _ = _make_service_and_repo(provider)

        with patch("runsight_api.logic.services.provider_service.httpx") as mock_httpx:
            mock_resp = Mock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"models": [{"name": "llama3"}]}
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_httpx.AsyncClient.return_value = mock_client

            result = await service.test_connection("prov_test123")

        assert result["success"] is True
        # The request should have been made (not blocked)
        mock_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_ollama_127_0_0_1_allowed(self):
        """Ollama with 127.0.0.1 base_url should NOT be blocked by SSRF."""
        provider = _make_provider(
            name="Ollama",
            provider_type="ollama",
            api_key=None,
            base_url="http://127.0.0.1:11434",
        )
        service, _ = _make_service_and_repo(provider)

        with patch("runsight_api.logic.services.provider_service.httpx") as mock_httpx:
            mock_resp = Mock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"models": [{"name": "llama3"}]}
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_httpx.AsyncClient.return_value = mock_client

            result = await service.test_connection("prov_test123")

        assert result["success"] is True
        mock_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_ollama_default_url_allowed(self):
        """Ollama with no explicit base_url (defaults to localhost:11434) should work."""
        provider = _make_provider(
            name="Ollama",
            provider_type="ollama",
            api_key=None,
            base_url=None,  # defaults to http://localhost:11434
        )
        service, _ = _make_service_and_repo(provider)

        with patch("runsight_api.logic.services.provider_service.httpx") as mock_httpx:
            mock_resp = Mock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"models": [{"name": "llama3"}]}
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_httpx.AsyncClient.return_value = mock_client

            result = await service.test_connection("prov_test123")

        assert result["success"] is True


# ===========================================================================
# 4. Normal public URLs continue to work
# ===========================================================================


class TestPublicURLsStillWork:
    """Normal public URLs should not be affected by SSRF protection."""

    @pytest.mark.asyncio
    async def test_public_openai_url_works(self):
        """Public OpenAI URL should pass SSRF validation."""
        provider = _make_provider(
            provider_type="openai",
            base_url="https://api.openai.com/v1",
        )
        service, _ = _make_service_and_repo(provider)

        with patch("runsight_api.logic.services.provider_service.httpx") as mock_httpx:
            mock_resp = Mock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"data": [{"id": "gpt-4o"}]}
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_httpx.AsyncClient.return_value = mock_client

            result = await service.test_connection("prov_test123")

        assert result["success"] is True
        mock_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_custom_provider_public_url_works(self):
        """Custom provider with a public URL should pass SSRF validation."""
        provider = _make_provider(
            provider_type="custom",
            base_url="https://my-custom-llm.example.com/v1",
        )
        service, _ = _make_service_and_repo(provider)

        with patch("runsight_api.logic.services.provider_service.httpx") as mock_httpx:
            mock_resp = Mock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"data": [{"id": "custom-model"}]}
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_httpx.AsyncClient.return_value = mock_client

            result = await service.test_connection("prov_test123")

        assert result["success"] is True
        mock_client.get.assert_called_once()


# ===========================================================================
# 5. SSRF validation happens BEFORE the HTTP request
# ===========================================================================


class TestSSRFValidationOrder:
    """SSRF validation must occur before the outbound HTTP request is made."""

    @pytest.mark.asyncio
    async def test_no_http_call_for_private_ip(self):
        """When SSRF blocks a URL, httpx.get() should never be called."""
        provider = _make_provider(base_url="http://192.168.1.1/v1")
        service, _ = _make_service_and_repo(provider)

        with patch("runsight_api.logic.services.provider_service.httpx") as mock_httpx:
            result = await service.test_connection("prov_test123")

        assert result["success"] is False
        # The HTTP client must NOT have been called
        mock_httpx.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_http_call_for_metadata_endpoint(self):
        """When SSRF blocks cloud metadata, httpx.get() should never be called."""
        provider = _make_provider(
            base_url="http://169.254.169.254/latest/meta-data",
        )
        service, _ = _make_service_and_repo(provider)

        with patch("runsight_api.logic.services.provider_service.httpx") as mock_httpx:
            result = await service.test_connection("prov_test123")

        assert result["success"] is False
        mock_httpx.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_http_call_for_loopback_non_ollama(self):
        """When SSRF blocks loopback for non-Ollama, httpx.get() should never be called."""
        provider = _make_provider(
            provider_type="openai",
            base_url="http://127.0.0.1:8080/v1",
        )
        service, _ = _make_service_and_repo(provider)

        with patch("runsight_api.logic.services.provider_service.httpx") as mock_httpx:
            result = await service.test_connection("prov_test123")

        assert result["success"] is False
        mock_httpx.get.assert_not_called()
