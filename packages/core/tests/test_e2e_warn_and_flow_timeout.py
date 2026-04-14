"""
RUN-729 — E2E tests for warn mode and flow-level timeout.

Full-path integration: YAML parse -> Workflow.run() -> execute_block() ->
LinearBlock -> RunsightTeamRunner -> LiteLLMClient.achat() -> BudgetSession
enforcement.

Mocks only: litellm.acompletion (external LLM call) and litellm.completion_cost
(cost calculator).  All internal modules exercise real code paths.

Scenarios:
1. Warn mode — run continues past cost cap (on_exceed=warn never raises)
2. Flow-level timeout via asyncio.wait_for — cancels entire workflow
3. Flow timeout within limits — completes normally
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from runsight_core.budget_enforcement import (
    BudgetKilledException,
    _active_budget,
)
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

_YAML_WARN_MODE = """\
version: "1.0"
id: test-workflow
kind: workflow
souls:
  worker:
    id: worker
    kind: soul
    name: Worker
    role: Worker
    system_prompt: Do work.
    provider: openai
    model_name: gpt-4o
blocks:
  block1:
    type: linear
    soul_ref: worker
  block2:
    type: linear
    soul_ref: worker
  block3:
    type: linear
    soul_ref: worker
workflow:
  name: warn_mode_test
  entry: block1
  transitions:
    - from: block1
      to: block2
    - from: block2
      to: block3
    - from: block3
      to: null
limits:
  cost_cap_usd: 0.001
  on_exceed: warn
"""

_YAML_FLOW_TIMEOUT_SHORT = """\
version: "1.0"
id: test-workflow
kind: workflow
souls:
  worker:
    id: worker
    kind: soul
    name: Worker
    role: Worker
    system_prompt: Do work.
    provider: openai
    model_name: gpt-4o
blocks:
  block1:
    type: linear
    soul_ref: worker
  block2:
    type: linear
    soul_ref: worker
workflow:
  name: flow_timeout_test
  entry: block1
  transitions:
    - from: block1
      to: block2
    - from: block2
      to: null
limits:
  max_duration_seconds: 1
"""

_YAML_FLOW_TIMEOUT_GENEROUS = """\
version: "1.0"
id: test-workflow
kind: workflow
souls:
  worker:
    id: worker
    kind: soul
    name: Worker
    role: Worker
    system_prompt: Do work.
    provider: openai
    model_name: gpt-4o
blocks:
  block1:
    type: linear
    soul_ref: worker
  block2:
    type: linear
    soul_ref: worker
workflow:
  name: flow_timeout_generous_test
  entry: block1
  transitions:
    - from: block1
      to: block2
    - from: block2
      to: null
limits:
  max_duration_seconds: 60
