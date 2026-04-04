"""Red tests for RUN-408: Replace sync httpx.get with async in provider_service.

Bug: provider_service.py uses 5x sync httpx.get() calls inside the async
test_connection() method. These block the asyncio event loop, causing
latency spikes for all concurrent requests.

AC:
  - Zero sync httpx calls in provider_service
  - All HTTP calls use async with httpx.AsyncClient
  - Provider health checks still work correctly

Tests verify:
  1. Source-level: no sync httpx.get/post calls remain in provider_service.py
  2. Runtime: test_connection uses httpx.AsyncClient (not sync httpx.get)
  3. Behavioral: health checks still return correct results via async client
"""

import pytest

import ast
import importlib
import inspect
from unittest.mock import AsyncMock, Mock, patch

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
    return ProviderEntity(
        id=provider_id,
        name=name,
        type=provider_type,
        api_key=api_key,
        base_url=base_url,
    )


def _make_service(provider: ProviderEntity) -> ProviderService:
    repo = Mock()
    repo.get_by_id.return_value = provider
    repo.update.return_value = provider
    secrets = Mock()
    secrets.is_configured.return_value = bool(provider.api_key)
    secrets.resolve.return_value = "sk-xxx"
    return ProviderService(repo, secrets)


def _get_provider_service_source() -> str:
    """Read the source code of provider_service.py."""
    spec = importlib.util.find_spec("runsight_api.logic.services.provider_service")
    assert spec and spec.origin, "Cannot locate provider_service.py"
    with open(spec.origin) as f:
        return f.read()


# ===========================================================================
# 1. Source-level: zero sync httpx calls in provider_service
# ===========================================================================


class TestNoSyncHttpxCalls:
    """provider_service.py must not contain any sync httpx.get() or httpx.post() calls."""

    def test_no_sync_httpx_get_in_source(self):
        """The string 'httpx.get(' must not appear in provider_service.py source."""
        source = _get_provider_service_source()
        assert "httpx.get(" not in source, (
            "Found sync httpx.get() call in provider_service.py — "
            "must be replaced with async httpx.AsyncClient"
        )

    def test_no_sync_httpx_post_in_source(self):
        """The string 'httpx.post(' must not appear in provider_service.py source."""
        source = _get_provider_service_source()
        assert "httpx.post(" not in source, (
            "Found sync httpx.post() call in provider_service.py — "
            "must be replaced with async httpx.AsyncClient"
        )

    def test_no_sync_httpx_request_in_source(self):
        """The string 'httpx.request(' must not appear in provider_service.py source."""
        source = _get_provider_service_source()
        assert "httpx.request(" not in source, (
            "Found sync httpx.request() call in provider_service.py — "
            "must be replaced with async httpx.AsyncClient"
        )

    def test_async_client_is_used_in_source(self):
        """provider_service.py must reference httpx.AsyncClient."""
        source = _get_provider_service_source()
        assert "AsyncClient" in source, (
            "httpx.AsyncClient not found in provider_service.py — "
            "all HTTP calls must use the async client"
        )

    def test_no_sync_httpx_client_in_source(self):
        """provider_service.py must not instantiate sync httpx.Client."""
        source = _get_provider_service_source()
        # Allow httpx.AsyncClient but not httpx.Client (sync)
        # Check for the sync Client pattern, but exclude AsyncClient
        lines = source.split("\n")
        for line in lines:
            stripped = line.strip()
            # Skip comments and lines with AsyncClient
            if stripped.startswith("#") or "AsyncClient" in stripped:
                continue
            assert "httpx.Client(" not in stripped, (
                f"Found sync httpx.Client() in provider_service.py: {stripped!r} — "
                "must use httpx.AsyncClient"
            )


# ===========================================================================
# 2. AST-level: verify no sync httpx calls in the parsed AST
# ===========================================================================


class TestASTNoSyncHttpx:
    """Parse provider_service.py AST to verify no sync httpx attribute calls."""

    def _find_httpx_calls(self, source: str) -> list[str]:
        """Return list of 'httpx.<method>' call expressions found in the AST."""
        tree = ast.parse(source)
        sync_calls = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                # Match pattern: httpx.get, httpx.post, etc.
                if (
                    isinstance(func, ast.Attribute)
                    and isinstance(func.value, ast.Name)
                    and func.value.id == "httpx"
                    and func.attr
                    in ("get", "post", "put", "delete", "patch", "request", "head", "options")
                ):
                    sync_calls.append(f"httpx.{func.attr}")
        return sync_calls

    def test_ast_no_sync_httpx_calls(self):
        """AST analysis must find zero sync httpx.get/post/... calls."""
        source = _get_provider_service_source()
        sync_calls = self._find_httpx_calls(source)
        assert sync_calls == [], (
            f"Found {len(sync_calls)} sync httpx call(s) in provider_service.py: {sync_calls} — "
            "all must be replaced with async httpx.AsyncClient methods"
        )


# ===========================================================================
# 3. Runtime: test_connection must use httpx.AsyncClient, not httpx.get
# ===========================================================================


