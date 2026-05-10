"""
Integration tests for workflow and block cost-cap enforcement.

Path under test: YAML fixture -> Workflow.run() -> LinearBlock ->
RunsightTeamRunner -> LiteLLMClient. The external completion and cost-calculation
functions are patched at the client boundary.

Scenarios:
- Workflow-level cost cap stops the next block after the first paid response exceeds the cap
- Terminal block-level cost cap preserves the already-paid response
- Workflows without limits execute without active budget context and still track totals
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from runsight_core.budget_enforcement import (
    BudgetKilledException,
    _active_budget,
)
from runsight_core.state import WorkflowState
from runsight_core.yaml.parser import parse_workflow_yaml

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "workflows"
_WORKFLOW_COST_CAP_FIXTURE = "workflow-cost-cap.yaml"
_TERMINAL_BLOCK_COST_CAP_FIXTURE = "terminal-block-cost-cap.yaml"
_NO_LIMITS_FIXTURE = "workflow-cost-tracking-no-limits.yaml"
_FIXTURE_MODEL = "fixture-cost-cap-model"


@pytest.fixture(autouse=True)
def _fixture_model_budget(monkeypatch):
    from runsight_core import runner as runner_module
    from runsight_core.isolation import handlers as handlers_module

    original_detect_provider = runner_module._detect_provider

    def _get_fixture_model_info(model: str):
        assert model == _FIXTURE_MODEL
        return {"max_input_tokens": 8192}

    def _detect_provider(model: str) -> str:
        if model == _FIXTURE_MODEL:
            return "openai"
        return original_detect_provider(model)

    monkeypatch.setattr("runsight_core.memory.budget.get_model_info", _get_fixture_model_info)
    monkeypatch.setattr(runner_module, "_detect_provider", _detect_provider)
    monkeypatch.setattr(handlers_module, "_detect_provider", _detect_provider)


def _parse_fixture_workflow(fixture_name: str):
    return parse_workflow_yaml(
        (_FIXTURE_DIR / fixture_name).read_text(encoding="utf-8"),
        api_keys={"openai": "dummy-openai-key"},
    )


def _make_completion_response(
    content: str = "completed",
    prompt_tokens: int = 50,
    completion_tokens: int = 30,
    total_tokens: int = 80,
):
    """Build the patched client response shape returned by acompletion."""
    message = MagicMock()
    message.content = content
    message.tool_calls = None

    choice = MagicMock()
    choice.message = message
    choice.finish_reason = "stop"

    usage = MagicMock()
    usage.prompt_tokens = prompt_tokens
    usage.completion_tokens = completion_tokens
    usage.total_tokens = total_tokens

    response = MagicMock()
    response.choices = [choice]
    response.usage = usage
    return response


class TestWorkflowCostCapStopsFollowupBlock:
    """Workflow-level cost cap exceeded by the first linear block."""

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_workflow_cap_raises_budget_killed_exception_after_first_paid_response(
        self, patched_cost_calculator, patched_completion_call
    ):
        patched_completion_call.return_value = _make_completion_response(
            content="expensive result", total_tokens=100
        )
        patched_cost_calculator.return_value = 0.002

        wf = _parse_fixture_workflow(_WORKFLOW_COST_CAP_FIXTURE)
        state = WorkflowState()

        with pytest.raises(BudgetKilledException) as exc_info:
            await wf.run(state)

        exc = exc_info.value
        assert exc.limit_kind == "cost_usd"
        assert exc.limit_value == 0.001
        assert exc.actual_value == pytest.approx(0.002)

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_workflow_cap_prevents_followup_block_request(
        self, patched_cost_calculator, patched_completion_call
    ):
        patched_completion_call.return_value = _make_completion_response(
            content="expensive result", total_tokens=100
        )
        patched_cost_calculator.return_value = 0.002

        wf = _parse_fixture_workflow(_WORKFLOW_COST_CAP_FIXTURE)
        state = WorkflowState()

        with pytest.raises(BudgetKilledException):
            await wf.run(state)

        assert patched_completion_call.await_count == 1

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_workflow_cap_exception_clears_active_budget_context(
        self, patched_cost_calculator, patched_completion_call
    ):
        patched_completion_call.return_value = _make_completion_response(total_tokens=100)
        patched_cost_calculator.return_value = 0.002

        wf = _parse_fixture_workflow(_WORKFLOW_COST_CAP_FIXTURE)
        state = WorkflowState()

        with pytest.raises(BudgetKilledException):
            await wf.run(state)

        assert _active_budget.get(None) is None

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_workflow_cap_exception_reports_workflow_scope(
        self, patched_cost_calculator, patched_completion_call
    ):
        patched_completion_call.return_value = _make_completion_response(total_tokens=100)
        patched_cost_calculator.return_value = 0.002

        wf = _parse_fixture_workflow(_WORKFLOW_COST_CAP_FIXTURE)
        state = WorkflowState()

        with pytest.raises(BudgetKilledException) as exc_info:
            await wf.run(state)

        assert exc_info.value.scope == "workflow"


class TestTerminalBlockCostCapPreservesPaidResult:
    """Block-level cost cap exceeded by a terminal block with an error route configured."""

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_terminal_block_cap_preserves_paid_output_without_taking_error_route(
        self, patched_cost_calculator, patched_completion_call
    ):
        patched_completion_call.side_effect = [
            _make_completion_response(content="expensive", total_tokens=100),
            _make_completion_response(content="recovered", total_tokens=50),
        ]
        patched_cost_calculator.side_effect = [0.002, 0.0001]

        wf = _parse_fixture_workflow(_TERMINAL_BLOCK_COST_CAP_FIXTURE)
        state = WorkflowState()

        result = await wf.run(state)

        assert result.results["terminal_budget_block"].output == "expensive"
        assert result.results["terminal_budget_block"].exit_handle == "done"
        assert "fallback_budget_recovery" not in result.results
        assert patched_completion_call.await_count == 1

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_terminal_block_cap_keeps_paid_result_as_success_envelope(
        self, patched_cost_calculator, patched_completion_call
    ):
        patched_completion_call.side_effect = [
            _make_completion_response(content="expensive", total_tokens=100),
            _make_completion_response(content="recovered", total_tokens=50),
        ]
        patched_cost_calculator.side_effect = [0.002, 0.0001]

        wf = _parse_fixture_workflow(_TERMINAL_BLOCK_COST_CAP_FIXTURE)
        state = WorkflowState()

        result = await wf.run(state)

        block_result = result.results["terminal_budget_block"]
        assert block_result.exit_handle == "done"
        assert block_result.metadata is None

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_terminal_block_cap_returns_paid_result_without_extra_request(
        self, patched_cost_calculator, patched_completion_call
    ):
        patched_completion_call.side_effect = [
            _make_completion_response(content="expensive", total_tokens=100),
            _make_completion_response(content="recovered", total_tokens=50),
        ]
        patched_cost_calculator.side_effect = [0.002, 0.0001]

        wf = _parse_fixture_workflow(_TERMINAL_BLOCK_COST_CAP_FIXTURE)
        state = WorkflowState()

        result = await wf.run(state)

        assert result is not None
        assert "fallback_budget_recovery" not in result.results
        assert patched_completion_call.await_count == 1

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_terminal_block_cap_does_not_record_error_route_metadata(
        self, patched_cost_calculator, patched_completion_call
    ):
        patched_completion_call.side_effect = [
            _make_completion_response(content="expensive", total_tokens=100),
            _make_completion_response(content="recovered", total_tokens=50),
        ]
        patched_cost_calculator.side_effect = [0.002, 0.0001]

        wf = _parse_fixture_workflow(_TERMINAL_BLOCK_COST_CAP_FIXTURE)
        state = WorkflowState()

        result = await wf.run(state)

        assert result.shared_memory.get("__error__terminal_budget_block") is None


class TestWorkflowCostTrackingWithoutLimits:
    """Parsed workflow without budget limits."""

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_no_limits_workflow_writes_both_linear_block_results(
        self, patched_cost_calculator, patched_completion_call
    ):
        patched_completion_call.side_effect = [
            _make_completion_response(content="start result", total_tokens=100),
            _make_completion_response(content="followup result", total_tokens=120),
        ]
        patched_cost_calculator.side_effect = [0.05, 0.06]

        wf = _parse_fixture_workflow(_NO_LIMITS_FIXTURE)
        state = WorkflowState()

        result = await wf.run(state)

        assert result.results["cost_tracking_start"].output == "start result"
        assert result.results["cost_tracking_followup"].output == "followup result"

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_no_limits_workflow_requests_run_without_active_budget_context(
        self, patched_cost_calculator, patched_completion_call
    ):
        captured_budgets = []

        async def _capturing_completion(*args, **kwargs):
            captured_budgets.append(_active_budget.get(None))
            return _make_completion_response(content="ok", total_tokens=80)

        patched_completion_call.side_effect = _capturing_completion
        patched_cost_calculator.return_value = 0.01

        wf = _parse_fixture_workflow(_NO_LIMITS_FIXTURE)
        state = WorkflowState()

        await wf.run(state)

        assert len(captured_budgets) == 2
        assert captured_budgets == [None, None]

    def test_no_limits_fixture_parses_without_budget_limits(self):
        wf = _parse_fixture_workflow(_NO_LIMITS_FIXTURE)

        assert getattr(wf, "limits", None) is None

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_no_limits_workflow_still_accumulates_cost_and_tokens(
        self, patched_cost_calculator, patched_completion_call
    ):
        patched_completion_call.side_effect = [
            _make_completion_response(content="start", total_tokens=100),
            _make_completion_response(content="followup", total_tokens=120),
        ]
        patched_cost_calculator.side_effect = [0.05, 0.06]

        wf = _parse_fixture_workflow(_NO_LIMITS_FIXTURE)
        state = WorkflowState()

        result = await wf.run(state)

        assert result.total_cost_usd == pytest.approx(0.11)
        assert result.total_tokens == 220
