"""Tool pipeline execution, isolation, iteration, and error feedback tests."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from runsight_core.primitives import Soul
from runsight_core.runner import ExecutionResult, RunsightTeamRunner
from runsight_core.yaml.parser import parse_workflow_yaml
from tool_integration_helpers import (
    _text_response,
    _tool_call_response,
    _workflow_dict,
    _write_echo_tool_yaml,
    _write_raising_tool_yaml,
    _write_workflow_dict_file,
)

# ===========================================================================
# Scenario 1: Full pipeline — YAML dict -> parse -> soul resolved_tools ->
#              execute -> tool call -> result fed back -> final answer
# ===========================================================================


class TestFullPipeline:
    """End-to-end: YAML dict with tools: section parsed, soul gets resolved_tools,
    runner enters tool loop, final ExecutionResult contains correct output."""

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_yaml_parse_and_execute_with_tool_call(
        self, mock_achat: AsyncMock, tmp_path: Path
    ) -> None:
        """Full pipeline: parse YAML dict, run task with tool call, get final output."""
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

        # Verify soul got resolved_tools from parse
        soul = workflow.blocks["step"].soul
        assert soul.resolved_tools is not None
        assert len(soul.resolved_tools) == 1
        assert soul.resolved_tools[0].name == "echo"

        # Now run execute_task with mocked LLM
        mock_achat.side_effect = [
            _tool_call_response("echo", arguments='{"message": "hello"}', call_id="c1"),
            _text_response("Tool call done, echo returned hello."),
        ]

        runner = RunsightTeamRunner(model_name="gpt-4o")
        result = await runner.execute("test instruction", None, soul)

        assert isinstance(result, ExecutionResult)
        assert (
            "hello" in result.output.lower()
            or result.output == "Tool call done, echo returned hello."
        )
        assert result.tool_iterations >= 1
        assert "echo" in result.tool_calls_made

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_tool_execute_receives_parsed_args(
        self, mock_achat: AsyncMock, tmp_path: Path
    ) -> None:
        """The echo tool's execute() is called with the parsed JSON arguments."""
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
                        "system_prompt": "Use echo.",
                        "tools": [echo_tool_id],
                    }
                },
                blocks={"step": {"type": "linear", "soul_ref": "agent"}},
            ),
        )

        workflow = parse_workflow_yaml(str(workflow_path))
        soul = workflow.blocks["step"].soul

        mock_achat.side_effect = [
            _tool_call_response("echo", arguments='{"message": "ping"}', call_id="c2"),
            _text_response("ping echoed"),
        ]

        runner = RunsightTeamRunner(model_name="gpt-4o")
        await runner.execute("test instruction", None, soul)

        # Tool result message should be present in second call
        second_call_messages = mock_achat.call_args_list[1].kwargs.get("messages", [])
        tool_msgs = [m for m in second_call_messages if m.get("role") == "tool"]
        assert len(tool_msgs) >= 1
        tool_result = json.loads(tool_msgs[0]["content"])
        assert tool_result["echo"]["message"] == "ping"

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_tool_schema_sent_to_llm(self, mock_achat: AsyncMock, tmp_path: Path) -> None:
        """The first LLM call must receive the resolved tool's OpenAI schema."""
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
                        "system_prompt": "Use echo.",
                        "tools": [echo_tool_id],
                    }
                },
                blocks={"step": {"type": "linear", "soul_ref": "agent"}},
            ),
        )

        workflow = parse_workflow_yaml(str(workflow_path))
        soul = workflow.blocks["step"].soul

        mock_achat.side_effect = [_text_response("Direct answer.")]

        runner = RunsightTeamRunner(model_name="gpt-4o")
        await runner.execute("test instruction", None, soul)

        first_call_kwargs = mock_achat.call_args_list[0].kwargs
        assert "tools" in first_call_kwargs
        tools_sent = first_call_kwargs["tools"]
        assert isinstance(tools_sent, list)
        assert len(tools_sent) == 1
        assert tools_sent[0]["function"]["name"] == "echo"


# ===========================================================================
# Scenario 2: Soul isolation — Soul A only sees http schema; Soul B only sees file_io schema
# ===========================================================================


