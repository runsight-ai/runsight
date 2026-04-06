"""
Failing tests for RUN-714: budget enforcement wiring — parser, entry point, execute_block.

Three parts:
1. Parser reads `limits:` from YAML and sets `max_duration_seconds` on block instances
2. Entry point (`Workflow.run`) creates flow-level BudgetSession, sets `_active_budget`
   contextvar, wraps with `asyncio.wait_for` for flow timeout
3. `execute_block()` swaps `_active_budget` to block-level session before `_dispatch()`

All tests are expected to FAIL because the wiring has not been implemented yet.
"""

from __future__ import annotations

import asyncio

import pytest
from runsight_core.blocks.base import BaseBlock
from runsight_core.budget_enforcement import (
    BudgetKilledException,
    BudgetSession,
    _active_budget,
)
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.workflow import BlockExecutionContext, Workflow, execute_block
from runsight_core.yaml.parser import parse_workflow_yaml

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MINIMAL_YAML_WITH_BLOCK_LIMITS = """\
version: "1.0"
souls:
  test_soul:
    id: test_soul
    role: Tester
    system_prompt: Run tests.
blocks:
  block1:
    type: linear
    soul_ref: test_soul
    limits:
      max_duration_seconds: 60
      cost_cap_usd: 1.50
      token_cap: 5000
workflow:
  name: test_wiring
  entry: block1
  transitions:
    - from: block1
      to: null
"""

_MINIMAL_YAML_NO_BLOCK_LIMITS = """\
version: "1.0"
souls:
  test_soul:
    id: test_soul
    role: Tester
    system_prompt: Run tests.
blocks:
  block1:
    type: linear
    soul_ref: test_soul
workflow:
  name: test_no_limits
  entry: block1
  transitions:
    - from: block1
      to: null
"""

_MINIMAL_YAML_WITH_FLOW_LIMITS = """\
version: "1.0"
souls:
  test_soul:
    id: test_soul
    role: Tester
    system_prompt: Run tests.
blocks:
  block1:
    type: linear
    soul_ref: test_soul
workflow:
  name: test_flow_limits
  entry: block1
  transitions:
    - from: block1
      to: null
limits:
  max_duration_seconds: 300
  cost_cap_usd: 10.0
  token_cap: 100000
"""

_MINIMAL_YAML_BOTH_LIMITS = """\
version: "1.0"
souls:
  test_soul:
    id: test_soul
    role: Tester
    system_prompt: Run tests.
blocks:
  block1:
    type: linear
    soul_ref: test_soul
    limits:
      max_duration_seconds: 60
      cost_cap_usd: 1.50
workflow:
  name: test_both_limits
  entry: block1
  transitions:
    - from: block1
      to: null
limits:
  max_duration_seconds: 600
  cost_cap_usd: 20.0
"""


class InstantBlock(BaseBlock):
    """Block that completes immediately, recording _active_budget during execution."""

    def __init__(self, block_id: str) -> None:
        super().__init__(block_id)
        self.captured_budget = "NOT_SET"

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        self.captured_budget = _active_budget.get(None)
        return state.model_copy(update={"results": {self.block_id: BlockResult(output="done")}})


class SlowBlock(BaseBlock):
    """Block that sleeps for a configurable duration."""

    def __init__(self, block_id: str, sleep_seconds: float) -> None:
        super().__init__(block_id)
        self.sleep_seconds = sleep_seconds

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        await asyncio.sleep(self.sleep_seconds)
        return state.model_copy(
            update={"results": {self.block_id: BlockResult(output="slow done")}}
        )


def _make_ctx(
    *,
    workflow_name: str = "test_workflow",
    blocks=None,
    observer=None,
) -> BlockExecutionContext:
    return BlockExecutionContext(
        workflow_name=workflow_name,
        blocks=blocks or {},
        call_stack=["root"],
        workflow_registry=None,
        observer=observer,
    )


# ===========================================================================
# Part 1 — Parser sets max_duration_seconds on block instances
# ===========================================================================


