"""Request executor tool pipeline tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from runsight_core.runner import RunsightTeamRunner
from runsight_core.yaml.parser import parse_workflow_yaml
from tool_integration_helpers import (
    _text_response,
    _tool_call_response,
    _write_custom_tool_yaml,
    _write_workflow_file,
)


class TestRequestExecutorToolPipeline:
    """Request executor metadata should resolve and feed HTTP results back into the loop."""

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_request_executor_tool_yaml_parse_resolve_and_agentic_loop(
        self,
        mock_achat: AsyncMock,
        tmp_path: Path,
    ) -> None:
        """Request executor metadata should resolve and feed HTTP results back."""
        _write_custom_tool_yaml(
            tmp_path,
            "fetch_answer",
            """\
version: "1.0"
id: fetch_answer
kind: tool
type: custom
executor: request
name: Fetch Answer
description: Fetch an answer from a remote API.
parameters:
  type: object
  properties:
    item_id:
      type: integer
    trace_id:
      type: string
  required:
    - item_id
request:
  method: POST
  url: https://fixture.test/items
  headers:
    X-Trace: static-header
  body_template: '{"item_id": {{ item_id }}, "trace_id": "{{ trace_id }}"}'
  response_path: data.answer
timeout_seconds: 9
""",
        )
        workflow_path = _write_workflow_file(
            tmp_path,
            """\
version: "1.0"
id: request_executor_pipeline
kind: workflow
config:
  model_name: gpt-4o
tools:
  - fetch_answer
souls:
  agent:
    id: agent
    kind: soul
    name: HTTP Agent
    role: HTTP Agent
    provider: openai
    model_name: gpt-4o
    system_prompt: Use the fetch tool.
    tools:
      - fetch_answer
blocks:
  step:
    type: linear
    soul_ref: agent
workflow:
  name: request_executor_pipeline
  entry: step
  transitions:
    - from: step
      to: null
""",
        )

        workflow = parse_workflow_yaml(str(workflow_path))
        soul = workflow.blocks["step"].soul

        class _FakeResponse:
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
                assert method == "POST"
                assert url == "https://fixture.test/items"
                assert headers == {"X-Trace": "static-header"}
                assert content == '{"item_id": 7, "trace_id": "trace-7"}'
                return _FakeResponse()

        mock_achat.side_effect = [
            _tool_call_response(
                "fetch_answer",
                arguments='{"item_id": 7, "trace_id": "trace-7"}',
                call_id="request_1",
            ),
            _text_response("Request tool complete."),
        ]

        with (
            patch("runsight_core.tools._catalog.validate_ssrf", new_callable=AsyncMock),
            patch("httpx.AsyncClient", _FakeAsyncClient),
        ):
            runner = RunsightTeamRunner(model_name="gpt-4o")
            result = await runner.execute("Fetch answer", None, soul)

        assert result.output == "Request tool complete."
        assert result.tool_calls_made == ["fetch_answer"]

        tool_messages = [
            msg
            for msg in mock_achat.call_args_list[1].kwargs["messages"]
            if msg.get("role") == "tool"
        ]
        assert json.loads(tool_messages[-1]["content"]) == "42"
