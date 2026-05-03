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


class TestPlainTransitionFallback:
    """When no exit_handle is set and no output_conditions exist,
    _resolve_next falls back to the plain transition."""

    def test_plain_transition_no_exit_handle(self):
        """Block with no exit_handle and no output_conditions uses plain transition."""
        wf = Workflow(name="plain_transition")

        wf.add_block(StubBlock("a"))
        wf.add_block(StubBlock("b"))
        wf.add_transition("a", "b")
        wf.set_entry("a")

        state = _fresh_state().model_copy(
            update={
                "results": {
                    "a": BlockResult(output="done"),
                },
            }
        )

        next_id = wf._resolve_next("a", state)
        assert next_id == "b"

    def test_terminal_block_returns_none(self):
        """Terminal block (no transition) returns None."""
        wf = Workflow(name="terminal_transition")

        wf.add_block(StubBlock("end"))
        wf.add_transition("end", None)
        wf.set_entry("end")

        state = _fresh_state().model_copy(
            update={
                "results": {
                    "end": BlockResult(output="finished"),
                },
            }
        )

        next_id = wf._resolve_next("end", state)
        assert next_id is None

    def test_plain_transition_with_exit_handle_none(self):
        """BlockResult(exit_handle=None) with plain transition works normally."""
        wf = Workflow(name="plain_transition_none")

        wf.add_block(StubBlock("a"))
        wf.add_block(StubBlock("b"))
        wf.add_transition("a", "b")
        wf.set_entry("a")

        state = _fresh_state().model_copy(
            update={
                "results": {
                    "a": BlockResult(output="x", exit_handle=None),
                },
            }
        )

        next_id = wf._resolve_next("a", state)
        assert next_id == "b"


# ==============================================================================
# "default" key in condition_map works as fallback
# ==============================================================================


class TestDefaultFallbackInConditionMap:
    """When exit_handle doesn't match any key in condition_map,
    the 'default' key is used as fallback."""

    def test_unknown_exit_handle_falls_back_to_default(self):
        """exit_handle value not in condition_map -> 'default' key used."""
        wf = Workflow(name="condition_map_default_fallback")

        wf.add_block(StubBlock("step"))
        wf.add_block(StubBlock("on_pass"))
        wf.add_block(StubBlock("on_default"))
        wf.set_entry("step")

        wf.add_conditional_transition(
            "step",
            {"pass": "on_pass", "default": "on_default"},
        )

        state = _fresh_state().model_copy(
            update={
                "results": {
                    "step": BlockResult(output="x", exit_handle="unknown_value"),
                },
            }
        )

        next_id = wf._resolve_next("step", state)
        assert next_id == "on_default"

    def test_output_conditions_no_match_uses_default_then_condition_map_default(self):
        """output_conditions default feeds into condition_map default lookup."""
        wf = Workflow(name="output_conditions_default_fallback")

        wf.add_block(StubBlock("step"))
        wf.add_block(StubBlock("target"))
        wf.set_entry("step")

        # No case will match
        cases = [
            _make_case(
                "never",
                [{"eval_key": "x", "operator": "equals", "value": "impossible"}],
            ),
        ]
        wf.set_output_conditions("step", cases, default="default")

        wf.add_conditional_transition(
            "step",
            {"never": "target", "default": "target"},
        )

        state = _fresh_state().model_copy(
            update={
                "results": {
                    "step": BlockResult(output=json.dumps({"x": "other"})),
                },
            }
        )

        next_id = wf._resolve_next("step", state)
        assert next_id == "target"


# ==============================================================================
# Missing exit_handle and no "default" in condition_map raises clear error
# ==============================================================================


class TestMissingExitHandleNoDefaultRaises:
    """When exit_handle doesn't match and there's no 'default' key
    in condition_map, a clear KeyError is raised."""

    def test_no_exit_handle_no_default_raises_key_error(self):
        """No exit_handle set, no output_conditions, conditional transition exists,
        no default -> KeyError."""
        wf = Workflow(name="missing_condition_map_default")

        wf.add_block(StubBlock("step"))
        wf.add_block(StubBlock("a"))
        wf.add_block(StubBlock("b"))
        wf.set_entry("step")

        wf.add_conditional_transition(
            "step",
            {"pass": "a", "fail": "b"},  # No "default" key
        )

        state = _fresh_state().model_copy(
            update={
                "results": {
                    "step": BlockResult(output="x"),  # exit_handle is None
                },
            }
        )

        with pytest.raises(KeyError, match="not found in condition_map"):
            wf._resolve_next("step", state)

    def test_unmatched_exit_handle_no_default_raises_key_error(self):
        """exit_handle set but value not in condition_map and no default -> KeyError."""
        wf = Workflow(name="unmatched_exit_handle")

        wf.add_block(StubBlock("step"))
        wf.add_block(StubBlock("a"))
        wf.set_entry("step")

        wf.add_conditional_transition(
            "step",
            {"pass": "a"},  # No "default", no "mystery" key
        )

        state = _fresh_state().model_copy(
            update={
                "results": {
                    "step": BlockResult(output="x", exit_handle="mystery"),
                },
            }
        )

        with pytest.raises(KeyError, match="not found in condition_map"):
            wf._resolve_next("step", state)


# ==============================================================================
# "router_decision" global key is gone from codebase
# ==============================================================================
