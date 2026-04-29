"""Tool parsing and canonical ID validation tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from runsight_core.yaml.parser import parse_workflow_yaml
from tool_integration_helpers import (
    _workflow_dict,
    _write_custom_tool_yaml,
    _write_workflow_file,
)

# ===========================================================================
# Scenario 5: Parse validation — undeclared tool ref and unknown source
# ===========================================================================


class TestParseValidation:
    """parse_workflow_yaml must tolerate undeclared soul tools as warnings."""

    def test_soul_references_undeclared_tool_parses_with_empty_resolved_tools(self) -> None:
        """Soul referencing tool not in tools: section -> warning and omission."""
        yaml_dict = _workflow_dict(
            tools=["http"],
            souls={
                "agent": {
                    "id": "agent",
                    "role": "Agent",
                    "provider": "openai",
                    "model_name": "gpt-4o",
                    "system_prompt": "Use tools.",
                    "tools": ["nonexistent_tool"],
                }
            },
            blocks={"step": {"type": "linear", "soul_ref": "agent"}},
        )

        workflow = parse_workflow_yaml(yaml_dict)
        soul = workflow.blocks["step"].soul
        assert soul.resolved_tools == []

    def test_undeclared_tool_warning_mentions_soul_name(self) -> None:
        """Warning for undeclared tool must still identify the soul's key."""
        yaml_dict = _workflow_dict(
            tools=["http"],
            souls={
                "my_special_soul": {
                    "id": "my_special_soul",
                    "role": "Agent",
                    "provider": "openai",
                    "model_name": "gpt-4o",
                    "system_prompt": "Use tools.",
                    "tools": ["missing_tool"],
                }
            },
            blocks={"step": {"type": "linear", "soul_ref": "my_special_soul"}},
        )

        workflow = parse_workflow_yaml(yaml_dict)
        soul = workflow.blocks["step"].soul
        assert soul.resolved_tools == []

    def test_unknown_tool_id_parses_with_empty_resolved_tools(self) -> None:
        """Unknown workflow tool IDs should parse and leave the authored tool list intact."""
        yaml_dict = _workflow_dict(
            tools=["does_not_exist"],
            souls={
                "agent": {
                    "id": "agent",
                    "role": "Agent",
                    "provider": "openai",
                    "model_name": "gpt-4o",
                    "system_prompt": "Use bad tool.",
                    "tools": ["does_not_exist"],
                }
            },
            blocks={"step": {"type": "linear", "soul_ref": "agent"}},
        )

        workflow = parse_workflow_yaml(yaml_dict)
        soul = workflow.blocks["step"].soul
        assert soul.tools == ["does_not_exist"]
        assert soul.resolved_tools == []

    def test_unknown_tool_id_warning_keeps_authored_tool_id(self) -> None:
        """Unknown workflow tool IDs should still be reported through the authored tool id."""
        yaml_dict = _workflow_dict(
            tools=["mystery_281"],
            souls={
                "agent": {
                    "id": "agent",
                    "role": "Agent",
                    "provider": "openai",
                    "model_name": "gpt-4o",
                    "system_prompt": "Use mystery.",
                    "tools": ["mystery_281"],
                }
            },
            blocks={"step": {"type": "linear", "soul_ref": "agent"}},
        )

        workflow = parse_workflow_yaml(yaml_dict)
        soul = workflow.blocks["step"].soul
        assert soul.tools == ["mystery_281"]
        assert soul.resolved_tools == []


class TestCanonicalWorkflowToolIdIntegration:
    """Canonical workflow tool whitelist coverage."""

    def test_canonical_builtin_ids_parse_from_workflow_whitelist(self) -> None:
        """A workflow whitelist like ['http', 'file_io'] should resolve builtin tools end to end."""
        yaml_dict = _workflow_dict(
            tools=["http", "file_io"],
            souls={
                "agent": {
                    "id": "agent",
                    "role": "Agent",
                    "provider": "openai",
                    "model_name": "gpt-4o",
                    "system_prompt": "Use tools.",
                    "tools": ["http", "file_io"],
                }
            },
            blocks={"step": {"type": "linear", "soul_ref": "agent"}},
        )

        workflow = parse_workflow_yaml(yaml_dict)
        soul = workflow.blocks["step"].soul

        assert soul.resolved_tools is not None
        assert {tool.name for tool in soul.resolved_tools} == {"http_request", "file_io"}

    def test_reserved_builtin_id_collision_with_custom_tool_file_raises(
        self, tmp_path: Path
    ) -> None:
        """A custom/tools/http.yaml file must make the reserved builtin http ID invalid."""
        _write_custom_tool_yaml(
            tmp_path,
            "http",
            """\
version: "1.0"
id: http
kind: tool
type: custom
executor: python
name: Shadow HTTP
description: Shadows the builtin http id.
parameters:
  type: object
code: |
  def main(args):
      return {"shadowed": True}
""",
        )
        workflow_file = _write_workflow_file(
            tmp_path,
            """\
version: "1.0"
id: canonical_tool_ids
kind: workflow
config:
  model_name: gpt-4o
tools:
  - http
souls:
  agent:
    id: agent
    kind: soul
    name: Agent
    role: Agent
    provider: openai
    model_name: gpt-4o
    system_prompt: Use tools.
    tools:
      - http
blocks:
  step:
    type: linear
    soul_ref: agent
workflow:
  name: canonical_tool_ids
  entry: step
  transitions:
    - from: step
      to: null
""",
        )

        with pytest.raises(
            ValueError, match=r"reserved.*http.*custom/tools/http\.yaml|collision.*http"
        ):
            parse_workflow_yaml(str(workflow_file))
