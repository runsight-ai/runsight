"""Custom python executor tool pipeline tests."""

from __future__ import annotations

import json
from pathlib import Path
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


class TestCustomExecutorToolPipeline:
    """Custom tool metadata should resolve and execute through the agentic loop."""

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_custom_tool_yaml_parse_resolve_and_agentic_loop(
        self,
        mock_achat: AsyncMock,
        tmp_path: Path,
    ) -> None:
        """Custom tool metadata should resolve and execute through the tool loop."""
        _write_custom_tool_yaml(
            tmp_path,
            "adder",
            """\
version: "1.0"
id: adder
kind: tool
type: custom
executor: python
name: Adder
description: Add two integers together.
parameters:
  type: object
  properties:
    a:
      type: integer
    b:
      type: integer
  required:
    - a
    - b
code: |
  def main(args):
      return {"sum": args["a"] + args["b"]}
""",
        )
        workflow_path = _write_workflow_file(
            tmp_path,
            """\
version: "1.0"
id: custom_executor_pipeline
kind: workflow
config:
  model_name: gpt-4o
tools:
  - adder
souls:
  agent:
    id: agent
    kind: soul
    name: Custom Agent
    role: Custom Agent
    provider: openai
    model_name: gpt-4o
    system_prompt: Use the adder tool.
    tools:
      - adder
blocks:
  step:
    type: linear
    soul_ref: agent
workflow:
  name: custom_executor_pipeline
  entry: step
  transitions:
    - from: step
      to: null
""",
        )

        workflow = parse_workflow_yaml(str(workflow_path))
        soul = workflow.blocks["step"].soul

        assert soul.resolved_tools is not None
        assert [tool.name for tool in soul.resolved_tools] == ["adder"]

        mock_achat.side_effect = [
            _tool_call_response("adder", arguments='{"a": 2, "b": 3}', call_id="custom_1"),
            _text_response("Custom tool complete."),
        ]

        runner = RunsightTeamRunner(model_name="gpt-4o")
        result = await runner.execute("Add numbers", None, soul)

        assert result.output == "Custom tool complete."
        assert result.tool_calls_made == ["adder"]

        tool_messages = [
            msg
            for msg in mock_achat.call_args_list[1].kwargs["messages"]
            if msg.get("role") == "tool"
        ]
        assert json.loads(tool_messages[-1]["content"]) == {"sum": 5}
