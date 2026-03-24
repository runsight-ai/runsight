"""
Integration tests for Workflow with output_conditions on blocks.

Red-phase TDD: These tests verify that Workflow._resolve_next() evaluates
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

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        return state.model_copy(
            update={
                "results": {**state.results, self.block_id: self._result},
                "execution_log": state.execution_log
                + [{"role": "system", "content": f"[Block {self.block_id}] Executed"}],
            }
        )


class MockJsonBlock(BaseBlock):
    """Block that writes a JSON string result to state.results."""

    def __init__(self, block_id: str, result_dict: dict):
        super().__init__(block_id)
        self._result = json.dumps(result_dict)

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        return state.model_copy(
            update={
                "results": {**state.results, self.block_id: self._result},
            }
        )


class MockCodeBlock(BaseBlock):
    """
    Simulates a CodeBlock that produces structured JSON output.
    Used to test output_conditions on code-like blocks.
    """

    def __init__(self, block_id: str, output: dict):
        super().__init__(block_id)
        self._output = output

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        return state.model_copy(
            update={
                "results": {**state.results, self.block_id: json.dumps(self._output)},
                "execution_log": state.execution_log
                + [{"role": "system", "content": f"[CodeBlock {self.block_id}] Executed"}],
            }
        )


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
        wf = Workflow(name="test_wf")
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
        wf = Workflow(name="test_wf")
        block = MockBlock("step_a")
        wf.add_block(block)

        cases = [
            _make_case("x", [{"eval_key": "k", "operator": "equals", "value": "v"}]),
        ]
        wf.set_output_conditions("step_a", cases)

        _, stored_default = wf._output_conditions["step_a"]
        assert stored_default == "default"


# ===== _resolve_next with output_conditions =====


class TestResolveNextWithOutputConditions:
    """Tests for _resolve_next evaluating output_conditions."""

    def test_resolve_next_evaluates_output_conditions(self):
        """_resolve_next returns the correct next block based on output_conditions match."""
        wf = Workflow(name="test_wf")

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

    def test_output_conditions_before_conditional_transitions(self):
        """output_conditions are evaluated FIRST, setting metadata that conditional_transitions reads."""
        wf = Workflow(name="test_wf")

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
        wf = Workflow(name="test_wf")

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
        wf = Workflow(name="test_wf")

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
        wf = Workflow(name="test_wf")

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


class TestOutputConditionsCombinatorsInWorkflow:
    """Test AND/OR combinators in the workflow routing context."""

    def test_output_conditions_with_and_combinator(self):
        """AND combinator: all conditions must pass for the case to match."""
        wf = Workflow(name="test_wf")

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
        wf = Workflow(name="test_wf")

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


# ===== End-to-end workflow run =====


class TestFullWorkflowRunWithOutputConditions:
    """End-to-end: build and run a workflow with output_conditions."""

    @pytest.mark.asyncio
    async def test_full_workflow_run_with_output_conditions(self):
        """Build workflow with output_conditions, run it, verify correct routing."""
        wf = Workflow(name="e2e_wf")

        # step_a produces JSON with status field
        step_a = MockJsonBlock("step_a", {"status": "approved"})
        step_approved = MockBlock("step_approved", result="approved_output")
        step_rejected = MockBlock("step_rejected", result="rejected_output")

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
            {
                "approved": "step_approved",
                "rejected": "step_rejected",
                "default": "step_rejected",
            },
        )
        # Terminal blocks
        wf.add_transition("step_approved", None)
        wf.add_transition("step_rejected", None)

        state = _initial_state()
        final_state = await wf.run(state)

        # step_a should have run, then routed to step_approved
        assert "step_a" in final_state.results
        assert "step_approved" in final_state.results
        assert "step_rejected" not in final_state.results
        assert final_state.results["step_approved"] == "approved_output"

    @pytest.mark.asyncio
    async def test_full_workflow_run_default_route(self):
        """Full run: no case matches, routes via default."""
        wf = Workflow(name="default_wf")

        step_a = MockJsonBlock("step_a", {"status": "unknown"})
        step_ok = MockBlock("step_ok", result="ok_output")
        step_fallback = MockBlock("step_fallback", result="fallback_output")

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
        wf.add_transition("step_ok", None)
        wf.add_transition("step_fallback", None)

        state = _initial_state()
        final_state = await wf.run(state)

        assert "step_fallback" in final_state.results
        assert "step_ok" not in final_state.results
        assert final_state.results["step_fallback"] == "fallback_output"


# ===== Output conditions on CodeBlock =====


class TestOutputConditionsOnCodeBlock:
    """Test output_conditions routing when applied to CodeBlock-like blocks."""

    @pytest.mark.asyncio
    async def test_output_conditions_on_code_block(self):
        """CodeBlock output evaluated by output_conditions, routes correctly."""
        wf = Workflow(name="code_wf")

        # Simulate CodeBlock producing structured output
        code_block = MockCodeBlock("code_step", {"exit_code": 0, "output": "success"})
        step_success = MockBlock("step_success", result="success_path")
        step_failure = MockBlock("step_failure", result="failure_path")

        wf.add_block(code_block)
        wf.add_block(step_success)
        wf.add_block(step_failure)
        wf.set_entry("code_step")

        cases = [
            _make_case(
                "success",
                [{"eval_key": "exit_code", "operator": "eq", "value": "0"}],
            ),
            _make_case(
                "failure",
                [{"eval_key": "exit_code", "operator": "neq", "value": "0"}],
            ),
        ]
        wf.set_output_conditions("code_step", cases, default="failure")

        wf.add_conditional_transition(
            "code_step",
            {
                "success": "step_success",
                "failure": "step_failure",
                "default": "step_failure",
            },
        )
        wf.add_transition("step_success", None)
        wf.add_transition("step_failure", None)

        state = _initial_state()
        final_state = await wf.run(state)

        assert "step_success" in final_state.results
        assert "step_failure" not in final_state.results
        assert final_state.results["step_success"] == "success_path"

    @pytest.mark.asyncio
    async def test_output_conditions_on_code_block_failure_route(self):
        """CodeBlock with non-zero exit code routes to failure path."""
        wf = Workflow(name="code_fail_wf")

        code_block = MockCodeBlock("code_step", {"exit_code": 1, "error": "syntax error"})
        step_success = MockBlock("step_success", result="success_path")
        step_failure = MockBlock("step_failure", result="failure_path")

        wf.add_block(code_block)
        wf.add_block(step_success)
        wf.add_block(step_failure)
        wf.set_entry("code_step")

        cases = [
            _make_case(
                "success",
                [{"eval_key": "exit_code", "operator": "eq", "value": "0"}],
            ),
            _make_case(
                "failure",
                [{"eval_key": "exit_code", "operator": "neq", "value": "0"}],
            ),
        ]
        wf.set_output_conditions("code_step", cases, default="failure")

        wf.add_conditional_transition(
            "code_step",
            {
                "success": "step_success",
                "failure": "step_failure",
                "default": "step_failure",
            },
        )
        wf.add_transition("step_success", None)
        wf.add_transition("step_failure", None)

        state = _initial_state()
        final_state = await wf.run(state)

        assert "step_failure" in final_state.results
        assert "step_success" not in final_state.results
        assert final_state.results["step_failure"] == "failure_path"


# ===== Stale metadata overwrite test (MAJOR #1) =====


class TestOutputConditionsOverwriteStaleMetadata:
    """Prove that output_conditions evaluation overwrites any pre-existing
    stale ``{block_id}_decision`` value in ``state.metadata``."""

    def test_output_conditions_overwrite_stale_exit_handle(self):
        """output_conditions evaluation sets exit_handle even when metadata has stale data.

        Scenario: state.metadata already contains a stale ``step_a_decision``
        from a previous run, but the BlockResult has no exit_handle yet
        (exit_handle=None).  When ``_resolve_next`` evaluates output_conditions,
        it must compute the fresh decision and persist it on
        ``state.results[block_id].exit_handle``, ignoring stale metadata.
        """
        wf = Workflow(name="stale_wf")

        step_a = MockJsonBlock("step_a", {"status": "ok"})
        step_good = MockBlock("step_good")
        step_stale = MockBlock("step_stale")

        wf.add_block(step_a)
        wf.add_block(step_good)
        wf.add_block(step_stale)
        wf.set_entry("step_a")

        cases = [
            _make_case("good", [{"eval_key": "status", "operator": "equals", "value": "ok"}]),
        ]
        wf.set_output_conditions("step_a", cases, default="fallback")

        wf.add_conditional_transition(
            "step_a",
            {
                "good": "step_good",
                "stale_val": "step_stale",
                "fallback": "step_stale",
                "default": "step_stale",
            },
        )

        # BlockResult has no exit_handle (None), so output_conditions will be
        # evaluated.  Stale metadata is present but no longer consulted.
        state = _initial_state().model_copy(
            update={
                "results": {
                    "step_a": BlockResult(
                        output=json.dumps({"status": "ok"}),
                    )
                },
                "metadata": {"step_a_decision": "stale_val"},
            }
        )

        next_id = wf._resolve_next("step_a", state)

        # output_conditions must win: exit_handle should be "good"
        assert state.results["step_a"].exit_handle == "good"
        assert next_id == "step_good"


# ===== Parameterized operator coverage via output_conditions (CRITICAL #1) =====


class TestAllOperatorsViaOutputConditions:
    """Verify every one of the 15+ operators works end-to-end through
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
        wf = Workflow(name="op_test")

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
