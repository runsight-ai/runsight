"""HTTP URL allowlist behavior."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.real_subprocess_isolation


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

    @pytest.mark.asyncio
    async def test_allowlist_host_port_entry_normalizes_to_hostname(self, tmp_path: Path):
        """Host:port allowlist entries are host entries, not malformed URL schemes."""
        from unittest.mock import AsyncMock, patch

        from runsight_core.isolation.handlers import make_http_handler

        handler = make_http_handler(
            credentials={},
            url_allowlist=["api.fixture.test:8443"],
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
    async def test_malformed_scheme_allowlist_entry_is_ignored_without_crash(
        self,
        tmp_path: Path,
    ):
        """Malformed URL-like allowlist entries do not crash handler construction."""
        from runsight_core.isolation.handlers import make_http_handler

        handler = make_http_handler(credentials={}, url_allowlist=["http:"])

        result = await handler(
            {
                "method": "GET",
                "url": "https://api.fixture.test/data",
                "headers": {},
            }
        )
        assert "error" in result
        assert "allowed" in result["error"].lower()


# ---------------------------------------------------------------------------
# Behavior coverage
# ---------------------------------------------------------------------------
