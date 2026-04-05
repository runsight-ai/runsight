"""
RUN-281 — End-to-end integration tests for the full tool pipeline.

8 integration scenarios:
  1. Full pipeline: YAML dict with tools: -> parse -> soul resolved_tools
     -> runner mock LLM returns tool_call -> tool executed -> result fed back
     -> final answer in ExecutionResult.
  2. Soul isolation: Soul A has [http], Soul B has [file_io]. LLM for Soul A
     only sees http schema; LLM for Soul B only sees file_io schema.
  3. Max iterations: LLM always calls tools. Loop caps at max_tool_iterations,
     last iteration strips tools.
  4. Tool errors: Tool raises. Error fed back to LLM as string, loop continues.
  5. Parse validation: Soul references undeclared tool -> ValueError. Unknown
     source -> ValueError.
  6. Delegate tool: Block with exits + soul with delegate. Port enum matches
     exits; execute returns the selected exit_handle string.
  7. Cost accumulation: 3-iteration loop. ExecutionResult.cost_usd sums all.
  8. No tools path: Soul without tools -> single-shot (current behaviour preserved).

Mocking strategy:
  - LiteLLMClient.achat() is mocked via unittest.mock.patch to return controlled
    dicts — no real API calls ever made.
  - ToolInstance.execute() is real for delegate/file_io where safe; for http we
    skip execute() because it hits the network. We use a custom registered tool
    factory for scenarios that need a safe execute.
"""

from __future__ import annotations

import asyncio
import json
import socket
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import AsyncMock, patch

import pytest
import yaml
from runsight_core.isolation.envelope import ResultEnvelope, ToolDefEnvelope
from runsight_core.isolation.handlers import make_tool_call_handler
from runsight_core.isolation.ipc import IPCServer
from runsight_core.isolation.worker import create_tool_stubs
from runsight_core.primitives import Soul, Task
from runsight_core.runner import ExecutionResult, RunsightTeamRunner
from runsight_core.state import WorkflowState
from runsight_core.tools import ToolInstance
from runsight_core.yaml.parser import parse_workflow_yaml
from runsight_core.yaml.schema import ExitDef

# ---------------------------------------------------------------------------
# Shared response builders (same pattern as test_agentic_tool_loop.py)
# ---------------------------------------------------------------------------


def _text_response(
    content: str = "Done.",
    cost_usd: float = 0.001,
    total_tokens: int = 10,
) -> Dict[str, Any]:
    return {
        "content": content,
        "cost_usd": cost_usd,
        "prompt_tokens": 5,
        "completion_tokens": 5,
        "total_tokens": total_tokens,
        "tool_calls": None,
        "finish_reason": "stop",
        "raw_message": {"role": "assistant", "content": content},
    }


def _tool_call_response(
    tool_name: str,
    arguments: str = "{}",
    call_id: str = "call_001",
    cost_usd: float = 0.002,
    total_tokens: int = 20,
) -> Dict[str, Any]:
    tc = {
        "id": call_id,
        "type": "function",
        "function": {"name": tool_name, "arguments": arguments},
    }
    return {
        "content": "",
        "cost_usd": cost_usd,
        "prompt_tokens": 10,
        "completion_tokens": 10,
        "total_tokens": total_tokens,
        "tool_calls": [tc],
        "finish_reason": "tool_calls",
        "raw_message": {"role": "assistant", "content": "", "tool_calls": [tc]},
    }


# ---------------------------------------------------------------------------
# Minimal YAML dict builder (avoids file-on-disk requirement)
# ---------------------------------------------------------------------------


def _workflow_dict(
    *,
    tools: List[str] | None = None,
    souls: Dict[str, Any] | None = None,
    blocks: Dict[str, Any] | None = None,
    transitions: List[Dict[str, Any]] | None = None,
    entry: str = "step",
    model_name: str = "gpt-4o",
) -> Dict[str, Any]:
    """Build a minimal workflow raw-dict for parse_workflow_yaml()."""
    d: Dict[str, Any] = {
        "version": "1.0",
        "config": {"model_name": model_name},
        "workflow": {
            "name": "integration_test_workflow",
            "entry": entry,
            "transitions": transitions or [{"from": entry, "to": None}],
        },
    }
    if tools:
        d["tools"] = tools
    if souls:
        d["souls"] = souls
    if blocks:
        d["blocks"] = blocks
    return d