class TestSoulIsolation:
    """When two souls have different tool sets, each LLM call only sees its own
    soul's resolved tools — not tools belonging to the other soul."""

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_soul_a_only_sees_http_schema(self, mock_achat: AsyncMock) -> None:
        """Soul A (http tool) — LLM call receives only the http_request schema."""
        yaml_dict = _workflow_dict(
            tools=["http", "file_io"],
            souls={
                "soul_a": {
                    "id": "soul_a",
                    "role": "HTTP Agent",
                    "provider": "openai",
                    "model_name": "gpt-4o",
                    "system_prompt": "Make HTTP calls.",
                    "tools": ["http"],
                },
                "soul_b": {
                    "id": "soul_b",
                    "role": "File Agent",
                    "provider": "openai",
                    "model_name": "gpt-4o",
                    "system_prompt": "Read files.",
                    "tools": ["file_io"],
                },
            },
            blocks={
                "block_a": {"type": "linear", "soul_ref": "soul_a"},
                "block_b": {"type": "linear", "soul_ref": "soul_b"},
            },
            transitions=[
                {"from": "block_a", "to": "block_b"},
                {"from": "block_b", "to": None},
            ],
            entry="block_a",
        )

        workflow = parse_workflow_yaml(yaml_dict)
        soul_a = workflow.blocks["block_a"].soul

        mock_achat.return_value = _text_response("HTTP done.")

        runner = RunsightTeamRunner(model_name="gpt-4o")
        await runner.execute("test instruction", None, soul_a)

        call_kwargs = mock_achat.call_args.kwargs
        tools_sent = call_kwargs.get("tools", [])
        tool_names = [t["function"]["name"] for t in tools_sent]

        assert "http_request" in tool_names
        assert "file_io" not in tool_names

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_soul_b_only_sees_file_io_schema(self, mock_achat: AsyncMock) -> None:
        """Soul B (file_io tool) — LLM call receives only the file_io schema."""
        yaml_dict = _workflow_dict(
            tools=["http", "file_io"],
            souls={
                "soul_a": {
                    "id": "soul_a",
                    "role": "HTTP Agent",
                    "provider": "openai",
                    "model_name": "gpt-4o",
                    "system_prompt": "Make HTTP calls.",
                    "tools": ["http"],
                },
                "soul_b": {
                    "id": "soul_b",
                    "role": "File Agent",
                    "provider": "openai",
                    "model_name": "gpt-4o",
                    "system_prompt": "Read files.",
                    "tools": ["file_io"],
                },
            },
            blocks={
                "block_a": {"type": "linear", "soul_ref": "soul_a"},
                "block_b": {"type": "linear", "soul_ref": "soul_b"},
            },
            transitions=[
                {"from": "block_a", "to": "block_b"},
                {"from": "block_b", "to": None},
            ],
            entry="block_a",
        )

        workflow = parse_workflow_yaml(yaml_dict)
        soul_b = workflow.blocks["block_b"].soul

        mock_achat.return_value = _text_response("File done.")

        runner = RunsightTeamRunner(model_name="gpt-4o")
        await runner.execute("test instruction", None, soul_b)

        call_kwargs = mock_achat.call_args.kwargs
        tools_sent = call_kwargs.get("tools", [])
        tool_names = [t["function"]["name"] for t in tools_sent]

        assert "file_io" in tool_names
        assert "http_request" not in tool_names

    def test_parsed_soul_a_resolved_tools_contains_only_http(self) -> None:
        """After parsing, soul_a.resolved_tools contains only http_request."""
        yaml_dict = _workflow_dict(
            tools=["http", "file_io"],
            souls={
                "soul_a": {
                    "id": "soul_a",
                    "role": "HTTP Agent",
                    "provider": "openai",
                    "model_name": "gpt-4o",
                    "system_prompt": "HTTP.",
                    "tools": ["http"],
                },
                "soul_b": {
                    "id": "soul_b",
                    "role": "File Agent",
                    "provider": "openai",
                    "model_name": "gpt-4o",
                    "system_prompt": "Files.",
                    "tools": ["file_io"],
                },
            },
            blocks={
                "block_a": {"type": "linear", "soul_ref": "soul_a"},
                "block_b": {"type": "linear", "soul_ref": "soul_b"},
            },
            transitions=[
                {"from": "block_a", "to": "block_b"},
                {"from": "block_b", "to": None},
            ],
            entry="block_a",
        )

        workflow = parse_workflow_yaml(yaml_dict)
        soul_a = workflow.blocks["block_a"].soul
        soul_b = workflow.blocks["block_b"].soul

        assert soul_a.resolved_tools is not None
        assert len(soul_a.resolved_tools) == 1
        assert soul_a.resolved_tools[0].name == "http_request"

        assert soul_b.resolved_tools is not None
        assert len(soul_b.resolved_tools) == 1
        assert soul_b.resolved_tools[0].name == "file_io"


