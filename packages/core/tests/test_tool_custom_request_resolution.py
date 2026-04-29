"""Custom and request tool resolution tests."""

from __future__ import annotations

from pathlib import Path

from runsight_core.yaml.parser import parse_workflow_yaml
from tool_integration_helpers import (
    _write_custom_tool_yaml,
    _write_workflow_file,
)


class TestCustomRequestToolResolution:
    """Custom, request, and builtin tools should resolve predictably from workflow YAML."""

    def test_builtin_custom_and_request_tools_parse_and_resolve_together(
        self,
        tmp_path: Path,
    ) -> None:
        """Mixed workflows should resolve builtin, python, and request tools."""
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
  required:
    - item_id
request:
  method: GET
  url: https://example.com/items/{{ item_id }}
""",
        )
        workflow_path = _write_workflow_file(
            tmp_path,
            """\
version: "1.0"
id: mixed_tool_resolution
kind: workflow
config:
  model_name: gpt-4o
tools:
  - http
  - adder
  - fetch_answer
souls:
  agent:
    id: agent
    kind: soul
    name: Mixed Agent
    role: Mixed Agent
    provider: openai
    model_name: gpt-4o
    system_prompt: Use every tool.
    tools:
      - http
      - adder
      - fetch_answer
blocks:
  step:
    type: linear
    soul_ref: agent
workflow:
  name: mixed_tool_resolution
  entry: step
  transitions:
    - from: step
      to: null
""",
        )

        workflow = parse_workflow_yaml(str(workflow_path))
        soul = workflow.blocks["step"].soul

        assert soul.resolved_tools is not None
        assert {tool.name for tool in soul.resolved_tools} == {
            "http_request",
            "adder",
            "fetch_answer",
        }

    def test_undeclared_tool_parses_with_empty_resolved_tools(self, tmp_path: Path) -> None:
        """Undeclared soul tools should parse and be omitted from resolution."""
        workflow_path = _write_workflow_file(
            tmp_path,
            """\
version: "1.0"
id: undeclared_tool_resolution
kind: workflow
config:
  model_name: gpt-4o
souls:
  agent:
    id: agent
    kind: soul
    name: Agent
    role: Agent
    provider: openai
    model_name: gpt-4o
    system_prompt: Use a missing tool.
    tools:
      - missing_tool
blocks:
  step:
    type: linear
    soul_ref: agent
workflow:
  name: undeclared_tool_resolution
  entry: step
  transitions:
    - from: step
      to: null
""",
        )

        workflow = parse_workflow_yaml(str(workflow_path))
        soul = workflow.blocks["step"].soul
        assert soul.resolved_tools == []