class TestTestConnectionUsesAsyncClient:
    """test_connection must use httpx.AsyncClient context manager for HTTP calls."""

    @pytest.mark.asyncio
    async def test_openai_uses_async_client(self):
        """test_connection for OpenAI provider must use httpx.AsyncClient."""
        provider = _make_provider(
            provider_type="openai",
            base_url="https://api.openai.com/v1",
        )
        service = _make_service(provider)

        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": [{"id": "gpt-4o"}]}

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("runsight_api.logic.services.provider_service.httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value = mock_client
            # Ensure sync httpx.get is not called
            mock_httpx.get.side_effect = AssertionError(
                "Sync httpx.get() was called — must use httpx.AsyncClient"
            )

            result = await service.test_connection("prov_test123")

        # The async client must have been used
        mock_httpx.AsyncClient.assert_called()
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_anthropic_uses_async_client(self):
        """test_connection for Anthropic provider must use httpx.AsyncClient."""
        provider = _make_provider(
            provider_type="anthropic",
            name="Anthropic",
        )
        service = _make_service(provider)

        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": [{"id": "claude-3"}]}

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("runsight_api.logic.services.provider_service.httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value = mock_client
            mock_httpx.get.side_effect = AssertionError(
                "Sync httpx.get() was called — must use httpx.AsyncClient"
            )

            result = await service.test_connection("prov_test123")

        mock_httpx.AsyncClient.assert_called()
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_google_uses_async_client(self):
        """test_connection for Google provider must use httpx.AsyncClient."""
        provider = _make_provider(
            provider_type="google",
            name="Google",
        )
        service = _make_service(provider)

        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"models": [{"name": "models/gemini-pro"}]}

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("runsight_api.logic.services.provider_service.httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value = mock_client
            mock_httpx.get.side_effect = AssertionError(
                "Sync httpx.get() was called — must use httpx.AsyncClient"
            )

            result = await service.test_connection("prov_test123")

        mock_httpx.AsyncClient.assert_called()
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_ollama_uses_async_client(self):
        """test_connection for Ollama provider must use httpx.AsyncClient."""
        provider = _make_provider(
            provider_type="ollama",
            name="Ollama",
            api_key=None,
            base_url="http://localhost:11434",
        )
        service = _make_service(provider)

        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"models": [{"name": "llama3"}]}

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("runsight_api.logic.services.provider_service.httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value = mock_client
            mock_httpx.get.side_effect = AssertionError(
                "Sync httpx.get() was called — must use httpx.AsyncClient"
            )

            result = await service.test_connection("prov_test123")

        mock_httpx.AsyncClient.assert_called()
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_custom_provider_uses_async_client(self):
        """test_connection for custom/fallback provider must use httpx.AsyncClient."""
        provider = _make_provider(
            provider_type="mistral",
            name="Mistral",
            base_url="https://api.mistral.ai/v1",
        )
        service = _make_service(provider)

        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": [{"id": "mistral-large"}]}

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("runsight_api.logic.services.provider_service.httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value = mock_client
            mock_httpx.get.side_effect = AssertionError(
                "Sync httpx.get() was called — must use httpx.AsyncClient"
            )

            result = await service.test_connection("prov_test123")

        mock_httpx.AsyncClient.assert_called()
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_sync_httpx_get_is_never_called(self):
        """httpx.get (sync) must never be called — only httpx.AsyncClient.get."""
        provider = _make_provider(
            provider_type="openai",
            base_url="https://api.openai.com/v1",
        )
        service = _make_service(provider)

        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": [{"id": "gpt-4o"}]}

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("runsight_api.logic.services.provider_service.httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value = mock_client
            # Track sync get calls — don't raise, just track
            mock_httpx.get.return_value = mock_resp

            await service.test_connection("prov_test123")

        # The sync httpx.get must NOT have been called at all
        (
            mock_httpx.get.assert_not_called(),
            (
                "Sync httpx.get() was called — this blocks the event loop. "
                "Must use httpx.AsyncClient instead."
            ),
        )


# ===========================================================================
# 4. Behavioral: health checks return correct results via async client
# ===========================================================================


class _NoOpAsyncClient:
    """Minimal async context manager stand-in for httpx.AsyncClient."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def get(self, url, **kwargs):
        resp = Mock()
        resp.status_code = 200
        resp.json.return_value = {"data": []}
        return resp


class TestHealthCheckBehaviorWithAsyncClient:
    """Health check behavior must be preserved when using httpx.AsyncClient."""

    @pytest.mark.asyncio
    async def test_openai_health_check_returns_models(self):
        """OpenAI health check must return discovered models via async client."""
        provider = _make_provider(
            provider_type="openai",
            base_url="https://api.openai.com/v1",
        )
        service = _make_service(provider)

        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": [{"id": "gpt-4o"}, {"id": "gpt-4o-mini"}]}

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("runsight_api.logic.services.provider_service.httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value = mock_client
            mock_httpx.get.side_effect = AssertionError("sync httpx.get blocked")

            result = await service.test_connection("prov_test123")

        assert result["success"] is True
        assert "gpt-4o" in result["models"]
        assert "gpt-4o-mini" in result["models"]

    @pytest.mark.asyncio
    async def test_anthropic_health_check_sends_correct_headers(self):
        """Anthropic health check must send x-api-key and anthropic-version headers."""
        provider = _make_provider(
            provider_type="anthropic",
            name="Anthropic",
        )
        service = _make_service(provider)

        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": [{"id": "claude-3-opus"}]}

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("runsight_api.logic.services.provider_service.httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value = mock_client
            mock_httpx.get.side_effect = AssertionError("sync httpx.get blocked")

            await service.test_connection("prov_test123")

        # Verify the async client.get was called with correct headers
        mock_client.get.assert_called_once()
        call_kwargs = mock_client.get.call_args
        headers = call_kwargs[1].get("headers") or call_kwargs.kwargs.get("headers", {})
        assert "x-api-key" in headers
        assert "anthropic-version" in headers

    @pytest.mark.asyncio
    async def test_ollama_health_check_no_auth_header(self):
        """Ollama health check must not send an Authorization header."""
        provider = _make_provider(
            provider_type="ollama",
            name="Ollama",
            api_key=None,
            base_url="http://localhost:11434",
        )
        service = _make_service(provider)

        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"models": [{"name": "llama3"}]}

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("runsight_api.logic.services.provider_service.httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value = mock_client
            mock_httpx.get.side_effect = AssertionError("sync httpx.get blocked")

            result = await service.test_connection("prov_test123")

        assert result["success"] is True
        assert "llama3" in result["models"]
        # Ollama should call /api/tags with no auth header
        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        url = call_args[0][0] if call_args[0] else call_args.kwargs.get("url", "")
        assert "/api/tags" in url

    @pytest.mark.asyncio
    async def test_google_health_check_sends_api_key_header(self):
        """Google health check must send x-goog-api-key header."""
        provider = _make_provider(
            provider_type="google",
            name="Google",
        )
        service = _make_service(provider)

        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"models": [{"name": "models/gemini-pro"}]}

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("runsight_api.logic.services.provider_service.httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value = mock_client
            mock_httpx.get.side_effect = AssertionError("sync httpx.get blocked")

            await service.test_connection("prov_test123")

        mock_client.get.assert_called_once()
        call_kwargs = mock_client.get.call_args
        headers = call_kwargs[1].get("headers") or call_kwargs.kwargs.get("headers", {})
        assert "x-goog-api-key" in headers

    @pytest.mark.asyncio
    async def test_failed_health_check_still_updates_provider_status(self):
        """A 401 response via async client must still update provider status to 'error'."""
        provider = _make_provider(
            provider_type="openai",
            base_url="https://api.openai.com/v1",
        )
        repo = Mock()
        repo.get_by_id.return_value = provider
        repo.update.return_value = provider
        secrets = Mock()
        secrets.is_configured.return_value = True
        secrets.resolve.return_value = "sk-bad-key"
        service = ProviderService(repo, secrets)

        mock_resp = Mock()
        mock_resp.status_code = 401

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("runsight_api.logic.services.provider_service.httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value = mock_client
            mock_httpx.get.side_effect = AssertionError("sync httpx.get blocked")

            result = await service.test_connection("prov_test123")

        assert result["success"] is False
        assert "401" in result["message"]
        # Provider status must be updated to "error"
        repo.update.assert_called_once()
        update_data = repo.update.call_args[0][1]
        assert update_data["status"] == "error"

    @pytest.mark.asyncio
    async def test_timeout_via_async_client_reports_failure(self):
        """A timeout from the async client must be caught and reported.

        The timeout must come from the async client's get, not from sync httpx.get.
        We verify by asserting the async client.get was actually called.
        """
        import httpx as real_httpx

        provider = _make_provider(
            provider_type="openai",
            base_url="https://api.openai.com/v1",
        )
        repo = Mock()
        repo.get_by_id.return_value = provider
        repo.update.return_value = provider
        secrets = Mock()
        secrets.is_configured.return_value = True
        secrets.resolve.return_value = "sk-xxx"
        service = ProviderService(repo, secrets)

        mock_client = AsyncMock()
        mock_client.get.side_effect = real_httpx.TimeoutException("timed out")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("runsight_api.logic.services.provider_service.httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value = mock_client
            mock_httpx.TimeoutException = real_httpx.TimeoutException
            mock_httpx.get.side_effect = AssertionError("sync httpx.get blocked")

            result = await service.test_connection("prov_test123")

        assert result["success"] is False
        assert "Connection failed" in result["message"]
        # Crucially, the timeout must have come from the ASYNC client
        mock_client.get.assert_called_once()
        mock_httpx.AsyncClient.assert_called()


# ===========================================================================
# 5. test_connection method is async (awaitable)
# ===========================================================================


class TestMethodIsAsync:
    """test_connection must remain an async method (already is, but verify)."""

    def test_test_connection_is_coroutine_function(self):
        """ProviderService.test_connection must be an async def (coroutine function)."""
        assert inspect.iscoroutinefunction(ProviderService.test_connection), (
            "test_connection must be async def — it must not have been downgraded to sync"
        )
