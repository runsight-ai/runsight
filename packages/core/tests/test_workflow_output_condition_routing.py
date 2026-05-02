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
from unittest.mock import patch

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


class TestResolveNextWithOutputConditions:
    """Tests for _resolve_next evaluating output_conditions."""

    def test_resolve_next_evaluates_output_conditions(self):
        """_resolve_next returns the correct next block based on output_conditions match."""
        wf = Workflow(name="workflow-block-execute-workflow")

        step_a = MockJsonBlock("step_a", {"status": "ok"})
        step_good = MockBlock("step_good")
        step_bad = MockBlock("step_bad")

        wf.add_block(step_a)
        wf.add_block(step_good)
        wf.add_block(step_bad)
        wf.set_entry("step_a")

        # Set output_conditions on step_a
        cases = [
            _make_case("good", [{"eval_key": "status", "operator": "equals", "value": "ok"}]),
            _make_case("bad", [{"eval_key": "status", "operator": "equals", "value": "error"}]),
        ]
        wf.set_output_conditions("step_a", cases)

        # Set conditional_transitions that consume the decision
        wf.add_conditional_transition(
            "step_a",
            {
                "good": "step_good",
                "bad": "step_bad",
                "default": "step_bad",
            },
        )

        # Simulate step_a having executed
        state = _initial_state().model_copy(
            update={"results": {"step_a": json.dumps({"status": "ok"})}}
        )

        # _resolve_next should evaluate output_conditions first,
        # set decision in metadata, then conditional_transitions picks it up
        next_id = wf._resolve_next("step_a", state)
        assert next_id == "step_good"

    def test_output_conditions_evaluate_block_result_output_not_str(self):
        """Output conditions read BlockResult.output instead of implicit __str__."""
        wf = Workflow(name="workflow-block-execute-workflow")
        wf.add_block(MockBlock("step_a"))
        wf.add_block(MockBlock("matched"))
        wf.add_block(MockBlock("fallback"))
        wf.set_entry("step_a")

        cases = [
            _make_case(
                "matched",
                [{"eval_key": "result", "operator": "contains", "value": "REAL_OUTPUT"}],
            ),
        ]
        wf.set_output_conditions("step_a", cases, default="fallback")
        wf.add_conditional_transition(
            "step_a",
            {"matched": "matched", "fallback": "fallback"},
        )
        state = WorkflowState(results={"step_a": BlockResult(output="REAL_OUTPUT")})

        with patch.object(BlockResult, "__str__", return_value="PATCHED_STR"):
            next_id = wf._resolve_next("step_a", state)

        assert next_id == "matched"

    def test_output_conditions_before_conditional_transitions(self):
        """output_conditions are evaluated FIRST, setting metadata that conditional_transitions reads."""
        wf = Workflow(name="workflow-block-execute-workflow")

        step_a = MockJsonBlock("step_a", {"quality": "high"})
        step_high = MockBlock("step_high")
        step_low = MockBlock("step_low")

        wf.add_block(step_a)
        wf.add_block(step_high)
        wf.add_block(step_low)
        wf.set_entry("step_a")

        cases = [
            _make_case("high", [{"eval_key": "quality", "operator": "equals", "value": "high"}]),
            _make_case("low", [{"eval_key": "quality", "operator": "equals", "value": "low"}]),
        ]
        wf.set_output_conditions("step_a", cases)

        wf.add_conditional_transition(
            "step_a",
            {
                "high": "step_high",
                "low": "step_low",
                "default": "step_low",
            },
        )

        state = _initial_state().model_copy(
            update={"results": {"step_a": json.dumps({"quality": "high"})}}
        )

        next_id = wf._resolve_next("step_a", state)
        assert next_id == "step_high"

    def test_output_conditions_default_fallback(self):
        """When no case matches, the default decision is used."""
        wf = Workflow(name="workflow-block-execute-workflow")

        step_a = MockJsonBlock("step_a", {"status": "unknown"})
        step_ok = MockBlock("step_ok")
        step_fallback = MockBlock("step_fallback")

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

        state = _initial_state().model_copy(
            update={"results": {"step_a": json.dumps({"status": "unknown"})}}
        )

        next_id = wf._resolve_next("step_a", state)
        assert next_id == "step_fallback"

    def test_output_conditions_decision_written_to_exit_handle(self):
        """_resolve_next writes the decision to state.results[block_id].exit_handle."""
        wf = Workflow(name="workflow-block-execute-workflow")

        step_a = MockJsonBlock("step_a", {"val": "match"})
        step_next = MockBlock("step_next")

        wf.add_block(step_a)
        wf.add_block(step_next)
        wf.set_entry("step_a")

        cases = [
            _make_case("matched", [{"eval_key": "val", "operator": "equals", "value": "match"}]),
        ]
        wf.set_output_conditions("step_a", cases)

        wf.add_conditional_transition(
            "step_a",
            {
                "matched": "step_next",
                "default": "step_next",
            },
        )

        state = _initial_state().model_copy(
            update={"results": {"step_a": BlockResult(output=json.dumps({"val": "match"}))}}
        )

        # After _resolve_next, the decision is persisted on the BlockResult's
        # exit_handle field (not in state.metadata).
        wf._resolve_next("step_a", state)
        assert state.results["step_a"].exit_handle == "matched"