"""


# ===========================================================================
# Scenario 1: Warn mode — run continues past cost cap
# ===========================================================================


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
            _make_litellm_response(content="result one", total_tokens=100),
            _make_litellm_response(content="result two", total_tokens=100),
            _make_litellm_response(content="result three", total_tokens=100),
        ]
        mock_cost.return_value = 0.001  # each block costs $0.001

        wf = parse_workflow_yaml(_YAML_WARN_MODE)
        state = WorkflowState(
            current_task=Task(id="t1", instruction="Do something"),
        )

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
            _make_litellm_response(content="r1", total_tokens=100),
            _make_litellm_response(content="r2", total_tokens=100),
            _make_litellm_response(content="r3", total_tokens=100),
        ]
        mock_cost.return_value = 0.001

        wf = parse_workflow_yaml(_YAML_WARN_MODE)
        state = WorkflowState(
            current_task=Task(id="t1", instruction="Do something"),
        )

        # Should NOT raise BudgetKilledException
        result = await wf.run(state)
        assert result is not None

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_llm_called_three_times(self, mock_cost, mock_acompletion):
        """LLM should be called exactly 3 times — once per block."""
        mock_acompletion.side_effect = [
            _make_litellm_response(content="r1", total_tokens=100),
            _make_litellm_response(content="r2", total_tokens=100),
            _make_litellm_response(content="r3", total_tokens=100),
        ]
        mock_cost.return_value = 0.001

        wf = parse_workflow_yaml(_YAML_WARN_MODE)
        state = WorkflowState(
            current_task=Task(id="t1", instruction="Do something"),
        )

        await wf.run(state)

        assert mock_acompletion.call_count == 3

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_total_cost_reflects_all_blocks(self, mock_cost, mock_acompletion):
        """Total cost should reflect all 3 blocks ($0.003) despite cap of $0.001."""
        mock_acompletion.side_effect = [
            _make_litellm_response(content="r1", total_tokens=100),
            _make_litellm_response(content="r2", total_tokens=100),
            _make_litellm_response(content="r3", total_tokens=100),
        ]
        mock_cost.return_value = 0.001

        wf = parse_workflow_yaml(_YAML_WARN_MODE)
        state = WorkflowState(
            current_task=Task(id="t1", instruction="Do something"),
        )

        result = await wf.run(state)

        assert result.total_cost_usd == pytest.approx(0.003)
        assert result.total_tokens == 300

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_active_budget_cleaned_up(self, mock_cost, mock_acompletion):
        """After workflow.run(), _active_budget contextvar is reset to None."""
        mock_acompletion.side_effect = [
            _make_litellm_response(total_tokens=100),
            _make_litellm_response(total_tokens=100),
            _make_litellm_response(total_tokens=100),
        ]
        mock_cost.return_value = 0.001

        wf = parse_workflow_yaml(_YAML_WARN_MODE)
        state = WorkflowState(
            current_task=Task(id="t1", instruction="Do something"),
        )

        await wf.run(state)
        assert _active_budget.get(None) is None


# ===========================================================================
# Scenario 2: Flow-level timeout via asyncio.wait_for
# ===========================================================================


class TestFlowLevelTimeout:
    """Workflow with limits: {max_duration_seconds: 1} and blocks that each
    take 2s via slow mock acompletion.  After ~1s,
    BudgetKilledException(scope="workflow", limit_kind="timeout").
    Only block-1 may have started."""

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_budget_killed_exception_raised(self, mock_cost, mock_acompletion):
        """Workflow.run() raises BudgetKilledException when flow timeout fires."""

        async def slow_response(*args, **kwargs):
            await asyncio.sleep(5)
            return _make_litellm_response(content="slow result")

        mock_acompletion.side_effect = slow_response
        mock_cost.return_value = 0.001

        wf = parse_workflow_yaml(_YAML_FLOW_TIMEOUT_SHORT)
        state = WorkflowState(
            current_task=Task(id="t1", instruction="Do something"),
        )

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
        """Flow timeout of 1s MUST terminate within 1.5s (T+0.5s tolerance)."""

        async def slow_response(*args, **kwargs):
            await asyncio.sleep(5)
            return _make_litellm_response(content="slow result")

        mock_acompletion.side_effect = slow_response
        mock_cost.return_value = 0.001

        wf = parse_workflow_yaml(_YAML_FLOW_TIMEOUT_SHORT)
        state = WorkflowState(
            current_task=Task(id="t1", instruction="Do something"),
        )

        t0 = time.monotonic()
        with pytest.raises(BudgetKilledException):
            await wf.run(state)
        elapsed = time.monotonic() - t0

        assert elapsed < 1.5, f"Flow timeout took {elapsed:.2f}s, expected <1.5s"

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_only_first_block_may_have_started(self, mock_cost, mock_acompletion):
        """With 1s flow timeout and 5s per-block sleep, at most block-1 starts.
        LLM should be called at most once (block-1's acompletion started but
        gets cancelled by timeout)."""
        call_count = 0

        async def slow_response(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(5)
            return _make_litellm_response(content="slow result")

        mock_acompletion.side_effect = slow_response
        mock_cost.return_value = 0.001

        wf = parse_workflow_yaml(_YAML_FLOW_TIMEOUT_SHORT)
        state = WorkflowState(
            current_task=Task(id="t1", instruction="Do something"),
        )

        with pytest.raises(BudgetKilledException):
            await wf.run(state)

        # Only block-1 should have started (called acompletion once)
        assert call_count <= 1

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_exception_actual_value_matches_timeout(self, mock_cost, mock_acompletion):
        """BudgetKilledException.actual_value should equal the flow timeout value."""

        async def slow_response(*args, **kwargs):
            await asyncio.sleep(5)
            return _make_litellm_response(content="slow result")

        mock_acompletion.side_effect = slow_response
        mock_cost.return_value = 0.001

        wf = parse_workflow_yaml(_YAML_FLOW_TIMEOUT_SHORT)
        state = WorkflowState(
            current_task=Task(id="t1", instruction="Do something"),
        )

        with pytest.raises(BudgetKilledException) as exc_info:
            await wf.run(state)

        assert exc_info.value.actual_value == 1

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_active_budget_cleaned_up_after_timeout(self, mock_cost, mock_acompletion):
        """After BudgetKilledException from flow timeout, _active_budget is reset."""

        async def slow_response(*args, **kwargs):
            await asyncio.sleep(5)
            return _make_litellm_response(content="slow result")

        mock_acompletion.side_effect = slow_response
        mock_cost.return_value = 0.001

        wf = parse_workflow_yaml(_YAML_FLOW_TIMEOUT_SHORT)
        state = WorkflowState(
            current_task=Task(id="t1", instruction="Do something"),
        )

        with pytest.raises(BudgetKilledException):
            await wf.run(state)

        assert _active_budget.get(None) is None


# ===========================================================================
# Scenario 3: Flow timeout within limits — completes normally
# ===========================================================================


class TestFlowTimeoutWithinLimits:
    """Workflow with limits: {max_duration_seconds: 60} and fast blocks.
    All blocks complete, no timeout."""

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_workflow_completes_normally(self, mock_cost, mock_acompletion):
        """Workflow with generous timeout runs both blocks and completes normally."""
        mock_acompletion.side_effect = [
            _make_litellm_response(content="result one", total_tokens=100),
            _make_litellm_response(content="result two", total_tokens=120),
        ]
        mock_cost.side_effect = [0.01, 0.02]

        wf = parse_workflow_yaml(_YAML_FLOW_TIMEOUT_GENEROUS)
        state = WorkflowState(
            current_task=Task(id="t1", instruction="Do something"),
        )

        result = await wf.run(state)

        assert "block1" in result.results
        assert "block2" in result.results
        assert result.results["block1"].output == "result one"
        assert result.results["block2"].output == "result two"

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_no_exception_raised(self, mock_cost, mock_acompletion):
        """No BudgetKilledException should be raised when blocks complete within timeout."""
        mock_acompletion.side_effect = [
            _make_litellm_response(content="fast one", total_tokens=100),
            _make_litellm_response(content="fast two", total_tokens=120),
        ]
        mock_cost.side_effect = [0.01, 0.02]

        wf = parse_workflow_yaml(_YAML_FLOW_TIMEOUT_GENEROUS)
        state = WorkflowState(
            current_task=Task(id="t1", instruction="Do something"),
        )

        result = await wf.run(state)
        assert result is not None

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_both_blocks_execute(self, mock_cost, mock_acompletion):
        """Both blocks should execute — LLM called twice."""
        mock_acompletion.side_effect = [
            _make_litellm_response(content="first", total_tokens=100),
            _make_litellm_response(content="second", total_tokens=120),
        ]
        mock_cost.side_effect = [0.01, 0.02]

        wf = parse_workflow_yaml(_YAML_FLOW_TIMEOUT_GENEROUS)
        state = WorkflowState(
            current_task=Task(id="t1", instruction="Do something"),
        )

        await wf.run(state)
        assert mock_acompletion.call_count == 2

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_cost_and_tokens_tracked(self, mock_cost, mock_acompletion):
        """Cost and tokens should be tracked even with flow timeout configured."""
        mock_acompletion.side_effect = [
            _make_litellm_response(content="r1", total_tokens=100),
            _make_litellm_response(content="r2", total_tokens=120),
        ]
        mock_cost.side_effect = [0.01, 0.02]

        wf = parse_workflow_yaml(_YAML_FLOW_TIMEOUT_GENEROUS)
        state = WorkflowState(
            current_task=Task(id="t1", instruction="Do something"),
        )

        result = await wf.run(state)

        assert result.total_cost_usd == pytest.approx(0.03)
        assert result.total_tokens == 220


# ---------------------------------------------------------------------------
# YAML template — mixed block-warn + flow-fail
# ---------------------------------------------------------------------------

_YAML_MIXED_BLOCK_WARN_FLOW_FAIL = """\
version: "1.0"
id: test-workflow
kind: workflow
souls:
  worker:
    id: worker
    kind: soul
    name: Worker
    role: Worker
    system_prompt: Do work.
    provider: openai
    model_name: gpt-4o
