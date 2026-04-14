"""
E2E tests for RUN-684: Exit handle coverage for all block types in loops.

Verifies that every block type correctly propagates exit_handle through
LoopBlock's break_on_exit mechanism. Covers:

1. GateBlock exits loop (regression guard)
2. WorkflowBlock exits loop on child completion
3. CodeBlock exits loop on success (RUN-680 feature)
4. CodeBlock exits loop on error (existing behavior)
5. LinearBlock exits loop via exit_conditions (RUN-681 feature)
6. LinearBlock with regex exit_conditions
7. SynthesizeBlock has no exit_handle (regression guard — loop runs to max_rounds)
8. DispatchBlock inside LoopBlock (regression guard — no break on combined result)
9. exit_conditions do NOT override explicit exit_handle (GateBlock pattern)
"""

from __future__ import annotations

import textwrap
from dataclasses import dataclass
from typing import Optional
from unittest.mock import AsyncMock

import pytest
from runsight_core.blocks.base import BaseBlock
from runsight_core.blocks.code import CodeBlock
from runsight_core.blocks.dispatch import DispatchBlock, DispatchBranch
from runsight_core.blocks.loop import LoopBlock
from runsight_core.blocks.synthesize import SynthesizeBlock
from runsight_core.blocks.workflow_block import WorkflowBlock
from runsight_core.primitives import Soul
from runsight_core.runner import ExecutionResult
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.workflow import BlockExecutionContext, Workflow, execute_block

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


@dataclass
class ExitCondition:
    exit_handle: str
    contains: Optional[str] = None
    regex: Optional[str] = None


def _make_state(**overrides) -> WorkflowState:
    defaults: dict = {
        "results": {},
        "metadata": {},
        "shared_memory": {},
        "execution_log": [],
    }
    defaults.update(overrides)
    return WorkflowState(**defaults)


def _make_ctx(
    blocks: dict[str, BaseBlock],
    workflow_name: str = "test_wf",
) -> BlockExecutionContext:
    return BlockExecutionContext(
        workflow_name=workflow_name,
        blocks=blocks,
        call_stack=[],
        workflow_registry=None,
        observer=None,
    )


def _make_soul(soul_id: str = "test_soul") -> Soul:
    return Soul(
        id=soul_id,
        kind="soul",
        name="Tester",
        role="Tester",
        system_prompt="You are a test agent.",
    )


def _make_mock_runner(output: str = "mock output") -> AsyncMock:
    """Create a mock RunsightTeamRunner that returns a fixed ExecutionResult."""
    runner = AsyncMock()
    runner.model_name = "gpt-4o-mini"
    runner.execute_task = AsyncMock(
        return_value=ExecutionResult(
            task_id="mock_task",
            soul_id="test_soul",
            output=output,
            cost_usd=0.0,
            total_tokens=0,
        )
    )
    runner._build_prompt = lambda task: task.instruction or ""
    return runner


def _make_workflow_with_loop(
    name: str,
    loop: LoopBlock,
    *inner_blocks: BaseBlock,
) -> Workflow:
    """Create a workflow with a LoopBlock as entry + all inner blocks registered."""
    wf = Workflow(name)
    wf.add_block(loop)
    for block in inner_blocks:
        wf.add_block(block)
    wf.set_entry(loop.block_id)
    wf.add_transition(loop.block_id, None)
    return wf


# ---------------------------------------------------------------------------
# Simple test block helpers
# ---------------------------------------------------------------------------


class OutputBlock(BaseBlock):
    """Block that writes a fixed output string with no exit_handle."""

    def __init__(self, block_id: str, output_text: str) -> None:
        super().__init__(block_id)
        self.output_text = output_text

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        return state.model_copy(
            update={
                "results": {
                    **state.results,
                    self.block_id: BlockResult(output=self.output_text),
                }
            }
        )


