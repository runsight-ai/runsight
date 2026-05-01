"""Request tool rendering, HTTP boundary, and SSRF/security behavior tests."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from runsight_core.security import SSRFError

from packages.core.tests.tool_catalog_fixtures import (
    fixture_url,
    write_lookup_admin_request_tool,
    write_lookup_profile_request_tool,
    write_read_page_request_tool,
    write_secure_lookup_request_tool,
)


class TestResolveCanonicalRequestTools:
    """Request-backed tools resolve only from canonical discovered IDs."""

    @pytest.mark.asyncio
    async def test_request_tool_renders_templates_resolves_env_and_extracts_json_path(
        self, monkeypatch, tmp_path
    ) -> None:
        from runsight_core.tools import resolve_tool

        monkeypatch.setenv("AUTH_VALUE", "dummy-auth-value")
        write_lookup_profile_request_tool(tmp_path)
        tool = resolve_tool("lookup_profile", base_dir=tmp_path)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.text = '{"data":{"profile":{"name":"Alice"}}}'
        mock_response.json.return_value = {"data": {"profile": {"name": "Alice"}}}

        with (
            patch(
                "runsight_core.tools._catalog.validate_ssrf", new_callable=AsyncMock
            ) as validate_ssrf,
            patch("httpx.AsyncClient") as mock_client,
        ):
            client_instance = AsyncMock()
            client_instance.request.return_value = mock_response
            client_instance.__aenter__ = AsyncMock(return_value=client_instance)
            client_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = client_instance

            result = await tool.execute({"user_id": "42", "note": "hello"})

        validate_ssrf.assert_awaited_once_with(fixture_url("/users/42"))
        client_instance.request.assert_awaited_once_with(
            "POST",
            fixture_url("/users/42"),
            headers={},
            content='{"token":"dummy-auth-value","note":"hello"}',
        )
        assert json.loads(result) == "Alice"

    @pytest.mark.asyncio
    async def test_request_tool_applies_ssrf_validation_to_rendered_url(self, tmp_path) -> None:
        from runsight_core.tools import resolve_tool

        write_lookup_admin_request_tool(tmp_path)
        tool = resolve_tool("lookup_admin", base_dir=tmp_path)

        with patch("httpx.AsyncClient") as mock_client:
            client_instance = AsyncMock()
            client_instance.__aenter__ = AsyncMock(return_value=client_instance)
            client_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = client_instance

            with pytest.raises(SSRFError):
                await tool.execute({"scheme": "http", "host": "127.0.0.1"})

        client_instance.request.assert_not_called()

    @pytest.mark.asyncio
    async def test_request_tool_returns_plain_text_responses_as_is(self, tmp_path) -> None:
        from runsight_core.tools import resolve_tool

        write_read_page_request_tool(tmp_path, path="/plain")
        tool = resolve_tool("read_page", base_dir=tmp_path)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/plain"}
        mock_response.text = "plain text body"

        with (
            patch("runsight_core.tools._catalog.validate_ssrf", new_callable=AsyncMock),
            patch("httpx.AsyncClient") as mock_client,
        ):
            client_instance = AsyncMock()
            client_instance.request.return_value = mock_response
            client_instance.__aenter__ = AsyncMock(return_value=client_instance)
            client_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = client_instance

            result = await tool.execute({})

        assert result == "plain text body"

    @pytest.mark.asyncio
    async def test_request_tool_normalizes_html_into_readable_text(self, tmp_path) -> None:
        from runsight_core.tools import resolve_tool

        write_read_page_request_tool(tmp_path, path="/html")
        tool = resolve_tool("read_page", base_dir=tmp_path)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html; charset=utf-8"}
        mock_response.text = (
            "<html><body><article><h1>Runsight Docs</h1>"
            "<p>Ship tools safely.</p><script>console.log('drop me')</script>"
            "</article></body></html>"
        )

        with (
            patch("runsight_core.tools._catalog.validate_ssrf", new_callable=AsyncMock),
            patch("httpx.AsyncClient") as mock_client,
        ):
            client_instance = AsyncMock()
            client_instance.request.return_value = mock_response
            client_instance.__aenter__ = AsyncMock(return_value=client_instance)
            client_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = client_instance

            result = await tool.execute({})

        assert "Runsight Docs" in result
        assert "Ship tools safely." in result
        assert "<html" not in result.lower()
        assert "<script" not in result.lower()
        assert "console.log" not in result

    @pytest.mark.parametrize("location", ["headers", "body_template"])
    @pytest.mark.asyncio
    async def test_request_tool_missing_env_secret_fails_closed_before_request(
        self, monkeypatch, tmp_path, location: str
    ) -> None:
        from runsight_core.tools import resolve_tool

        monkeypatch.delenv("MISSING_AUTH_VALUE", raising=False)
        write_secure_lookup_request_tool(tmp_path, location=location)
        tool = resolve_tool(f"secure_lookup_{location}", base_dir=tmp_path)

        with patch("httpx.AsyncClient") as mock_client:
            client_instance = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.headers = {"content-type": "application/json"}
            mock_response.text = '{"ok": true}'
            mock_response.json.return_value = {"ok": True}
            client_instance.request.return_value = mock_response
            client_instance.__aenter__ = AsyncMock(return_value=client_instance)
            client_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = client_instance

            with pytest.raises(ValueError, match=r"MISSING_AUTH_VALUE"):
                await tool.execute({})

        client_instance.request.assert_not_called()

    @pytest.mark.asyncio
    async def test_request_tool_oversized_response_invokes_size_policy_and_can_truncate(
        self, tmp_path
    ) -> None:
        from runsight_core.tools import resolve_tool

        write_read_page_request_tool(tmp_path, slug="read_large_page", path="/large")
        response_size_policy = Mock(return_value="truncated body")
        tool = resolve_tool(
            "read_large_page",
            base_dir=tmp_path,
            max_output_bytes=5,
            response_size_policy=response_size_policy,
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/plain"}
        mock_response.text = "0123456789"

        with (
            patch("runsight_core.tools._catalog.validate_ssrf", new_callable=AsyncMock),
            patch("httpx.AsyncClient") as mock_client,
        ):
            client_instance = AsyncMock()
            client_instance.request.return_value = mock_response
            client_instance.__aenter__ = AsyncMock(return_value=client_instance)
            client_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = client_instance

            result = await tool.execute({})

        assert result == "truncated body"
        response_size_policy.assert_called_once()

    @pytest.mark.asyncio
    async def test_request_tool_applies_default_size_cap_when_no_explicit_limit_is_passed(
        self, tmp_path
    ) -> None:
        from runsight_core.tools import resolve_tool

        write_read_page_request_tool(tmp_path, slug="read_large_page", path="/large")
        response_size_policy = Mock(return_value="default-capped body")
        tool = resolve_tool(
            "read_large_page",
            base_dir=tmp_path,
            response_size_policy=response_size_policy,
        )

        large_html = "<html><body>" + ("Alpha " * 300_000) + "</body></html>"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html"}
        mock_response.text = large_html

        with (
            patch("runsight_core.tools._catalog.validate_ssrf", new_callable=AsyncMock),
            patch("httpx.AsyncClient") as mock_client,
        ):
            client_instance = AsyncMock()
            client_instance.request.return_value = mock_response
            client_instance.__aenter__ = AsyncMock(return_value=client_instance)
            client_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = client_instance

            result = await tool.execute({})

        assert result == "default-capped body"
        response_size_policy.assert_called_once()
        assert response_size_policy.call_args.kwargs["max_output_bytes"] is not None

    @pytest.mark.asyncio
    async def test_request_tool_size_policy_can_fail_closed_for_oversized_response(
        self, tmp_path
    ) -> None:
        from runsight_core.tools import resolve_tool

        write_read_page_request_tool(tmp_path, slug="read_large_page", path="/large")
        response_size_policy = Mock(side_effect=ValueError("response exceeded max_output_bytes"))
        tool = resolve_tool(
            "read_large_page",
            base_dir=tmp_path,
            max_output_bytes=5,
            response_size_policy=response_size_policy,
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/plain"}
        mock_response.text = "0123456789"

        with (
            patch("runsight_core.tools._catalog.validate_ssrf", new_callable=AsyncMock),
            patch("httpx.AsyncClient") as mock_client,
        ):
            client_instance = AsyncMock()
            client_instance.request.return_value = mock_response
            client_instance.__aenter__ = AsyncMock(return_value=client_instance)
            client_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = client_instance

            with pytest.raises(ValueError, match="max_output_bytes"):
                await tool.execute({})

        response_size_policy.assert_called_once()
