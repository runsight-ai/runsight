"""Delegate tool behavior tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from runsight_core.runner import RunsightTeamRunner
from runsight_core.yaml.parser import parse_workflow_yaml
from runsight_core.yaml.schema import ExitDef
from tool_integration_helpers import (
    _text_response,
    _tool_call_response,
    _workflow_dict,
)


class TestDelegateToolBehavior:
    """Delegate tool ports should match block exits and feed selected ports back to the loop."""

    def test_delegate_port_enum_matches_block_exits(self) -> None:
        """Parsed soul with delegate tool has port enum equal to block exits."""
        yaml_dict = _workflow_dict(
            tools=["delegate"],
            souls={
                "gate_agent": {
                    "id": "gate_agent",
                    "role": "Gate Agent",
                    "provider": "openai",
                    "model_name": "gpt-4o",
                    "system_prompt": "Evaluate and route.",
                    "tools": ["delegate"],
                }
            },
            blocks={
                "step": {
                    "type": "linear",
                    "soul_ref": "gate_agent",
                    "exits": [
                        {"id": "approve", "label": "Approve"},
                        {"id": "reject", "label": "Reject"},
                    ],
                }
            },
        )

        workflow = parse_workflow_yaml(yaml_dict)
        soul = workflow.blocks["step"].soul

        assert soul.resolved_tools is not None
        delegate = next(t for t in soul.resolved_tools if t.name == "delegate")
        port_enum = delegate.parameters["properties"]["port"].get("enum")
        assert port_enum is not None
        assert set(port_enum) == {"approve", "reject"}

    @pytest.mark.asyncio
    async def test_delegate_execute_returns_valid_port(self) -> None:
        """Executing delegate with a valid port returns the port string."""
        from runsight_core.tools.delegate import create_delegate_tool

        exits = [ExitDef(id="approve", label="Approve"), ExitDef(id="reject", label="Reject")]
        delegate = create_delegate_tool(exits=exits)

        result = await delegate.execute({"port": "approve"})
        assert result == "approve"

    @pytest.mark.asyncio
    async def test_delegate_execute_returns_reject_port(self) -> None:
        """Executing delegate with 'reject' port returns 'reject'."""
        from runsight_core.tools.delegate import create_delegate_tool

        exits = [ExitDef(id="approve", label="Approve"), ExitDef(id="reject", label="Reject")]
        delegate = create_delegate_tool(exits=exits)

        result = await delegate.execute({"port": "reject"})
        assert result == "reject"

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_delegate_port_returned_in_tool_result(self, mock_achat: AsyncMock) -> None:
        """In the runner loop, delegate execute result (port string) is fed back as tool message."""
        yaml_dict = _workflow_dict(
            tools=["delegate"],
            souls={
                "gate_agent": {
                    "id": "gate_agent",
                    "role": "Gate Agent",
                    "provider": "openai",
                    "model_name": "gpt-4o",
                    "system_prompt": "Delegate.",
                    "tools": ["delegate"],
                    "exits": [
                        {"id": "approve", "label": "Approve"},
                        {"id": "reject", "label": "Reject"},
                    ],
                }
            },
            blocks={
                "step": {
                    "type": "linear",
                    "soul_ref": "gate_agent",
                    "exits": [
                        {"id": "approve", "label": "Approve"},
                        {"id": "reject", "label": "Reject"},
                    ],
                }
            },
        )

        workflow = parse_workflow_yaml(yaml_dict)
        soul = workflow.blocks["step"].soul

        mock_achat.side_effect = [
            _tool_call_response(
                "delegate",
                arguments='{"port": "approve"}',
                call_id="del_1",
            ),
            _text_response("Approved."),
        ]

        runner = RunsightTeamRunner(model_name="gpt-4o")
        result = await runner.execute("test instruction", None, soul)

        assert result.output == "Approved."

        # The tool result message (second call) must include the port value
        second_messages = mock_achat.call_args_list[1].kwargs.get("messages", [])
        tool_msgs = [m for m in second_messages if m.get("role") == "tool"]
        assert len(tool_msgs) >= 1
        assert tool_msgs[0]["content"] == "approve"

    def test_delegate_three_exits_port_enum_complete(self) -> None:
        """With three exits, port enum has all three IDs."""
        yaml_dict = _workflow_dict(
            tools=["delegate"],
            souls={
                "router_agent": {
                    "id": "router_agent",
                    "role": "Router",
                    "provider": "openai",
                    "model_name": "gpt-4o",
                    "system_prompt": "Route.",
                    "tools": ["delegate"],
                }
            },
            blocks={
                "step": {
                    "type": "linear",
                    "soul_ref": "router_agent",
                    "exits": [
                        {"id": "fast", "label": "Fast"},
                        {"id": "slow", "label": "Slow"},
                        {"id": "skip", "label": "Skip"},
                    ],
                }
            },
        )

        workflow = parse_workflow_yaml(yaml_dict)
        soul = workflow.blocks["step"].soul
        delegate = next(t for t in soul.resolved_tools if t.name == "delegate")
        port_enum = delegate.parameters["properties"]["port"]["enum"]
        assert set(port_enum) == {"fast", "slow", "skip"}
