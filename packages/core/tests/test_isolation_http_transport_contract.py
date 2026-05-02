"""HTTP transport contract behavior."""

from __future__ import annotations

from typing import Any

import pytest


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