blocks:
  block1:
    type: linear
    soul_ref: worker
    limits:
      cost_cap_usd: 0.001
      on_exceed: warn
  block2:
    type: linear
    soul_ref: worker
    limits:
      cost_cap_usd: 0.001
      on_exceed: warn
  block3:
    type: linear
    soul_ref: worker
    limits:
      cost_cap_usd: 0.001
      on_exceed: warn
  block4:
    type: linear
    soul_ref: worker
    limits:
      cost_cap_usd: 0.001
      on_exceed: warn
workflow:
  name: mixed_block_warn_flow_fail_test
  entry: block1
  transitions:
    - from: block1
      to: block2
    - from: block2
      to: block3
    - from: block3
      to: block4
    - from: block4
      to: null
limits:
  cost_cap_usd: 0.01
  on_exceed: fail
"""


# ===========================================================================
# Scenario 4: Mixed block-warn + flow-fail enforcement
# ===========================================================================


class TestMixedBlockWarnFlowFail:
    """Block has limits: {cost_cap_usd: 0.001, on_exceed: warn},
    flow has limits: {cost_cap_usd: 0.01, on_exceed: fail}.

    Sub-case A: Block exceeds its own cap but flow total stays within cap.
      -> block continues (warn), flow continues, no exception.

    Sub-case B: Block costs accumulate past the flow cap.
      -> the next block's IPC request raises BudgetKilledException(scope="workflow").
    """

    # -----------------------------------------------------------------------
    # Sub-case A: Block exceeds block cap, flow within cap
    # -----------------------------------------------------------------------

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_block_exceeds_own_cap_flow_continues(self, mock_cost, mock_acompletion):
        """Each block costs $0.005 (5x block cap of $0.001, warn mode).
        Total = $0.005 (1 block), well within flow cap $0.01.
        All 3 blocks should execute because block warn never kills."""
        mock_acompletion.side_effect = [
            _make_litellm_response(content="result one", total_tokens=100),
            _make_litellm_response(content="result two", total_tokens=100),
        ]
        # Each block costs $0.003 — exceeds block cap $0.001 but total $0.006 < flow $0.01
        mock_cost.return_value = 0.003

        # Use a 2-block variant to keep total under flow cap
        yaml_2_blocks = """\