# ===========================================================================
# Scenario 3: Max iterations — loop caps, last iteration strips tools
# ===========================================================================


class TestMaxIterationsIntegration:
    """Runner caps tool loop at soul.max_tool_iterations and strips tools
    on the final forced response."""

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_loop_caps_at_max_tool_iterations(
        self, mock_achat: AsyncMock, tmp_path: Path
    ) -> None:
        """With max_tool_iterations=2, loop stops after 2 tool iterations."""
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
                        "system_prompt": "Always call echo.",
                        "tools": [echo_tool_id],
                        "max_tool_iterations": 2,
                    }
                },
                blocks={"step": {"type": "linear", "soul_ref": "agent"}},
            ),
        )

        workflow = parse_workflow_yaml(str(workflow_path))
        soul = workflow.blocks["step"].soul

        # LLM always calls the tool; after max iterations, forced final response
        mock_achat.side_effect = [
            _tool_call_response("echo", arguments='{"message": "a"}', call_id="c1"),
            _tool_call_response("echo", arguments='{"message": "b"}', call_id="c2"),
            _text_response("Max iterations reached."),
        ]

        runner = RunsightTeamRunner(model_name="gpt-4o")
        result = await runner.execute("test instruction", None, soul)

        assert result.output == "Max iterations reached."
        assert result.tool_iterations == 2

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_last_iteration_call_strips_tools(
        self, mock_achat: AsyncMock, tmp_path: Path
    ) -> None:
        """On the last iteration (iteration == max-1), tools= is passed as []."""
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
                        "system_prompt": "Echo always.",
                        "tools": [echo_tool_id],
                        "max_tool_iterations": 1,
                    }
                },
                blocks={"step": {"type": "linear", "soul_ref": "agent"}},
            ),
        )

        workflow = parse_workflow_yaml(str(workflow_path))
        soul = workflow.blocks["step"].soul

        # max_tool_iterations=1: first iteration (iteration=0) is the last,
        # so tools must be stripped to []
        mock_achat.side_effect = [_text_response("Forced.")]

        runner = RunsightTeamRunner(model_name="gpt-4o")
        await runner.execute("test instruction", None, soul)

        call_kwargs = mock_achat.call_args_list[0].kwargs
        assert call_kwargs.get("tools") == []

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_tool_calls_made_tracks_all_iterations(
        self, mock_achat: AsyncMock, tmp_path: Path
    ) -> None:
        """tool_calls_made in ExecutionResult lists every tool called across iterations."""
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
                        "system_prompt": "Echo.",
                        "tools": [echo_tool_id],
                        "max_tool_iterations": 5,
                    }
                },
                blocks={"step": {"type": "linear", "soul_ref": "agent"}},
            ),
        )

        workflow = parse_workflow_yaml(str(workflow_path))
        soul = workflow.blocks["step"].soul

        mock_achat.side_effect = [
            _tool_call_response("echo", arguments='{"message": "1"}', call_id="c1"),
            _tool_call_response("echo", arguments='{"message": "2"}', call_id="c2"),
            _text_response("Done."),
        ]

        runner = RunsightTeamRunner(model_name="gpt-4o")
        result = await runner.execute("test instruction", None, soul)

        assert result.tool_calls_made.count("echo") == 2


# ===========================================================================
# Scenario 4: Tool errors — error string fed back, loop continues
# ===========================================================================


