"""
Integration tests for dispatch branch budget accounting through parsed workflows.

Path under test: YAML fixture -> Workflow.run() -> DispatchBlock ->
RunsightTeamRunner -> LiteLLMClient. The external completion and cost-calculation
functions are patched at the client boundary.

Scenarios:
- Branch costs under the workflow cap preserve per-exit and aggregate dispatch results
- Terminal dispatch results remain observable after combined branch costs exceed the cap
- Workflows without limits run dispatch branches without active budget sessions
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from runsight_core.budget_enforcement import _active_budget
from runsight_core.state import WorkflowState
from runsight_core.yaml.parser import parse_workflow_yaml

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "workflows"
_COST_CAP_WORKFLOW_FIXTURE = "dispatch-budget-cost-cap.yaml"
_NO_LIMITS_WORKFLOW_FIXTURE = "dispatch-budget-no-limits.yaml"
_DISPATCH_KEY = "budgeted_dispatch"
_BRANCH_KEYS = [
    "budgeted_dispatch.budget_branch_alpha",
    "budgeted_dispatch.budget_branch_beta",
    "budgeted_dispatch.budget_branch_gamma",
]


def _parse_fixture_workflow(fixture_name: str):
    return parse_workflow_yaml((_FIXTURE_DIR / fixture_name).read_text(encoding="utf-8"))


def _make_completion_response(
    content: str = "branch completed",
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


def _assert_dispatch_result_keys(result):
    for key in _BRANCH_KEYS:
        assert key in result.results
    assert _DISPATCH_KEY in result.results


class TestDispatchBudgetWorkflowWithinCap:
    """Parsed dispatch workflow with cost_cap_usd above the combined branch cost."""

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_under_cap_workflow_writes_per_exit_and_aggregate_dispatch_results(
        self, patched_cost_calculator, patched_completion_call
    ):
        patched_completion_call.side_effect = [
            _make_completion_response(content="alpha result", total_tokens=100),
            _make_completion_response(content="beta result", total_tokens=120),
            _make_completion_response(content="gamma result", total_tokens=80),
        ]
        patched_cost_calculator.side_effect = [0.50, 0.60, 0.40]

        wf = _parse_fixture_workflow(_COST_CAP_WORKFLOW_FIXTURE)
        state = WorkflowState()

        result = await wf.run(state)

        _assert_dispatch_result_keys(result)

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_under_cap_workflow_totals_branch_cost_and_tokens(
        self, patched_cost_calculator, patched_completion_call
    ):
        patched_completion_call.side_effect = [
            _make_completion_response(content="alpha", total_tokens=100),
            _make_completion_response(content="beta", total_tokens=120),
            _make_completion_response(content="gamma", total_tokens=80),
        ]
        patched_cost_calculator.side_effect = [0.50, 0.60, 0.40]

        wf = _parse_fixture_workflow(_COST_CAP_WORKFLOW_FIXTURE)
        state = WorkflowState()

        result = await wf.run(state)

        assert result.total_cost_usd == pytest.approx(1.50)
        assert result.total_tokens == 300

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_under_cap_client_calls_run_outside_parent_budget_context(
        self, patched_cost_calculator, patched_completion_call
    ):
        captured_sessions = []

        async def _capturing_completion(**kwargs):
            captured_sessions.append(_active_budget.get(None))
            return _make_completion_response(content="ok", total_tokens=80)

        patched_completion_call.side_effect = _capturing_completion
        patched_cost_calculator.return_value = 0.30

        wf = _parse_fixture_workflow(_COST_CAP_WORKFLOW_FIXTURE)
        state = WorkflowState()

        result = await wf.run(state)

        assert result is not None
        assert len(captured_sessions) == 3
        assert captured_sessions == [None, None, None]

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_under_cap_workflow_clears_active_budget_context(
        self, patched_cost_calculator, patched_completion_call
    ):
        patched_completion_call.side_effect = [
            _make_completion_response(total_tokens=100),
            _make_completion_response(total_tokens=100),
            _make_completion_response(total_tokens=100),
        ]
        patched_cost_calculator.return_value = 0.30

        wf = _parse_fixture_workflow(_COST_CAP_WORKFLOW_FIXTURE)
        state = WorkflowState()

        await wf.run(state)

        assert _active_budget.get(None) is None


class TestDispatchBudgetWorkflowOverCap:
    """Parsed dispatch workflow whose combined terminal branch cost exceeds its cap."""

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_terminal_dispatch_result_preserves_paid_branch_outputs_after_cap_overrun(
        self, patched_cost_calculator, patched_completion_call
    ):
        patched_completion_call.side_effect = [
            _make_completion_response(content="alpha", total_tokens=200),
            _make_completion_response(content="beta", total_tokens=225),
            _make_completion_response(content="gamma", total_tokens=175),
        ]
        patched_cost_calculator.side_effect = [0.80, 0.90, 0.70]

        wf = _parse_fixture_workflow(_COST_CAP_WORKFLOW_FIXTURE)
        state = WorkflowState()

        result = await wf.run(state)

        assert result.total_cost_usd == pytest.approx(2.40)
        assert result.total_tokens == 600
        _assert_dispatch_result_keys(result)

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_cap_overrun_is_observed_after_all_parallel_branches_execute(
        self, patched_cost_calculator, patched_completion_call
    ):
        patched_completion_call.side_effect = [
            _make_completion_response(content="alpha", total_tokens=200),
            _make_completion_response(content="beta", total_tokens=225),
            _make_completion_response(content="gamma", total_tokens=175),
        ]
        patched_cost_calculator.side_effect = [0.80, 0.90, 0.70]

        wf = _parse_fixture_workflow(_COST_CAP_WORKFLOW_FIXTURE)
        state = WorkflowState()

        await wf.run(state)

        assert patched_completion_call.await_count == 3

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_over_cap_workflow_clears_active_budget_context(
        self, patched_cost_calculator, patched_completion_call
    ):
        patched_completion_call.side_effect = [
            _make_completion_response(total_tokens=200),
            _make_completion_response(total_tokens=225),
            _make_completion_response(total_tokens=175),
        ]
        patched_cost_calculator.side_effect = [0.80, 0.90, 0.70]

        wf = _parse_fixture_workflow(_COST_CAP_WORKFLOW_FIXTURE)
        state = WorkflowState()

        await wf.run(state)

        assert _active_budget.get(None) is None

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_over_cap_client_calls_run_outside_parent_budget_context(
        self, patched_cost_calculator, patched_completion_call
    ):
        captured_sessions = []

        async def _capturing_completion(**kwargs):
            captured_sessions.append(_active_budget.get(None))
            return _make_completion_response(content="ok", total_tokens=100)

        patched_completion_call.side_effect = _capturing_completion
        patched_cost_calculator.return_value = 0.80

        wf = _parse_fixture_workflow(_COST_CAP_WORKFLOW_FIXTURE)
        state = WorkflowState()

        await wf.run(state)

        assert len(captured_sessions) == 3
        assert captured_sessions == [None, None, None]


class TestDispatchBudgetWorkflowWithoutLimits:
    """Parsed dispatch workflow without budget limits."""

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_no_limits_workflow_writes_per_exit_and_aggregate_dispatch_results(
        self, patched_cost_calculator, patched_completion_call
    ):
        patched_completion_call.side_effect = [
            _make_completion_response(content="alpha result", total_tokens=100),
            _make_completion_response(content="beta result", total_tokens=120),
            _make_completion_response(content="gamma result", total_tokens=80),
        ]
        patched_cost_calculator.side_effect = [0.50, 0.60, 0.40]

        wf = _parse_fixture_workflow(_NO_LIMITS_WORKFLOW_FIXTURE)
        state = WorkflowState()

        result = await wf.run(state)

        _assert_dispatch_result_keys(result)

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_no_limits_workflow_branches_run_without_active_budget_sessions(
        self, patched_cost_calculator, patched_completion_call
    ):
        captured_sessions = []

        async def _capturing_completion(**kwargs):
            captured_sessions.append(_active_budget.get(None))
            return _make_completion_response(content="ok", total_tokens=80)

        patched_completion_call.side_effect = _capturing_completion
        patched_cost_calculator.return_value = 0.10

        wf = _parse_fixture_workflow(_NO_LIMITS_WORKFLOW_FIXTURE)
        state = WorkflowState()

        await wf.run(state)

        assert len(captured_sessions) == 3
        assert captured_sessions == [None, None, None]

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_no_limits_workflow_still_tracks_cost_and_tokens(
        self, patched_cost_calculator, patched_completion_call
    ):
        patched_completion_call.side_effect = [
            _make_completion_response(content="alpha", total_tokens=100),
            _make_completion_response(content="beta", total_tokens=120),
            _make_completion_response(content="gamma", total_tokens=80),
        ]
        patched_cost_calculator.side_effect = [0.50, 0.60, 0.40]

        wf = _parse_fixture_workflow(_NO_LIMITS_WORKFLOW_FIXTURE)
        state = WorkflowState()

        result = await wf.run(state)

        assert result.total_cost_usd == pytest.approx(1.50)
        assert result.total_tokens == 300

    def test_no_limits_fixture_parses_without_budget_limits(self):
        wf = _parse_fixture_workflow(_NO_LIMITS_WORKFLOW_FIXTURE)

        assert getattr(wf, "limits", None) is None
