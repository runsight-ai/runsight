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


class TestOutputConditionsPersistExitHandleOnBlockResult:
    """When output_conditions fire, they set exit_handle on BlockResult
    (not metadata), and the exit_handle feeds into conditional_transitions."""

    def test_output_conditions_set_exit_handle_on_block_result(self):
        """output_conditions evaluation persists exit_handle on the BlockResult
        in state.results, not in state.metadata."""
        wf = Workflow(name="output_conditions_exit_handle")

        wf.add_block(StubBlock("step_a"))
        wf.add_block(StubBlock("step_good"))
        wf.add_block(StubBlock("step_bad"))
        wf.set_entry("step_a")

        cases = [
            _make_case(
                "good",
                [{"eval_key": "status", "operator": "equals", "value": "ok"}],
            ),
        ]
        wf.set_output_conditions("step_a", cases, default="bad")

        wf.add_conditional_transition(
            "step_a",
            {"good": "step_good", "bad": "step_bad", "default": "step_bad"},
        )

        # Simulate step_a having produced a BlockResult (no exit_handle yet)
        state = _fresh_state().model_copy(
            update={
                "results": {
                    "step_a": BlockResult(output=json.dumps({"status": "ok"})),
                },
            }
        )

        next_id = wf._resolve_next("step_a", state)
        assert next_id == "step_good"

        # Key assertion: exit_handle is persisted on the BlockResult.
        assert state.results["step_a"].exit_handle == "good"

    def test_output_conditions_do_not_write_to_metadata(self):
        """After output_conditions fire, state.metadata must not contain
        the old '{block_id}_decision' key because the decision goes on BlockResult."""
        wf = Workflow(name="output_conditions_no_metadata")

        wf.add_block(StubBlock("step_a"))
        wf.add_block(StubBlock("target"))
        wf.set_entry("step_a")

        cases = [
            _make_case(
                "hit",
                [{"eval_key": "v", "operator": "equals", "value": "1"}],
            ),
        ]
        wf.set_output_conditions("step_a", cases, default="miss")

        wf.add_conditional_transition(
            "step_a",
            {"hit": "target", "miss": "target", "default": "target"},
        )

        state = _fresh_state().model_copy(
            update={
                "results": {
                    "step_a": BlockResult(output=json.dumps({"v": "1"})),
                },
            }
        )

        wf._resolve_next("step_a", state)

        # Legacy behavior wrote to metadata; exit handles should not.
        assert "step_a_decision" not in state.metadata

    def test_output_conditions_default_persists_on_block_result(self):
        """When no case matches, the default decision is persisted as exit_handle
        on BlockResult."""
        wf = Workflow(name="output_conditions_default")

        wf.add_block(StubBlock("step_a"))
        wf.add_block(StubBlock("fallback"))
        wf.set_entry("step_a")

        cases = [
            _make_case(
                "match",
                [{"eval_key": "k", "operator": "equals", "value": "nope"}],
            ),
        ]
        wf.set_output_conditions("step_a", cases, default="fallback_decision")

        wf.add_conditional_transition(
            "step_a",
            {"match": "fallback", "fallback_decision": "fallback", "default": "fallback"},
        )

        state = _fresh_state().model_copy(
            update={
                "results": {
                    "step_a": BlockResult(output=json.dumps({"k": "other"})),
                },
            }
        )

        next_id = wf._resolve_next("step_a", state)
        assert next_id == "fallback"
        # exit_handle persisted as the default decision
        assert state.results["step_a"].exit_handle == "fallback_decision"

    @pytest.mark.asyncio
    async def test_output_conditions_integration_exit_handle_persisted(self):
        """Integration: output_conditions compute exit_handle, persisted on BlockResult,
        routing follows."""
        wf = Workflow(name="output_conditions_integration")

        step_a = JsonOutputBlock("step_a", {"status": "approved"})
        step_approved = StubBlock("step_approved")
        step_rejected = StubBlock("step_rejected")

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
            {"approved": "step_approved", "rejected": "step_rejected", "default": "step_rejected"},
        )
        wf.add_transition("step_approved", None)
        wf.add_transition("step_rejected", None)

        final = await wf.run(_fresh_state())

        # Routing went to step_approved
        assert "step_a" in final.results
        # exit_handle was persisted on BlockResult
        assert final.results["step_a"].exit_handle == "approved"


# ==============================================================================
# Block without exit_handle or output_conditions uses plain transition
# ==============================================================================
