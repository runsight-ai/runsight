"""Gate exit-port routing integration coverage."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from conftest import block_output_from_state
from runsight_core.blocks.base import BaseBlock
from runsight_core.blocks.gate import GateBlock
from runsight_core.blocks.loop import LoopBlock
from runsight_core.primitives import Soul
from runsight_core.runner import ExecutionResult, RunsightTeamRunner
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.workflow import Workflow

# ---------------------------------------------------------------------------
# Helpers: mock runner and blocks
# ---------------------------------------------------------------------------


def _mock_runner(output: str, cost: float = 0.01, tokens: int = 100) -> RunsightTeamRunner:
    runner = MagicMock(spec=RunsightTeamRunner)
    runner.model_name = "gpt-4o"
    runner.execute = AsyncMock(
        return_value=ExecutionResult(
            task_id="test", soul_id="test", output=output, cost_usd=cost, total_tokens=tokens
        )
    )
    return runner


def _make_soul(soul_id: str = "test_soul") -> Soul:
    return Soul(id=soul_id, kind="soul", name="Test", role="Test", system_prompt="Test prompt")


class StubBlock(BaseBlock):
    """Minimal block that stores a fixed output."""

    def __init__(self, block_id: str, output: str = "done"):
        super().__init__(block_id)
        self._output = output

    async def execute(self, ctx):
        state = ctx.state_snapshot
        next_state = state.model_copy(
            update={
                "results": {
                    **state.results,
                    self.block_id: BlockResult(output=self._output),
                },
            }
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


def _fresh_state(**kwargs) -> WorkflowState:
    return WorkflowState(**kwargs)


class TestGateStandaloneRoutingIntegration:
    """Gate block used standalone with conditional_transitions."""

    @pytest.mark.asyncio
    async def test_gate_pass_routes_to_success_block(self):
        """Gate returns exit_handle='pass' -> conditional_transition routes to on_pass."""
        runner = _mock_runner("PASS")
        gate = GateBlock(
            block_id="quality_gate",
            gate_soul=_make_soul("evaluator"),
            eval_key="draft",
            runner=runner,
        )
        on_pass = StubBlock("on_pass", output="success_path")
        on_fail = StubBlock("on_fail", output="failure_path")

        wf = Workflow(name="gate_standalone_pass")
        wf.add_block(StubBlock("draft", output="Some content"))
        wf.add_block(gate)
        wf.add_block(on_pass)
        wf.add_block(on_fail)
        wf.set_entry("draft")

        wf.add_transition("draft", "quality_gate")
        wf.add_conditional_transition(
            "quality_gate",
            {"pass": "on_pass", "fail": "on_fail", "default": "on_fail"},
        )
        wf.add_transition("on_pass", None)
        wf.add_transition("on_fail", None)

        state = _fresh_state()
        # Pre-seed draft result since gate reads eval_key from results
        state = state.model_copy(update={"results": {"draft": BlockResult(output="Some content")}})

        final = await wf.run(state)

        assert final.results["quality_gate"].exit_handle == "pass"
        assert "on_pass" in final.results, "Should route to on_pass via exit_handle='pass'"
        assert "on_fail" not in final.results, "Should not route to on_fail"

    @pytest.mark.asyncio
    async def test_gate_fail_routes_to_failure_block(self):
        """Gate returns exit_handle='fail' -> conditional_transition routes to on_fail."""
        runner = _mock_runner("FAIL: needs improvement")
        gate = GateBlock(
            block_id="quality_gate",
            gate_soul=_make_soul("evaluator"),
            eval_key="draft",
            runner=runner,
        )
        on_pass = StubBlock("on_pass", output="success_path")
        on_fail = StubBlock("on_fail", output="failure_path")

        wf = Workflow(name="gate_standalone_fail")
        wf.add_block(StubBlock("draft", output="Bad content"))
        wf.add_block(gate)
        wf.add_block(on_pass)
        wf.add_block(on_fail)
        wf.set_entry("draft")

        wf.add_transition("draft", "quality_gate")
        wf.add_conditional_transition(
            "quality_gate",
            {"pass": "on_pass", "fail": "on_fail", "default": "on_fail"},
        )
        wf.add_transition("on_pass", None)
        wf.add_transition("on_fail", None)

        state = _fresh_state()
        state = state.model_copy(update={"results": {"draft": BlockResult(output="Bad content")}})

        final = await wf.run(state)

        assert final.results["quality_gate"].exit_handle == "fail"
        assert "on_fail" in final.results, "Should route to on_fail via exit_handle='fail'"
        assert "on_pass" not in final.results, "Should not route to on_pass"

    @pytest.mark.asyncio
    async def test_gate_standalone_default_fallback(self):
        """If gate exit_handle is somehow not in the map, 'default' is used."""
        wf = Workflow(name="gate_default_fallback")

        gate = ExitHandleBlock("gate", exit_handle="unknown_value", output="gate out")
        fallback = StubBlock("fallback", output="default_route")

        wf.add_block(gate)
        wf.add_block(fallback)
        wf.set_entry("gate")

        wf.add_conditional_transition(
            "gate",
            {"pass": "fallback", "fail": "fallback", "default": "fallback"},
        )
        wf.add_transition("fallback", None)

        final = await wf.run(_fresh_state())

        assert "fallback" in final.results


# ==============================================================================
# Gate-in-loop routing works through workflow execution
# ==============================================================================


class TestGateInLoopRoutingIntegration:
    """Gate inside a LoopBlock with break_on_exit / retry_on_exit."""

    @pytest.mark.asyncio
    async def test_gate_pass_triggers_break_on_exit(self):
        """Gate inside loop: exit_handle='pass' matches break_on_exit -> loop exits early."""
        runner = _mock_runner("PASS")
        gate = GateBlock(
            block_id="gate",
            gate_soul=_make_soul("evaluator"),
            eval_key="writer",
            runner=runner,
        )
        writer = StubBlock("writer", output="Draft content")

        loop = LoopBlock(
            block_id="review_loop",
            inner_block_refs=["writer", "gate"],
            max_rounds=3,
            break_on_exit="pass",
        )

        wf = Workflow(name="gate_in_loop_break")
        wf.add_block(writer)
        wf.add_block(gate)
        wf.add_block(loop)
        wf.add_block(StubBlock("done", output="finished"))
        wf.set_entry("review_loop")
        wf.add_transition("review_loop", "done")
        wf.add_transition("done", None)

        state = _fresh_state()

        final = await wf.run(state)

        # Gate passed -> loop should have broken early
        loop_meta = final.shared_memory.get("__loop__review_loop", {})
        assert loop_meta.get("broke_early") is True, (
            "Loop should break early when gate exit_handle='pass' matches break_on_exit"
        )
        assert loop_meta.get("rounds_completed") == 1, (
            "Loop should complete only 1 round since gate passed immediately"
        )
        assert final.results["gate"].exit_handle == "pass"

    @pytest.mark.asyncio
    async def test_gate_fail_triggers_retry_on_exit(self):
        """Gate inside loop: exit_handle='fail' matches retry_on_exit -> loop retries.
        After max_rounds, loop exits normally (no break)."""
        runner = _mock_runner("FAIL: needs work")
        gate = GateBlock(
            block_id="gate",
            gate_soul=_make_soul("evaluator"),
            eval_key="writer",
            runner=runner,
        )
        writer = StubBlock("writer", output="Draft content")

        loop = LoopBlock(
            block_id="review_loop",
            inner_block_refs=["writer", "gate"],
            max_rounds=2,
            retry_on_exit="fail",
            break_on_exit="pass",
        )

        wf = Workflow(name="gate_in_loop_retry")
        wf.add_block(writer)
        wf.add_block(gate)
        wf.add_block(loop)
        wf.add_block(StubBlock("done", output="finished"))
        wf.set_entry("review_loop")
        wf.add_transition("review_loop", "done")
        wf.add_transition("done", None)

        state = _fresh_state()

        final = await wf.run(state)

        # Gate always fails -> retry_on_exit triggers retry -> exhausts max_rounds
        loop_meta = final.shared_memory.get("__loop__review_loop", {})
        assert loop_meta.get("rounds_completed") == 2, (
            "Loop should exhaust max_rounds when gate always fails and retry_on_exit='fail'"
        )
        assert loop_meta.get("broke_early") is False, (
            "Loop should not break early when gate always fails"
        )

    @pytest.mark.asyncio
    async def test_gate_fail_then_pass_in_loop(self):
        """Gate fails first round (retry), passes second round (break).

        Uses a runner that returns FAIL on first call, PASS on second.
        """
        call_count = {"n": 0}

        async def _side_effect(instruction, context, soul, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return ExecutionResult(
                    task_id="test",
                    soul_id="test",
                    output="FAIL: first attempt bad",
                    cost_usd=0.01,
                    total_tokens=100,
                )
            return ExecutionResult(
                task_id="test",
                soul_id="test",
                output="PASS",
                cost_usd=0.01,
                total_tokens=100,
            )

        runner = MagicMock(spec=RunsightTeamRunner)
        runner.model_name = "gpt-4o"
        runner.execute = AsyncMock(side_effect=_side_effect)

        gate = GateBlock(
            block_id="gate",
            gate_soul=_make_soul("evaluator"),
            eval_key="writer",
            runner=runner,
        )
        writer = StubBlock("writer", output="Draft content")

        loop = LoopBlock(
            block_id="review_loop",
            inner_block_refs=["writer", "gate"],
            max_rounds=5,
            retry_on_exit="fail",
            break_on_exit="pass",
        )

        wf = Workflow(name="gate_in_loop_fail_then_pass")
        wf.add_block(writer)
        wf.add_block(gate)
        wf.add_block(loop)
        wf.add_block(StubBlock("done", output="finished"))
        wf.set_entry("review_loop")
        wf.add_transition("review_loop", "done")
        wf.add_transition("done", None)

        state = _fresh_state()

        final = await wf.run(state)

        loop_meta = final.shared_memory.get("__loop__review_loop", {})
        assert loop_meta.get("broke_early") is True, (
            "Loop should break early on second round when gate passes"
        )
        assert loop_meta.get("rounds_completed") == 2, (
            "Loop should complete exactly 2 rounds (fail, then pass)"
        )
        assert final.results["gate"].exit_handle == "pass"

    @pytest.mark.asyncio
    async def test_loop_without_break_or_retry_falls_through_to_break_condition(self):
        """Loop with gate but NO break_on_exit/retry_on_exit: the gate exit_handle
        is ignored by the loop, and it falls through to break_condition or max_rounds."""
        runner = _mock_runner("PASS")
        gate = GateBlock(
            block_id="gate",
            gate_soul=_make_soul("evaluator"),
            eval_key="writer",
            runner=runner,
        )
        writer = StubBlock("writer", output="Draft content")

        # No break_on_exit, no retry_on_exit -> loop runs all max_rounds
        loop = LoopBlock(
            block_id="review_loop",
            inner_block_refs=["writer", "gate"],
            max_rounds=2,
        )

        wf = Workflow(name="gate_in_loop_no_exit_control")
        wf.add_block(writer)
        wf.add_block(gate)
        wf.add_block(loop)
        wf.set_entry("review_loop")
        wf.add_transition("review_loop", None)

        state = _fresh_state()

        final = await wf.run(state)

        loop_meta = final.shared_memory.get("__loop__review_loop", {})
        assert loop_meta.get("rounds_completed") == 2, (
            "Loop should run all max_rounds when no break_on_exit/retry_on_exit"
        )
        assert loop_meta.get("break_reason") == "max_rounds reached"


# ==============================================================================
# Output conditions feed exit handles and conditional transitions
# ==============================================================================