class TestToolErrorFeedback:
    """When a real ToolInstance.execute() raises, the error is caught and
    fed back to the LLM as a tool message string; the loop continues."""

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_tool_error_fed_back_as_string(
        self, mock_achat: AsyncMock, tmp_path: Path
    ) -> None:
        """Tool raises RuntimeError -> error message sent to LLM as tool result."""
        failing_tool_id = _write_raising_tool_yaml(
            tmp_path,
            "failing_tool",
            error_type="RuntimeError",
            message="Simulated tool failure",
        )
        workflow_path = _write_workflow_dict_file(
            tmp_path,
            _workflow_dict(
                tools=[failing_tool_id],
                souls={
                    "agent": {
                        "id": "agent",
                        "role": "Test Agent",
                        "provider": "openai",
                        "model_name": "gpt-4o",
                        "system_prompt": "Use the fail tool.",
                        "tools": [failing_tool_id],
                    }
                },
                blocks={"step": {"type": "linear", "soul_ref": "agent"}},
            ),
        )

        workflow = parse_workflow_yaml(str(workflow_path))
        soul = workflow.blocks["step"].soul

        mock_achat.side_effect = [
            _tool_call_response("failing_tool", call_id="c_fail"),
            _text_response("Recovered after error."),
        ]

        runner = RunsightTeamRunner(model_name="gpt-4o")
        result = await runner.execute("test instruction", None, soul)

        # Loop must not crash; final output returned
        assert result.output == "Recovered after error."
        assert mock_achat.call_count == 2

        # The error must be present in the second call's tool messages
        second_messages = mock_achat.call_args_list[1].kwargs.get("messages", [])
        tool_msgs = [m for m in second_messages if m.get("role") == "tool"]
        assert len(tool_msgs) >= 1
        assert "Simulated tool failure" in tool_msgs[0]["content"]

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_tool_error_loop_does_not_raise(
        self, mock_achat: AsyncMock, tmp_path: Path
    ) -> None:
        """An exception in tool.execute() must not propagate out of execute_task()."""
        error_tool_id = _write_raising_tool_yaml(
            tmp_path,
            "error_tool",
            error_type="ValueError",
            message="Intentional ValueError",
        )
        workflow_path = _write_workflow_dict_file(
            tmp_path,
            _workflow_dict(
                tools=[error_tool_id],
                souls={
                    "agent": {
                        "id": "agent",
                        "role": "Test Agent",
                        "provider": "openai",
                        "model_name": "gpt-4o",
                        "system_prompt": "Use err tool.",
                        "tools": [error_tool_id],
                    }
                },
                blocks={"step": {"type": "linear", "soul_ref": "agent"}},
            ),
        )

        workflow = parse_workflow_yaml(str(workflow_path))
        soul = workflow.blocks["step"].soul

        mock_achat.side_effect = [
            _tool_call_response("error_tool", call_id="c_ve"),
            _text_response("Survived ValueError."),
        ]

        runner = RunsightTeamRunner(model_name="gpt-4o")
        result = await runner.execute("test instruction", None, soul)

        assert result.output == "Survived ValueError."


class TestRequiredToolCalls:
    """Souls can require specific tool calls before the runner accepts completion."""

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_runner_fails_when_required_tool_calls_are_missing(
        self, mock_achat: AsyncMock, tmp_path: Path
    ) -> None:
        from runsight_core.tools import resolve_tool

        echo_tool_id = _write_echo_tool_yaml(tmp_path)
        soul = Soul(
            id="agent_1",
            kind="soul",
            name="Test Agent",
            role="Test Agent",
            system_prompt="Use the echo tool.",
            tools=[echo_tool_id],
            required_tool_calls=["echo", "slack_webhook"],
            max_tool_iterations=3,
            provider="openai",
            model_name="gpt-4o",
            resolved_tools=[resolve_tool(echo_tool_id, base_dir=tmp_path)],
        )

        mock_achat.side_effect = [
            _tool_call_response("echo", arguments='{"message": "hello"}', call_id="c1"),
            _text_response("Done."),
        ]

        runner = RunsightTeamRunner(model_name="gpt-4o")
        with pytest.raises(ValueError, match=r"required tool calls completed: slack_webhook"):
            await runner.execute("test instruction", None, soul)

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_runner_requires_tools_while_required_calls_remain(
        self, mock_achat: AsyncMock, tmp_path: Path
    ) -> None:
        from runsight_core.tools import resolve_tool

        echo_tool_id = _write_echo_tool_yaml(tmp_path)
        soul = Soul(
            id="agent_1",
            kind="soul",
            name="Test Agent",
            role="Test Agent",
            system_prompt="Use the echo tool.",
            tools=[echo_tool_id],
            required_tool_calls=["echo"],
            max_tool_iterations=3,
            provider="openai",
            model_name="gpt-4o",
            resolved_tools=[resolve_tool(echo_tool_id, base_dir=tmp_path)],
        )

        mock_achat.side_effect = [
            _tool_call_response("echo", arguments='{"message": "hello"}', call_id="c1"),
            _text_response("Done."),
        ]

        runner = RunsightTeamRunner(model_name="gpt-4o")
        result = await runner.execute("test instruction", None, soul)

        assert result.output == "Done."
        assert mock_achat.call_args_list[0].kwargs["tool_choice"] == "required"
        assert mock_achat.call_args_list[1].kwargs.get("tool_choice") is None