# ---------------------------------------------------------------------------
# File helpers for checkout-local custom tool workflows
# ---------------------------------------------------------------------------


def _write_custom_tool_yaml(tmp_path: Path, slug: str, yaml_body: str) -> None:
    tools_dir = tmp_path / "custom" / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)
    (tools_dir / f"{slug}.yaml").write_text(yaml_body, encoding="utf-8")


def _write_workflow_file(tmp_path: Path, yaml_body: str) -> Path:
    workflow_path = tmp_path / "workflow.yaml"
    workflow_path.write_text(yaml_body, encoding="utf-8")
    return workflow_path


def _write_workflow_dict_file(tmp_path: Path, workflow_data: Dict[str, Any]) -> Path:
    workflow_path = tmp_path / "workflow.yaml"
    workflow_path.write_text(yaml.safe_dump(workflow_data, sort_keys=False), encoding="utf-8")
    return workflow_path


# ---------------------------------------------------------------------------
# Safe custom tool fixtures used by integration scenarios
# ---------------------------------------------------------------------------

_ECHO_TOOL_ID = "echo_tool"


def _write_echo_tool_yaml(tmp_path: Path, slug: str = _ECHO_TOOL_ID) -> str:
    _write_custom_tool_yaml(
        tmp_path,
        slug,
        """\
version: "1.0"
type: custom
executor: python
name: Echo Tool
description: Echo values back to the caller.
parameters:
  type: object
  properties:
    message:
      type: string
  required:
    - message
code: |
  def main(args):
      return {"echo": args}
""",
    )
    return slug


