"""
Failing tests for RUN-267: Rewrite _resolve_next() to use exit_handle — delete metadata routing.

After this ticket:
- _resolve_next() reads exit_handle from state.results[block_id].exit_handle
- output_conditions persist exit_handle on BlockResult (not metadata)
- "router_decision" global key is deleted from codebase
- "{block_id}_decision" metadata reads are gone from _resolve_next

Resolution order (new):
1. Read state.results[block_id].exit_handle (if BlockResult with exit_handle set)
2. If no exit_handle, evaluate output_conditions (if present) — persist exit_handle on BlockResult
3. If conditional_transitions exist: use exit_handle as lookup key
4. Fallback to "default" key in condition_map
5. Fallback to plain transition

Tests cover:
- AC1: Block returning BlockResult(exit_handle="pass") routes correctly via conditional_transitions
- AC2: Block with output_conditions: computed exit_handle routes correctly AND is persisted on BlockResult
- AC3: Block without exit_handle or output_conditions: uses plain transition
- AC4: "default" key in condition_map works as fallback
- AC5: Missing exit_handle + no default raises clear error
- AC6: "router_decision" global key is gone from codebase
- AC7: "{block_id}_decision" metadata reads are gone from _resolve_next
"""

import inspect
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
# AC1: Block returning BlockResult(exit_handle="pass") routes correctly
#      via conditional_transitions
# ==============================================================================


