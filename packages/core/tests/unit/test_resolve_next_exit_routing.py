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


class TestExitHandleRoutesViaConditionalTransitions:
    """_resolve_next reads exit_handle from BlockResult in state.results
    and uses it as the lookup key in conditional_transitions."""

    def test_exit_handle_pass_routes_to_correct_block(self):
        """BlockResult with exit_handle='pass' selects the 'pass' branch."""
        wf = Workflow(name="exit_handle_routing")

        wf.add_block(StubBlock("gate"))
        wf.add_block(StubBlock("on_pass"))
        wf.add_block(StubBlock("on_fail"))
        wf.set_entry("gate")

        wf.add_conditional_transition(
            "gate",
            {"pass": "on_pass", "fail": "on_fail", "default": "on_fail"},
        )

        state = _fresh_state().model_copy(
            update={
                "results": {
                    "gate": BlockResult(output="checked", exit_handle="pass"),
                },
            }
        )

        next_id = wf._resolve_next("gate", state)
        assert next_id == "on_pass"

    def test_exit_handle_fail_routes_to_correct_block(self):
        """BlockResult with exit_handle='fail' selects the 'fail' branch,
        not the 'default' branch, proving exit_handle is actually read."""
        wf = Workflow(name="exit_handle_routing")

        wf.add_block(StubBlock("gate"))
        wf.add_block(StubBlock("on_pass"))
        wf.add_block(StubBlock("on_fail"))
        wf.add_block(StubBlock("on_default"))
        wf.set_entry("gate")

        # "default" points to a different block than "fail", so this test can
        # only pass if exit_handle is actually used as lookup key.
        wf.add_conditional_transition(
            "gate",
            {"pass": "on_pass", "fail": "on_fail", "default": "on_default"},
        )

        state = _fresh_state().model_copy(
            update={
                "results": {
                    "gate": BlockResult(output="checked", exit_handle="fail"),
                },
            }
        )

        next_id = wf._resolve_next("gate", state)
        assert next_id == "on_fail"

    def test_exit_handle_custom_key_routes_correctly(self):
        """exit_handle with an arbitrary key routes through the condition_map."""
        wf = Workflow(name="custom_exit_handle_routing")

        wf.add_block(StubBlock("dispatch"))
        wf.add_block(StubBlock("branch_a"))
        wf.add_block(StubBlock("branch_b"))
        wf.add_block(StubBlock("branch_c"))
        wf.set_entry("dispatch")

        wf.add_conditional_transition(
            "dispatch",
            {
                "case_a": "branch_a",
                "case_b": "branch_b",
                "case_c": "branch_c",
                "default": "branch_a",
            },
        )

        state = _fresh_state().model_copy(
            update={
                "results": {
                    "dispatch": BlockResult(output="routed", exit_handle="case_b"),
                },
            }
        )

        next_id = wf._resolve_next("dispatch", state)
        assert next_id == "branch_b"

    def test_exit_handle_takes_priority_over_metadata(self):
        """exit_handle on BlockResult is used instead of metadata.

        This proves the new resolution order: BlockResult.exit_handle first,
        metadata-based routing is deleted.
        """
        wf = Workflow(name="exit_handle_precedence")

        wf.add_block(StubBlock("step"))
        wf.add_block(StubBlock("from_handle"))
        wf.add_block(StubBlock("from_metadata"))
        wf.set_entry("step")

        wf.add_conditional_transition(
            "step",
            {
                "handle_val": "from_handle",
                "meta_val": "from_metadata",
                "default": "from_metadata",
            },
        )

        state = _fresh_state().model_copy(
            update={
                "results": {
                    "step": BlockResult(output="x", exit_handle="handle_val"),
                },
                # Legacy metadata should be ignored.
                "metadata": {
                    "router_decision": "meta_val",
                    "step_decision": "meta_val",
                },
            }
        )

        next_id = wf._resolve_next("step", state)
        # Must use exit_handle, not metadata.
        assert next_id == "from_handle"


# ==============================================================================
# Full workflow run with exit_handle routing
# ==============================================================================


class TestExitHandleWorkflowIntegration:
    """Run a workflow where a block sets exit_handle and routing follows."""

    @pytest.mark.asyncio
    async def test_full_run_exit_handle_pass(self):
        """Full workflow run: gate block sets exit_handle='pass', routes to on_pass
        (not to on_default which is the 'default' key target)."""
        wf = Workflow(name="exit_handle_workflow_integration")

        gate = ExitHandleBlock("gate", exit_handle="pass", output="gate_output")
        on_pass = ExitHandleBlock("on_pass", exit_handle="done", output="pass_output")
        on_default = ExitHandleBlock("on_default", exit_handle="done", output="default_output")

        wf.add_block(gate)
        wf.add_block(on_pass)
        wf.add_block(on_default)
        wf.set_entry("gate")

        # "default" points to on_default, not on_pass, proving exit_handle is read.
        wf.add_conditional_transition(
            "gate",
            {"pass": "on_pass", "default": "on_default"},
        )
        wf.add_transition("on_pass", None)
        wf.add_transition("on_default", None)

        final = await wf.run(_fresh_state())

        # gate executed, then routed to on_pass (not on_default)
        assert "gate" in final.results
        assert final.results["gate"].exit_handle == "pass"
        assert "on_pass" in final.results, "Should route to on_pass via exit_handle"
        assert "on_default" not in final.results, "Should not fall to default"

    @pytest.mark.asyncio
    async def test_full_run_exit_handle_fail(self):
        """Full workflow run: gate block sets exit_handle='fail', routes to on_fail
        (not to on_default which is the 'default' key target)."""
        wf = Workflow(name="exit_handle_full_run_fail")

        gate = ExitHandleBlock("gate", exit_handle="fail", output="gate_output")
        on_fail = ExitHandleBlock("on_fail", exit_handle="done", output="fail_output")
        on_default = ExitHandleBlock("on_default", exit_handle="done", output="default_output")

        wf.add_block(gate)
        wf.add_block(on_fail)
        wf.add_block(on_default)
        wf.set_entry("gate")

        # "default" points to on_default, not on_fail.
        wf.add_conditional_transition(
            "gate",
            {"fail": "on_fail", "default": "on_default"},
        )
        wf.add_transition("on_fail", None)
        wf.add_transition("on_default", None)

        final = await wf.run(_fresh_state())

        assert "gate" in final.results
        assert final.results["gate"].exit_handle == "fail"
        assert "on_fail" in final.results, "Should route to on_fail via exit_handle"
        assert "on_default" not in final.results, "Should not fall to default"


# ==============================================================================
# output_conditions compute and persist exit_handle on BlockResult
# ==============================================================================