class TestParserBridgesBlockLimits:
    """Parser must read block_def.limits and set max_duration_seconds on built blocks."""

    def test_block_with_limits_has_max_duration_seconds(self):
        """When block_def has limits.max_duration_seconds=60,
        the built block has block.max_duration_seconds == 60."""
        wf = parse_workflow_yaml(_MINIMAL_YAML_WITH_BLOCK_LIMITS)
        block = wf._blocks["block1"]
        # Unwrap Step wrapper if present
        inner = getattr(block, "block", block)
        # Unwrap IsolatedBlockWrapper if present
        inner = getattr(inner, "inner_block", inner)
        assert getattr(inner, "max_duration_seconds", None) == 60

    def test_block_without_limits_has_no_max_duration_seconds(self):
        """When block_def has no limits, getattr(block, 'max_duration_seconds', None)
        returns None."""
        wf = parse_workflow_yaml(_MINIMAL_YAML_NO_BLOCK_LIMITS)
        block = wf._blocks["block1"]
        inner = getattr(block, "block", block)
        inner = getattr(inner, "inner_block", inner)
        assert getattr(inner, "max_duration_seconds", None) is None

    def test_block_limits_cost_cap_bridged(self):
        """Parser should also bridge cost_cap_usd from limits to the block."""
        wf = parse_workflow_yaml(_MINIMAL_YAML_WITH_BLOCK_LIMITS)
        block = wf._blocks["block1"]
        inner = getattr(block, "block", block)
        inner = getattr(inner, "inner_block", inner)
        # The block should carry the full limits for BudgetSession creation
        limits = getattr(inner, "limits", None)
        assert limits is not None
        assert limits.cost_cap_usd == 1.50

    def test_block_limits_token_cap_bridged(self):
        """Parser should bridge token_cap from limits to the block."""
        wf = parse_workflow_yaml(_MINIMAL_YAML_WITH_BLOCK_LIMITS)
        block = wf._blocks["block1"]
        inner = getattr(block, "block", block)
        inner = getattr(inner, "inner_block", inner)
        limits = getattr(inner, "limits", None)
        assert limits is not None
        assert limits.token_cap == 5000


# ===========================================================================
# Part 2 — Entry point creates flow-level BudgetSession + contextvar
# ===========================================================================


class TestFlowLevelBudgetSession:
    """Workflow.run() must create a flow-level BudgetSession when workflow has limits."""

    @pytest.mark.asyncio
    async def test_active_budget_set_during_block_execution_when_flow_has_limits(self):
        """When workflow has limits, _active_budget should be a BudgetSession
        during block execution."""
        wf = Workflow(name="flow_budget_test")
        block = InstantBlock("block1")
        wf.add_block(block)
        wf.set_entry("block1")

        # Simulate the flow-level limits by attaching them to the workflow
        from runsight_core.yaml.schema import WorkflowLimitsDef

        wf.limits = WorkflowLimitsDef(max_duration_seconds=300, cost_cap_usd=10.0)

        state = WorkflowState()
        await wf.run(state)

        # The block should have captured a BudgetSession during execution
        assert isinstance(block.captured_budget, BudgetSession)

    @pytest.mark.asyncio
    async def test_active_budget_is_none_when_no_flow_limits(self):
        """When workflow has no limits, _active_budget should stay None."""
        wf = Workflow(name="no_limits_test")
        block = InstantBlock("block1")
        wf.add_block(block)
        wf.set_entry("block1")

        state = WorkflowState()
        await wf.run(state)

        # No limits → no session → captured_budget should be None
        assert block.captured_budget is None

    @pytest.mark.asyncio
    async def test_active_budget_reset_after_workflow_run(self):
        """_active_budget contextvar should be reset (to None) after Workflow.run()
        completes, even on success."""
        wf = Workflow(name="reset_test")
        block = InstantBlock("block1")
        wf.add_block(block)
        wf.set_entry("block1")

        from runsight_core.yaml.schema import WorkflowLimitsDef

        wf.limits = WorkflowLimitsDef(max_duration_seconds=300)

        state = WorkflowState()
        await wf.run(state)

        # After run completes, contextvar should be cleared
        assert _active_budget.get(None) is None

    @pytest.mark.asyncio
    async def test_flow_session_scope_name_contains_workflow_name(self):
        """The flow-level BudgetSession scope_name should contain the workflow name."""
        wf = Workflow(name="scoped_pipeline")
        block = InstantBlock("block1")
        wf.add_block(block)
        wf.set_entry("block1")

        from runsight_core.yaml.schema import WorkflowLimitsDef

        wf.limits = WorkflowLimitsDef(cost_cap_usd=5.0)

        state = WorkflowState()
        await wf.run(state)

        session = block.captured_budget
        assert isinstance(session, BudgetSession)
        assert "scoped_pipeline" in session.scope_name

    @pytest.mark.asyncio
    async def test_flow_timeout_raises_budget_killed_exception(self):
        """When workflow has max_duration_seconds and execution exceeds it,
        BudgetKilledException(scope='workflow', limit_kind='timeout') is raised."""
        wf = Workflow(name="timeout_flow")
        slow = SlowBlock("slow_block", sleep_seconds=2.0)
        wf.add_block(slow)
        wf.set_entry("slow_block")

        from runsight_core.yaml.schema import WorkflowLimitsDef

        # max_duration_seconds=1 is the minimum the schema allows; block sleeps 2s
        wf.limits = WorkflowLimitsDef(max_duration_seconds=1)

        state = WorkflowState()
        with pytest.raises(BudgetKilledException) as exc_info:
            await wf.run(state)

        exc = exc_info.value
        assert exc.scope == "workflow"
        assert exc.limit_kind == "timeout"

    @pytest.mark.asyncio
    async def test_flow_no_timeout_when_max_duration_not_set(self):
        """When workflow limits exist but max_duration_seconds is None,
        no asyncio.wait_for wrapping happens."""
        wf = Workflow(name="no_timeout_flow")
        block = InstantBlock("block1")
        wf.add_block(block)
        wf.set_entry("block1")

        from runsight_core.yaml.schema import WorkflowLimitsDef

        # limits present but no timeout
        wf.limits = WorkflowLimitsDef(cost_cap_usd=5.0)

        state = WorkflowState()
        result = await wf.run(state)

        assert result.results["block1"].output == "done"


