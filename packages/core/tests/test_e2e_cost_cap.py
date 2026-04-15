"""
RUN-726 — E2E tests for workflow cost cap enforcement.

Full-path integration: YAML parse -> Workflow.run() -> execute_block() ->
LinearBlock -> RunsightTeamRunner -> LiteLLMClient.achat() -> BudgetSession
enforcement.

Mocks only: litellm.acompletion (external LLM call) and litellm.completion_cost
(cost calculator).  All internal modules exercise real code paths.

Scenarios:
1. Workflow cost cap mid-block kill: first block exceeds cap, second never runs
2. Block cost cap preserves paid over-cap response
3. No limits — zero overhead, workflow completes normally
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from runsight_core.budget_enforcement import (
    BudgetKilledException,
    _active_budget,
)
from runsight_core.state import WorkflowState
from runsight_core.yaml.parser import parse_workflow_yaml as _parse_workflow_yaml

_TEST_API_KEYS = {"openai": "sk-test-openai"}


def parse_workflow_yaml(*args, **kwargs):
    """Parse legacy e2e workflows with the engine-side IPC credential seam wired."""
    kwargs.setdefault("api_keys", _TEST_API_KEYS)
    return _parse_workflow_yaml(*args, **kwargs)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_litellm_response(
    content: str = "done",
    prompt_tokens: int = 50,
    completion_tokens: int = 30,
    total_tokens: int = 80,
):
    """Build a mock object mimicking litellm.acompletion() return value."""
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


# ---------------------------------------------------------------------------
# YAML templates
# ---------------------------------------------------------------------------

_YAML_WORKFLOW_COST_CAP = """\
version: "1.0"
souls:
  s1:
    id: s1
    role: Worker
    system_prompt: Do work.
    provider: openai
    model_name: gpt-4o
blocks:
  block1:
    type: linear
    soul_ref: s1
  block2:
    type: linear
    soul_ref: s1
workflow:
  name: cost_cap_test
  entry: block1
  transitions:
    - from: block1
      to: block2
    - from: block2
      to: null
limits:
  cost_cap_usd: 0.001
  on_exceed: fail
"""

_YAML_BLOCK_COST_CAP_WITH_ERROR_ROUTE = """\
version: "1.0"
souls:
  s1:
    id: s1
    role: Worker
    system_prompt: Do work.
    provider: openai
    model_name: gpt-4o
blocks:
  block1:
    type: linear
    soul_ref: s1
    limits:
      cost_cap_usd: 0.001
      on_exceed: fail
    error_route: fallback
  fallback:
    type: linear
    soul_ref: s1
workflow:
  name: block_cap_fallback
  entry: block1
  transitions:
    - from: block1
      to: null
    - from: fallback
      to: null
"""

_YAML_NO_LIMITS = """\
version: "1.0"
souls:
  s1:
    id: s1
    role: Worker
    system_prompt: Do work.
    provider: openai
    model_name: gpt-4o
blocks:
  block1:
    type: linear
    soul_ref: s1
  block2:
    type: linear
    soul_ref: s1
workflow:
  name: no_limits_test
  entry: block1
  transitions:
    - from: block1
      to: block2
    - from: block2
      to: null
