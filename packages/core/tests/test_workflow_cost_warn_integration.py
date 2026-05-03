"""
Integration coverage for workflow cost warn behavior.

Owner decision: this suite owns cost-cap interactions where child block warn
mode must not hide workflow-level fail behavior. Workflow timeout behavior has
its own suite.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from runsight_core.budget_enforcement import (
    BudgetKilledException,
    _active_budget,
)
from runsight_core.state import WorkflowState
from workflow_limit_helpers import (
    make_litellm_response,
    parse_workflow_fixture,
    patch_fixture_model_budget,
)

_WORKFLOW_COST_WARN_FIXTURE = "workflow-cost-warn.yaml"
_BLOCK_WARN_UNDER_FLOW_CAP_FIXTURE = "workflow-block-warn-under-flow-cap.yaml"
_BLOCK_WARN_OVER_FLOW_CAP_FIXTURE = "workflow-block-warn-over-flow-cap.yaml"


@pytest.fixture(autouse=True)
def _fixture_model_budget(monkeypatch):
    patch_fixture_model_budget(monkeypatch)


class TestWarnModeContinuesPastCostCap:
    """Workflow with limits: {cost_cap_usd: 0.001, on_exceed: warn} and 3 blocks
    each costing $0.001.  All 3 blocks execute (total $0.003, 3x the cap).
    No exception raised."""

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_all_three_blocks_execute(self, mock_cost, mock_acompletion):
        """All 3 blocks run to completion despite exceeding cost cap 3x."""
        mock_acompletion.side_effect = [
            make_litellm_response(content="result one", total_tokens=100),
            make_litellm_response(content="result two", total_tokens=100),
            make_litellm_response(content="result three", total_tokens=100),
        ]
        mock_cost.return_value = 0.001  # each block costs $0.001

        wf = parse_workflow_fixture(_WORKFLOW_COST_WARN_FIXTURE)
        state = WorkflowState()

        result = await wf.run(state)

        assert "block1" in result.results
        assert "block2" in result.results
        assert "block3" in result.results
        assert result.results["block1"].output == "result one"
        assert result.results["block2"].output == "result two"
        assert result.results["block3"].output == "result three"

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_no_exception_raised(self, mock_cost, mock_acompletion):
        """Warn mode MUST NEVER raise BudgetKilledException regardless of overshoot."""
        mock_acompletion.side_effect = [
            make_litellm_response(content="r1", total_tokens=100),
            make_litellm_response(content="r2", total_tokens=100),
            make_litellm_response(content="r3", total_tokens=100),
        ]
        mock_cost.return_value = 0.001

        wf = parse_workflow_fixture(_WORKFLOW_COST_WARN_FIXTURE)
        state = WorkflowState()

        # Should NOT raise BudgetKilledException
        result = await wf.run(state)
        assert result is not None

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_llm_called_three_times(self, mock_cost, mock_acompletion):
        """LLM should be called exactly 3 times — once per block."""
        mock_acompletion.side_effect = [
            make_litellm_response(content="r1", total_tokens=100),
            make_litellm_response(content="r2", total_tokens=100),
            make_litellm_response(content="r3", total_tokens=100),
        ]
        mock_cost.return_value = 0.001

        wf = parse_workflow_fixture(_WORKFLOW_COST_WARN_FIXTURE)
        state = WorkflowState()

        await wf.run(state)

        assert mock_acompletion.call_count == 3

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_total_cost_reflects_all_blocks(self, mock_cost, mock_acompletion):
        """Total cost should reflect all 3 blocks ($0.003) despite cap of $0.001."""
        mock_acompletion.side_effect = [
            make_litellm_response(content="r1", total_tokens=100),
            make_litellm_response(content="r2", total_tokens=100),
            make_litellm_response(content="r3", total_tokens=100),
        ]
        mock_cost.return_value = 0.001

        wf = parse_workflow_fixture(_WORKFLOW_COST_WARN_FIXTURE)
        state = WorkflowState()

        result = await wf.run(state)

        assert result.total_cost_usd == pytest.approx(0.003)
        assert result.total_tokens == 300

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_active_budget_cleaned_up(self, mock_cost, mock_acompletion):
        """After workflow.run(), _active_budget contextvar is reset to None."""
        mock_acompletion.side_effect = [
            make_litellm_response(total_tokens=100),
            make_litellm_response(total_tokens=100),
            make_litellm_response(total_tokens=100),
        ]
        mock_cost.return_value = 0.001

        wf = parse_workflow_fixture(_WORKFLOW_COST_WARN_FIXTURE)
        state = WorkflowState()

        await wf.run(state)
        assert _active_budget.get(None) is None


class TestBlockWarnWithWorkflowCostCap:
    """Block has limits: {cost_cap_usd: 0.001, on_exceed: warn},
    flow has limits: {cost_cap_usd: 0.01, on_exceed: fail}.

    Under the workflow cap: block continues in warn mode and the workflow continues.
      -> block continues (warn), flow continues, no exception.

    Over the workflow cap: accumulated block costs reject the next block request.
      -> the next block's IPC request raises BudgetKilledException(scope="workflow").
    """

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_block_exceeds_own_cap_flow_continues(self, mock_cost, mock_acompletion):
        """Two blocks exceed their own warn caps while the workflow stays under cap."""
        mock_acompletion.side_effect = [
            make_litellm_response(content="result one", total_tokens=100),
            make_litellm_response(content="result two", total_tokens=100),
        ]
        # Each block costs $0.003 — exceeds block cap $0.001 but total $0.006 < flow $0.01
        mock_cost.return_value = 0.003

        # Use a 2-block variant to keep total under flow cap
        wf = parse_workflow_fixture(_BLOCK_WARN_UNDER_FLOW_CAP_FIXTURE)
        state = WorkflowState()

        result = await wf.run(state)

        assert "block1" in result.results
        assert "block2" in result.results
        assert result.results["block1"].output == "result one"
        assert result.results["block2"].output == "result two"

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_no_exception_when_flow_within_cap(self, mock_cost, mock_acompletion):
        """Block-warn + flow-fail: no exception when aggregate stays under flow cap."""
        mock_acompletion.side_effect = [
            make_litellm_response(content="r1", total_tokens=100),
            make_litellm_response(content="r2", total_tokens=100),
        ]
        mock_cost.return_value = 0.003  # each block $0.003, total $0.006 < flow $0.01

        wf = parse_workflow_fixture(_BLOCK_WARN_UNDER_FLOW_CAP_FIXTURE)
        state = WorkflowState()

        # Should NOT raise
        result = await wf.run(state)
        assert result is not None

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_cost_propagates_to_flow_session(self, mock_cost, mock_acompletion):
        """Block costs propagate to flow session via parent chain.
        2 blocks x $0.003 = $0.006 total on the flow session."""
        mock_acompletion.side_effect = [
            make_litellm_response(content="r1", total_tokens=100),
            make_litellm_response(content="r2", total_tokens=100),
        ]
        mock_cost.return_value = 0.003

        wf = parse_workflow_fixture(_BLOCK_WARN_UNDER_FLOW_CAP_FIXTURE)
        state = WorkflowState()

        result = await wf.run(state)

        assert result.total_cost_usd == pytest.approx(0.006)
        assert result.total_tokens == 200

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_flow_cap_breached_raises_budget_killed(self, mock_cost, mock_acompletion):
        """3 blocks x $0.004 = $0.012 total, exceeds flow cap $0.01.
        BudgetKilledException(scope="workflow") raised on block4's next IPC request."""
        mock_acompletion.side_effect = [
            make_litellm_response(content="r1", total_tokens=100),
            make_litellm_response(content="r2", total_tokens=100),
            make_litellm_response(content="r3", total_tokens=100),
        ]
        mock_cost.return_value = 0.004  # each block $0.004, total crosses $0.01 at block 3

        wf = parse_workflow_fixture(_BLOCK_WARN_OVER_FLOW_CAP_FIXTURE)
        state = WorkflowState()

        with pytest.raises(BudgetKilledException) as exc_info:
            await wf.run(state)

        exc = exc_info.value
        assert exc.scope == "workflow"
        assert exc.limit_kind == "cost_usd"
        assert exc.limit_value == 0.01

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_flow_cap_breached_actual_value_exceeds_cap(self, mock_cost, mock_acompletion):
        """BudgetKilledException.actual_value must reflect the accumulated flow cost
        that crossed the cap."""
        mock_acompletion.side_effect = [
            make_litellm_response(content="r1", total_tokens=100),
            make_litellm_response(content="r2", total_tokens=100),
            make_litellm_response(content="r3", total_tokens=100),
        ]
        mock_cost.return_value = 0.004

        wf = parse_workflow_fixture(_BLOCK_WARN_OVER_FLOW_CAP_FIXTURE)
        state = WorkflowState()

        with pytest.raises(BudgetKilledException) as exc_info:
            await wf.run(state)

        assert exc_info.value.actual_value > 0.01

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_block_warn_does_not_prevent_flow_fail(self, mock_cost, mock_acompletion):
        """Even though blocks are on_exceed=warn, the parent flow session with
        on_exceed=fail MUST still raise on the next request after its cap is breached."""
        mock_acompletion.side_effect = [
            make_litellm_response(content="r1", total_tokens=100),
            make_litellm_response(content="r2", total_tokens=100),
            make_litellm_response(content="r3", total_tokens=100),
        ]
        mock_cost.return_value = 0.005  # $0.005/block, total $0.015 >> flow cap $0.01

        wf = parse_workflow_fixture(_BLOCK_WARN_OVER_FLOW_CAP_FIXTURE)
        state = WorkflowState()

        with pytest.raises(BudgetKilledException) as exc_info:
            await wf.run(state)

        # The exception MUST come from the flow level, not block level
        assert exc_info.value.scope == "workflow"

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_some_blocks_execute_before_flow_cap_breached(self, mock_cost, mock_acompletion):
        """With $0.004/block and flow cap $0.01, blocks 1-3 complete
        ($0.012 > $0.01) and block 4 is rejected before another LLM call."""
        call_count = 0

        original_response = make_litellm_response

        async def counting_response(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return original_response(content=f"r{call_count}", total_tokens=100)

        mock_acompletion.side_effect = counting_response
        mock_cost.return_value = 0.004

        wf = parse_workflow_fixture(_BLOCK_WARN_OVER_FLOW_CAP_FIXTURE)
        state = WorkflowState()

        with pytest.raises(BudgetKilledException):
            await wf.run(state)

        # Blocks 1-3 execute and block 4 is rejected before calling the LLM.
        assert call_count == 3

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_active_budget_cleaned_up_after_flow_cap_breach(
        self, mock_cost, mock_acompletion
    ):
        """After BudgetKilledException from flow cap breach, _active_budget is reset."""
        mock_acompletion.side_effect = [
            make_litellm_response(total_tokens=100),
            make_litellm_response(total_tokens=100),
            make_litellm_response(total_tokens=100),
        ]
        mock_cost.return_value = 0.004

        wf = parse_workflow_fixture(_BLOCK_WARN_OVER_FLOW_CAP_FIXTURE)
        state = WorkflowState()

        with pytest.raises(BudgetKilledException):
            await wf.run(state)

        assert _active_budget.get(None) is None
