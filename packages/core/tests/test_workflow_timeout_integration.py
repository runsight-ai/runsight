"""
Integration coverage for workflow-level timeout enforcement.

Owner decision: this suite owns workflow ``max_duration_seconds`` behavior,
including whole-flow cancellation and the successful within-limit path. Cost
warn and block timeout behavior have separate suites.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, patch

import pytest
from runsight_core.budget_enforcement import BudgetKilledException, _active_budget
from runsight_core.state import WorkflowState
from workflow_limit_helpers import (
    make_litellm_response,
    parse_workflow_fixture,
    patch_fixture_model_budget,
)

_SHORT_TIMEOUT_FIXTURE = "workflow-timeout-short.yaml"
_GENEROUS_TIMEOUT_FIXTURE = "workflow-timeout-generous.yaml"


@pytest.fixture(autouse=True)
def _fixture_model_budget(monkeypatch):
    patch_fixture_model_budget(monkeypatch)


class TestWorkflowTimeoutFailure:
    """Workflow-level timeout cancels the whole flow."""

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_budget_killed_exception_raised(self, mock_cost, mock_acompletion):
        async def slow_response(*args, **kwargs):
            await asyncio.sleep(5)
            return make_litellm_response(content="slow result")

        mock_acompletion.side_effect = slow_response
        mock_cost.return_value = 0.001

        wf = parse_workflow_fixture(_SHORT_TIMEOUT_FIXTURE)
        state = WorkflowState()

        with pytest.raises(BudgetKilledException) as exc_info:
            await wf.run(state)

        exc = exc_info.value
        assert exc.scope == "workflow"
        assert exc.limit_kind == "timeout"
        assert exc.limit_value == 1

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_timeout_fires_within_tolerance(self, mock_cost, mock_acompletion):
        async def slow_response(*args, **kwargs):
            await asyncio.sleep(5)
            return make_litellm_response(content="slow result")

        mock_acompletion.side_effect = slow_response
        mock_cost.return_value = 0.001

        wf = parse_workflow_fixture(_SHORT_TIMEOUT_FIXTURE)
        state = WorkflowState()

        t0 = time.monotonic()
        with pytest.raises(BudgetKilledException):
            await wf.run(state)
        elapsed = time.monotonic() - t0

        assert elapsed < 1.5, f"Flow timeout took {elapsed:.2f}s, expected <1.5s"

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_only_first_block_may_have_started(self, mock_cost, mock_acompletion):
        call_count = 0

        async def slow_response(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(5)
            return make_litellm_response(content="slow result")

        mock_acompletion.side_effect = slow_response
        mock_cost.return_value = 0.001

        wf = parse_workflow_fixture(_SHORT_TIMEOUT_FIXTURE)
        state = WorkflowState()

        with pytest.raises(BudgetKilledException):
            await wf.run(state)

        assert call_count <= 1

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_exception_actual_value_matches_timeout(self, mock_cost, mock_acompletion):
        async def slow_response(*args, **kwargs):
            await asyncio.sleep(5)
            return make_litellm_response(content="slow result")

        mock_acompletion.side_effect = slow_response
        mock_cost.return_value = 0.001

        wf = parse_workflow_fixture(_SHORT_TIMEOUT_FIXTURE)
        state = WorkflowState()

        with pytest.raises(BudgetKilledException) as exc_info:
            await wf.run(state)

        assert exc_info.value.actual_value == 1

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_active_budget_cleaned_up_after_timeout(self, mock_cost, mock_acompletion):
        async def slow_response(*args, **kwargs):
            await asyncio.sleep(5)
            return make_litellm_response(content="slow result")

        mock_acompletion.side_effect = slow_response
        mock_cost.return_value = 0.001

        wf = parse_workflow_fixture(_SHORT_TIMEOUT_FIXTURE)
        state = WorkflowState()

        with pytest.raises(BudgetKilledException):
            await wf.run(state)

        assert _active_budget.get(None) is None


class TestWorkflowTimeoutWithinLimit:
    """Workflow-level timeout allows fast blocks to complete."""

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_workflow_completes_normally(self, mock_cost, mock_acompletion):
        mock_acompletion.side_effect = [
            make_litellm_response(content="result one", total_tokens=100),
            make_litellm_response(content="result two", total_tokens=120),
        ]
        mock_cost.side_effect = [0.01, 0.02]

        wf = parse_workflow_fixture(_GENEROUS_TIMEOUT_FIXTURE)
        state = WorkflowState()

        result = await wf.run(state)

        assert "block1" in result.results
        assert "block2" in result.results
        assert result.results["block1"].output == "result one"
        assert result.results["block2"].output == "result two"

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_no_exception_raised(self, mock_cost, mock_acompletion):
        mock_acompletion.side_effect = [
            make_litellm_response(content="fast one", total_tokens=100),
            make_litellm_response(content="fast two", total_tokens=120),
        ]
        mock_cost.side_effect = [0.01, 0.02]

        wf = parse_workflow_fixture(_GENEROUS_TIMEOUT_FIXTURE)
        state = WorkflowState()

        result = await wf.run(state)
        assert result is not None

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_both_blocks_execute(self, mock_cost, mock_acompletion):
        mock_acompletion.side_effect = [
            make_litellm_response(content="first", total_tokens=100),
            make_litellm_response(content="second", total_tokens=120),
        ]
        mock_cost.side_effect = [0.01, 0.02]

        wf = parse_workflow_fixture(_GENEROUS_TIMEOUT_FIXTURE)
        state = WorkflowState()

        await wf.run(state)
        assert mock_acompletion.call_count == 2

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_cost_and_tokens_tracked(self, mock_cost, mock_acompletion):
        mock_acompletion.side_effect = [
            make_litellm_response(content="r1", total_tokens=100),
            make_litellm_response(content="r2", total_tokens=120),
        ]
        mock_cost.side_effect = [0.01, 0.02]

        wf = parse_workflow_fixture(_GENEROUS_TIMEOUT_FIXTURE)
        state = WorkflowState()

        result = await wf.run(state)

        assert result.total_cost_usd == pytest.approx(0.03)
        assert result.total_tokens == 220
