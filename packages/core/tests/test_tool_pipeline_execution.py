"""Smoke coverage for YAML custom tool parsing through runner execution."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from runsight_core.runner import ExecutionResult, RunsightTeamRunner
from runsight_core.yaml.parser import parse_workflow_yaml
from tool_integration_helpers import (
    _text_response,
    _tool_call_response,
    _workflow_dict,
    _write_echo_tool_yaml,
    _write_workflow_dict_file,
)

pytestmark = pytest.mark.real_subprocess_isolation


@pytest.mark.asyncio
@patch("runsight_core.runner.LiteLLMClient.achat")
async def test_yaml_custom_tool_is_resolved_sent_to_llm_executed_and_fed_back(
    mock_achat: AsyncMock,
    tmp_path: Path,
) -> None:
    echo_tool_id = _write_echo_tool_yaml(tmp_path)
    workflow_path = _write_workflow_dict_file(
        tmp_path,
        _workflow_dict(
            tools=[echo_tool_id],
            souls={
                "agent": {
                    "id": "agent",
                    "role": "Test Agent",
                    "provider": "openai",
                    "model_name": "gpt-4o",
                    "system_prompt": "Use the echo tool.",
                    "tools": [echo_tool_id],
                }
            },
            blocks={"step": {"type": "linear", "soul_ref": "agent"}},
        ),
    )

    workflow = parse_workflow_yaml(str(workflow_path))
    soul = workflow.blocks["step"].soul
    assert [tool.name for tool in soul.resolved_tools or []] == ["echo"]

    mock_achat.side_effect = [
        _tool_call_response("echo", arguments='{"message": "ping"}', call_id="c1"),
        _text_response("Echo returned ping."),
    ]

    result = await RunsightTeamRunner(model_name="gpt-4o").execute("test instruction", None, soul)

    assert isinstance(result, ExecutionResult)
    assert result.output == "Echo returned ping."
    assert result.tool_iterations == 1
    assert result.tool_calls_made == ["echo"]

    first_call_tools = mock_achat.call_args_list[0].kwargs["tools"]
    assert first_call_tools[0]["function"]["name"] == "echo"

    second_call_messages = mock_achat.call_args_list[1].kwargs["messages"]
    tool_messages = [message for message in second_call_messages if message.get("role") == "tool"]
    assert json.loads(tool_messages[0]["content"])["echo"]["message"] == "ping"
