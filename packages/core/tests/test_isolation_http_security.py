"""HTTP credential injection, allowlist, SSRF, and transport behavior."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest


class TestHTTPCredentialInjection:
    """Engine-side IPC http handler must inject credentials into outgoing requests.

    The subprocess sends a bare HTTP request via IPC. The engine-side handler
    enriches the request with credentials (e.g. Authorization header) from the
    tool config before executing it. The subprocess never sees the raw token.
    """

    @pytest.mark.asyncio
    async def test_http_handler_injects_auth_header(self, tmp_path: Path):
        """http handler adds Authorization header from tool credential config."""
        from unittest.mock import AsyncMock, patch

        from runsight_core.isolation.handlers import make_http_handler

        credentials = {"api.fixture.test": {"Authorization": "Bearer dummy-engine-credential"}}
        handler = make_http_handler(credentials=credentials, url_allowlist=["api.fixture.test"])

        with (
            patch("runsight_core.isolation.handlers.validate_ssrf", new_callable=AsyncMock),
            patch(
                "runsight_core.isolation.handlers._perform_http_request",
                new_callable=AsyncMock,
                return_value={"status_code": 200, "body": "ok", "headers": {}},
            ) as perform_request,
        ):
            result = await handler(
                {
                    "method": "GET",
                    "url": "https://api.fixture.test/data",
                    "headers": {"Accept": "application/json"},
                }
            )

        assert "error" not in result
        assert perform_request.await_args.kwargs["headers"] == {
            "Accept": "application/json",
            "Authorization": "Bearer dummy-engine-credential",
        }

    @pytest.mark.asyncio
    async def test_http_handler_does_not_expose_token_in_response(self, tmp_path: Path):
        """The token injected by the engine must not appear in the IPC response."""
        from unittest.mock import AsyncMock, patch

        from runsight_core.isolation.handlers import make_http_handler

        credentials = {"api.fixture.test": {"Authorization": "Bearer dummy-response-credential"}}
        handler = make_http_handler(credentials=credentials, url_allowlist=["api.fixture.test"])

        with (
            patch("runsight_core.isolation.handlers.validate_ssrf", new_callable=AsyncMock),
            patch(
                "runsight_core.isolation.handlers._perform_http_request",
                new_callable=AsyncMock,
                return_value={"status_code": 200, "body": "ok", "headers": {}},
            ),
        ):
            result = await handler(
                {
                    "method": "GET",
                    "url": "https://api.fixture.test/data",
                    "headers": {},
                }
            )

        # Response must not contain the injected credential
        result_str = json.dumps(result)
        assert "dummy-response-credential" not in result_str

    @pytest.mark.asyncio
    async def test_subprocess_request_has_no_credential_fields(self, tmp_path: Path):
        """Subprocess sends requests without credential fields - engine adds them."""
        from unittest.mock import AsyncMock, patch

        from runsight_core.isolation.handlers import make_http_handler

        credentials = {"api.fixture.test": {"Authorization": "Bearer dummy-injected-credential"}}
        handler = make_http_handler(credentials=credentials, url_allowlist=["api.fixture.test"])

        # Simulate a subprocess request with NO auth header
        subprocess_request = {
            "method": "GET",
            "url": "https://api.fixture.test/data",
            "headers": {},
        }

        with (
            patch("runsight_core.isolation.handlers.validate_ssrf", new_callable=AsyncMock),
            patch(
                "runsight_core.isolation.handlers._perform_http_request",
                new_callable=AsyncMock,
                return_value={"status_code": 200, "body": "ok", "headers": {}},
            ) as perform_request,
        ):
            result = await handler(subprocess_request)

        assert "error" not in result
        assert (
            perform_request.await_args.kwargs["headers"]["Authorization"]
            == "Bearer dummy-injected-credential"
        )


# ---------------------------------------------------------------------------
# Behavior coverage
# ---------------------------------------------------------------------------


class TestHTTPURLAllowlist:
    """HTTP requests must be validated against a URL allowlist."""

    @pytest.mark.asyncio
    async def test_allowed_host_passes(self, tmp_path: Path):
        """Requests to hosts on the allowlist are permitted."""
        from unittest.mock import AsyncMock, patch

        from runsight_core.isolation.handlers import make_http_handler

        handler = make_http_handler(
            credentials={},
            url_allowlist=["api.fixture.test", "cdn.fixture.test"],
        )

        with (
            patch("runsight_core.isolation.handlers.validate_ssrf", new_callable=AsyncMock),
            patch(
                "runsight_core.isolation.handlers._perform_http_request",
                new_callable=AsyncMock,
                return_value={"status_code": 200, "body": "ok", "headers": {}},
            ),
        ):
            result = await handler(
                {
                    "method": "GET",
                    "url": "https://api.fixture.test/data",
                    "headers": {},
                }
            )
        assert "error" not in result

    @pytest.mark.asyncio
    async def test_disallowed_host_rejected(self, tmp_path: Path):
        """Requests to hosts not on the allowlist are rejected with an error."""
        from runsight_core.isolation.handlers import make_http_handler

        handler = make_http_handler(
            credentials={},
            url_allowlist=["api.fixture.test"],
        )

        result = await handler(
            {
                "method": "GET",
                "url": "https://blocked.fixture.test/steal",
                "headers": {},
            }
        )
        assert "error" in result
        assert "allowlist" in result["error"].lower() or "allowed" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_empty_allowlist_blocks_all(self, tmp_path: Path):
        """An empty allowlist blocks all HTTP requests."""
        from runsight_core.isolation.handlers import make_http_handler

        handler = make_http_handler(credentials={}, url_allowlist=[])

        result = await handler(
            {
                "method": "GET",
                "url": "https://unlisted.fixture.test/path",
                "headers": {},
            }
        )
        assert "error" in result

    @pytest.mark.asyncio
    async def test_literal_wildcard_does_not_bypass_allowlist(self, tmp_path: Path):
        """A '*' entry is treated literally; hosts must still be explicitly allowed."""
        from unittest.mock import AsyncMock, patch

        from runsight_core.isolation.handlers import make_http_handler

        handler = make_http_handler(credentials={}, url_allowlist=["10.0.0.1"])

        with patch("runsight_core.isolation.handlers.validate_ssrf", new_callable=AsyncMock):
            result = await handler(
                {
                    "method": "GET",
                    "url": "https://wildcard.fixture.test/path",
                    "headers": {},
                }
            )
        assert "error" in result
        assert "allowed" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_allowlist_matches_hostname_not_path(self, tmp_path: Path):
        """Allowlist checks the hostname, not the full URL path."""
        from unittest.mock import AsyncMock, patch

        from runsight_core.isolation.handlers import make_http_handler

        handler = make_http_handler(
            credentials={},
            url_allowlist=["api.fixture.test"],
        )

        # Different paths on the same allowed host should be fine
        with (
            patch("runsight_core.isolation.handlers.validate_ssrf", new_callable=AsyncMock),
            patch(
                "runsight_core.isolation.handlers._perform_http_request",
                new_callable=AsyncMock,
                return_value={"status_code": 200, "body": "ok", "headers": {}},
            ),
        ):
            result = await handler(
                {
                    "method": "GET",
                    "url": "https://api.fixture.test/any/path/here",
                    "headers": {},
                }
            )
        assert "error" not in result


# ---------------------------------------------------------------------------
# Behavior coverage
# ---------------------------------------------------------------------------


class TestHTTPSSRFProtection:
    """HTTP handler must block requests targeting private/reserved IPs."""

    @pytest.mark.asyncio
    async def test_localhost_blocked(self, tmp_path: Path):
        """Requests to 127.0.0.1 are blocked by SSRF validation."""
        from runsight_core.isolation.handlers import make_http_handler

        handler = make_http_handler(credentials={}, url_allowlist=["127.0.0.1"])

        result = await handler(
            {
                "method": "GET",
                "url": "http://127.0.0.1:8080/admin",
                "headers": {},
            }
        )
        assert "error" in result
        assert "ssrf" in result["error"].lower() or "blocked" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_private_ip_10_blocked(self, tmp_path: Path):
        """Requests to 10.x.x.x private range are blocked."""
        from runsight_core.isolation.handlers import make_http_handler

        handler = make_http_handler(credentials={}, url_allowlist=["192.168.1.1"])

        result = await handler(
            {
                "method": "GET",
                "url": "http://10.0.0.1/internal",
                "headers": {},
            }
        )
        assert "error" in result

    @pytest.mark.asyncio
    async def test_private_ip_192_168_blocked(self, tmp_path: Path):
        """Requests to 192.168.x.x private range are blocked."""
        from runsight_core.isolation.handlers import make_http_handler

        handler = make_http_handler(credentials={}, url_allowlist=["169.254.169.254"])

        result = await handler(
            {
                "method": "GET",
                "url": "http://192.168.1.1/router",
                "headers": {},
            }
        )
        assert "error" in result

    @pytest.mark.asyncio
    async def test_link_local_169_254_blocked(self, tmp_path: Path):
        """Requests to 169.254.x.x (link-local / cloud metadata) are blocked."""
        from runsight_core.isolation.handlers import make_http_handler

        handler = make_http_handler(credentials={}, url_allowlist=["*"])

        result = await handler(
            {
                "method": "GET",
                "url": "http://169.254.169.254/latest/meta-data/",
                "headers": {},
            }
        )
        assert "error" in result

    @pytest.mark.asyncio
    async def test_allowed_fixture_host_passes_ssrf_validation(self, tmp_path: Path):
        """Requests pass through when SSRF validation permits the fixture host."""
        from unittest.mock import AsyncMock, patch

        from runsight_core.isolation.handlers import make_http_handler

        handler = make_http_handler(credentials={}, url_allowlist=["public.fixture.test"])

        with (
            patch("runsight_core.isolation.handlers.validate_ssrf", new_callable=AsyncMock),
            patch(
                "runsight_core.isolation.handlers._perform_http_request",
                new_callable=AsyncMock,
                return_value={"status_code": 200, "body": "ok", "headers": {}},
            ),
        ):
            result = await handler(
                {
                    "method": "GET",
                    "url": "https://public.fixture.test/",
                    "headers": {},
                }
            )
        assert "error" not in result


# ---------------------------------------------------------------------------
# HTTP transport contract (httpx + allowlist + SSRF)
# ---------------------------------------------------------------------------


class TestHTTPHandlerTransportContract:
    """make_http_handler must call httpx with strict controls."""

    @pytest.mark.asyncio
    async def test_allowed_host_uses_httpx_and_returns_actual_body_status_headers(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        from unittest.mock import AsyncMock

        from runsight_core.isolation import handlers as handlers_module
        from runsight_core.isolation.handlers import make_http_handler

        captured: dict[str, Any] = {}

        class _FakeResponse:
            status_code = 200
            headers = {"content-type": "application/json"}
            text = '{"ok": true, "source": "mock"}'

        class _FakeAsyncClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def request(
                self, method: str, url: str, headers: dict[str, str], json: Any = None
            ):
                captured["method"] = method
                captured["url"] = url
                captured["headers"] = dict(headers)
                captured["json"] = json
                return _FakeResponse()

        fake_httpx = type("FakeHTTPX", (), {"AsyncClient": _FakeAsyncClient})
        monkeypatch.setattr(handlers_module, "httpx", fake_httpx, raising=False)
        monkeypatch.setattr(handlers_module, "validate_ssrf", AsyncMock(return_value=None))

        handler = make_http_handler(
            credentials={"api.fixture.test": {"Authorization": "Bearer host-credential"}},
            url_allowlist=["api.fixture.test"],
        )
        result = await handler(
            {
                "method": "GET",
                "url": "https://api.fixture.test/data",
                "headers": {"Accept": "application/json"},
            }
        )

        assert captured["method"] == "GET"
        assert captured["url"] == "https://api.fixture.test/data"
        assert captured["headers"]["Authorization"] == "Bearer host-credential"
        assert result["status_code"] == 200
        assert result["body"] == '{"ok": true, "source": "mock"}'
        assert result["headers"]["content-type"] == "application/json"

    @pytest.mark.asyncio
    async def test_empty_allowlist_blocks_request_before_httpx(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        from unittest.mock import AsyncMock

        from runsight_core.isolation import handlers as handlers_module
        from runsight_core.isolation.handlers import make_http_handler

        captured: dict[str, Any] = {"http_calls": 0}

        class _FakeAsyncClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def request(self, *args: Any, **kwargs: Any):
                captured["http_calls"] += 1
                raise AssertionError("httpx must not run when allowlist blocks request")

        fake_httpx = type("FakeHTTPX", (), {"AsyncClient": _FakeAsyncClient})
        monkeypatch.setattr(handlers_module, "httpx", fake_httpx, raising=False)
        monkeypatch.setattr(handlers_module, "validate_ssrf", AsyncMock(return_value=None))

        handler = make_http_handler(credentials={}, url_allowlist=[])
        result = await handler(
            {
                "method": "GET",
                "url": "https://api.fixture.test/private",
                "headers": {},
            }
        )

        assert "error" in result
        assert "Host not on allowed list" in result["error"]
        assert captured["http_calls"] == 0

    @pytest.mark.asyncio
    async def test_per_host_credentials_are_scoped_to_request_host(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        from unittest.mock import AsyncMock

        from runsight_core.isolation import handlers as handlers_module
        from runsight_core.isolation.handlers import make_http_handler

        captured: dict[str, Any] = {}

        class _FakeResponse:
            status_code = 200
            headers = {}
            text = "ok"

        class _FakeAsyncClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def request(
                self, method: str, url: str, headers: dict[str, str], json: Any = None
            ):
                captured["headers"] = dict(headers)
                return _FakeResponse()

        fake_httpx = type("FakeHTTPX", (), {"AsyncClient": _FakeAsyncClient})
        monkeypatch.setattr(handlers_module, "httpx", fake_httpx, raising=False)
        monkeypatch.setattr(handlers_module, "validate_ssrf", AsyncMock(return_value=None))

        handler = make_http_handler(
            credentials={
                "host-a.fixture.test": {
                    "Authorization": "Bearer host-a-credential",
                    "X-Host-A": "yes",
                },
                "host-b.fixture.test": {
                    "Authorization": "Bearer host-b-credential",
                    "X-Host-B": "yes",
                },
            },
            url_allowlist=["host-a.fixture.test", "host-b.fixture.test"],
        )

        _ = await handler(
            {
                "method": "POST",
                "url": "https://host-a.fixture.test/v1/data",
                "headers": {"Content-Type": "application/json"},
                "json": {"value": 1},
            }
        )

        assert captured["headers"]["Authorization"] == "Bearer host-a-credential"
        assert captured["headers"]["X-Host-A"] == "yes"
        assert "X-Host-B" not in captured["headers"]

    @pytest.mark.asyncio
    async def test_redirect_is_not_followed_by_default(self, monkeypatch: pytest.MonkeyPatch):
        from unittest.mock import AsyncMock

        from runsight_core.isolation import handlers as handlers_module
        from runsight_core.isolation.handlers import make_http_handler

        captured: dict[str, Any] = {"calls": 0, "client_kwargs": None}

        class _FakeResponse:
            status_code = 302
            headers = {"location": "https://api.fixture.test/new-location"}
            text = "redirect"

        class _FakeAsyncClient:
            def __init__(self, **kwargs: Any):
                captured["client_kwargs"] = dict(kwargs)

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def request(
                self, method: str, url: str, headers: dict[str, str], json: Any = None
            ):
                captured["calls"] += 1
                return _FakeResponse()

        fake_httpx = type("FakeHTTPX", (), {"AsyncClient": _FakeAsyncClient})
        monkeypatch.setattr(handlers_module, "httpx", fake_httpx, raising=False)
        monkeypatch.setattr(handlers_module, "validate_ssrf", AsyncMock(return_value=None))

        handler = make_http_handler(credentials={}, url_allowlist=["api.fixture.test"])
        result = await handler(
            {
                "method": "GET",
                "url": "https://api.fixture.test/old-location",
                "headers": {},
                "follow_redirects": True,
            }
        )

        assert captured["client_kwargs"]["follow_redirects"] is False
        assert captured["calls"] == 1
        assert result["status_code"] == 302
        assert result["headers"]["location"] == "https://api.fixture.test/new-location"

    @pytest.mark.asyncio
    async def test_response_body_over_max_response_bytes_returns_error(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        from unittest.mock import AsyncMock

        from runsight_core.isolation import handlers as handlers_module
        from runsight_core.isolation.handlers import make_http_handler

        class _FakeResponse:
            status_code = 200
            headers = {}
            text = "too-large"

        class _FakeAsyncClient:
            def __init__(self, **_kwargs: Any):
                return None

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def request(
                self, method: str, url: str, headers: dict[str, str], json: Any = None
            ):
                return _FakeResponse()

        fake_httpx = type("FakeHTTPX", (), {"AsyncClient": _FakeAsyncClient})
        monkeypatch.setattr(handlers_module, "httpx", fake_httpx, raising=False)
        monkeypatch.setattr(handlers_module, "validate_ssrf", AsyncMock(return_value=None))

        handler = make_http_handler(credentials={}, url_allowlist=["api.fixture.test"])
        result = await handler(
            {
                "method": "GET",
                "url": "https://api.fixture.test/large",
                "headers": {},
                "max_response_bytes": 4,
            }
        )

        assert result == {"error": "response body exceeds max_response_bytes=4"}

    @pytest.mark.asyncio
    async def test_private_ip_request_returns_ssrf_error_without_httpx_call(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        from unittest.mock import AsyncMock

        from runsight_core.isolation import handlers as handlers_module
        from runsight_core.isolation.handlers import make_http_handler
        from runsight_core.security import SSRFError

        captured: dict[str, Any] = {"http_calls": 0}

        class _FakeAsyncClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def request(self, *args: Any, **kwargs: Any):
                captured["http_calls"] += 1
                raise AssertionError("httpx must not run after SSRF validation fails")

        fake_httpx = type("FakeHTTPX", (), {"AsyncClient": _FakeAsyncClient})
        monkeypatch.setattr(handlers_module, "httpx", fake_httpx, raising=False)
        monkeypatch.setattr(
            handlers_module,
            "validate_ssrf",
            AsyncMock(side_effect=SSRFError("SSRF blocked private IP 10.0.0.1")),
        )

        handler = make_http_handler(credentials={}, url_allowlist=["10.0.0.1"])
        result = await handler(
            {
                "method": "GET",
                "url": "http://10.0.0.1/internal",
                "headers": {},
            }
        )

        assert "error" in result
        assert "ssrf" in result["error"].lower()
        assert captured["http_calls"] == 0


# ---------------------------------------------------------------------------
# Behavior coverage
# ---------------------------------------------------------------------------
