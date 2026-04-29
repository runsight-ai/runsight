"""Builtin HTTP tool pipeline tests."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from runsight_core.primitives import Soul
from runsight_core.runner import RunsightTeamRunner
from runsight_core.yaml.parser import parse_workflow_yaml
from tool_integration_helpers import (
    _text_response,
    _tool_call_response,
    _workflow_dict,
)


class TestBuiltinHttpToolPipeline:
    """Builtin HTTP execution should feed normalized, extracted, and bounded results into the loop."""

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_builtin_http_tool_pipeline_returns_normalized_json_payload(
        self,
        mock_achat: AsyncMock,
    ) -> None:
        """Builtin http should feed the same normalized JSON payload shape into the loop."""
        yaml_dict = _workflow_dict(
            tools=["http"],
            souls={
                "agent": {
                    "id": "agent",
                    "role": "HTTP Agent",
                    "provider": "openai",
                    "model_name": "gpt-4o",
                    "system_prompt": "Use the builtin http tool.",
                    "tools": ["http"],
                }
            },
            blocks={"step": {"type": "linear", "soul_ref": "agent"}},
        )

        workflow = parse_workflow_yaml(yaml_dict)
        soul = workflow.blocks["step"].soul

        class _FakeResponse:
            status_code = 200
            headers = {"content-type": "application/json"}

            def json(self) -> dict[str, Any]:
                return {"answer": "42"}

            @property
            def text(self) -> str:
                return json.dumps(self.json())

        class _FakeAsyncClient:
            async def __aenter__(self) -> "_FakeAsyncClient":
                return self

            async def __aexit__(self, exc_type, exc, tb) -> None:
                return None

            async def request(
                self,
                method: str,
                url: str,
                headers: dict[str, str] | None = None,
                content: str | None = None,
            ) -> _FakeResponse:
                assert method == "GET"
                assert url == "https://example.com/data"
                assert headers is None
                assert content is None
                return _FakeResponse()

        mock_achat.side_effect = [
            _tool_call_response(
                "http_request",
                arguments='{"method": "GET", "url": "https://example.com/data"}',
                call_id="builtin_http_1",
            ),
            _text_response("Builtin http complete."),
        ]

        with patch("httpx.AsyncClient", _FakeAsyncClient):
            runner = RunsightTeamRunner(model_name="gpt-4o")
            result = await runner.execute("Fetch data", None, soul)

        assert result.output == "Builtin http complete."
        assert result.tool_calls_made == ["http_request"]

        tool_messages = [
            msg
            for msg in mock_achat.call_args_list[1].kwargs["messages"]
            if msg.get("role") == "tool"
        ]
        assert json.loads(tool_messages[-1]["content"]) == {"answer": "42"}

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_builtin_http_tool_pipeline_returns_extracted_json_value_when_response_path_is_provided(
        self,
        mock_achat: AsyncMock,
    ) -> None:
        """Builtin http should feed the extracted nested JSON value into the loop."""
        from runsight_core.tools import resolve_tool

        soul = Soul(
            id="agent_1",
            kind="soul",
            name="HTTP Agent",
            role="HTTP Agent",
            system_prompt="Use the builtin http tool.",
            tools=["http"],
            provider="openai",
            model_name="gpt-4o",
            resolved_tools=[resolve_tool("http")],
        )

        class _FakeResponse:
            status_code = 200
            headers = {"content-type": "application/json"}

            def json(self) -> dict[str, Any]:
                return {"data": {"answer": "42"}}

            @property
            def text(self) -> str:
                return json.dumps(self.json())

        class _FakeAsyncClient:
            async def __aenter__(self) -> "_FakeAsyncClient":
                return self

            async def __aexit__(self, exc_type, exc, tb) -> None:
                return None

            async def request(
                self,
                method: str,
                url: str,
                headers: dict[str, str] | None = None,
                content: str | None = None,
            ) -> _FakeResponse:
                assert method == "GET"
                assert url == "https://example.com/data"
                assert headers is None
                assert content is None
                return _FakeResponse()

        mock_achat.side_effect = [
            _tool_call_response(
                "http_request",
                arguments='{"method": "GET", "url": "https://example.com/data", "response_path": "data.answer"}',
                call_id="builtin_http_response_path_1",
            ),
            _text_response("Builtin http response_path complete."),
        ]

        with patch("httpx.AsyncClient", _FakeAsyncClient):
            runner = RunsightTeamRunner(model_name="gpt-4o")
            result = await runner.execute("Fetch nested data", None, soul)

        assert result.output == "Builtin http response_path complete."
        assert result.tool_calls_made == ["http_request"]

        tool_messages = [
            msg
            for msg in mock_achat.call_args_list[1].kwargs["messages"]
            if msg.get("role") == "tool"
        ]
        assert json.loads(tool_messages[-1]["content"]) == "42"

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_builtin_http_tool_pipeline_caps_and_sanitizes_multiple_large_html_pages(
        self,
        mock_achat: AsyncMock,
    ) -> None:
        """Builtin http should keep repeated large HTML fetches readable and bounded in-loop."""
        yaml_dict = _workflow_dict(
            tools=["http"],
            souls={
                "agent": {
                    "id": "agent",
                    "role": "HTTP Agent",
                    "provider": "openai",
                    "model_name": "gpt-4o",
                    "system_prompt": "Use the builtin http tool.",
                    "tools": ["http"],
                }
            },
            blocks={"step": {"type": "linear", "soul_ref": "agent"}},
        )

        workflow = parse_workflow_yaml(yaml_dict)
        soul = workflow.blocks["step"].soul

        page_inputs = {
            "https://example.com/page-1": (
                "<html><body><article><h1>Runsight Docs One</h1>"
                + "".join(
                    f"<section><h2>Heading {i}</h2><p>Keep responses bounded.</p></section>"
                    for i in range(250)
                )
                + '<script>console.log("drop me")</script></article></body></html>'
            ),
            "https://example.com/page-2": (
                "<html><body><article><h1>Runsight Docs Two</h1>"
                + "".join(
                    f"<div><span>Chunk {i}</span><p>Trim raw HTML before tool replay.</p></div>"
                    for i in range(250)
                )
                + "<style>body { color: red; }</style></article></body></html>"
            ),
        }

        class _FakeResponse:
            status_code = 200
            headers = {"content-type": "text/html; charset=utf-8"}

            def __init__(self, body: str) -> None:
                self._body = body

            @property
            def text(self) -> str:
                return self._body

        class _FakeAsyncClient:
            async def __aenter__(self) -> "_FakeAsyncClient":
                return self

            async def __aexit__(self, exc_type, exc, tb) -> None:
                return None

            async def request(
                self,
                method: str,
                url: str,
                headers: dict[str, str] | None = None,
                content: str | None = None,
            ) -> _FakeResponse:
                assert method == "GET"
                assert url in page_inputs
                assert headers is None
                assert content is None
                return _FakeResponse(page_inputs[url])

        mock_achat.side_effect = [
            _tool_call_response(
                "http_request",
                arguments='{"method": "GET", "url": "https://example.com/page-1"}',
                call_id="builtin_http_html_1",
            ),
            _tool_call_response(
                "http_request",
                arguments='{"method": "GET", "url": "https://example.com/page-2"}',
                call_id="builtin_http_html_2",
            ),
            _text_response("Builtin http HTML complete."),
        ]

        with patch("httpx.AsyncClient", _FakeAsyncClient):
            runner = RunsightTeamRunner(model_name="gpt-4o")
            result = await runner.execute("Fetch two HTML pages", None, soul)

        assert result.output == "Builtin http HTML complete."
        assert result.tool_calls_made == ["http_request", "http_request"]

        tool_messages = [
            msg
            for msg in mock_achat.call_args_list[2].kwargs["messages"]
            if msg.get("role") == "tool"
        ]

        assert len(tool_messages) == 2
        expected_titles = ["Runsight Docs One", "Runsight Docs Two"]
        raw_input_sizes = [
            len(page_inputs["https://example.com/page-1"]),
            len(page_inputs["https://example.com/page-2"]),
        ]
        for message, expected_title, raw_size in zip(
            tool_messages, expected_titles, raw_input_sizes, strict=True
        ):
            assert expected_title in message["content"]
            assert "<html" not in message["content"].lower()
            assert "<script" not in message["content"].lower()
            assert "<style" not in message["content"].lower()
            assert "console.log" not in message["content"]
            assert len(message["content"]) < raw_size
