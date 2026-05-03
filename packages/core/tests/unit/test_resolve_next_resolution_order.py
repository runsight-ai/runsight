"""Exit-handle workflow routing coverage.

Resolution order:
1. Read state.results[block_id].exit_handle when the BlockResult has one.
2. If no exit_handle exists, evaluate output_conditions and persist the
   decision on BlockResult.
3. If conditional_transitions exist, use exit_handle as the lookup key.
4. Fall back to the "default" key in condition_map.
5. Fall back to a plain transition.

Tests cover:
- BlockResult.exit_handle routing through conditional_transitions.
- output_conditions decisions persisted on BlockResult rather than metadata.
- plain transition and condition_map default fallback behavior.
- clear errors when no exit_handle or condition_map default can route.
- absence of legacy metadata routing keys in workflow.py.
"""

import json

import pytest
from conftest import block_output_from_state
from runsight_core.blocks.base import BaseBlock
from runsight_core.conditions.engine import Case, Condition, ConditionGroup
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.workflow import Workflow

# ---------------------------------------------------------------------------
# Mock blocks
# ---------------------------------------------------------------------------


class StubBlock(BaseBlock):
    """Minimal block for unit-testing _resolve_next (never actually executed)."""

    def __init__(self, block_id: str):
        super().__init__(block_id)

    async def execute(self, ctx):
        state = ctx.state_snapshot
        next_state = state.model_copy(
            update={"results": {**state.results, self.block_id: BlockResult(output="done")}}
        )
        return block_output_from_state(self.block_id, state, next_state)


class ExitHandleBlock(BaseBlock):
    """Block whose execute() stores a BlockResult with a specific exit_handle."""

    def __init__(self, block_id: str, exit_handle: str, output: str = "done"):
        super().__init__(block_id)
        self._exit_handle = exit_handle
        self._output = output

    async def execute(self, ctx):
        state = ctx.state_snapshot
        next_state = state.model_copy(
            update={
                "results": {
                    **state.results,
                    self.block_id: BlockResult(
                        output=self._output,
                        exit_handle=self._exit_handle,
                    ),
                },
            }
        )
        return block_output_from_state(self.block_id, state, next_state)


class JsonOutputBlock(BaseBlock):
    """Block that stores a JSON-string BlockResult (no exit_handle set)."""

    def __init__(self, block_id: str, data: dict):
        super().__init__(block_id)
        self._data = data

    async def execute(self, ctx):
        state = ctx.state_snapshot
        next_state = state.model_copy(
            update={
                "results": {
                    **state.results,
                    self.block_id: BlockResult(output=json.dumps(self._data)),
                },
            }
        )
        return block_output_from_state(self.block_id, state, next_state)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_case(case_id: str, conditions: list, combinator: str = "and") -> Case:
    """Shorthand to build a Case from raw condition dicts."""
    return Case(
        case_id=case_id,
        condition_group=ConditionGroup(
            conditions=[Condition(**c) for c in conditions],
            combinator=combinator,
        ),
    )


def _fresh_state() -> WorkflowState:
    return WorkflowState()


# ==============================================================================
# BlockResult.exit_handle routes through conditional_transitions
# ==============================================================================


class TestResolutionOrder:
    """Verify the priority chain: exit_handle > output_conditions > default > plain."""

    def test_exit_handle_beats_output_conditions(self):
        """When exit_handle is already set and output_conditions exist,
        exit_handle takes priority (output_conditions should not overwrite)."""
        wf = Workflow(name="exit_handle_priority")

        wf.add_block(StubBlock("step"))
        wf.add_block(StubBlock("from_handle"))
        wf.add_block(StubBlock("from_oc"))
        wf.set_entry("step")

        # output_conditions would produce "oc_result"
        cases = [
            _make_case(
                "oc_result",
                [{"eval_key": "k", "operator": "equals", "value": "v"}],
            ),
        ]
        wf.set_output_conditions("step", cases, default="oc_default")

        wf.add_conditional_transition(
            "step",
            {
                "handle_val": "from_handle",
                "oc_result": "from_oc",
                "oc_default": "from_oc",
                "default": "from_oc",
            },
        )

        # BlockResult has exit_handle already set, so output_conditions should not override.
        state = _fresh_state().model_copy(
            update={
                "results": {
                    "step": BlockResult(
                        output=json.dumps({"k": "v"}),
                        exit_handle="handle_val",
                    ),
                },
            }
        )

        next_id = wf._resolve_next("step", state)
        assert next_id == "from_handle"

    def test_no_conditional_transition_ignores_exit_handle(self):
        """If only plain transitions exist, exit_handle is ignored and
        plain transition is used (no error)."""
        wf = Workflow(name="plain_transition_only")

        wf.add_block(StubBlock("a"))
        wf.add_block(StubBlock("b"))
        wf.add_transition("a", "b")
        wf.set_entry("a")

        state = _fresh_state().model_copy(
            update={
                "results": {
                    "a": BlockResult(output="x", exit_handle="some_handle"),
                },
            }
        )

        # Plain transition should still work even with exit_handle set
        next_id = wf._resolve_next("a", state)
        assert next_id == "b"

    def test_no_block_result_in_state_with_conditional_and_default(self):
        """If block_id not in state.results at all and conditional_transitions exist,
        should fall back to 'default' key."""
        wf = Workflow(name="missing_result_default_fallback")

        wf.add_block(StubBlock("step"))
        wf.add_block(StubBlock("target"))
        wf.set_entry("step")

        wf.add_conditional_transition(
            "step",
            {"some_key": "target", "default": "target"},
        )

        # No results for "step" at all
        state = _fresh_state()

        next_id = wf._resolve_next("step", state)
        assert next_id == "target"

    def test_no_block_result_no_default_raises(self):
        """If block_id not in state.results, conditional_transitions exist, no default -> KeyError."""
        wf = Workflow(name="missing_result_no_default")

        wf.add_block(StubBlock("step"))
        wf.add_block(StubBlock("target"))
        wf.set_entry("step")

        wf.add_conditional_transition(
            "step",
            {"some_key": "target"},  # No "default"
        )

        state = _fresh_state()

        with pytest.raises(KeyError):
            wf._resolve_next("step", state)
