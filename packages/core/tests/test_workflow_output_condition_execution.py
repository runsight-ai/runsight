"""
Integration tests for Workflow with output_conditions on blocks.

These tests verify that Workflow._resolve_next() evaluates
output_conditions BEFORE existing conditional_transitions lookup, and that
any block type can use output_conditions for routing.

The key architectural change:
- Workflow gets `_output_conditions: Dict[str, Tuple[List[Case], str]]`
- Workflow gets `set_output_conditions(block_id, cases, default)` method
- `_resolve_next()` evaluates output_conditions first, writes decision to
  state.metadata[f"{block_id}_decision"], then conditional_transitions
  can consume that decision.
"""

import json

import pytest
from conftest import block_output_from_state
from runsight_core.blocks.base import BaseBlock
from runsight_core.conditions.engine import Case, Condition, ConditionGroup
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.workflow import Workflow

# ---------------------------------------------------------------------------
# Mock Blocks
# ---------------------------------------------------------------------------


class MockBlock(BaseBlock):
    """Block that writes a known result string to state.results."""

    def __init__(self, block_id: str, result: str = "mock"):
        super().__init__(block_id)
        self._result = result

    async def execute(self, ctx):
        state = ctx.state_snapshot
        next_state = state.model_copy(
            update={
                "results": {**state.results, self.block_id: BlockResult(output=self._result)},
                "execution_log": state.execution_log
                + [{"role": "system", "content": f"[Block {self.block_id}] Executed"}],
            }
        )
        return block_output_from_state(self.block_id, state, next_state)


class MockJsonBlock(BaseBlock):
    """Block that writes a JSON string result to state.results."""

    def __init__(self, block_id: str, result_dict: dict):
        super().__init__(block_id)
        self._result = json.dumps(result_dict)

    async def execute(self, ctx):
        state = ctx.state_snapshot
        next_state = state.model_copy(
            update={
                "results": {**state.results, self.block_id: BlockResult(output=self._result)},
            }
        )
        return block_output_from_state(self.block_id, state, next_state)


class MockCodeBlock(BaseBlock):
    """
    Simulates a CodeBlock that produces structured JSON output.
    Used to test output_conditions on code-like blocks.
    """

    def __init__(self, block_id: str, output: dict):
        super().__init__(block_id)
        self._output = output

    async def execute(self, ctx):
        state = ctx.state_snapshot
        next_state = state.model_copy(
            update={
                "results": {
                    **state.results,
                    self.block_id: BlockResult(output=json.dumps(self._output)),
                },
                "execution_log": state.execution_log
                + [{"role": "system", "content": f"[CodeBlock {self.block_id}] Executed"}],
            }
        )
        return block_output_from_state(self.block_id, state, next_state)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_case(case_id: str, conditions: list, combinator: str = "and") -> Case:
    """Shorthand to build a Case."""
    return Case(
        case_id=case_id,
        condition_group=ConditionGroup(
            conditions=[Condition(**c) for c in conditions],
            combinator=combinator,
        ),
    )


def _initial_state() -> WorkflowState:
    """Fresh WorkflowState for tests."""
    return WorkflowState()


# ===== Unit Tests for Workflow.set_output_conditions & storage =====


class TestFullWorkflowRunWithOutputConditions:
    """Integration: build and run a workflow with output_conditions."""

    @pytest.mark.asyncio
    async def test_full_workflow_run_with_output_conditions(self):
        """Build workflow with output_conditions, run it, verify correct routing."""
        wf = Workflow(name="workflow-output-conditions-integration")

        # step_a produces JSON with status field
        step_a = MockJsonBlock("step_a", {"status": "approved"})
        step_approved = MockBlock("step_approved", result="approved_output")
        step_rejected = MockBlock("step_rejected", result="rejected_output")

        wf.add_block(step_a)
        wf.add_block(step_approved)
        wf.add_block(step_rejected)
        wf.set_entry("step_a")

        cases = [
            _make_case(
                "approved",
                [{"eval_key": "status", "operator": "equals", "value": "approved"}],
            ),
            _make_case(
                "rejected",
                [{"eval_key": "status", "operator": "equals", "value": "rejected"}],
            ),
        ]
        wf.set_output_conditions("step_a", cases, default="rejected")

        wf.add_conditional_transition(
            "step_a",
            {
                "approved": "step_approved",
                "rejected": "step_rejected",
                "default": "step_rejected",
            },
        )
        # Terminal blocks
        wf.add_transition("step_approved", None)
        wf.add_transition("step_rejected", None)

        state = _initial_state()
        final_state = await wf.run(state)

        # step_a should have run, then routed to step_approved
        assert "step_a" in final_state.results
        assert "step_approved" in final_state.results
        assert "step_rejected" not in final_state.results
        assert final_state.results["step_approved"].output == "approved_output"

    @pytest.mark.asyncio
    async def test_full_workflow_run_default_route(self):
        """Full run: no case matches, routes via default."""
        wf = Workflow(name="workflow-output-default-route")

        step_a = MockJsonBlock("step_a", {"status": "unknown"})
        step_ok = MockBlock("step_ok", result="ok_output")
        step_fallback = MockBlock("step_fallback", result="fallback_output")

        wf.add_block(step_a)
        wf.add_block(step_ok)
        wf.add_block(step_fallback)
        wf.set_entry("step_a")

        cases = [
            _make_case("ok", [{"eval_key": "status", "operator": "equals", "value": "ok"}]),
        ]
        wf.set_output_conditions("step_a", cases, default="fallback")

        wf.add_conditional_transition(
            "step_a",
            {
                "ok": "step_ok",
                "fallback": "step_fallback",
                "default": "step_fallback",
            },
        )
        wf.add_transition("step_ok", None)
        wf.add_transition("step_fallback", None)

        state = _initial_state()
        final_state = await wf.run(state)

        assert "step_fallback" in final_state.results
        assert "step_ok" not in final_state.results
        assert final_state.results["step_fallback"].output == "fallback_output"


