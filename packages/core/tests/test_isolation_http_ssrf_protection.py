"""HTTP SSRF protection behavior."""

from __future__ import annotations

from pathlib import Path

import pytest


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
