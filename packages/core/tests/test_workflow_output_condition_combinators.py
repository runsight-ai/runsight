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


class TestOutputConditionsCombinatorsInWorkflow:
    """Test AND/OR combinators in the workflow routing context."""

    def test_output_conditions_with_and_combinator(self):
        """AND combinator: all conditions must pass for the case to match."""
        wf = Workflow(name="workflow-block-execute-workflow")

        step_a = MockJsonBlock("step_a", {"status": "ok", "priority": "high"})
        step_match = MockBlock("step_match")
        step_default = MockBlock("step_default")

        wf.add_block(step_a)
        wf.add_block(step_match)
        wf.add_block(step_default)
        wf.set_entry("step_a")

        cases = [
            _make_case(
                "both_ok",
                [
                    {"eval_key": "status", "operator": "equals", "value": "ok"},
                    {"eval_key": "priority", "operator": "equals", "value": "high"},
                ],
                combinator="and",
            ),
        ]
        wf.set_output_conditions("step_a", cases, default="none")
        wf.add_conditional_transition(
            "step_a",
            {
                "both_ok": "step_match",
                "none": "step_default",
                "default": "step_default",
            },
        )

        state = _initial_state().model_copy(
            update={"results": {"step_a": json.dumps({"status": "ok", "priority": "high"})}}
        )

        next_id = wf._resolve_next("step_a", state)
        assert next_id == "step_match"

    def test_output_conditions_with_or_combinator(self):
        """OR combinator: at least one condition must pass."""
        wf = Workflow(name="workflow-block-execute-workflow")

        step_a = MockJsonBlock("step_a", {"status": "error", "fallback": "yes"})
        step_match = MockBlock("step_match")
        step_default = MockBlock("step_default")

        wf.add_block(step_a)
        wf.add_block(step_match)
        wf.add_block(step_default)
        wf.set_entry("step_a")

        cases = [
            _make_case(
                "any_ok",
                [
                    {"eval_key": "status", "operator": "equals", "value": "ok"},
                    {"eval_key": "fallback", "operator": "equals", "value": "yes"},
                ],
                combinator="or",
            ),
        ]
        wf.set_output_conditions("step_a", cases, default="none")
        wf.add_conditional_transition(
            "step_a",
            {
                "any_ok": "step_match",
                "none": "step_default",
                "default": "step_default",
            },
        )

        state = _initial_state().model_copy(
            update={"results": {"step_a": json.dumps({"status": "error", "fallback": "yes"})}}
        )

        next_id = wf._resolve_next("step_a", state)
        assert next_id == "step_match"


# ===== Integration workflow run =====