version: "1.0"
id: test-workflow
kind: workflow
souls:
  worker:
    id: worker
    kind: soul
    name: Worker
    role: Worker
    system_prompt: Do work.
    provider: openai
    model_name: gpt-4o
blocks:
  block1:
    type: linear
    soul_ref: worker
    limits:
      cost_cap_usd: 0.001
      on_exceed: warn
  block2:
    type: linear
    soul_ref: worker
    limits:
      cost_cap_usd: 0.001
      on_exceed: warn
workflow:
  name: mixed_under_flow_cap
  entry: block1
  transitions:
    - from: block1
      to: block2
    - from: block2
      to: null
limits:
  cost_cap_usd: 0.01
  on_exceed: fail
"""
        wf = parse_workflow_yaml(yaml_2_blocks)
        state = WorkflowState(
            current_task=Task(id="t1", instruction="Do something"),
        )

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
            _make_litellm_response(content="r1", total_tokens=100),
            _make_litellm_response(content="r2", total_tokens=100),
        ]
        mock_cost.return_value = 0.003  # each block $0.003, total $0.006 < flow $0.01

        yaml_2_blocks = """\
version: "1.0"
id: test-workflow
kind: workflow
souls:
  worker:
    id: worker
    kind: soul
    name: Worker
    role: Worker
    system_prompt: Do work.
    provider: openai
    model_name: gpt-4o
blocks:
  block1:
    type: linear
    soul_ref: worker
    limits:
      cost_cap_usd: 0.001
      on_exceed: warn
  block2:
    type: linear
    soul_ref: worker
    limits:
      cost_cap_usd: 0.001
      on_exceed: warn
workflow:
  name: mixed_no_exception
  entry: block1
  transitions:
    - from: block1
      to: block2
    - from: block2
      to: null