class ExplicitExitBlock(BaseBlock):
    """Block that sets exit_handle explicitly."""

    def __init__(self, block_id: str, output_text: str, exit_handle: str) -> None:
        super().__init__(block_id)
        self.output_text = output_text
        self._exit_handle = exit_handle

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        return state.model_copy(
            update={
                "results": {
                    **state.results,
                    self.block_id: BlockResult(
                        output=self.output_text,
                        exit_handle=self._exit_handle,
                    ),
                }
            }
        )


class RoundAwareOutputBlock(BaseBlock):
    """Block that emits different output based on loop round number."""

    def __init__(
        self, block_id: str, trigger_round: int = 2, trigger_text: str = "APPROVED"
    ) -> None:
        super().__init__(block_id)
        self.trigger_round = trigger_round
        self.trigger_text = trigger_text

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        round_num = 0
        for key, value in state.shared_memory.items():
            if key.endswith("_round"):
                round_num = value
                break
        if round_num >= self.trigger_round:
            output = f"Review result: {self.trigger_text}"
        else:
            output = "Review result: NEEDS_REVISION"
        return state.model_copy(
            update={
                "results": {
                    **state.results,
                    self.block_id: BlockResult(output=output),
                }
            }
        )


# ===========================================================================
# Scenario 1: GateBlock exits loop (regression guard)
# ===========================================================================


class TestScenario1GateBlockExitsLoop:
    @pytest.mark.asyncio
    async def test_gate_pass_breaks_loop(self):
        """GateBlock returning exit_handle='pass' should break the loop when
        break_on_exit='pass' is configured.

        Uses a mock runner so the GateBlock always evaluates 'PASS'.
        """
        soul = _make_soul("gate_soul")
        runner = _make_mock_runner("PASS")

        from runsight_core.blocks.gate import GateBlock

        # Prerequisite: a block whose output the gate evaluates
        writer = OutputBlock("writer", "some content to evaluate")

        gate = GateBlock(
            block_id="quality_gate",
            gate_soul=soul,
            eval_key="writer",
            runner=runner,
        )

        loop = LoopBlock(
            "gate_loop",
            inner_block_refs=["writer", "quality_gate"],
            max_rounds=5,
            break_on_exit="pass",
        )

        wf = _make_workflow_with_loop("gate_loop_wf", loop, writer, gate)
        state = _make_state()
        final = await wf.run(state)

        loop_meta = final.shared_memory["__loop__gate_loop"]
        assert loop_meta["broke_early"] is True
        assert loop_meta["rounds_completed"] == 1
        assert "exit_handle" in loop_meta["break_reason"]

        gate_br = final.results["quality_gate"]
        assert isinstance(gate_br, BlockResult)
        assert gate_br.exit_handle == "pass"

    @pytest.mark.asyncio
    async def test_gate_fail_does_not_break_loop(self):
        """GateBlock returning exit_handle='fail' should NOT break a loop
        configured with break_on_exit='pass'."""
        soul = _make_soul("gate_soul")
        runner = _make_mock_runner("FAIL: needs improvement")

        from runsight_core.blocks.gate import GateBlock

        writer = OutputBlock("writer", "some content")
        gate = GateBlock(
            block_id="quality_gate",
            gate_soul=soul,
            eval_key="writer",
            runner=runner,
        )

        loop = LoopBlock(
            "gate_loop",
            inner_block_refs=["writer", "quality_gate"],
            max_rounds=2,
            break_on_exit="pass",
        )

        wf = _make_workflow_with_loop("gate_fail_wf", loop, writer, gate)
        state = _make_state()
        final = await wf.run(state)

        loop_meta = final.shared_memory["__loop__gate_loop"]
        assert loop_meta["broke_early"] is False
        assert loop_meta["rounds_completed"] == 2

        gate_br = final.results["quality_gate"]
        assert gate_br.exit_handle == "fail"


# ===========================================================================
# Scenario 2: WorkflowBlock exits loop
# ===========================================================================


