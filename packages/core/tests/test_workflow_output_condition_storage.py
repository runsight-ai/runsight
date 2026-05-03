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


class TestSetOutputConditions:
    """Tests for storing output_conditions on Workflow."""

    def test_set_output_conditions_stores_correctly(self):
        """Workflow.set_output_conditions stores cases and default for a block_id."""
        wf = Workflow(name="workflow-block-execute-workflow")
        block = MockBlock("step_a", result="ok")
        wf.add_block(block)

        cases = [
            _make_case("good", [{"eval_key": "status", "operator": "equals", "value": "ok"}]),
        ]
        wf.set_output_conditions("step_a", cases, default="fallback")

        # Verify internal storage
        assert "step_a" in wf._output_conditions
        stored_cases, stored_default = wf._output_conditions["step_a"]
        assert len(stored_cases) == 1
        assert stored_cases[0].case_id == "good"
        assert stored_default == "fallback"

    def test_set_output_conditions_default_default(self):
        """Default parameter defaults to 'default' string."""
        wf = Workflow(name="workflow-block-execute-workflow")
        block = MockBlock("step_a")
        wf.add_block(block)

        cases = [
            _make_case("x", [{"eval_key": "k", "operator": "equals", "value": "v"}]),
        ]
        wf.set_output_conditions("step_a", cases)

        _, stored_default = wf._output_conditions["step_a"]
        assert stored_default == "default"


# ===== _resolve_next with output_conditions =====
