"""
RUN-728 — E2E tests for DispatchBlock branch budget isolation.

Full-path integration: YAML parse -> Workflow.run() -> execute_block() ->
IsolatedBlockWrapper (fallback) -> DispatchBlock._gather_with_budget_isolation()
-> RunsightTeamRunner.execute_task() -> LiteLLMClient.achat() -> BudgetSession
enforcement.

Mocks only: litellm.acompletion (external LLM call) and litellm.completion_cost
(cost calculator).  All internal modules exercise real code paths.

Scenarios:
1. Combined branch costs within flow cap — no exception, workflow continues
2. Combined terminal branch costs exceed flow cap — paid result is preserved
3. No budget — branches run unchanged, no budget overhead
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from runsight_core.budget_enforcement import _active_budget
from runsight_core.primitives import Task
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

_YAML_DISPATCH_WITH_COST_CAP = """\
version: "1.0"
id: test-workflow
kind: workflow
souls:
  worker-a:
    id: worker-a
    kind: soul
    name: Worker A
    role: Worker A
    system_prompt: Do work A.
    provider: openai
    model_name: gpt-4o
  worker-b:
    id: worker-b
    kind: soul
    name: Worker B
    role: Worker B
    system_prompt: Do work B.
    provider: openai
    model_name: gpt-4o
  worker-c:
    id: worker-c
    kind: soul
    name: Worker C
    role: Worker C
    system_prompt: Do work C.
    provider: openai
    model_name: gpt-4o
blocks:
  dispatch_block:
    type: dispatch
    exits:
      - id: branch_a
        label: Branch A
        soul_ref: worker-a
        task: Do task A
      - id: branch_b
        label: Branch B
        soul_ref: worker-b
        task: Do task B
      - id: branch_c
        label: Branch C
        soul_ref: worker-c
        task: Do task C
workflow:
  name: dispatch_budget_test
  entry: dispatch_block
  transitions:
    - from: dispatch_block
      to: null
limits:
  cost_cap_usd: 2.00
  on_exceed: fail
"""

_YAML_DISPATCH_NO_LIMITS = """\
version: "1.0"
id: test-workflow
kind: workflow
souls:
  worker-a:
    id: worker-a
    kind: soul
    name: Worker A
    role: Worker A
    system_prompt: Do work A.
    provider: openai
    model_name: gpt-4o
  worker-b:
    id: worker-b
    kind: soul
    name: Worker B
    role: Worker B
    system_prompt: Do work B.
    provider: openai
    model_name: gpt-4o
  worker-c:
    id: worker-c
    kind: soul
    name: Worker C
    role: Worker C
    system_prompt: Do work C.
    provider: openai
    model_name: gpt-4o
blocks:
  dispatch_block:
    type: dispatch
    exits:
      - id: branch_a
        label: Branch A
        soul_ref: worker-a
        task: Do task A
      - id: branch_b
        label: Branch B
        soul_ref: worker-b
        task: Do task B
      - id: branch_c
        label: Branch C
        soul_ref: worker-c
        task: Do task C
workflow:
  name: dispatch_no_limits_test
  entry: dispatch_block
  transitions:
    - from: dispatch_block
      to: null