class TestScenario2WorkflowBlockExitsLoop:
    @pytest.mark.asyncio
    async def test_workflow_block_completed_breaks_loop(self):
        """WorkflowBlock always returns exit_handle='completed' on success.
        LoopBlock with break_on_exit='completed' should break immediately."""
        child_step = OutputBlock("child_step", "child output")
        child_wf = Workflow("child_wf")
        child_wf.add_block(child_step)
        child_wf.set_entry("child_step")
        child_wf.add_transition("child_step", None)

        wf_block = WorkflowBlock(
            block_id="sub_workflow",
            child_workflow=child_wf,
            inputs={},
            outputs={},
        )

        loop = LoopBlock(
            "wf_loop",
            inner_block_refs=["sub_workflow"],
            max_rounds=5,
            break_on_exit="completed",
        )

        wf = _make_workflow_with_loop("wf_loop_test", loop, wf_block)
        state = _make_state()
        final = await wf.run(state)

        loop_meta = final.shared_memory["__loop__wf_loop"]
        assert loop_meta["broke_early"] is True
        assert loop_meta["rounds_completed"] == 1
        assert "exit_handle" in loop_meta["break_reason"]

        wf_br = final.results["sub_workflow"]
        assert isinstance(wf_br, BlockResult)
        assert wf_br.exit_handle == "completed"


# ===========================================================================
# Scenario 3: CodeBlock exits loop on success (RUN-680 feature)
# ===========================================================================


class TestScenario3CodeBlockExitsLoopOnSuccess:
    @pytest.mark.asyncio
    async def test_codeblock_exit_handle_done_breaks_loop(self):
        """CodeBlock returning {"exit_handle": "done", "result": "..."} should
        break a loop with break_on_exit='done'."""
        code = textwrap.dedent("""\
def main(data):
    return {"exit_handle": "done", "result": "computed value"}
""")
        code_block = CodeBlock("code_step", code)

        loop = LoopBlock(
            "code_loop",
            inner_block_refs=["code_step"],
            max_rounds=5,
            break_on_exit="done",
        )

        wf = _make_workflow_with_loop("code_loop_wf", loop, code_block)
        state = _make_state()
        final = await wf.run(state)

        loop_meta = final.shared_memory["__loop__code_loop"]
        assert loop_meta["broke_early"] is True
        assert loop_meta["rounds_completed"] == 1

        code_br = final.results["code_step"]
        assert isinstance(code_br, BlockResult)
        assert code_br.exit_handle == "done"

    @pytest.mark.asyncio
    async def test_codeblock_no_exit_handle_loop_runs_to_max(self):
        """CodeBlock returning dict without exit_handle key should NOT break the loop."""
        code = textwrap.dedent("""\
def main(data):
    return {"value": 42}
""")
        code_block = CodeBlock("code_step", code)

        loop = LoopBlock(
            "code_loop",
            inner_block_refs=["code_step"],
            max_rounds=3,
            break_on_exit="done",
        )

        wf = _make_workflow_with_loop("code_no_exit_wf", loop, code_block)
        state = _make_state()
        final = await wf.run(state)

        loop_meta = final.shared_memory["__loop__code_loop"]
        assert loop_meta["broke_early"] is False
        assert loop_meta["rounds_completed"] == 3


# ===========================================================================
# Scenario 4: CodeBlock exits loop on error (existing behavior)
# ===========================================================================


class TestScenario4CodeBlockExitsLoopOnError:
    @pytest.mark.asyncio
    async def test_codeblock_error_exit_handle_breaks_loop(self):
        """CodeBlock that fails (non-zero exit) produces exit_handle='error'.
        LoopBlock with break_on_exit='error' should break."""
        code = textwrap.dedent("""\
def main(data):
    raise RuntimeError("intentional failure")
""")
        code_block = CodeBlock("error_code", code)

        loop = LoopBlock(
            "error_loop",
            inner_block_refs=["error_code"],
            max_rounds=5,
            break_on_exit="error",
        )

        wf = _make_workflow_with_loop("error_loop_wf", loop, code_block)
        state = _make_state()
        final = await wf.run(state)

        loop_meta = final.shared_memory["__loop__error_loop"]
        assert loop_meta["broke_early"] is True
        assert loop_meta["rounds_completed"] == 1

        code_br = final.results["error_code"]
        assert isinstance(code_br, BlockResult)
        assert code_br.exit_handle == "error"
        assert "Error:" in code_br.output


