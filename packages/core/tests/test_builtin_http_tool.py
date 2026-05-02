"""Built-in HTTP tool behavior."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from runsight_core.security import SSRFError
from runsight_core.tools import ToolInstance, resolve_tool


def _mock_response(*, body: str, content_type: str, status_code: int = 200, json_value=None):
    response = MagicMock()
    response.status_code = status_code
    response.headers = {"content-type": content_type}
    response.text = body
    if json_value is not None:
        response.json.return_value = json_value
    return response


async def _execute_with_mock_response(tool, args: dict, response):
    with patch("httpx.AsyncClient") as mock_client_type:
        client = AsyncMock()
        client.request.return_value = response
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        mock_client_type.return_value = client
        return await tool.execute(args)


def test_http_factory_returns_named_tool_with_request_schema() -> None:
    from runsight_core.tools.http import create_http_tool

    tool = create_http_tool()

    assert isinstance(tool, ToolInstance)
    assert tool.name == "http_request"
    assert {"method", "url", "headers", "body", "response_path"}.issubset(
        tool.parameters["properties"]
    )
    assert {"method", "url"}.issubset(tool.parameters["required"])
    assert tool.to_openai_schema()["function"]["name"] == "http_request"


@pytest.fixture(autouse=True)
def _mock_ssrf_for_success_paths(request):
    if request.node.name in {
        "test_http_blocks_private_ip_before_request",
        "test_http_dns_resolution_failure_fails_closed_before_request",
    }:
        yield
        return
    with patch("runsight_core.tools._catalog.validate_ssrf", new_callable=AsyncMock):
        yield


@pytest.mark.asyncio
async def test_http_returns_normalized_json_and_response_path_values() -> None:
    tool = resolve_tool("http")
    payload = {"data": {"answer": "42", "items": ["a", "b"]}}
    response = _mock_response(
        body=json.dumps(payload), content_type="application/json", json_value=payload
    )

    full_result = await _execute_with_mock_response(
        tool,
        {"method": "GET", "url": "https://fixture.test/api"},
        response,
    )
    path_result = await _execute_with_mock_response(
        tool,
        {"method": "GET", "url": "https://fixture.test/api", "response_path": "data.items"},
        response,
    )

    assert json.loads(full_result) == payload
    assert json.loads(path_result) == ["a", "b"]


@pytest.mark.asyncio
@pytest.mark.parametrize("response_path", ["data.missing", "", "data..answer"])
async def test_http_invalid_or_missing_response_path_raises_valueerror(response_path: str) -> None:
    tool = resolve_tool("http")
    payload = {"data": {"answer": "42"}}
    response = _mock_response(
        body=json.dumps(payload), content_type="application/json", json_value=payload
    )

    with pytest.raises(ValueError, match="Response path"):
        await _execute_with_mock_response(
            tool,
            {"method": "GET", "url": "https://fixture.test/api", "response_path": response_path},
            response,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("content_type", "body", "expected"),
    [
        ("text/plain", "hello", "hello"),
        (
            "text/html; charset=utf-8",
            "<html><body><h1>Runsight Docs</h1><script>drop()</script></body></html>",
            "Runsight Docs",
        ),
    ],
)
async def test_http_returns_textual_responses_without_json_wrapper(
    content_type: str,
    body: str,
    expected: str,
) -> None:
    tool = resolve_tool("http")
    response = _mock_response(body=body, content_type=content_type)

    result = await _execute_with_mock_response(
        tool,
        {"method": "GET", "url": "https://fixture.test/docs", "response_path": "data.answer"},
        response,
    )

    assert expected in result
    assert "<script" not in result.lower()


@pytest.mark.asyncio
async def test_http_blocks_private_ip_before_request() -> None:
    tool = resolve_tool("http")

    with patch("httpx.AsyncClient") as mock_client_type:
        client = AsyncMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        mock_client_type.return_value = client

        with pytest.raises(SSRFError):
            await tool.execute({"method": "GET", "url": "http://192.168.1.1/admin"})

    client.request.assert_not_called()


@pytest.mark.asyncio
async def test_http_dns_resolution_failure_fails_closed_before_request() -> None:
    tool = resolve_tool("http")
    fake_loop = Mock()
    fake_loop.getaddrinfo = AsyncMock(side_effect=OSError("temporary DNS failure"))

    with patch("runsight_core.security.asyncio.get_running_loop", return_value=fake_loop):
        with patch("httpx.AsyncClient") as mock_client_type:
            client = AsyncMock()
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=False)
            mock_client_type.return_value = client

            with pytest.raises(SSRFError):
                await tool.execute({"method": "GET", "url": "https://provider.example/api"})

    client.request.assert_not_called()


@pytest.mark.asyncio
async def test_http_applies_response_size_policy_after_normalization() -> None:
    response_size_policy = Mock(return_value="truncated body")
    tool = resolve_tool("http", max_output_bytes=5, response_size_policy=response_size_policy)
    payload = {"data": {"answer": "0123456789"}}
    response = _mock_response(
        body=json.dumps(payload), content_type="application/json", json_value=payload
    )

    result = await _execute_with_mock_response(
        tool,
        {"method": "GET", "url": "https://fixture.test/api", "response_path": "data.answer"},
        response,
    )

    assert result == "truncated body"
    response_size_policy.assert_called_once_with('"0123456789"', max_output_bytes=5)
