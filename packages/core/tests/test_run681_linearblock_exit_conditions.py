"""
Failing tests for RUN-681: LinearBlock exit_handle via exit conditions.

Block-level exit_conditions — evaluated in execute_block() after block.execute()
returns — should set exit_handle on BlockResult based on output content matching.

ExitCondition model:
    contains: Optional[str]  — substring match
    regex: Optional[str]     — regex match
    exit_handle: str         — value to set on match

Evaluation rules:
- Evaluated AFTER block.execute() returns, inside execute_block()
- Only applies when BlockResult.exit_handle is None (explicit takes precedence)
- First-match wins
- Both contains and regex on same condition: contains checked first

Tests cover:
- AC1: contains match → exit_handle set
- AC2: contains no match → exit_handle stays None
- AC3: regex match → exit_handle set
- AC4: LoopBlock integration: exit_conditions + break_on_exit triggers loop break
- AC5: Block with explicit exit_handle + exit_conditions → explicit takes precedence
- AC6: Multiple conditions, output matches second → second condition's exit_handle used
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pytest
from runsight_core.block_io import BlockOutput
from runsight_core.blocks.base import BaseBlock
from runsight_core.blocks.loop import LoopBlock
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.workflow import BlockExecutionContext, Workflow, execute_block

# ---------------------------------------------------------------------------
# Stand-in for the ExitCondition model (doesn't exist yet in source)
# ---------------------------------------------------------------------------


@dataclass
class ExitCondition:
    exit_handle: str
    contains: Optional[str] = None
    regex: Optional[str] = None


# ---------------------------------------------------------------------------
# Test block helpers
# ---------------------------------------------------------------------------


class OutputBlock(BaseBlock):
    """Block that writes a fixed output string to results."""

    def __init__(self, block_id: str, output_text: str) -> None:
        super().__init__(block_id)
        self.output_text = output_text

    async def execute(self, ctx):
        return BlockOutput(output=self.output_text)


class ExplicitExitBlock(BaseBlock):
    """Block that sets exit_handle explicitly in its own execute()."""

    def __init__(self, block_id: str, output_text: str, exit_handle: str) -> None:
        super().__init__(block_id)
        self.output_text = output_text
        self._exit_handle = exit_handle

    async def execute(self, ctx):
        return BlockOutput(
            output=self.output_text,
            exit_handle=self._exit_handle,
        )


class RoundAwareOutputBlock(BaseBlock):
    """Block that emits different output based on loop round, used for AC4."""

    def __init__(self, block_id: str) -> None:
        super().__init__(block_id)
        self.context_access = "all"

    async def execute(self, ctx):
        state = ctx.state_snapshot
        # LoopBlock stores round as "{loop_block_id}_round" in shared_memory
        round_num = 0
        for key, value in state.shared_memory.items():
            if key.endswith("_round"):
                round_num = value
                break
        # On round >= 2, output contains "APPROVED" to trigger exit_conditions
        if round_num >= 2:
            output = "Review result: APPROVED"
        else:
            output = "Review result: NEEDS_REVISION"
        return BlockOutput(output=output)


# ---------------------------------------------------------------------------
# Minimal context factory
# ---------------------------------------------------------------------------


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


def _make_state(**overrides) -> WorkflowState:
    defaults: dict = {
        "results": {},
        "metadata": {},
        "shared_memory": {},
        "execution_log": [],
    }
    defaults.update(overrides)
    return WorkflowState(**defaults)


# ===========================================================================
# AC1: contains match -> exit_handle set
# ===========================================================================


class TestAC1ContainsMatch:
    @pytest.mark.asyncio
    async def test_exit_conditions_contains_match_sets_exit_handle(self):
        """A block with exit_conditions [{contains: "PASS", exit_handle: "pass"}]
        and output containing "PASS" should have exit_handle=="pass" after
        execute_block() returns."""
        block = OutputBlock("checker", "Test result: PASS — all checks passed")
        block.exit_conditions = [
            ExitCondition(contains="PASS", exit_handle="pass"),
        ]

        ctx = _make_ctx({"checker": block})
        state = _make_state()

        result_state = await execute_block(block, state, ctx)

        br = result_state.results["checker"]
        assert isinstance(br, BlockResult)
        assert br.exit_handle == "pass"


# ===========================================================================
# AC2: contains no match -> exit_handle stays None
# ===========================================================================


class TestAC2ContainsNoMatch:
    @pytest.mark.asyncio
    async def test_exit_conditions_no_match_leaves_exit_handle_none(self):
        """When exit_conditions contains pattern is NOT found in output,
        exit_handle should remain None."""
        block = OutputBlock("checker", "Test result: FAIL — needs revision")
        block.exit_conditions = [
            ExitCondition(contains="PASS", exit_handle="pass"),
        ]

        ctx = _make_ctx({"checker": block})
        state = _make_state()

        result_state = await execute_block(block, state, ctx)

        br = result_state.results["checker"]
        assert isinstance(br, BlockResult)
        assert br.exit_handle is None


# ===========================================================================
# AC3: regex match -> exit_handle set
# ===========================================================================


class TestAC3RegexMatch:
    @pytest.mark.asyncio
    async def test_exit_conditions_regex_match_sets_exit_handle(self):
        """A block with exit_conditions using regex pattern that matches
        the output should set exit_handle accordingly."""
        block = OutputBlock("validator", "Score: 95/100 — GRADE_A")
        block.exit_conditions = [
            ExitCondition(regex=r"GRADE_[AB]", exit_handle="high_grade"),
        ]

        ctx = _make_ctx({"validator": block})
        state = _make_state()

        result_state = await execute_block(block, state, ctx)

        br = result_state.results["validator"]
        assert isinstance(br, BlockResult)
        assert br.exit_handle == "high_grade"

    @pytest.mark.asyncio
    async def test_exit_conditions_regex_no_match_leaves_none(self):
        """Regex that does not match should leave exit_handle as None."""
        block = OutputBlock("validator", "Score: 40/100 — GRADE_F")
        block.exit_conditions = [
            ExitCondition(regex=r"GRADE_[AB]", exit_handle="high_grade"),
        ]

        ctx = _make_ctx({"validator": block})
        state = _make_state()

        result_state = await execute_block(block, state, ctx)

        br = result_state.results["validator"]
        assert isinstance(br, BlockResult)
        assert br.exit_handle is None


# ===========================================================================
# AC4: LoopBlock integration — exit_conditions + break_on_exit
# ===========================================================================


class TestAC4LoopBlockIntegration:
    @pytest.mark.asyncio
    async def test_exit_conditions_trigger_loop_break_on_exit(self):
        """A block inside a LoopBlock with exit_conditions that sets
        exit_handle should trigger break_on_exit when the handle matches.

        Round 1: output = "NEEDS_REVISION" -> no match -> loop continues
        Round 2: output = "APPROVED" -> contains match -> exit_handle="approved"
                 -> break_on_exit="approved" triggers loop break
        """
        critic = RoundAwareOutputBlock("critic")
        critic.exit_conditions = [
            ExitCondition(contains="APPROVED", exit_handle="approved"),
        ]

        loop_block = LoopBlock(
            "loop",
            inner_block_refs=["critic"],
            max_rounds=5,
            break_on_exit="approved",
        )

        wf = Workflow("test_loop_exit_cond")
        wf.add_block(loop_block)
        wf.add_block(critic)
        wf.set_entry("loop")
        wf.add_transition("loop", None)

        state = _make_state()
        result_state = await wf.run(state)

        # Loop should have broken early on round 2
        loop_meta = result_state.shared_memory.get("__loop__loop")
        assert loop_meta is not None
        assert loop_meta["broke_early"] is True
        assert loop_meta["rounds_completed"] == 2
        assert "approved" in loop_meta.get("break_reason", "")

        # The critic result should have exit_handle="approved"
        critic_br = result_state.results.get("critic")
        assert isinstance(critic_br, BlockResult)
        assert critic_br.exit_handle == "approved"


# ===========================================================================
# AC5: Explicit exit_handle takes precedence over exit_conditions
# ===========================================================================


class TestAC5ExplicitExitHandlePrecedence:
    @pytest.mark.asyncio
    async def test_explicit_exit_handle_not_overridden_by_exit_conditions(self):
        """A block that sets exit_handle explicitly (e.g., GateBlock pattern)
        should NOT have it overridden by exit_conditions evaluation.

        The block's output contains "PASS" which would match the exit_condition,
        but the explicit exit_handle="explicit_gate" takes precedence."""
        block = ExplicitExitBlock("gate", output_text="Result: PASS", exit_handle="explicit_gate")
        block.exit_conditions = [
            ExitCondition(contains="PASS", exit_handle="condition_match"),
        ]

        ctx = _make_ctx({"gate": block})
        state = _make_state()

        result_state = await execute_block(block, state, ctx)

        br = result_state.results["gate"]
        assert isinstance(br, BlockResult)
        # Explicit exit_handle must be preserved, NOT overridden by exit_conditions
        assert br.exit_handle == "explicit_gate"


# ===========================================================================
# AC6: Multiple conditions — second match wins (first-match semantics)
# ===========================================================================


class TestAC6MultipleConditionsSecondMatch:
    @pytest.mark.asyncio
    async def test_multiple_conditions_first_match_wins(self):
        """With multiple exit_conditions, the first condition that matches
        should set the exit_handle. Output matches second but not first."""
        block = OutputBlock("multi", "The review says: NEEDS_WORK on section 3")
        block.exit_conditions = [
            ExitCondition(contains="APPROVED", exit_handle="approved"),
            ExitCondition(contains="NEEDS_WORK", exit_handle="revision"),
            ExitCondition(contains="REJECTED", exit_handle="rejected"),
        ]

        ctx = _make_ctx({"multi": block})
        state = _make_state()

        result_state = await execute_block(block, state, ctx)

        br = result_state.results["multi"]
        assert isinstance(br, BlockResult)
        # Only second condition matches -> exit_handle should be "revision"
        assert br.exit_handle == "revision"

    @pytest.mark.asyncio
    async def test_multiple_conditions_none_match(self):
        """When no conditions match in a list, exit_handle stays None."""
        block = OutputBlock("multi_none", "Everything is fine, no flags here")
        block.exit_conditions = [
            ExitCondition(contains="APPROVED", exit_handle="approved"),
            ExitCondition(contains="REJECTED", exit_handle="rejected"),
        ]

        ctx = _make_ctx({"multi_none": block})
        state = _make_state()

        result_state = await execute_block(block, state, ctx)

        br = result_state.results["multi_none"]
        assert isinstance(br, BlockResult)
        assert br.exit_handle is None


# ===========================================================================
# Edge: contains + regex on same condition — contains checked first
# ===========================================================================


class TestEdgeCombinedContainsAndRegex:
    @pytest.mark.asyncio
    async def test_contains_checked_before_regex_on_same_condition(self):
        """When a single ExitCondition has both contains and regex,
        contains is checked first. If contains matches, exit_handle is set
        regardless of regex."""
        block = OutputBlock("combo", "PASS: score=95")
        block.exit_conditions = [
            ExitCondition(
                contains="PASS",
                regex=r"score=\d+",
                exit_handle="matched",
            ),
        ]

        ctx = _make_ctx({"combo": block})
        state = _make_state()

        result_state = await execute_block(block, state, ctx)

        br = result_state.results["combo"]
        assert isinstance(br, BlockResult)
        assert br.exit_handle == "matched"

    @pytest.mark.asyncio
    async def test_contains_fails_regex_matches_on_same_condition(self):
        """When contains does NOT match but regex DOES, exit_handle
        should still be set (regex acts as fallback within same condition)."""
        block = OutputBlock("combo2", "Result: score=88")
        block.exit_conditions = [
            ExitCondition(
                contains="PASS",
                regex=r"score=\d+",
                exit_handle="regex_fallback",
            ),
        ]

        ctx = _make_ctx({"combo2": block})
        state = _make_state()

        result_state = await execute_block(block, state, ctx)

        br = result_state.results["combo2"]
        assert isinstance(br, BlockResult)
        assert br.exit_handle == "regex_fallback"
