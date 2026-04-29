"""Tool runner cost accumulation and no-tools path tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from runsight_core.primitives import Soul
from runsight_core.runner import RunsightTeamRunner
from runsight_core.yaml.parser import parse_workflow_yaml
from tool_integration_helpers import (
    _text_response,
    _tool_call_response,
    _workflow_dict,
    _write_echo_tool_yaml,
    _write_workflow_dict_file,
)

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
                        "id": "agent",
                        "role": "Test Agent",
                        "provider": "openai",
                        "model_name": "gpt-4o",
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
        result = await runner.execute("test instruction", None, soul)

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
        result = await runner.execute("test instruction", None, soul)

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
                    "id": "plain_agent",
                    "role": "Plain Agent",
                    "provider": "openai",
                    "model_name": "gpt-4o",
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
        result = await runner.execute("test instruction", None, soul)

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
                    "id": "plain_agent",
                    "role": "Plain Agent",
                    "provider": "openai",
                    "model_name": "gpt-4o",
                    "system_prompt": "Just answer.",
                }
            },
            blocks={"step": {"type": "linear", "soul_ref": "plain_agent"}},
        )

        workflow = parse_workflow_yaml(yaml_dict)
        soul = workflow.blocks["step"].soul

        mock_achat.return_value = _text_response("OK.")

        runner = RunsightTeamRunner(model_name="gpt-4o")
        await runner.execute("test instruction", None, soul)

        call_kwargs = mock_achat.call_args.kwargs
        assert "tools" not in call_kwargs or call_kwargs.get("tools") is None

    def test_parsed_soul_without_tools_has_none_resolved_tools(self) -> None:
        """After parsing, a soul with no tools: field has resolved_tools=None."""
        yaml_dict = _workflow_dict(
            tools=["http"],
            souls={
                "no_tool_soul": {
                    "id": "no_tool_soul",
                    "role": "No Tools",
                    "provider": "openai",
                    "model_name": "gpt-4o",
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
            kind="soul",
            name="Plain",
            role="Plain",
            system_prompt="Just answer.",
            provider="openai",
            model_name="gpt-4o",
        )

        runner = RunsightTeamRunner(model_name="gpt-4o")
        result = await runner.execute("test instruction", None, soul)

        assert result.cost_usd == pytest.approx(0.0042)
        assert result.total_tokens == 88
        assert result.tool_iterations == 0