class TestExitHandleRoutesViaConditionalTransitions:
    """AC1: _resolve_next reads exit_handle from BlockResult in state.results
    and uses it as the lookup key in conditional_transitions."""

    def test_exit_handle_pass_routes_to_correct_block(self):
        """BlockResult with exit_handle='pass' selects the 'pass' branch."""
        wf = Workflow(name="eh_routing")

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
        NOT the 'default' branch — proving exit_handle is actually read."""
        wf = Workflow(name="eh_routing")

        wf.add_block(StubBlock("gate"))
        wf.add_block(StubBlock("on_pass"))
        wf.add_block(StubBlock("on_fail"))
        wf.add_block(StubBlock("on_default"))
        wf.set_entry("gate")

        # "default" points to a DIFFERENT block than "fail" —
        # so this test can only pass if exit_handle is actually used as lookup key
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
        wf = Workflow(name="eh_custom")

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
        """exit_handle on BlockResult is used INSTEAD of metadata — metadata is ignored.

        This proves the new resolution order: BlockResult.exit_handle first,
        metadata-based routing is deleted.
        """
        wf = Workflow(name="eh_priority")

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
                # Old-style metadata that SHOULD be ignored
                "metadata": {
                    "router_decision": "meta_val",
                    "step_decision": "meta_val",
                },
            }
        )

        next_id = wf._resolve_next("step", state)
        # Must use exit_handle, not metadata
        assert next_id == "from_handle"


# ==============================================================================
# AC1 (end-to-end): Full workflow run with exit_handle routing
# ==============================================================================


class TestExitHandleEndToEnd:
    """AC1 end-to-end: run a workflow where a block sets exit_handle and routing follows."""

    @pytest.mark.asyncio
    async def test_full_run_exit_handle_pass(self):
        """Full workflow run: gate block sets exit_handle='pass', routes to on_pass
        (not to on_default which is the 'default' key target)."""
        wf = Workflow(name="e2e_eh")

        gate = ExitHandleBlock("gate", exit_handle="pass", output="gate_output")
        on_pass = ExitHandleBlock("on_pass", exit_handle="done", output="pass_output")
        on_default = ExitHandleBlock("on_default", exit_handle="done", output="default_output")

        wf.add_block(gate)
        wf.add_block(on_pass)
        wf.add_block(on_default)
        wf.set_entry("gate")

        # "default" points to on_default, NOT on_pass — proves exit_handle is read
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
        assert "on_default" not in final.results, "Should NOT fall to default"

    @pytest.mark.asyncio
    async def test_full_run_exit_handle_fail(self):
        """Full workflow run: gate block sets exit_handle='fail', routes to on_fail
        (not to on_default which is the 'default' key target)."""
        wf = Workflow(name="e2e_eh_fail")

        gate = ExitHandleBlock("gate", exit_handle="fail", output="gate_output")
        on_fail = ExitHandleBlock("on_fail", exit_handle="done", output="fail_output")
        on_default = ExitHandleBlock("on_default", exit_handle="done", output="default_output")

        wf.add_block(gate)
        wf.add_block(on_fail)
        wf.add_block(on_default)
        wf.set_entry("gate")

        # "default" points to on_default, NOT on_fail
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
        assert "on_default" not in final.results, "Should NOT fall to default"


# ==============================================================================
# AC2: output_conditions compute exit_handle AND persist it on BlockResult
# ==============================================================================


class TestOutputConditionsPersistExitHandleOnBlockResult:
    """AC2: When output_conditions fire, they set exit_handle on BlockResult
    (not metadata), and the exit_handle feeds into conditional_transitions."""

    def test_output_conditions_set_exit_handle_on_block_result(self):
        """output_conditions evaluation persists exit_handle on the BlockResult
        in state.results, not in state.metadata."""
        wf = Workflow(name="oc_eh")

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

        # AC2 key assertion: exit_handle is persisted on the BlockResult
        assert state.results["step_a"].exit_handle == "good"

    def test_output_conditions_do_NOT_write_to_metadata(self):
        """After output_conditions fire, state.metadata must NOT contain
        the old '{block_id}_decision' key — it goes on BlockResult instead."""
        wf = Workflow(name="oc_no_meta")

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

        # OLD behavior wrote to metadata — new behavior must NOT
        assert "step_a_decision" not in state.metadata

    def test_output_conditions_default_persists_on_block_result(self):
        """When no case matches, the default decision is persisted as exit_handle
        on BlockResult."""
        wf = Workflow(name="oc_default")

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
    async def test_output_conditions_e2e_exit_handle_persisted(self):
        """End-to-end: output_conditions compute exit_handle, persisted on BlockResult,
        routing follows."""
        wf = Workflow(name="oc_e2e")

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
# AC3: Block without exit_handle or output_conditions uses plain transition
# ==============================================================================


class TestPlainTransitionFallback:
    """AC3: When no exit_handle is set and no output_conditions exist,
    _resolve_next falls back to the plain transition."""

    def test_plain_transition_no_exit_handle(self):
        """Block with no exit_handle and no output_conditions uses plain transition."""
        wf = Workflow(name="plain")

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
        wf = Workflow(name="terminal")

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
        wf = Workflow(name="plain_none")

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
# AC4: "default" key in condition_map works as fallback
# ==============================================================================


class TestDefaultFallbackInConditionMap:
    """AC4: When exit_handle doesn't match any key in condition_map,
    the 'default' key is used as fallback."""

    def test_unknown_exit_handle_falls_back_to_default(self):
        """exit_handle value not in condition_map -> 'default' key used."""
        wf = Workflow(name="default_fb")

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
        wf = Workflow(name="oc_default_fb")

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
# AC5: Missing exit_handle + no "default" in condition_map raises clear error
# ==============================================================================


class TestMissingExitHandleNoDefaultRaises:
    """AC5: When exit_handle doesn't match and there's no 'default' key
    in condition_map, a clear KeyError is raised."""

    def test_no_exit_handle_no_default_raises_key_error(self):
        """No exit_handle set, no output_conditions, conditional transition exists,
        no default -> KeyError."""
        wf = Workflow(name="no_default")

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
        wf = Workflow(name="unmatched")

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
# AC6: "router_decision" global key is gone from codebase (source scan)
# ==============================================================================


class TestRouterDecisionRemoved:
    """AC6: The string 'router_decision' must not appear in workflow.py source code."""

    def test_router_decision_string_absent_from_resolve_next(self):
        """_resolve_next source code must NOT contain 'router_decision'."""
        source = inspect.getsource(Workflow._resolve_next)
        assert "router_decision" not in source, (
            "_resolve_next still references 'router_decision' — "
            "it should read exit_handle from BlockResult instead"
        )

    def test_router_decision_string_absent_from_workflow_module(self):
        """The entire workflow module must NOT contain 'router_decision'."""
        import runsight_core.workflow as wf_module

        source = inspect.getsource(wf_module)
        assert "router_decision" not in source, (
            "workflow.py still contains 'router_decision' — "
            "all metadata-based routing must be deleted"
        )

    def test_resolve_next_does_not_read_global_metadata_key(self):
        """_resolve_next must NOT read state.metadata.get('router_decision').

        Even if metadata has the key, _resolve_next must ignore it.
        """
        wf = Workflow(name="no_global")

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
                    # Old-style global key — must be ignored
                    "router_decision": "meta_decision",
                },
            }
        )

        next_id = wf._resolve_next("step", state)
        # Should NOT follow metadata; should fall to "default"
        assert next_id == "from_default"


# ==============================================================================
# AC7: "{block_id}_decision" metadata reads are gone from _resolve_next
# ==============================================================================


class TestBlockScopedDecisionMetadataRemoved:
    """AC7: _resolve_next must NOT read '{block_id}_decision' from state.metadata."""

    def test_block_scoped_decision_string_absent_from_source(self):
        """_resolve_next source must NOT contain the pattern '{...}_decision'
        reading from metadata."""
        source = inspect.getsource(Workflow._resolve_next)
        # The old code did: state.metadata.get(f"{current_block_id}_decision")
        assert "_decision" not in source or "exit_handle" in source, (
            "_resolve_next still reads '{block_id}_decision' from metadata — "
            "it should use exit_handle from BlockResult instead"
        )

    def test_block_scoped_metadata_not_used_for_routing(self):
        """Even if state.metadata has '{block_id}_decision', _resolve_next ignores it."""
        wf = Workflow(name="no_scoped")

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
                    # Old-style block-scoped key — must be ignored
                    "step_decision": "scoped_val",
                },
            }
        )

        next_id = wf._resolve_next("step", state)
        # Must NOT follow metadata; should fall to "default"
        assert next_id == "from_default"

    def test_metadata_get_f_decision_absent_from_resolve_next_source(self):
        """The exact pattern `state.metadata.get(f"...decision")` must be gone."""
        source = inspect.getsource(Workflow._resolve_next)
        # Check for the metadata.get pattern with _decision
        assert 'metadata.get(f"' not in source or "_decision" not in source, (
            "_resolve_next still uses metadata.get(f'..._decision') pattern"
        )


# ==============================================================================
# Edge cases: resolution order and interaction tests
# ==============================================================================


class TestResolutionOrder:
    """Verify the priority chain: exit_handle > output_conditions > default > plain."""

    def test_exit_handle_beats_output_conditions(self):
        """When exit_handle is already set AND output_conditions exist,
        exit_handle takes priority (output_conditions should not overwrite)."""
        wf = Workflow(name="priority")

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

        # BlockResult has exit_handle already set — output_conditions should not override
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
        wf = Workflow(name="plain_only")

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
        wf = Workflow(name="no_result")

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
        wf = Workflow(name="no_result_no_default")

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


# ==============================================================================
# Docstring/contract test: set_output_conditions docstring updated
# ==============================================================================


class TestDocstringUpdated:
    """Verify that set_output_conditions docstring no longer references metadata."""

    def test_set_output_conditions_docstring_no_metadata_reference(self):
        """set_output_conditions docstring should NOT reference
        'state.metadata' for writing decisions."""
        doc = Workflow.set_output_conditions.__doc__ or ""
        assert "metadata" not in doc.lower(), (
            "set_output_conditions docstring still references metadata — "
            "it should describe persisting exit_handle on BlockResult"
        )
