"""Metadata keys are ignored when resolving exit-handle routing."""

import json

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


class TestRouterDecisionMetadataIgnored:
    """Global routing metadata must not affect conditional transitions."""

    def test_resolve_next_does_not_read_global_metadata_key(self):
        """_resolve_next must not read state.metadata.get('router_decision').

        Even if metadata has the key, _resolve_next must ignore it.
        """
        wf = Workflow(name="global_metadata_ignored")

        wf.add_block(StubBlock("step"))
        wf.add_block(StubBlock("from_metadata"))
        wf.add_block(StubBlock("from_default"))
        wf.set_entry("step")

        wf.add_conditional_transition(
            "step",
            {
                "meta_decision": "from_metadata",
                "default": "from_default",
            },
        )

        state = _fresh_state().model_copy(
            update={
                "results": {
                    "step": BlockResult(output="x"),  # No exit_handle
                },
                "metadata": {
                    # Legacy global key must be ignored.
                    "router_decision": "meta_decision",
                },
            }
        )

        next_id = wf._resolve_next("step", state)
        # Should not follow metadata; should fall to "default".
        assert next_id == "from_default"


# ==============================================================================
# "{block_id}_decision" metadata reads are gone from _resolve_next
# ==============================================================================


class TestBlockScopedDecisionMetadataIgnored:
    """_resolve_next must not read '{block_id}_decision' from state.metadata."""

    def test_block_scoped_metadata_not_used_for_routing(self):
        """Even if state.metadata has '{block_id}_decision', _resolve_next ignores it."""
        wf = Workflow(name="block_scoped_metadata_ignored")

        wf.add_block(StubBlock("step"))
        wf.add_block(StubBlock("from_metadata"))
        wf.add_block(StubBlock("from_default"))
        wf.set_entry("step")

        wf.add_conditional_transition(
            "step",
            {
                "scoped_val": "from_metadata",
                "default": "from_default",
            },
        )

        state = _fresh_state().model_copy(
            update={
                "results": {
                    "step": BlockResult(output="x"),  # No exit_handle
                },
                "metadata": {
                    # Legacy block-scoped key must be ignored.
                    "step_decision": "scoped_val",
                },
            }
        )

        next_id = wf._resolve_next("step", state)
        # Must not follow metadata; should fall to "default".
        assert next_id == "from_default"