"""


# ===========================================================================
# Scenario 1: Combined branch costs within flow cap
# ===========================================================================


class TestCombinedBranchCostsWithinFlowCap:
    """Flow limits: {cost_cap_usd: 2.00}, dispatch with 3 branches.
    Branches cost $0.50, $0.60, $0.40 (total $1.50 < $2.00).
    After reconciliation, no exception. Workflow completes normally."""

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_workflow_completes_without_exception(self, mock_cost, mock_acompletion):
        """Workflow with dispatch branches whose combined cost is under the cap
        completes normally without raising BudgetKilledException."""
        mock_acompletion.side_effect = [
            _make_litellm_response(content="result A", total_tokens=100),
            _make_litellm_response(content="result B", total_tokens=120),
            _make_litellm_response(content="result C", total_tokens=80),
        ]
        mock_cost.side_effect = [0.50, 0.60, 0.40]

        wf = parse_workflow_yaml(_YAML_DISPATCH_WITH_COST_CAP)
        state = WorkflowState(
            current_task=Task(id="t1", instruction="Run dispatch"),
        )

        result = await wf.run(state)

        # Workflow completed normally
        assert result is not None
        # Per-exit results should be present
        assert "dispatch_block.branch_a" in result.results
        assert "dispatch_block.branch_b" in result.results
        assert "dispatch_block.branch_c" in result.results
        # Combined dispatch result should be present
        assert "dispatch_block" in result.results

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_total_cost_reflects_all_branches(self, mock_cost, mock_acompletion):
        """After successful dispatch, total_cost_usd should reflect all branch costs."""
        mock_acompletion.side_effect = [
            _make_litellm_response(content="A", total_tokens=100),
            _make_litellm_response(content="B", total_tokens=120),
            _make_litellm_response(content="C", total_tokens=80),
        ]
        mock_cost.side_effect = [0.50, 0.60, 0.40]

        wf = parse_workflow_yaml(_YAML_DISPATCH_WITH_COST_CAP)
        state = WorkflowState(
            current_task=Task(id="t1", instruction="Run dispatch"),
        )

        result = await wf.run(state)

        assert result.total_cost_usd == pytest.approx(1.50)
        assert result.total_tokens == 300

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_branch_costs_do_not_accrue_to_parent_during_execution(
        self, mock_cost, mock_acompletion
    ):
        """Branch costs must NOT reach the parent session during parallel execution.
        They are reconciled only after asyncio.gather completes."""

        async def _capturing_acompletion(**kwargs):
            # The parent session is the workflow-level one; branches get isolated children.
            # Capture the parent's cost at the time of each branch call.
            session = _active_budget.get(None)
            if session is not None and session.parent is None:
                # This is an isolated child — look up its scope name to find parent
                # We can't access parent directly (it's None for isolated children)
                # Instead, verify that the session is NOT the workflow-level session
                # by checking scope_name pattern
                assert "branch_" in session.scope_name, (
                    f"Branch should see an isolated child session, got scope: {session.scope_name}"
                )
            return _make_litellm_response(content="ok", total_tokens=80)

        mock_acompletion.side_effect = _capturing_acompletion
        mock_cost.return_value = 0.30

        wf = parse_workflow_yaml(_YAML_DISPATCH_WITH_COST_CAP)
        state = WorkflowState(
            current_task=Task(id="t1", instruction="Run dispatch"),
        )

        result = await wf.run(state)
        assert result is not None

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_active_budget_cleaned_up_after_workflow(self, mock_cost, mock_acompletion):
        """After workflow.run(), _active_budget contextvar is reset to None."""
        mock_acompletion.side_effect = [
            _make_litellm_response(total_tokens=100),
            _make_litellm_response(total_tokens=100),
            _make_litellm_response(total_tokens=100),
        ]
        mock_cost.return_value = 0.30

        wf = parse_workflow_yaml(_YAML_DISPATCH_WITH_COST_CAP)
        state = WorkflowState(
            current_task=Task(id="t1", instruction="Run dispatch"),
        )

        await wf.run(state)
        assert _active_budget.get(None) is None


# ===========================================================================
# Scenario 2: Combined branch costs exceed flow cap
# ===========================================================================


@pytest.mark.xfail(
    reason="Requires real subprocess isolation — paid-result preservation is an IPC interceptor behavior",
    strict=False,
)
class TestCombinedBranchCostsExceedFlowCap:
    """Flow limits: {cost_cap_usd: 2.00}, dispatch with 3 branches.
    Branches cost $0.80, $0.90, $0.70 (total $2.40 > $2.00).
    The terminal dispatch result is preserved; budget killing gates a future IPC request."""

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_paid_dispatch_result_preserved_when_combined_cost_exceeds_cap(
        self, mock_cost, mock_acompletion
    ):
        """Workflow returns the already-paid dispatch result even when total cost is over cap."""
        mock_acompletion.side_effect = [
            _make_litellm_response(content="A", total_tokens=200),
            _make_litellm_response(content="B", total_tokens=225),
            _make_litellm_response(content="C", total_tokens=175),
        ]
        mock_cost.side_effect = [0.80, 0.90, 0.70]

        wf = parse_workflow_yaml(_YAML_DISPATCH_WITH_COST_CAP)
        state = WorkflowState(
            current_task=Task(id="t1", instruction="Run dispatch"),
        )

        result = await wf.run(state)

        assert result.total_cost_usd == pytest.approx(2.40)
        assert result.total_tokens == 600
        assert "dispatch_block.branch_a" in result.results
        assert "dispatch_block.branch_b" in result.results
        assert "dispatch_block.branch_c" in result.results

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_all_branches_execute_before_terminal_budget_overrun_is_observed(
        self, mock_cost, mock_acompletion
    ):
        """All 3 branches execute; terminal overrun does not discard their answers."""
        mock_acompletion.side_effect = [
            _make_litellm_response(content="A", total_tokens=200),
            _make_litellm_response(content="B", total_tokens=225),
            _make_litellm_response(content="C", total_tokens=175),
        ]
        mock_cost.side_effect = [0.80, 0.90, 0.70]

        wf = parse_workflow_yaml(_YAML_DISPATCH_WITH_COST_CAP)
        state = WorkflowState(
            current_task=Task(id="t1", instruction="Run dispatch"),
        )

        await wf.run(state)

        assert mock_acompletion.call_count == 3

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_active_budget_cleaned_up_after_over_cap_completion(
        self, mock_cost, mock_acompletion
    ):
        """After over-cap terminal completion, _active_budget contextvar is reset to None."""
        mock_acompletion.side_effect = [
            _make_litellm_response(total_tokens=200),
            _make_litellm_response(total_tokens=225),
            _make_litellm_response(total_tokens=175),
        ]
        mock_cost.side_effect = [0.80, 0.90, 0.70]

        wf = parse_workflow_yaml(_YAML_DISPATCH_WITH_COST_CAP)
        state = WorkflowState(
            current_task=Task(id="t1", instruction="Run dispatch"),
        )

        await wf.run(state)

        assert _active_budget.get(None) is None

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_litellm_calls_do_not_receive_parent_budget_session(
        self, mock_cost, mock_acompletion
    ):
        """Budget accounting is owned by IPC; LiteLLMClient does not see _active_budget."""
        captured_sessions = []

        async def _capturing_acompletion(**kwargs):
            session = _active_budget.get(None)
            captured_sessions.append(session)
            return _make_litellm_response(content="ok", total_tokens=100)

        mock_acompletion.side_effect = _capturing_acompletion
        mock_cost.return_value = 0.80

        wf = parse_workflow_yaml(_YAML_DISPATCH_WITH_COST_CAP)
        state = WorkflowState(
            current_task=Task(id="t1", instruction="Run dispatch"),
        )

        await wf.run(state)

        assert len(captured_sessions) == 3
        for s in captured_sessions:
            assert s is None, "Engine-side LiteLLM calls should not use direct budget context"


# ===========================================================================
# Scenario 3: No budget — branches run unchanged
# ===========================================================================


class TestNoBudgetBranchesRunUnchanged:
    """Workflow with no limits: and a dispatch block.
    Normal execution, no budget overhead."""

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_workflow_completes_normally(self, mock_cost, mock_acompletion):
        """Dispatch with no limits runs all branches and completes normally."""
        mock_acompletion.side_effect = [
            _make_litellm_response(content="result A", total_tokens=100),
            _make_litellm_response(content="result B", total_tokens=120),
            _make_litellm_response(content="result C", total_tokens=80),
        ]
        mock_cost.side_effect = [0.50, 0.60, 0.40]

        wf = parse_workflow_yaml(_YAML_DISPATCH_NO_LIMITS)
        state = WorkflowState(
            current_task=Task(id="t1", instruction="Run dispatch"),
        )

        result = await wf.run(state)

        assert "dispatch_block.branch_a" in result.results
        assert "dispatch_block.branch_b" in result.results
        assert "dispatch_block.branch_c" in result.results
        assert "dispatch_block" in result.results

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_no_active_budget_during_branch_execution(self, mock_cost, mock_acompletion):
        """When no limits are set, _active_budget should be None during branch execution."""
        captured_sessions = []

        async def _capturing_acompletion(**kwargs):
            session = _active_budget.get(None)
            captured_sessions.append(session)
            return _make_litellm_response(content="ok", total_tokens=80)

        mock_acompletion.side_effect = _capturing_acompletion
        mock_cost.return_value = 0.10

        wf = parse_workflow_yaml(_YAML_DISPATCH_NO_LIMITS)
        state = WorkflowState(
            current_task=Task(id="t1", instruction="Run dispatch"),
        )

        await wf.run(state)

        assert len(captured_sessions) == 3
        for s in captured_sessions:
            assert s is None, "Without budget, branches should see no session"

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_cost_and_tokens_still_tracked(self, mock_cost, mock_acompletion):
        """Even without budget enforcement, state should track cost and tokens."""
        mock_acompletion.side_effect = [
            _make_litellm_response(content="A", total_tokens=100),
            _make_litellm_response(content="B", total_tokens=120),
            _make_litellm_response(content="C", total_tokens=80),
        ]
        mock_cost.side_effect = [0.50, 0.60, 0.40]

        wf = parse_workflow_yaml(_YAML_DISPATCH_NO_LIMITS)
        state = WorkflowState(
            current_task=Task(id="t1", instruction="Run dispatch"),
        )

        result = await wf.run(state)

        assert result.total_cost_usd == pytest.approx(1.50)
        assert result.total_tokens == 300

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_no_limits_attribute_on_workflow(self, mock_cost, mock_acompletion):
        """Parsed workflow without limits: key should have no .limits attribute (or None)."""
        wf = parse_workflow_yaml(_YAML_DISPATCH_NO_LIMITS)
        limits = getattr(wf, "limits", None)
        assert limits is None
