"""HTTP credential injection behavior."""

from __future__ import annotations

import json
from pathlib import Path

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


# ---------------------------------------------------------------------------
# Behavior coverage
# ---------------------------------------------------------------------------
