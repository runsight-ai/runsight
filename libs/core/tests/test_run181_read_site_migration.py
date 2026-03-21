"""
Failing tests for RUN-181: Trivial read site migrations (.output extraction).

Strategy:
  Five read sites currently consume BlockResult objects via str() wrapping
  or implicit __str__() conversion instead of explicit .output extraction.

  To prove the code is NOT using .output, we patch BlockResult.__str__ to
  return a sentinel value ("PATCHED_STR") that differs from the actual
  .output value ("REAL_OUTPUT"). If the code path uses str(block_result)
  or relies on __str__(), it will see "PATCHED_STR". If it uses .output,
  it will see "REAL_OUTPUT".

  Each test asserts the code produces results consistent with "REAL_OUTPUT",
  which will FAIL until the Green agent replaces str() / implicit __str__
  with explicit .output extraction.

Read sites under test:
  1. workflow.py — evaluate_output_conditions receives state.results.get(block_id, "")
  2. implementations.py — LoopBlock break condition: state.results.get(last_ref)
  3. implementations.py — SynthesizeBlock: state.results[bid] in f-string
  4. implementations.py — GateBlock: str(state.results[self.eval_key])
  5. implementations.py — FileWriterBlock: str(state.results[self.content_key])
"""

from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from runsight_core.conditions.engine import (
    Case,
    Condition,
    ConditionGroup,
)
from runsight_core.primitives import Soul, Task
from runsight_core.runner import ExecutionResult
from runsight_core.state import BlockResult, WorkflowState


# ==============================================================================
# Helpers
# ==============================================================================

REAL_OUTPUT = "REAL_OUTPUT"
PATCHED_STR = "PATCHED_STR"


def _make_state(**overrides) -> WorkflowState:
    """Create a minimal WorkflowState with sensible defaults."""
    defaults: Dict[str, Any] = {
        "current_task": Task(id="t1", instruction="do something"),
        "results": {},
        "execution_log": [],
        "shared_memory": {},
        "metadata": {},
        "total_cost_usd": 0.0,
        "total_tokens": 0,
    }
    defaults.update(overrides)
    return WorkflowState(**defaults)


def _make_soul(name: str = "test_soul") -> Soul:
    return Soul(id=name, role="tester", system_prompt="You are a test agent.")


def _make_runner(output: str = "PASS") -> MagicMock:
    runner = MagicMock()
    runner.execute_task = AsyncMock(
        return_value=ExecutionResult(
            task_id="test_task",
            soul_id="test_soul",
            output=output,
            cost_usd=0.0,
            total_tokens=0,
        )
    )
    return runner


# ==============================================================================
# Test 1: workflow.py — evaluate_output_conditions receives raw BlockResult
# ==============================================================================


class TestEvaluateOutputConditionsReadSite:
    """
    workflow.py line 343-344:
        evaluate_output_conditions(cases, state.results.get(current_block_id, ""), default)

    The second argument is state.results.get(block_id, ""), which returns a
    BlockResult object (not a string). evaluate_output_conditions should
    receive the .output string, not the BlockResult object.

    We test this by patching __str__ and checking that the condition engine
    sees the real .output value ("REAL_OUTPUT"), not the __str__ sentinel.
    """

    @pytest.mark.asyncio
    async def test_output_conditions_uses_output_not_str(self):
        """evaluate_output_conditions should receive .output, not str(BlockResult)."""
        from runsight_core.workflow import Workflow
        from runsight_core.blocks.base import BaseBlock

        # Set up a condition that matches "REAL_OUTPUT" via contains
        cases = [
            Case(
                case_id="found_real",
                condition_group=ConditionGroup(
                    conditions=[
                        Condition(eval_key="result", operator="contains", value="REAL_OUTPUT"),
                    ],
                ),
            ),
        ]

        # Build a minimal block + workflow with output_conditions
        class StubBlock(BaseBlock):
            async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
                return state.model_copy(
                    update={
                        "results": {
                            **state.results,
                            self.block_id: BlockResult(output=REAL_OUTPUT),
                        },
                    }
                )

        wf = Workflow(name="test_wf")
        wf.add_block(StubBlock("b1"))
        wf.add_transition("b1", None)
        wf.set_entry("b1")
        wf.set_output_conditions("b1", cases, default="fallback")

        state = _make_state()

        with patch.object(BlockResult, "__str__", return_value=PATCHED_STR):
            final_state = await wf.run(state)

        # If workflow._resolve_next passed .output to evaluate_output_conditions,
        # the "contains REAL_OUTPUT" condition would match and decision = "found_real".
        # If it passed the BlockResult (and str() was called), it gets "PATCHED_STR"
        # and the condition won't match, falling through to "fallback".
        assert final_state.metadata.get("b1_decision") == "found_real", (
            "evaluate_output_conditions received str(BlockResult) instead of .output"
        )


# ==============================================================================
# Test 2: LoopBlock break condition receives raw BlockResult
# ==============================================================================