# ===========================================================================
# Scenario 5: Block with exit_conditions (contains) exits loop (RUN-681)
# ===========================================================================


class TestScenario5ExitConditionsContains:
    @pytest.mark.asyncio
    async def test_exit_conditions_contains_breaks_loop(self):
        """A block with exit_conditions [{contains: "APPROVED", exit_handle: "approved"}]
        that outputs "APPROVED" on round 2 should break the loop.

        Uses RoundAwareOutputBlock (lightweight substitute for a LinearBlock
        requiring LLM) to test the exit_conditions mechanism via execute_block.
        """
        critic = RoundAwareOutputBlock("critic", trigger_round=2, trigger_text="APPROVED")
        critic.exit_conditions = [
            ExitCondition(contains="APPROVED", exit_handle="approved"),
        ]

        loop = LoopBlock(
            "cond_loop",
            inner_block_refs=["critic"],
            max_rounds=5,
            break_on_exit="approved",
        )

        wf = _make_workflow_with_loop("cond_loop_wf", loop, critic)
        state = _make_state()
        final = await wf.run(state)

        loop_meta = final.shared_memory["__loop__cond_loop"]
        assert loop_meta["broke_early"] is True
        assert loop_meta["rounds_completed"] == 2

        critic_br = final.results["critic"]
        assert isinstance(critic_br, BlockResult)
        assert critic_br.exit_handle == "approved"


# ===========================================================================
# Scenario 6: Block with regex exit_conditions exits loop
# ===========================================================================


class TestScenario6ExitConditionsRegex:
    @pytest.mark.asyncio
    async def test_exit_conditions_regex_breaks_loop(self):
        """exit_conditions with regex pattern that matches on round 2 should
        break the loop."""
        # Use GRADE_A as the trigger text — the regex pattern matches GRADE_[AB]
        critic = RoundAwareOutputBlock(
            "validator", trigger_round=2, trigger_text="Score: 95 GRADE_A"
        )
        critic.exit_conditions = [
            ExitCondition(regex=r"GRADE_[AB]", exit_handle="high_grade"),
        ]

        loop = LoopBlock(
            "regex_loop",
            inner_block_refs=["validator"],
            max_rounds=5,
            break_on_exit="high_grade",
        )

        wf = _make_workflow_with_loop("regex_loop_wf", loop, critic)
        state = _make_state()
        final = await wf.run(state)

        loop_meta = final.shared_memory["__loop__regex_loop"]
        assert loop_meta["broke_early"] is True
        assert loop_meta["rounds_completed"] == 2

        val_br = final.results["validator"]
        assert isinstance(val_br, BlockResult)
        assert val_br.exit_handle == "high_grade"

    @pytest.mark.asyncio
    async def test_exit_conditions_regex_no_match_runs_to_max(self):
        """When regex never matches, the loop should run to max_rounds."""
        block = OutputBlock("no_match", "Score: 30 GRADE_F")
        block.exit_conditions = [
            ExitCondition(regex=r"GRADE_[AB]", exit_handle="high_grade"),
        ]

        loop = LoopBlock(
            "regex_no_match_loop",
            inner_block_refs=["no_match"],
            max_rounds=3,
            break_on_exit="high_grade",
        )

        wf = _make_workflow_with_loop("regex_no_match_wf", loop, block)
        state = _make_state()
        final = await wf.run(state)

        loop_meta = final.shared_memory["__loop__regex_no_match_loop"]
        assert loop_meta["broke_early"] is False
        assert loop_meta["rounds_completed"] == 3