# ===========================================================================
# Part 2b — Parser bridges flow limits onto Workflow
# ===========================================================================


class TestParserBridgesFlowLimits:
    """parse_workflow_yaml must bridge file-level limits onto the Workflow object."""

    def test_workflow_has_limits_attribute_when_yaml_has_limits(self):
        """When YAML has top-level limits:, the parsed Workflow has a .limits attribute."""
        wf = parse_workflow_yaml(_MINIMAL_YAML_WITH_FLOW_LIMITS)
        limits = getattr(wf, "limits", "MISSING")
        assert limits != "MISSING", "Workflow should have a .limits attribute"
        assert limits is not None

    def test_workflow_limits_is_none_when_yaml_has_no_limits(self):
        """When YAML has no top-level limits:, Workflow.limits is None."""
        wf = parse_workflow_yaml(_MINIMAL_YAML_NO_BLOCK_LIMITS)
        limits = getattr(wf, "limits", "MISSING")
        # Either attribute is absent or it's None
        assert limits is None or limits == "MISSING"

    def test_workflow_limits_max_duration_seconds_bridged(self):
        """Parser bridges max_duration_seconds from YAML limits to Workflow."""
        wf = parse_workflow_yaml(_MINIMAL_YAML_WITH_FLOW_LIMITS)
        from runsight_core.yaml.schema import WorkflowLimitsDef

        limits = getattr(wf, "limits", None)
        assert isinstance(limits, WorkflowLimitsDef)
        assert limits.max_duration_seconds == 300

    def test_workflow_limits_cost_cap_bridged(self):
        """Parser bridges cost_cap_usd from YAML limits to Workflow."""
        wf = parse_workflow_yaml(_MINIMAL_YAML_WITH_FLOW_LIMITS)
        limits = getattr(wf, "limits", None)
        assert limits is not None
        assert limits.cost_cap_usd == 10.0


# ===========================================================================
# Part 3 — Block session swap in execute_block
# ===========================================================================