class TestLoopBlockBreakConditionReadSite:
    """
    implementations.py line 364:
        last_output = state.results.get(last_ref)

    The break condition evaluator receives last_output which is a BlockResult.
    It should receive .output (a string) instead.
    """

    @pytest.mark.asyncio
    async def test_loop_break_condition_uses_output_not_str(self):
        """LoopBlock break condition should evaluate against .output, not BlockResult."""
        from runsight_core import LoopBlock
        from runsight_core.blocks.base import BaseBlock

        class InnerBlock(BaseBlock):
            async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
                return state.model_copy(
                    update={
                        "results": {
                            **state.results,
                            self.block_id: BlockResult(output=REAL_OUTPUT),
                        },
                    }
                )

        inner = InnerBlock("inner1")

        # Break condition: contains "REAL_OUTPUT" — should match on .output
        break_cond = Condition(eval_key="result", operator="contains", value="REAL_OUTPUT")

        loop = LoopBlock(
            block_id="loop1",
            inner_block_refs=["inner1"],
            max_rounds=5,
            break_condition=break_cond,
        )

        state = _make_state()
        blocks = {"inner1": inner, "loop1": loop}

        with patch.object(BlockResult, "__str__", return_value=PATCHED_STR):
            result_state = await loop.execute(state, blocks=blocks)

        # If break condition used .output, it matches "REAL_OUTPUT" on round 1
        # and loop exits early after 1 round.
        # If it used str(BlockResult) = "PATCHED_STR", the condition checking for
        # "REAL_OUTPUT" won't match and the loop runs all 5 rounds.
        loop_meta = result_state.shared_memory.get("__loop__loop1", {})
        assert loop_meta.get("broke_early") is True, (
            "LoopBlock break condition evaluated str(BlockResult) instead of .output"
        )
        assert loop_meta.get("rounds_completed") == 1


# ==============================================================================
# Test 3: SynthesizeBlock reads raw BlockResult in f-string
# ==============================================================================


class TestSynthesizeBlockReadSite:
    """
    implementations.py line 214-215:
        combined_outputs = "\\n\\n".join(
            [f"=== Output from {bid} ===\\n{state.results[bid]}" for bid in ...]
        )

    The f-string uses state.results[bid] which calls __str__() on BlockResult.
    It should use state.results[bid].output instead.
    """

    @pytest.mark.asyncio
    async def test_synthesize_block_uses_output_not_str(self):
        """SynthesizeBlock prompt should contain .output text, not __str__ value."""
        from runsight_core import SynthesizeBlock

        runner = _make_runner(output="synthesized result")
        soul = _make_soul()

        synth = SynthesizeBlock(
            block_id="synth1",
            input_block_ids=["input_a"],
            synthesizer_soul=soul,
            runner=runner,
        )

        state = _make_state(
            results={"input_a": BlockResult(output=REAL_OUTPUT)},
        )

        with patch.object(BlockResult, "__str__", return_value=PATCHED_STR):
            await synth.execute(state)

        # Check what prompt was sent to the runner
        call_args = runner.execute_task.call_args
        task_sent: Task = call_args[0][0]

        # The instruction should contain the actual .output value
        assert REAL_OUTPUT in task_sent.instruction, (
            f"SynthesizeBlock prompt used __str__() ({PATCHED_STR!r}) "
            f"instead of .output ({REAL_OUTPUT!r})"
        )
        assert PATCHED_STR not in task_sent.instruction, (
            "SynthesizeBlock prompt contains patched __str__ value, "
            "proving it uses implicit string conversion instead of .output"
        )


# ==============================================================================
# Test 4: GateBlock reads raw BlockResult via str()
# ==============================================================================


class TestGateBlockReadSite:
    """
    implementations.py line 1101:
        content = str(state.results[self.eval_key])

    GateBlock wraps the result with str(), which invokes __str__() on
    BlockResult. It should use state.results[self.eval_key].output instead.
    """

    @pytest.mark.asyncio
    async def test_gate_block_uses_output_not_str(self):
        """GateBlock should evaluate .output content, not str(BlockResult)."""
        from runsight_core import GateBlock

        runner = _make_runner(output="PASS")
        soul = _make_soul()

        gate = GateBlock(
            block_id="gate1",
            gate_soul=soul,
            eval_key="source_block",
            runner=runner,
        )

        state = _make_state(
            results={"source_block": BlockResult(output=REAL_OUTPUT)},
        )

        with patch.object(BlockResult, "__str__", return_value=PATCHED_STR):
            await gate.execute(state)

        # Check the task instruction sent to the runner
        call_args = runner.execute_task.call_args
        task_sent: Task = call_args[0][0]

        # The instruction should contain .output value, not __str__ value
        assert REAL_OUTPUT in task_sent.instruction, (
            f"GateBlock prompt used str(BlockResult) ({PATCHED_STR!r}) "
            f"instead of .output ({REAL_OUTPUT!r})"
        )
        assert PATCHED_STR not in task_sent.instruction, (
            "GateBlock prompt contains patched __str__ value, "
            "proving it uses str() instead of .output"
        )


# ==============================================================================
# Test 5: FileWriterBlock reads raw BlockResult via str()
# ==============================================================================


class TestFileWriterBlockReadSite:
    """
    implementations.py line 1182-1183:
        raw_content = state.results[self.content_key]
        content = str(raw_content)

    FileWriterBlock wraps with str(), which invokes __str__() on BlockResult.
    It should use state.results[self.content_key].output instead.
    """

    @pytest.mark.asyncio
    async def test_file_writer_uses_output_not_str(self, tmp_path):
        """FileWriterBlock should write .output content, not str(BlockResult)."""
        from runsight_core import FileWriterBlock

        output_file = tmp_path / "output.txt"

        writer = FileWriterBlock(
            block_id="writer1",
            output_path=str(output_file),
            content_key="source_block",
        )

        state = _make_state(
            results={"source_block": BlockResult(output=REAL_OUTPUT)},
        )

        with patch.object(BlockResult, "__str__", return_value=PATCHED_STR):
            await writer.execute(state)

        written_content = output_file.read_text(encoding="utf-8")

        # The file should contain .output, not the patched __str__ value
        assert written_content == REAL_OUTPUT, (
            f"FileWriterBlock wrote str(BlockResult) ({PATCHED_STR!r}) "
            f"instead of .output ({REAL_OUTPUT!r}). "
            f"Actual content: {written_content!r}"
        )