def _write_raising_tool_yaml(
    tmp_path: Path,
    slug: str,
    *,
    error_type: str,
    message: str,
) -> str:
    _write_custom_tool_yaml(
        tmp_path,
        slug,
        f"""\
version: "1.0"
type: custom
executor: python
name: {slug.replace("_", " ").title()}
description: Raises an error for integration coverage.
parameters:
  type: object
code: |
  def main(args):
      raise {error_type}({message!r})
""",
    )
    return slug


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
                        "id": "agent_1",
                        "role": "Test Agent",
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
        task = Task(id="t1", instruction="Echo hello.")
        result = await runner.execute_task(task, soul)

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
                        "id": "agent_1",
                        "role": "Test Agent",
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
        task = Task(id="t2", instruction="Ping.")
        await runner.execute_task(task, soul)

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
                        "id": "agent_1",
                        "role": "Test Agent",
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
        task = Task(id="t3", instruction="Do something.")
        await runner.execute_task(task, soul)

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
                    "id": "soul_a_id",
                    "role": "HTTP Agent",
                    "system_prompt": "Make HTTP calls.",
                    "tools": ["http"],
                },
                "soul_b": {
                    "id": "soul_b_id",
                    "role": "File Agent",
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
        task = Task(id="ta", instruction="Make a request.")
        await runner.execute_task(task, soul_a)

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
                    "id": "soul_a_id",
                    "role": "HTTP Agent",
                    "system_prompt": "Make HTTP calls.",
                    "tools": ["http"],
                },
                "soul_b": {
                    "id": "soul_b_id",
                    "role": "File Agent",
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
        task = Task(id="tb", instruction="Read a file.")
        await runner.execute_task(task, soul_b)

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
                    "id": "soul_a_id",
                    "role": "HTTP Agent",
                    "system_prompt": "HTTP.",
                    "tools": ["http"],
                },
                "soul_b": {
                    "id": "soul_b_id",
                    "role": "File Agent",
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
                        "id": "agent_1",
                        "role": "Test Agent",
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
        task = Task(id="t_max", instruction="Keep calling echo.")
        result = await runner.execute_task(task, soul)

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
                        "id": "agent_1",
                        "role": "Test Agent",
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
        task = Task(id="t_strip", instruction="Do it.")
        await runner.execute_task(task, soul)

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
                        "id": "agent_1",
                        "role": "Test Agent",
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
        task = Task(id="t_calls", instruction="Call echo twice.")
        result = await runner.execute_task(task, soul)

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
                        "id": "agent_1",
                        "role": "Test Agent",
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
        task = Task(id="t_err", instruction="Call the failing tool.")
        result = await runner.execute_task(task, soul)

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
                        "id": "agent_1",
                        "role": "Test Agent",
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
        task = Task(id="t_ve", instruction="Trigger error.")
        result = await runner.execute_task(task, soul)

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
        task = Task(id="t_required_missing", instruction="Call every required tool.")
        with pytest.raises(ValueError, match=r"required tool calls completed: slack_webhook"):
            await runner.execute_task(task, soul)

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_runner_requires_tools_while_required_calls_remain(
        self, mock_achat: AsyncMock, tmp_path: Path
    ) -> None:
        from runsight_core.tools import resolve_tool

        echo_tool_id = _write_echo_tool_yaml(tmp_path)
        soul = Soul(
            id="agent_1",
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
        task = Task(id="t_required_choice", instruction="Call the required tool.")
        result = await runner.execute_task(task, soul)

        assert result.output == "Done."
        assert mock_achat.call_args_list[0].kwargs["tool_choice"] == "required"
        assert mock_achat.call_args_list[1].kwargs.get("tool_choice") is None


# ===========================================================================
# Scenario 5: Parse validation — undeclared tool ref and unknown source
# ===========================================================================


class TestParseValidation:
    """parse_workflow_yaml must raise ValueError for bad tool configurations."""

    def test_soul_references_undeclared_tool_raises_value_error(self) -> None:
        """Soul referencing tool not in tools: section -> ValueError."""
        yaml_dict = _workflow_dict(
            tools=["http"],
            souls={
                "agent": {
                    "id": "agent_1",
                    "role": "Agent",
                    "system_prompt": "Use tools.",
                    "tools": ["nonexistent_tool"],
                }
            },
            blocks={"step": {"type": "linear", "soul_ref": "agent"}},
        )

        with pytest.raises(ValueError, match="undeclared tool"):
            parse_workflow_yaml(yaml_dict)

    def test_undeclared_tool_error_mentions_soul_name(self) -> None:
        """ValueError for undeclared tool must mention the soul's key."""
        yaml_dict = _workflow_dict(
            tools=["http"],
            souls={
                "my_special_soul": {
                    "id": "mss_1",
                    "role": "Agent",
                    "system_prompt": "Use tools.",
                    "tools": ["missing_tool"],
                }
            },
            blocks={"step": {"type": "linear", "soul_ref": "my_special_soul"}},
        )

        with pytest.raises(ValueError, match="my_special_soul"):
            parse_workflow_yaml(yaml_dict)

    def test_unknown_tool_id_raises_value_error(self) -> None:
        """Workflow tool IDs not found in the builtin registry or discovered custom tools should fail."""
        yaml_dict = _workflow_dict(
            tools=["does_not_exist"],
            souls={
                "agent": {
                    "id": "agent_1",
                    "role": "Agent",
                    "system_prompt": "Use bad tool.",
                    "tools": ["does_not_exist"],
                }
            },
            blocks={"step": {"type": "linear", "soul_ref": "agent"}},
        )

        with pytest.raises(ValueError):
            parse_workflow_yaml(yaml_dict)

    def test_unknown_tool_id_error_mentions_id_string(self) -> None:
        """ValueError for an unknown workflow tool ID must include the offending ID string."""
        yaml_dict = _workflow_dict(
            tools=["mystery_281"],
            souls={
                "agent": {
                    "id": "agent_1",
                    "role": "Agent",
                    "system_prompt": "Use mystery.",
                    "tools": ["mystery_281"],
                }
            },
            blocks={"step": {"type": "linear", "soul_ref": "agent"}},
        )

        with pytest.raises(ValueError, match="mystery_281"):
            parse_workflow_yaml(yaml_dict)


class TestCanonicalWorkflowToolIdIntegration:
    """RUN-577 integration coverage for the canonical workflow tool whitelist."""

    def test_canonical_builtin_ids_parse_from_workflow_whitelist(self) -> None:
        """A workflow whitelist like ['http', 'file_io'] should resolve builtin tools end to end."""
        yaml_dict = _workflow_dict(
            tools=["http", "file_io"],
            souls={
                "agent": {
                    "id": "agent_1",
                    "role": "Agent",
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
config:
  model_name: gpt-4o
tools:
  - http
souls:
  agent:
    id: agent_1
    role: Agent
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


# ===========================================================================
# Scenario 6: Delegate tool — port enum matches exits; execute returns exit_handle
# ===========================================================================


class TestDelegateTool:
    """Delegate tool integration: port enum built from block exits; executing
    the delegate with a valid port returns that port string (the exit_handle)."""

    def test_delegate_port_enum_matches_block_exits(self) -> None:
        """Parsed soul with delegate tool has port enum equal to block exits."""
        yaml_dict = _workflow_dict(
            tools=["delegate"],
            souls={
                "gate_agent": {
                    "id": "gate_1",
                    "role": "Gate Agent",
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
                    "id": "gate_1",
                    "role": "Gate Agent",
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
        task = Task(id="t_del", instruction="Evaluate and delegate.")
        result = await runner.execute_task(task, soul)

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
                    "id": "router_1",
                    "role": "Router",
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


# ===========================================================================
# Scenario 7: Cost accumulation — 3-iteration loop, cost_usd sums all iterations
# ===========================================================================


class TestCostAccumulationIntegration:
    """ExecutionResult.cost_usd and total_tokens must sum across all achat() calls
    when the runner enters a multi-iteration tool loop."""

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_cost_sums_three_iterations(self, mock_achat: AsyncMock, tmp_path: Path) -> None:
        """3-iteration loop (2 tool calls + 1 final text): cost_usd = sum of all."""
        echo_tool_id = _write_echo_tool_yaml(tmp_path)
        workflow_path = _write_workflow_dict_file(
            tmp_path,
            _workflow_dict(
                tools=[echo_tool_id],
                souls={
                    "agent": {
                        "id": "agent_1",
                        "role": "Test Agent",
                        "system_prompt": "Echo three times.",
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
            _tool_call_response(
                "echo", arguments='{"message": "1"}', call_id="c1", cost_usd=0.001, total_tokens=10
            ),
            _tool_call_response(
                "echo", arguments='{"message": "2"}', call_id="c2", cost_usd=0.002, total_tokens=20
            ),
            _text_response("All done.", cost_usd=0.003, total_tokens=30),
        ]

        runner = RunsightTeamRunner(model_name="gpt-4o")
        task = Task(id="t_cost", instruction="Echo three times.")
        result = await runner.execute_task(task, soul)

        assert result.cost_usd == pytest.approx(0.006)
        assert result.total_tokens == 60
        assert result.tool_iterations == 2

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_cost_accumulation_matches_call_count(
        self, mock_achat: AsyncMock, tmp_path: Path
    ) -> None:
        """cost_usd equals the sum of cost_usd from all achat() calls."""
        echo_tool_id = _write_echo_tool_yaml(tmp_path)
        workflow_path = _write_workflow_dict_file(
            tmp_path,
            _workflow_dict(
                tools=[echo_tool_id],
                souls={
                    "agent": {
                        "id": "agent_1",
                        "role": "Test Agent",
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

        costs = [0.0015, 0.0025, 0.0035]
        tokens = [15, 25, 35]

        mock_achat.side_effect = [
            _tool_call_response(
                "echo",
                arguments='{"message": "a"}',
                call_id="ca",
                cost_usd=costs[0],
                total_tokens=tokens[0],
            ),
            _tool_call_response(
                "echo",
                arguments='{"message": "b"}',
                call_id="cb",
                cost_usd=costs[1],
                total_tokens=tokens[1],
            ),
            _text_response("Final.", cost_usd=costs[2], total_tokens=tokens[2]),
        ]

        runner = RunsightTeamRunner(model_name="gpt-4o")
        task = Task(id="t_cost2", instruction="Echo twice then done.")
        result = await runner.execute_task(task, soul)

        assert result.cost_usd == pytest.approx(sum(costs))
        assert result.total_tokens == sum(tokens)


# ===========================================================================
# Scenario 8: No tools path — soul without tools: single-shot, no loop
# ===========================================================================


class TestNoToolsPath:
    """Soul without tools -> single achat() call, no tool loop, current behaviour preserved."""

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_soul_without_tools_single_achat_call(self, mock_achat: AsyncMock) -> None:
        """Soul without tools: exactly one achat() call, tool_iterations=0."""
        yaml_dict = _workflow_dict(
            souls={
                "plain_agent": {
                    "id": "plain_1",
                    "role": "Plain Agent",
                    "system_prompt": "Just answer.",
                }
            },
            blocks={"step": {"type": "linear", "soul_ref": "plain_agent"}},
        )

        workflow = parse_workflow_yaml(yaml_dict)
        soul = workflow.blocks["step"].soul

        assert soul.resolved_tools is None

        mock_achat.return_value = _text_response("Plain answer.")

        runner = RunsightTeamRunner(model_name="gpt-4o")
        task = Task(id="t_plain", instruction="Tell me something.")
        result = await runner.execute_task(task, soul)

        assert result.output == "Plain answer."
        assert mock_achat.call_count == 1
        assert result.tool_iterations == 0
        assert result.tool_calls_made == []

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_no_tools_achat_not_given_tools_kwarg(self, mock_achat: AsyncMock) -> None:
        """Without resolved_tools, achat() must not receive a tools kwarg (or it's None)."""
        yaml_dict = _workflow_dict(
            souls={
                "plain_agent": {
                    "id": "plain_1",
                    "role": "Plain Agent",
                    "system_prompt": "Just answer.",
                }
            },
            blocks={"step": {"type": "linear", "soul_ref": "plain_agent"}},
        )

        workflow = parse_workflow_yaml(yaml_dict)
        soul = workflow.blocks["step"].soul

        mock_achat.return_value = _text_response("OK.")

        runner = RunsightTeamRunner(model_name="gpt-4o")
        task = Task(id="t_notools", instruction="Do.")
        await runner.execute_task(task, soul)

        call_kwargs = mock_achat.call_args.kwargs
        assert "tools" not in call_kwargs or call_kwargs.get("tools") is None

    def test_parsed_soul_without_tools_has_none_resolved_tools(self) -> None:
        """After parsing, a soul with no tools: field has resolved_tools=None."""
        yaml_dict = _workflow_dict(
            tools=["http"],
            souls={
                "no_tool_soul": {
                    "id": "nt_1",
                    "role": "No Tools",
                    "system_prompt": "I have no tools.",
                }
            },
            blocks={"step": {"type": "linear", "soul_ref": "no_tool_soul"}},
        )

        workflow = parse_workflow_yaml(yaml_dict)
        soul = workflow.blocks["step"].soul

        assert soul.resolved_tools is None

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_no_tools_cost_and_tokens_populated(self, mock_achat: AsyncMock) -> None:
        """Single-shot path: cost_usd and total_tokens still correctly populated."""
        mock_achat.return_value = _text_response("Answer.", cost_usd=0.0042, total_tokens=88)

        soul = Soul(
            id="plain_soul",
            role="Plain",
            system_prompt="Just answer.",
        )

        runner = RunsightTeamRunner(model_name="gpt-4o")
        task = Task(id="t_costs", instruction="Cost test.")
        result = await runner.execute_task(task, soul)

        assert result.cost_usd == pytest.approx(0.0042)
        assert result.total_tokens == 88
        assert result.tool_iterations == 0


# ===========================================================================
# Bonus: YAML workflow files on disk parse successfully after tools: update
# ===========================================================================


CUSTOM_WORKFLOWS_DIR = Path(__file__).resolve().parents[3] / "custom" / "workflows"


class TestExistingYamlWorkflowsParseClean:
    """All existing YAML workflow files in custom/workflows/ must parse without
    error after any tools: section updates. This test will fail if a workflow
    file references an undeclared tool source or has a broken tool reference."""

    def test_mockup_pipeline_yaml_is_valid_yaml(self) -> None:
        """custom/workflows/mockup_pipeline.yaml must be parseable YAML with a tools: section."""
        import yaml

        yaml_path = CUSTOM_WORKFLOWS_DIR / "mockup_pipeline.yaml"
        assert yaml_path.exists(), f"Workflow file missing: {yaml_path}"

        with open(yaml_path) as f:
            raw = yaml.safe_load(f)

        # Must be a dict with required top-level keys
        assert isinstance(raw, dict)
        assert "workflow" in raw
        assert "version" in raw
        # If the workflow declares any tool-using souls, they must reference valid tool keys
        tools_section = raw.get("tools", [])
        souls_section = raw.get("souls", {})
        for soul_key, soul_data in souls_section.items():
            if isinstance(soul_data, dict) and soul_data.get("tools"):
                for tool_ref in soul_data["tools"]:
                    assert tool_ref in tools_section, (
                        f"Soul '{soul_key}' references undeclared tool '{tool_ref}'. "
                        f"Declared tools: {list(tools_section)}"
                    )

    def test_mockup_generate_review_yaml_parses(self) -> None:
        """custom/workflows/mockup_generate_review.yaml must parse successfully."""
        yaml_path = CUSTOM_WORKFLOWS_DIR / "mockup_generate_review.yaml"
        assert yaml_path.exists(), f"Workflow file missing: {yaml_path}"
        workflow = parse_workflow_yaml(str(yaml_path))
        assert workflow is not None


# ===========================================================================
# RUN-532: Full custom/request tool pipeline integration
# ===========================================================================


class TestRun532ToolPipelineIntegration:
    """Integration coverage for custom/request tools across parse, resolve, loop, and IPC seams."""

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_custom_tool_yaml_parse_resolve_and_agentic_loop(
        self,
        mock_achat: AsyncMock,
        tmp_path: Path,
    ) -> None:
        """RUN-532 AC1: custom tool metadata should resolve and execute through the tool loop."""
        _write_custom_tool_yaml(
            tmp_path,
            "adder",
            """\
version: "1.0"
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
config:
  model_name: gpt-4o
tools:
  - adder
souls:
  agent:
    id: agent_1
    role: Custom Agent
    system_prompt: Use the adder tool.
    tools:
      - adder
blocks:
  step:
    type: linear
    soul_ref: agent
workflow:
  name: run_532_custom_pipeline
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
        result = await runner.execute_task(
            Task(id="run-532-custom", instruction="Add numbers"), soul
        )

        assert result.output == "Custom tool complete."
        assert result.tool_calls_made == ["adder"]

        tool_messages = [
            msg
            for msg in mock_achat.call_args_list[1].kwargs["messages"]
            if msg.get("role") == "tool"
        ]
        assert json.loads(tool_messages[-1]["content"]) == {"sum": 5}

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_request_executor_tool_yaml_parse_resolve_and_agentic_loop(
        self,
        mock_achat: AsyncMock,
        tmp_path: Path,
    ) -> None:
        """RUN-532 AC2: request executor metadata should resolve and feed HTTP results back."""
        _write_custom_tool_yaml(
            tmp_path,
            "fetch_answer",
            """\
version: "1.0"
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
  url: https://example.com/items
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
config:
  model_name: gpt-4o
tools:
  - fetch_answer
souls:
  agent:
    id: agent_1
    role: HTTP Agent
    system_prompt: Use the fetch tool.
    tools:
      - fetch_answer
blocks:
  step:
    type: linear
    soul_ref: agent
workflow:
  name: run_532_http_pipeline
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
                assert url == "https://example.com/items"
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

        with patch("httpx.AsyncClient", _FakeAsyncClient):
            runner = RunsightTeamRunner(model_name="gpt-4o")
            result = await runner.execute_task(
                Task(id="run-532-request", instruction="Fetch answer"),
                soul,
            )

        assert result.output == "Request tool complete."
        assert result.tool_calls_made == ["fetch_answer"]

        tool_messages = [
            msg
            for msg in mock_achat.call_args_list[1].kwargs["messages"]
            if msg.get("role") == "tool"
        ]
        assert json.loads(tool_messages[-1]["content"]) == "42"

    @pytest.mark.asyncio
    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_builtin_http_tool_pipeline_returns_normalized_json_payload(
        self,
        mock_achat: AsyncMock,
    ) -> None:
        """RUN-582: builtin http should feed the same normalized JSON payload shape into the loop."""
        yaml_dict = _workflow_dict(
            tools=["http"],
            souls={
                "agent": {
                    "id": "agent_1",
                    "role": "HTTP Agent",
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
            result = await runner.execute_task(
                Task(id="run-582-builtin-http", instruction="Fetch data"),
                soul,
            )

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
        """RUN-597: builtin http should feed the extracted nested JSON value into the loop."""
        from runsight_core.tools import resolve_tool

        soul = Soul(
            id="agent_1",
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
            result = await runner.execute_task(
                Task(id="run-597-builtin-http", instruction="Fetch nested data"),
                soul,
            )

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
        """RUN-489: builtin http should keep repeated large HTML fetches readable and bounded in-loop."""
        yaml_dict = _workflow_dict(
            tools=["http"],
            souls={
                "agent": {
                    "id": "agent_1",
                    "role": "HTTP Agent",
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
            result = await runner.execute_task(
                Task(id="run-489-builtin-http-html", instruction="Fetch two HTML pages"),
                soul,
            )

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

    def test_builtin_custom_and_request_tools_parse_and_resolve_together(
        self,
        tmp_path: Path,
    ) -> None:
        """RUN-532 AC3 + AC6: mixed workflows should resolve builtin, python, and request tools."""
        _write_custom_tool_yaml(
            tmp_path,
            "adder",
            """\
version: "1.0"
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
config:
  model_name: gpt-4o
tools:
  - http
  - adder
  - fetch_answer
souls:
  agent:
    id: agent_1
    role: Mixed Agent
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
  name: run_532_mixed_pipeline
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

    def test_undeclared_tool_raises_actionable_valueerror(self, tmp_path: Path) -> None:
        """RUN-532 AC4: governance errors should stay actionable in the end-to-end parse path."""
        workflow_path = _write_workflow_file(
            tmp_path,
            """\
version: "1.0"
config:
  model_name: gpt-4o
souls:
  agent:
    id: agent_1
    role: Agent
    system_prompt: Use a missing tool.
    tools:
      - missing_tool
blocks:
  step:
    type: linear
    soul_ref: agent
workflow:
  name: run_532_governance_error
  entry: step
  transitions:
    - from: step
      to: null
""",
        )

        with pytest.raises(
            ValueError,
            match=r"agent.*undeclared tool 'missing_tool'.*Declared tools: \[\]",
        ):
            parse_workflow_yaml(str(workflow_path))

    @pytest.mark.asyncio
    async def test_ipc_tool_call_round_trip_returns_engine_tool_output(
        self, tmp_path: Path
    ) -> None:
        """RUN-532 AC5: worker-side tool stubs should round-trip through IPC tool_call."""

        async def _echo(args: dict[str, Any]) -> str:
            return f"echo:{args['value']}"

        socket_path = tmp_path / "tool_call.sock"
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.bind(str(socket_path))
        sock.listen(1)

        server = IPCServer(
            sock=sock,
            handlers={
                "tool_call": make_tool_call_handler(
                    {
                        "echo_tool": ToolInstance(
                            name="echo_tool",
                            description="Echo values.",
                            parameters={
                                "type": "object",
                                "properties": {"value": {"type": "string"}},
                                "required": ["value"],
                            },
                            execute=_echo,
                        )
                    }
                )
            },
        )
        server_task = asyncio.create_task(server.serve())
        await asyncio.sleep(0)

        try:
            stubs = create_tool_stubs(
                [
                    ToolDefEnvelope(
                        source="echo_tool",
                        config={},
                        exits=[],
                        name="echo_tool",
                        description="Echo values.",
                        parameters={
                            "type": "object",
                            "properties": {"value": {"type": "string"}},
                            "required": ["value"],
                        },
                        tool_type="custom",
                    )
                ],
                socket_path=str(socket_path),
            )

            assert await stubs[0].execute({"value": "hi"}) == "echo:hi"
        finally:
            await server.shutdown()
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass
            sock.close()
            socket_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_isolated_linear_block_envelope_includes_tool_definitions_for_worker_loop(
        self,
        tmp_path: Path,
    ) -> None:
        """RUN-532 AC5 + AC6: isolated execution must ship resolved tool metadata to the worker."""
        _write_custom_tool_yaml(
            tmp_path,
            "adder",
            """\
version: "1.0"
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
config:
  model_name: gpt-4o
tools:
  - http
  - adder
  - fetch_answer
souls:
  agent:
    id: agent_1
    role: Mixed Agent
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
  name: run_532_isolated_envelope
  entry: step
  transitions:
    - from: step
      to: null
""",
        )

        workflow = parse_workflow_yaml(str(workflow_path))
        block = workflow.blocks["step"]
        state = WorkflowState(current_task=Task(id="run-532-envelope", instruction="Do work"))
        captured: dict[str, Any] = {}

        async def _capture(envelope: Any) -> ResultEnvelope:
            captured["envelope"] = envelope
            return ResultEnvelope(
                block_id="step",
                output="done",
                exit_handle="done",
                cost_usd=0.0,
                total_tokens=0,
                tool_calls_made=0,
                delegate_artifacts={},
                conversation_history=[],
                error=None,
                error_type=None,
            )

        with patch.object(block, "_run_in_subprocess", side_effect=_capture):
            await block.execute(state)

        envelope = captured["envelope"]
        assert [tool.name for tool in envelope.tools] == ["http_request", "adder", "fetch_answer"]
        assert {tool.tool_type for tool in envelope.tools} == {"builtin", "custom"}