limits:
  cost_cap_usd: 0.01
  on_exceed: fail
"""
        wf = parse_workflow_yaml(yaml_2_blocks)
        state = WorkflowState(
            current_task=Task(id="t1", instruction="Do something"),
        )

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
            _make_litellm_response(content="r1", total_tokens=100),
            _make_litellm_response(content="r2", total_tokens=100),
        ]
        mock_cost.return_value = 0.003

        yaml_2_blocks = """\
version: "1.0"
id: test-workflow
kind: workflow
souls:
  worker:
    id: worker
    kind: soul
    name: Worker
    role: Worker
    system_prompt: Do work.
    provider: openai
    model_name: gpt-4o
blocks:
  block1:
    type: linear
    soul_ref: worker
    limits:
      cost_cap_usd: 0.001
      on_exceed: warn
  block2:
    type: linear
    soul_ref: worker
    limits:
      cost_cap_usd: 0.001
      on_exceed: warn
workflow:
  name: mixed_cost_propagation
  entry: block1
  transitions:
    - from: block1
      to: block2
    - from: block2
      to: null
limits:
  cost_cap_usd: 0.01
  on_exceed: fail
"""
        wf = parse_workflow_yaml(yaml_2_blocks)
        state = WorkflowState(
            current_task=Task(id="t1", instruction="Do something"),
        )

        result = await wf.run(state)

        assert result.total_cost_usd == pytest.approx(0.006)
        assert result.total_tokens == 200

    # -----------------------------------------------------------------------
    # Sub-case B: Flow cap breached via block cost accumulation
    # -----------------------------------------------------------------------

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_flow_cap_breached_raises_budget_killed(self, mock_cost, mock_acompletion):
        """3 blocks x $0.004 = $0.012 total, exceeds flow cap $0.01.
        BudgetKilledException(scope="workflow") raised on block4's next IPC request."""
        mock_acompletion.side_effect = [
            _make_litellm_response(content="r1", total_tokens=100),
            _make_litellm_response(content="r2", total_tokens=100),
            _make_litellm_response(content="r3", total_tokens=100),
        ]
        mock_cost.return_value = 0.004  # each block $0.004, total crosses $0.01 at block 3

        wf = parse_workflow_yaml(_YAML_MIXED_BLOCK_WARN_FLOW_FAIL)
        state = WorkflowState(
            current_task=Task(id="t1", instruction="Do something"),
        )

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
            _make_litellm_response(content="r1", total_tokens=100),
            _make_litellm_response(content="r2", total_tokens=100),
            _make_litellm_response(content="r3", total_tokens=100),
        ]
        mock_cost.return_value = 0.004

        wf = parse_workflow_yaml(_YAML_MIXED_BLOCK_WARN_FLOW_FAIL)
        state = WorkflowState(
            current_task=Task(id="t1", instruction="Do something"),
        )

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
            _make_litellm_response(content="r1", total_tokens=100),
            _make_litellm_response(content="r2", total_tokens=100),
            _make_litellm_response(content="r3", total_tokens=100),
        ]
        mock_cost.return_value = 0.005  # $0.005/block, total $0.015 >> flow cap $0.01

        wf = parse_workflow_yaml(_YAML_MIXED_BLOCK_WARN_FLOW_FAIL)
        state = WorkflowState(
            current_task=Task(id="t1", instruction="Do something"),
        )

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

        original_response = _make_litellm_response

        async def counting_response(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return original_response(content=f"r{call_count}", total_tokens=100)

        mock_acompletion.side_effect = counting_response
        mock_cost.return_value = 0.004

        wf = parse_workflow_yaml(_YAML_MIXED_BLOCK_WARN_FLOW_FAIL)
        state = WorkflowState(
            current_task=Task(id="t1", instruction="Do something"),
        )

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
            _make_litellm_response(total_tokens=100),
            _make_litellm_response(total_tokens=100),
            _make_litellm_response(total_tokens=100),
        ]
        mock_cost.return_value = 0.004

        wf = parse_workflow_yaml(_YAML_MIXED_BLOCK_WARN_FLOW_FAIL)
        state = WorkflowState(
            current_task=Task(id="t1", instruction="Do something"),
        )

        with pytest.raises(BudgetKilledException):
            await wf.run(state)

        assert _active_budget.get(None) is None