# ===== Output conditions on CodeBlock =====


class TestOutputConditionsOnCodeBlock:
    """Test output_conditions routing when applied to CodeBlock-like blocks."""

    @pytest.mark.asyncio
    async def test_output_conditions_on_code_block(self):
        """CodeBlock output evaluated by output_conditions, routes correctly."""
        wf = Workflow(name="workflow-output-code-route")

        # Simulate CodeBlock producing structured output
        code_block = MockCodeBlock("code_step", {"exit_code": 0, "output": "success"})
        step_success = MockBlock("step_success", result="success_path")
        step_failure = MockBlock("step_failure", result="failure_path")

        wf.add_block(code_block)
        wf.add_block(step_success)
        wf.add_block(step_failure)
        wf.set_entry("code_step")

        cases = [
            _make_case(
                "success",
                [{"eval_key": "exit_code", "operator": "eq", "value": "0"}],
            ),
            _make_case(
                "failure",
                [{"eval_key": "exit_code", "operator": "neq", "value": "0"}],
            ),
        ]
        wf.set_output_conditions("code_step", cases, default="failure")

        wf.add_conditional_transition(
            "code_step",
            {
                "success": "step_success",
                "failure": "step_failure",
                "default": "step_failure",
            },
        )
        wf.add_transition("step_success", None)
        wf.add_transition("step_failure", None)

        state = _initial_state()
        final_state = await wf.run(state)

        assert "step_success" in final_state.results
        assert "step_failure" not in final_state.results
        assert final_state.results["step_success"].output == "success_path"

    @pytest.mark.asyncio
    async def test_output_conditions_on_code_block_failure_route(self):
        """CodeBlock with non-zero exit code routes to failure path."""
        wf = Workflow(name="workflow-output-code-failure-route")

        code_block = MockCodeBlock("code_step", {"exit_code": 1, "error": "syntax error"})
        step_success = MockBlock("step_success", result="success_path")
        step_failure = MockBlock("step_failure", result="failure_path")

        wf.add_block(code_block)
        wf.add_block(step_success)
        wf.add_block(step_failure)
        wf.set_entry("code_step")

        cases = [
            _make_case(
                "success",
                [{"eval_key": "exit_code", "operator": "eq", "value": "0"}],
            ),
            _make_case(
                "failure",
                [{"eval_key": "exit_code", "operator": "neq", "value": "0"}],
            ),
        ]
        wf.set_output_conditions("code_step", cases, default="failure")

        wf.add_conditional_transition(
            "code_step",
            {
                "success": "step_success",
                "failure": "step_failure",
                "default": "step_failure",
            },
        )
        wf.add_transition("step_success", None)
        wf.add_transition("step_failure", None)

        state = _initial_state()
        final_state = await wf.run(state)

        assert "step_failure" in final_state.results
        assert "step_success" not in final_state.results
        assert final_state.results["step_failure"].output == "failure_path"


# ===== Stale metadata overwrite test (MAJOR #1) =====


class TestOutputConditionsOverwriteStaleMetadata:
    """Prove that output_conditions evaluation overwrites any pre-existing
    stale ``{block_id}_decision`` value in ``state.metadata``."""

    def test_output_conditions_overwrite_stale_exit_handle(self):
        """output_conditions evaluation sets exit_handle even when metadata has stale data.

        Scenario: state.metadata already contains a stale ``step_a_decision``
        from a previous run, but the BlockResult has no exit_handle yet
        (exit_handle=None).  When ``_resolve_next`` evaluates output_conditions,
        it must compute the fresh decision and persist it on
        ``state.results[block_id].exit_handle``, ignoring stale metadata.
        """
        wf = Workflow(name="workflow-output-stale-decision")

        step_a = MockJsonBlock("step_a", {"status": "ok"})
        step_good = MockBlock("step_good")
        step_stale = MockBlock("step_stale")

        wf.add_block(step_a)
        wf.add_block(step_good)
        wf.add_block(step_stale)
        wf.set_entry("step_a")

        cases = [
            _make_case("good", [{"eval_key": "status", "operator": "equals", "value": "ok"}]),
        ]
        wf.set_output_conditions("step_a", cases, default="fallback")

        wf.add_conditional_transition(
            "step_a",
            {
                "good": "step_good",
                "stale_val": "step_stale",
                "fallback": "step_stale",
                "default": "step_stale",
            },
        )

        # BlockResult has no exit_handle (None), so output_conditions will be
        # evaluated.  Stale metadata is present but no longer consulted.
        state = _initial_state().model_copy(
            update={
                "results": {
                    "step_a": BlockResult(
                        output=json.dumps({"status": "ok"}),
                    )
                },
                "metadata": {"step_a_decision": "stale_val"},
            }
        )

        next_id = wf._resolve_next("step_a", state)

        # output_conditions must win: exit_handle should be "good"
        assert state.results["step_a"].exit_handle == "good"
        assert next_id == "step_good"


# ===== Parameterized operator coverage via output_conditions (CRITICAL #1) =====