# ===========================================================================
# Scenario 7: SynthesizeBlock has no exit_handle (regression guard)
# ===========================================================================


class TestScenario7SynthesizeBlockNoExitHandle:
    @pytest.mark.asyncio
    async def test_synthesize_block_does_not_set_exit_handle(self):
        """SynthesizeBlock produces a BlockResult with exit_handle=None.
        When inside a LoopBlock with break_on_exit='done', the loop should
        run to max_rounds because SynthesizeBlock never sets an exit_handle.

        Uses a mock runner for the LLM call inside SynthesizeBlock.
        """
        soul = _make_soul("synth_soul")
        runner = _make_mock_runner("Synthesized output from inputs")

        # SynthesizeBlock needs input_block_ids whose results already exist.
        # We use a writer block that runs before the synthesize block in the loop.
        writer = OutputBlock("writer", "writer output for synthesis")

        synth = SynthesizeBlock(
            block_id="synthesizer",
            input_block_ids=["writer"],
            synthesizer_soul=soul,
            runner=runner,
        )

        loop = LoopBlock(
            "synth_loop",
            inner_block_refs=["writer", "synthesizer"],
            max_rounds=2,
            break_on_exit="done",
        )

        wf = _make_workflow_with_loop("synth_loop_wf", loop, writer, synth)
        state = _make_state()
        final = await wf.run(state)

        loop_meta = final.shared_memory["__loop__synth_loop"]
        assert loop_meta["broke_early"] is False
        assert loop_meta["rounds_completed"] == 2
        assert loop_meta["break_reason"] == "max_rounds reached"

        synth_br = final.results["synthesizer"]
        assert isinstance(synth_br, BlockResult)
        assert synth_br.exit_handle is None


# ===========================================================================
# Scenario 8: DispatchBlock inside LoopBlock (regression guard)
# ===========================================================================


class TestScenario8DispatchBlockInLoop:
    @pytest.mark.asyncio
    async def test_dispatch_block_no_exit_handle_on_combined_result(self):
        """DispatchBlock stores per-exit results with exit_handle set to exit_id,
        but the combined result at state.results[block_id] has exit_handle=None.
        So LoopBlock with break_on_exit should NOT break on the combined key.

        The loop should run to max_rounds.
        """
        soul_a = _make_soul("soul_a")
        soul_b = _make_soul("soul_b")
        runner = _make_mock_runner("branch output")

        dispatch = DispatchBlock(
            block_id="dispatcher",
            branches=[
                DispatchBranch(
                    exit_id="branch_a", label="Branch A", soul=soul_a, task_instruction="Do A"
                ),
                DispatchBranch(
                    exit_id="branch_b", label="Branch B", soul=soul_b, task_instruction="Do B"
                ),
            ],
            runner=runner,
        )

        loop = LoopBlock(
            "dispatch_loop",
            inner_block_refs=["dispatcher"],
            max_rounds=2,
            break_on_exit="done",
        )

        # DispatchBlock needs current_task to read context from
        from runsight_core.primitives import Task

        state = _make_state()
        state = state.model_copy(
            update={"current_task": Task(id="t1", instruction="test dispatch", context="ctx")}
        )

        wf = _make_workflow_with_loop("dispatch_loop_wf", loop, dispatch)
        final = await wf.run(state)

        loop_meta = final.shared_memory["__loop__dispatch_loop"]
        assert loop_meta["broke_early"] is False
        assert loop_meta["rounds_completed"] == 2

        # The combined result should have no exit_handle
        dispatch_br = final.results["dispatcher"]
        assert isinstance(dispatch_br, BlockResult)
        assert dispatch_br.exit_handle is None

    @pytest.mark.asyncio
    async def test_dispatch_per_exit_results_have_exit_handles(self):
        """Verify that per-exit results (dispatcher.branch_a) DO have exit_handle set
        to their exit_id, even though the combined result does not."""
        soul_a = _make_soul("soul_a")
        runner = _make_mock_runner("branch result")

        dispatch = DispatchBlock(
            block_id="dispatcher",
            branches=[
                DispatchBranch(exit_id="branch_a", label="A", soul=soul_a, task_instruction="Do A"),
            ],
            runner=runner,
        )

        from runsight_core.primitives import Task

        state = _make_state()
        state = state.model_copy(
            update={"current_task": Task(id="t1", instruction="test", context="ctx")}
        )

        final = await dispatch.execute(state)

        per_exit_br = final.results["dispatcher.branch_a"]
        assert isinstance(per_exit_br, BlockResult)
        assert per_exit_br.exit_handle == "branch_a"