# ===== Block without output_conditions =====


class TestBlockWithoutOutputConditions:
    """Ensure blocks without output_conditions route normally."""

    def test_block_without_output_conditions_routes_normally(self):
        """Plain transitions still work when no output_conditions are set."""
        wf = Workflow(name="workflow-block-execute-workflow")

        step_a = MockBlock("step_a")
        step_b = MockBlock("step_b")

        wf.add_block(step_a)
        wf.add_block(step_b)
        wf.add_transition("step_a", "step_b")
        wf.set_entry("step_a")

        state = _initial_state().model_copy(update={"results": {"step_a": "done"}})

        next_id = wf._resolve_next("step_a", state)
        assert next_id == "step_b"


# ===== Same block, different workflows =====


class TestSameBlockDifferentWorkflows:
    """Test that output_conditions are workflow-scoped, not block-scoped."""

    def test_same_block_different_workflows_different_conditions(self):
        """Same block instance in two workflows can have different output_conditions."""
        shared_block = MockJsonBlock("shared", {"score": "80"})
        target_a = MockBlock("target_a")
        target_b = MockBlock("target_b")
        target_c = MockBlock("target_c")

        # Workflow 1: routes on score > 70 -> "high"
        wf1 = Workflow(name="wf1")
        wf1.add_block(shared_block)
        wf1.add_block(target_a)
        wf1.add_block(target_b)
        wf1.set_entry("shared")
        wf1.set_output_conditions(
            "shared",
            [
                _make_case("high", [{"eval_key": "score", "operator": "gt", "value": "70"}]),
            ],
            default="low",
        )
        wf1.add_conditional_transition(
            "shared",
            {
                "high": "target_a",
                "low": "target_b",
                "default": "target_b",
            },
        )

        # Workflow 2: routes on score > 90 -> "high" (same block, different threshold)
        wf2 = Workflow(name="wf2")
        wf2.add_block(shared_block)
        wf2.add_block(target_b)
        wf2.add_block(target_c)
        wf2.set_entry("shared")
        wf2.set_output_conditions(
            "shared",
            [
                _make_case("high", [{"eval_key": "score", "operator": "gt", "value": "90"}]),
            ],
            default="low",
        )
        wf2.add_conditional_transition(
            "shared",
            {
                "high": "target_b",
                "low": "target_c",
                "default": "target_c",
            },
        )

        state = _initial_state().model_copy(
            update={"results": {"shared": json.dumps({"score": "80"})}}
        )

        # wf1: 80 > 70 -> "high" -> target_a
        next1 = wf1._resolve_next("shared", state)
        assert next1 == "target_a"

        # wf2: 80 > 90 is False -> default "low" -> target_c
        next2 = wf2._resolve_next("shared", state)
        assert next2 == "target_c"


# ===== Combinator tests in workflow context =====