"""


# ===========================================================================
# Scenario 1: Workflow cost cap — mid-block kill
# ===========================================================================


class TestWorkflowCostCapMidBlockKill:
    """YAML with limits: {cost_cap_usd: 0.001, on_exceed: fail}.
    First block's achat() costs $0.002 -> exceeds cap.
    BudgetKilledException propagates, second block never executes."""

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_budget_killed_exception_raised(self, mock_cost, mock_acompletion):
        """Workflow.run() raises BudgetKilledException when first block exceeds cap."""
        mock_acompletion.return_value = _make_litellm_response(
            content="expensive result", total_tokens=100
        )
        mock_cost.return_value = 0.002  # exceeds cap of 0.001

        wf = parse_workflow_yaml(_YAML_WORKFLOW_COST_CAP)
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
    async def test_second_block_never_executes(self, mock_cost, mock_acompletion):
        """When first block exceeds workflow cap, LLM should only be called once
        (second block never runs)."""
        mock_acompletion.return_value = _make_litellm_response(
            content="expensive result", total_tokens=100
        )
        mock_cost.return_value = 0.002

        wf = parse_workflow_yaml(_YAML_WORKFLOW_COST_CAP)
        state = WorkflowState()

        with pytest.raises(BudgetKilledException):
            await wf.run(state)

        # achat (via acompletion) should only have been called once — for block1.
        # block2 should never have started.
        assert mock_acompletion.call_count == 1

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_active_budget_cleaned_up_after_exception(self, mock_cost, mock_acompletion):
        """After BudgetKilledException, _active_budget contextvar is reset to None."""
        mock_acompletion.return_value = _make_litellm_response(total_tokens=100)
        mock_cost.return_value = 0.002

        wf = parse_workflow_yaml(_YAML_WORKFLOW_COST_CAP)
        state = WorkflowState()

        with pytest.raises(BudgetKilledException):
            await wf.run(state)

        # Contextvar must be cleaned up even after exception
        assert _active_budget.get(None) is None

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_exception_scope_is_workflow(self, mock_cost, mock_acompletion):
        """BudgetKilledException scope should be 'workflow' since it's a workflow-level cap."""
        mock_acompletion.return_value = _make_litellm_response(total_tokens=100)
        mock_cost.return_value = 0.002

        wf = parse_workflow_yaml(_YAML_WORKFLOW_COST_CAP)
        state = WorkflowState()

        with pytest.raises(BudgetKilledException) as exc_info:
            await wf.run(state)

        assert exc_info.value.scope == "workflow"


# ===========================================================================
# Scenario 2: Block cost cap preserves paid over-cap response
# ===========================================================================


@pytest.mark.xfail(
    reason="Requires real subprocess isolation — paid-result preservation is an IPC interceptor behavior",
    strict=False,
)
class TestBlockCostCapWithErrorRoute:
    """Block-1 has limits: {cost_cap_usd: 0.001} and error_route: fallback.
    The over-cap paid response is preserved; budget killing gates the next IPC
    request, so a terminal block does not discard the result or route fallback."""

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_paid_result_is_preserved_after_budget_exceeded(
        self, mock_cost, mock_acompletion
    ):
        """An over-cap response is still delivered because the call was already paid for."""
        mock_acompletion.side_effect = [
            _make_litellm_response(content="expensive", total_tokens=100),
            _make_litellm_response(content="fallback result", total_tokens=50),
        ]
        mock_cost.side_effect = [0.002, 0.0001]  # block1 exceeds, fallback is cheap

        wf = parse_workflow_yaml(_YAML_BLOCK_COST_CAP_WITH_ERROR_ROUTE)
        state = WorkflowState()

        result = await wf.run(state)

        assert result.results["block1"].output == "expensive"
        assert result.results["block1"].exit_handle == "done"
        assert "fallback" not in result.results
        assert mock_acompletion.call_count == 1

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_block1_result_does_not_contain_error_info(self, mock_cost, mock_acompletion):
        """The paid result is not converted into an error envelope after the fact."""
        mock_acompletion.side_effect = [
            _make_litellm_response(content="expensive", total_tokens=100),
            _make_litellm_response(content="fallback result", total_tokens=50),
        ]
        mock_cost.side_effect = [0.002, 0.0001]

        wf = parse_workflow_yaml(_YAML_BLOCK_COST_CAP_WITH_ERROR_ROUTE)
        state = WorkflowState()

        result = await wf.run(state)

        # block1 should preserve the already-paid response as a normal result
        assert "block1" in result.results
        block1_result = result.results["block1"]
        assert block1_result.exit_handle == "done"
        assert block1_result.metadata is None

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_workflow_completes_normally_with_paid_result(self, mock_cost, mock_acompletion):
        """A terminal over-cap block completes with its result and no extra LLM call."""
        mock_acompletion.side_effect = [
            _make_litellm_response(content="expensive", total_tokens=100),
            _make_litellm_response(content="recovered", total_tokens=50),
        ]
        mock_cost.side_effect = [0.002, 0.0001]

        wf = parse_workflow_yaml(_YAML_BLOCK_COST_CAP_WITH_ERROR_ROUTE)
        state = WorkflowState()

        # Should NOT raise — there is no next IPC request to gate in this workflow
        result = await wf.run(state)
        assert result is not None
        assert "fallback" not in result.results
        assert mock_acompletion.call_count == 1

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_no_error_info_in_shared_memory_without_next_request(
        self, mock_cost, mock_acompletion
    ):
        """No error route metadata is recorded when no next IPC request is gated."""
        mock_acompletion.side_effect = [
            _make_litellm_response(content="expensive", total_tokens=100),
            _make_litellm_response(content="recovered", total_tokens=50),
        ]
        mock_cost.side_effect = [0.002, 0.0001]

        wf = parse_workflow_yaml(_YAML_BLOCK_COST_CAP_WITH_ERROR_ROUTE)
        state = WorkflowState()

        result = await wf.run(state)

        # No error is recorded because the paid response was not discarded
        error_info = result.shared_memory.get("__error__block1")
        assert error_info is None