# ===========================================================================
# Scenario 9: exit_conditions do NOT override explicit exit_handle
# ===========================================================================


class TestScenario9ExplicitExitHandlePrecedence:
    @pytest.mark.asyncio
    async def test_explicit_exit_handle_takes_precedence_over_exit_conditions(self):
        """A GateBlock-like block that sets exit_handle explicitly should NOT
        have it overridden by exit_conditions, even when the output matches.

        The block outputs 'PASS' which would match the exit_condition for
        'condition_match', but the explicit exit_handle='explicit_gate' takes
        precedence because execute_block() only evaluates exit_conditions when
        exit_handle is None.
        """
        block = ExplicitExitBlock("gate", output_text="Result: PASS", exit_handle="explicit_gate")
        block.exit_conditions = [
            ExitCondition(contains="PASS", exit_handle="condition_match"),
        ]

        ctx = _make_ctx({"gate": block})
        state = _make_state()

        result_state = await execute_block(block, state, ctx)

        br = result_state.results["gate"]
        assert isinstance(br, BlockResult)
        assert br.exit_handle == "explicit_gate"

    @pytest.mark.asyncio
    async def test_explicit_exit_handle_in_loop_breaks_on_explicit_value(self):
        """In a loop context, break_on_exit matches against the EXPLICIT exit_handle,
        not the exit_conditions value. So break_on_exit='explicit_gate' should trigger."""
        block = ExplicitExitBlock("gate", output_text="Result: PASS", exit_handle="explicit_gate")
        block.exit_conditions = [
            ExitCondition(contains="PASS", exit_handle="condition_match"),
        ]

        loop = LoopBlock(
            "precedence_loop",
            inner_block_refs=["gate"],
            max_rounds=5,
            break_on_exit="explicit_gate",
        )

        wf = _make_workflow_with_loop("precedence_wf", loop, block)
        state = _make_state()
        final = await wf.run(state)

        loop_meta = final.shared_memory["__loop__precedence_loop"]
        assert loop_meta["broke_early"] is True
        assert loop_meta["rounds_completed"] == 1

        gate_br = final.results["gate"]
        assert gate_br.exit_handle == "explicit_gate"

    @pytest.mark.asyncio
    async def test_exit_conditions_value_does_not_break_loop_when_explicit_set(self):
        """If break_on_exit='condition_match' but the block sets exit_handle explicitly
        to something else, the loop should NOT break on 'condition_match'."""
        block = ExplicitExitBlock("gate", output_text="Result: PASS", exit_handle="explicit_gate")
        block.exit_conditions = [
            ExitCondition(contains="PASS", exit_handle="condition_match"),
        ]

        loop = LoopBlock(
            "no_break_loop",
            inner_block_refs=["gate"],
            max_rounds=2,
            break_on_exit="condition_match",
        )

        wf = _make_workflow_with_loop("no_break_wf", loop, block)
        state = _make_state()
        final = await wf.run(state)

        # The explicit exit_handle is "explicit_gate", not "condition_match",
        # so break_on_exit="condition_match" should NOT trigger.
        loop_meta = final.shared_memory["__loop__no_break_loop"]
        assert loop_meta["broke_early"] is False
        assert loop_meta["rounds_completed"] == 2