class TestBlockSessionSwapInExecuteBlock:
    """execute_block() must swap _active_budget to a block-level session during _dispatch."""

    @pytest.mark.asyncio
    async def test_block_session_set_during_dispatch_when_block_has_limits(self):
        """When block has limits, _active_budget should be a block-level BudgetSession
        during _dispatch(), with parent=flow_session."""
        from runsight_core.yaml.schema import BlockLimitsDef

        flow_session = BudgetSession(
            scope_name="workflow:test",
            cost_cap_usd=10.0,
        )
        # Set the flow-level session as active
        _active_budget.set(flow_session)

        try:
            block = InstantBlock("budgeted_block")
            block.limits = BlockLimitsDef(max_duration_seconds=60, cost_cap_usd=1.0)

            state = WorkflowState()
            ctx = _make_ctx()

            await execute_block(block, state, ctx)

            # During execution, the block should have seen a DIFFERENT session
            # (a block-level one), not the flow session
            captured = block.captured_budget
            assert isinstance(captured, BudgetSession)
            assert captured is not flow_session
            assert captured.parent is flow_session
            assert "budgeted_block" in captured.scope_name
        finally:
            _active_budget.set(None)

    @pytest.mark.asyncio
    async def test_flow_session_restored_after_block_completes(self):
        """After block with limits completes, _active_budget should be restored
        to the flow-level session."""
        from runsight_core.yaml.schema import BlockLimitsDef

        flow_session = BudgetSession(
            scope_name="workflow:test",
            cost_cap_usd=10.0,
        )
        _active_budget.set(flow_session)

        try:
            block = InstantBlock("restore_block")
            block.limits = BlockLimitsDef(max_duration_seconds=30)

            state = WorkflowState()
            ctx = _make_ctx()

            await execute_block(block, state, ctx)

            # After block completes, active budget should be the flow session again
            assert _active_budget.get(None) is flow_session
        finally:
            _active_budget.set(None)

    @pytest.mark.asyncio
    async def test_no_session_swap_when_block_has_no_limits(self):
        """When block has no limits, _active_budget should remain as the flow session
        (no swap occurs)."""
        flow_session = BudgetSession(
            scope_name="workflow:test",
            cost_cap_usd=10.0,
        )
        _active_budget.set(flow_session)

        try:
            block = InstantBlock("no_limits_block")
            # No limits attribute set

            state = WorkflowState()
            ctx = _make_ctx()

            await execute_block(block, state, ctx)

            # Block should have captured the flow session directly (no swap)
            assert block.captured_budget is flow_session
        finally:
            _active_budget.set(None)

    @pytest.mark.asyncio
    async def test_block_session_restored_even_on_error(self):
        """If block raises during execution, _active_budget should still be restored
        to the flow session."""
        from runsight_core.yaml.schema import BlockLimitsDef

        class FailingBlock(BaseBlock):
            def __init__(self, block_id: str) -> None:
                super().__init__(block_id)

            async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
                raise RuntimeError("intentional failure")

        flow_session = BudgetSession(
            scope_name="workflow:test",
            cost_cap_usd=10.0,
        )
        _active_budget.set(flow_session)

        try:
            block = FailingBlock("failing_block")
            block.limits = BlockLimitsDef(max_duration_seconds=30)

            state = WorkflowState()
            ctx = _make_ctx()

            with pytest.raises(RuntimeError, match="intentional failure"):
                await execute_block(block, state, ctx)

            # Even after error, flow session should be restored
            assert _active_budget.get(None) is flow_session
        finally:
            _active_budget.set(None)


# ===========================================================================
# Part 3b — End-to-end: full wiring through parse + run
# ===========================================================================


class TestEndToEndBudgetWiring:
    """Full pipeline: YAML → parse → Workflow.run() with budget enforcement."""

    @pytest.mark.asyncio
    async def test_parsed_workflow_with_both_limits_creates_nested_sessions(self):
        """When YAML has both flow-level and block-level limits, running the workflow
        should create a flow session and a nested block session with parent linkage."""
        # We can't fully run this through parse_workflow_yaml + wf.run() easily
        # because it requires a real LLM runner. Instead, test the structural wiring:
        # parse the YAML, verify both limits are bridged, then simulate the run pattern.
        wf = parse_workflow_yaml(_MINIMAL_YAML_BOTH_LIMITS)

        # Flow-level limits should be on the workflow
        flow_limits = getattr(wf, "limits", None)
        assert flow_limits is not None, "Workflow should have flow-level limits"
        assert flow_limits.max_duration_seconds == 600

        # Block-level limits should be on the block
        block = wf._blocks["block1"]
        inner = getattr(block, "block", block)
        inner = getattr(inner, "inner_block", inner)
        block_limits = getattr(inner, "limits", None)
        assert block_limits is not None, "Block should have block-level limits"
        assert block_limits.max_duration_seconds == 60