# ===========================================================================
# Scenario 3: No limits — zero overhead
# ===========================================================================


class TestNoLimitsZeroOverhead:
    """Workflow YAML with no limits: key. _active_budget stays None.
    Workflow completes normally with zero budget overhead."""

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_workflow_completes_normally(self, mock_cost, mock_acompletion):
        """Workflow with no limits runs both blocks and completes normally."""
        mock_acompletion.side_effect = [
            _make_litellm_response(content="result one", total_tokens=100),
            _make_litellm_response(content="result two", total_tokens=120),
        ]
        mock_cost.side_effect = [0.05, 0.06]

        wf = parse_workflow_yaml(_YAML_NO_LIMITS)
        state = WorkflowState()

        result = await wf.run(state)

        assert "block1" in result.results
        assert "block2" in result.results
        assert result.results["block1"].output == "result one"
        assert result.results["block2"].output == "result two"

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_active_budget_stays_none_during_execution(self, mock_cost, mock_acompletion):
        """When no limits are set, _active_budget should remain None throughout execution."""
        captured_budgets = []

        original_return = _make_litellm_response(content="ok", total_tokens=80)

        async def capturing_acompletion(*args, **kwargs):
            captured_budgets.append(_active_budget.get(None))
            return original_return

        mock_acompletion.side_effect = capturing_acompletion
        mock_cost.return_value = 0.01

        wf = parse_workflow_yaml(_YAML_NO_LIMITS)
        state = WorkflowState()

        await wf.run(state)

        # Both block1 and block2 should have executed with no active budget
        assert len(captured_budgets) == 2
        assert all(b is None for b in captured_budgets)

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_no_limits_attribute_on_workflow(self, mock_cost, mock_acompletion):
        """Parsed workflow without limits: key should have no .limits attribute (or None)."""
        wf = parse_workflow_yaml(_YAML_NO_LIMITS)

        limits = getattr(wf, "limits", None)
        assert limits is None

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_cost_and_tokens_accumulated_without_limits(self, mock_cost, mock_acompletion):
        """Even without budget enforcement, state should track cost and tokens."""
        mock_acompletion.side_effect = [
            _make_litellm_response(content="r1", total_tokens=100),
            _make_litellm_response(content="r2", total_tokens=120),
        ]
        mock_cost.side_effect = [0.05, 0.06]

        wf = parse_workflow_yaml(_YAML_NO_LIMITS)
        state = WorkflowState()

        result = await wf.run(state)

        assert result.total_cost_usd == pytest.approx(0.11)
        assert result.total_tokens == 220
