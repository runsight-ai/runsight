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


class TestAllOperatorsViaOutputConditions:
    """Verify every one of the 15+ operators works through the workflow router via
    ``Workflow.set_output_conditions()`` + ``Workflow._resolve_next()``.

    This is a parameterized integration test — one sub-case per operator.
    """

    @pytest.mark.parametrize(
        "operator, eval_key, value, block_result, expected_case",
        [
            # --- String operators ---
            ("equals", "s", "ok", {"s": "ok"}, "match"),
            ("not_equals", "s", "ok", {"s": "bad"}, "match"),
            ("contains", "s", "ell", {"s": "hello"}, "match"),
            ("not_contains", "s", "xyz", {"s": "hello"}, "match"),
            ("starts_with", "s", "hel", {"s": "hello"}, "match"),
            ("ends_with", "s", "llo", {"s": "hello"}, "match"),
            ("is_empty", "s", None, {"s": ""}, "match"),
            ("not_empty", "s", None, {"s": "data"}, "match"),
            ("regex", "s", r"^\d{3}$", {"s": "200"}, "match"),
            # --- Numeric operators ---
            ("eq", "n", "10", {"n": "10"}, "match"),
            ("neq", "n", "10", {"n": "20"}, "match"),
            ("gt", "n", "10", {"n": "20"}, "match"),
            ("lt", "n", "10", {"n": "5"}, "match"),
            ("gte", "n", "10", {"n": "10"}, "match"),
            ("lte", "n", "10", {"n": "10"}, "match"),
            # --- Universal operators ---
            ("exists", "k", None, {"k": "val"}, "match"),
            ("not_exists", "k", None, {"other": "val"}, "match"),
        ],
        ids=[
            "equals",
            "not_equals",
            "contains",
            "not_contains",
            "starts_with",
            "ends_with",
            "is_empty",
            "not_empty",
            "regex",
            "eq",
            "neq",
            "gt",
            "lt",
            "gte",
            "lte",
            "exists",
            "not_exists",
        ],
    )
    def test_operator_via_output_conditions(
        self,
        operator,
        eval_key,
        value,
        block_result,
        expected_case,
    ):
        """Operator '{operator}' routes correctly through output_conditions."""
        wf = Workflow(name="workflow-output-operator-conditions")

        step_a = MockBlock("step_a")
        step_match = MockBlock("step_match")
        step_default = MockBlock("step_default")

        wf.add_block(step_a)
        wf.add_block(step_match)
        wf.add_block(step_default)
        wf.set_entry("step_a")

        # Build condition dict — value may be None for unary operators
        cond = {"eval_key": eval_key, "operator": operator}
        if value is not None:
            cond["value"] = value

        cases = [_make_case("match", [cond])]
        wf.set_output_conditions("step_a", cases, default="no_match")

        wf.add_conditional_transition(
            "step_a",
            {
                "match": "step_match",
                "no_match": "step_default",
                "default": "step_default",
            },
        )

        state = _initial_state().model_copy(
            update={"results": {"step_a": json.dumps(block_result)}}
        )

        next_id = wf._resolve_next("step_a", state)
        assert next_id == "step_match", (
            f"Operator '{operator}' did not route to 'step_match'; got next_id={next_id}"
        )
