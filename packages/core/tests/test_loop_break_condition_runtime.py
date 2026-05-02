"""LoopBlock break-condition schema, execution, metadata, and workflow behavior."""

from __future__ import annotations

import pytest
from pydantic import TypeAdapter
from runsight_core.blocks.base import BaseBlock
from runsight_core.state import WorkflowState
from runsight_core.yaml.schema import (
    BlockDef,
)

# -- Shared TypeAdapter for discriminated union --------------------------------

block_adapter = TypeAdapter(BlockDef)


def _validate_block(data: dict):
    """Validate a dict as a BlockDef via the discriminated union."""
    return block_adapter.validate_python(data)


async def _run_loop(loop, state: WorkflowState, blocks: dict) -> WorkflowState:
    """Helper: build BlockContext, run LoopBlock, apply output → WorkflowState."""
    from runsight_core.block_io import BlockContext, BlockOutput, apply_block_output

    ctx = BlockContext(
        block_id=loop.block_id,
        instruction="loop",
        inputs={"blocks": blocks},
        state_snapshot=state,
    )
    output = await loop.execute(ctx)
    if isinstance(output, WorkflowState):
        return output
    if isinstance(output, BlockOutput):
        return apply_block_output(state, loop.block_id, output)
    return state


# -- Test helpers --------------------------------------------------------------


class TrackingBlock(BaseBlock):
    """Block that records each call in shared_memory under its block_id."""

    def __init__(self, block_id: str):
        super().__init__(block_id)
        self.context_access = "declared"
        self.calls: list[int] = []

    async def execute(self, ctx):
        from runsight_core.block_io import BlockOutput

        self.calls.append(len(self.calls) + 1)
        return BlockOutput(
            output=f"call_{len(self.calls)}",
            shared_memory_updates={f"{self.block_id}_calls": list(self.calls)},
        )


class KeywordBlock(BaseBlock):
    """Block that outputs a keyword on a specific call number.

    Before the target call, outputs "working...".
    On and after the target call, outputs "DONE: finished".
    """

    def __init__(self, block_id: str, keyword_on_call: int = 2):
        super().__init__(block_id)
        self.context_access = "declared"
        self.keyword_on_call = keyword_on_call
        self.calls: list[int] = []

    async def execute(self, ctx):
        from runsight_core.block_io import BlockOutput

        self.calls.append(len(self.calls) + 1)
        call_num = len(self.calls)
        if call_num >= self.keyword_on_call:
            output = "DONE: finished"
        else:
            output = "working..."
        return BlockOutput(
            output=output,
            shared_memory_updates={f"{self.block_id}_calls": list(self.calls)},
        )


class JsonOutputBlock(BaseBlock):
    """Block that outputs structured JSON with a score field.

    Score increases by 20 each call: 20, 40, 60, 80, 100.
    """

    def __init__(self, block_id: str):
        super().__init__(block_id)
        self.context_access = "declared"
        self.calls: list[int] = []

    async def execute(self, ctx):
        import json

        from runsight_core.block_io import BlockOutput

        self.calls.append(len(self.calls) + 1)
        call_num = len(self.calls)
        output = json.dumps(
            {"score": call_num * 20, "status": "complete" if call_num >= 3 else "pending"}
        )
        return BlockOutput(
            output=output,
            shared_memory_updates={f"{self.block_id}_calls": list(self.calls)},
        )


class GatePassBlock(BaseBlock):
    """Simulates a gate block that writes PASS/FAIL to results based on round number.

    Returns "PASS" starting from the target round, "FAIL: not ready" before that.
    """

    def __init__(self, block_id: str, pass_on_round: int = 2):
        super().__init__(block_id)
        self.context_access = "declared"
        self.pass_on_round = pass_on_round
        self.calls: list[int] = []

    async def execute(self, ctx):
        from runsight_core.block_io import BlockOutput

        self.calls.append(len(self.calls) + 1)
        call_num = len(self.calls)
        if call_num >= self.pass_on_round:
            output = "PASS"
        else:
            output = "FAIL: not ready"
        return BlockOutput(
            output=output,
            shared_memory_updates={f"{self.block_id}_calls": list(self.calls)},
        )


class BadFieldBlock(BaseBlock):
    """Block that outputs a dict without the field the break condition references."""

    def __init__(self, block_id: str):
        super().__init__(block_id)
        self.context_access = "declared"
        self.calls: list[int] = []

    async def execute(self, ctx):
        import json

        from runsight_core.block_io import BlockOutput

        self.calls.append(len(self.calls) + 1)
        # Output has "name" but NOT "status" — condition referencing "status" should get None
        output = json.dumps({"name": "status source", "round": len(self.calls)})
        return BlockOutput(
            output=output,
            shared_memory_updates={f"{self.block_id}_calls": list(self.calls)},
        )


# ==============================================================================
# 1. Schema tests -- LoopBlockDef accepts break_condition
# ==============================================================================


class TestLoopBlockBreakEarly:
    """LoopBlock breaks early when break condition is met."""

    @pytest.mark.asyncio
    async def test_breaks_on_round_2_of_5(self):
        """LoopBlock with max_rounds=5 should break after round 2 when condition met."""
        from runsight_core import LoopBlock
        from runsight_core.conditions.engine import Condition

        # KeywordBlock outputs "DONE: finished" on call 2
        inner = KeywordBlock("inner_block", keyword_on_call=2)
        blocks = {"inner_block": inner}

        # Break when inner_block output contains "DONE"
        break_cond = Condition(eval_key="inner_block", operator="contains", value="DONE")

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["inner_block"],
            max_rounds=5,
            break_condition=break_cond,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        result_state = await _run_loop(loop, state, blocks)

        # Should have executed only 2 rounds, not 5
        calls = result_state.shared_memory.get("inner_block_calls", [])
        assert len(calls) == 2, f"Expected 2 calls (break on round 2), got {len(calls)}"

    @pytest.mark.asyncio
    async def test_runs_all_max_rounds_when_condition_never_met(self):
        """LoopBlock should run all max_rounds when break condition never evaluates True."""
        from runsight_core import LoopBlock
        from runsight_core.conditions.engine import Condition

        # TrackingBlock never outputs "IMPOSSIBLE_VALUE"
        inner = TrackingBlock("inner_block")
        blocks = {"inner_block": inner}

        # Condition that will never match
        break_cond = Condition(eval_key="inner_block", operator="equals", value="IMPOSSIBLE_VALUE")

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["inner_block"],
            max_rounds=4,
            break_condition=break_cond,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        result_state = await _run_loop(loop, state, blocks)

        # Should run all 4 rounds
        calls = result_state.shared_memory.get("inner_block_calls", [])
        assert len(calls) == 4, f"Expected 4 calls (all rounds), got {len(calls)}"

    @pytest.mark.asyncio
    async def test_no_break_condition_runs_all_rounds(self):
        """LoopBlock with break_condition=None should run all max_rounds by default."""
        from runsight_core import LoopBlock

        inner = TrackingBlock("inner_block")
        blocks = {"inner_block": inner}

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["inner_block"],
            max_rounds=3,
            break_condition=None,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        result_state = await _run_loop(loop, state, blocks)

        calls = result_state.shared_memory.get("inner_block_calls", [])
        assert len(calls) == 3, f"Expected 3 calls (all rounds, no break), got {len(calls)}"


class TestLoopBlockConditionGroupBreak:
    """ConditionGroupDef (AND/OR) works as break condition."""

    @pytest.mark.asyncio
    async def test_and_condition_group_breaks_when_all_met(self):
        """AND group: breaks only when all conditions in the group are True."""
        from runsight_core import LoopBlock
        from runsight_core.conditions.engine import Condition, ConditionGroup

        # JsonOutputBlock: round 3 -> score=60, status="complete"
        inner = JsonOutputBlock("scorer")
        blocks = {"scorer": inner}

        # Break when score >= 60 AND status == "complete"
        break_cond = ConditionGroup(
            conditions=[
                Condition(eval_key="score", operator="gte", value=60),
                Condition(eval_key="status", operator="equals", value="complete"),
            ],
            combinator="and",
        )

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["scorer"],
            max_rounds=5,
            break_condition=break_cond,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        result_state = await _run_loop(loop, state, blocks)

        # Round 1: score=20, status=pending -> no break
        # Round 2: score=40, status=pending -> no break
        # Round 3: score=60, status=complete -> break!
        calls = result_state.shared_memory.get("scorer_calls", [])
        assert len(calls) == 3, f"Expected 3 rounds (AND group met on round 3), got {len(calls)}"

    @pytest.mark.asyncio
    async def test_or_condition_group_breaks_when_any_met(self):
        """OR group: breaks when any condition in the group is True."""
        from runsight_core import LoopBlock
        from runsight_core.conditions.engine import Condition, ConditionGroup

        # JsonOutputBlock: round 1 -> score=20
        inner = JsonOutputBlock("scorer")
        blocks = {"scorer": inner}

        # Break when score >= 80 OR status == "complete"
        # status becomes "complete" on round 3 (score=60)
        # score reaches 80 on round 4
        # But status == "complete" hits first on round 3
        break_cond = ConditionGroup(
            conditions=[
                Condition(eval_key="score", operator="gte", value=80),
                Condition(eval_key="status", operator="equals", value="complete"),
            ],
            combinator="or",
        )

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["scorer"],
            max_rounds=5,
            break_condition=break_cond,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        result_state = await _run_loop(loop, state, blocks)

        # Round 1: score=20, status=pending -> no break
        # Round 2: score=40, status=pending -> no break
        # Round 3: score=60, status=complete -> break (OR: status matches)
        calls = result_state.shared_memory.get("scorer_calls", [])
        assert len(calls) == 3, f"Expected 3 rounds (OR group met on round 3), got {len(calls)}"


# ==============================================================================
# 3. Break metadata in shared_memory
# ==============================================================================


class TestLoopBlockBreakEdgeCases:
    """Edge cases for break conditions."""

    @pytest.mark.asyncio
    async def test_missing_field_treated_as_false(self):
        """Break condition referencing a field not in output should treat as False (continue)."""
        from runsight_core import LoopBlock
        from runsight_core.conditions.engine import Condition

        # BadFieldBlock outputs a name and round, but no status field.
        inner = BadFieldBlock("inner_block")
        blocks = {"inner_block": inner}

        # Condition references "status" which doesn't exist in output
        break_cond = Condition(eval_key="status", operator="equals", value="done")

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["inner_block"],
            max_rounds=3,
            break_condition=break_cond,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        result_state = await _run_loop(loop, state, blocks)

        # Should run all 3 rounds because condition never matches
        calls = result_state.shared_memory.get("inner_block_calls", [])
        assert len(calls) == 3, f"Expected 3 calls (missing field -> continue), got {len(calls)}"
        assert result_state.shared_memory["__loop__loop_block"]["broke_early"] is False

    @pytest.mark.asyncio
    async def test_break_on_round_1(self):
        """Break condition met on round 1 should exit loop after single execution."""
        from runsight_core import LoopBlock
        from runsight_core.conditions.engine import Condition

        # KeywordBlock outputs "DONE: finished" on call 1
        inner = KeywordBlock("inner_block", keyword_on_call=1)
        blocks = {"inner_block": inner}

        break_cond = Condition(eval_key="inner_block", operator="contains", value="DONE")

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["inner_block"],
            max_rounds=5,
            break_condition=break_cond,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        result_state = await _run_loop(loop, state, blocks)

        calls = result_state.shared_memory.get("inner_block_calls", [])
        assert len(calls) == 1, f"Expected 1 call (break on round 1), got {len(calls)}"
        assert result_state.shared_memory["__loop__loop_block"]["broke_early"] is True
        assert result_state.shared_memory["__loop__loop_block"]["rounds_completed"] == 1

    @pytest.mark.asyncio
    async def test_condition_error_propagates(self):
        """If condition evaluation throws an error, it should propagate, not be swallowed."""
        from runsight_core import LoopBlock
        from runsight_core.conditions.engine import Condition

        inner = TrackingBlock("inner_block")
        blocks = {"inner_block": inner}

        # Invalid regex pattern should cause ValueError during evaluation
        break_cond = Condition(eval_key="inner_block", operator="regex", value="[invalid")

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["inner_block"],
            max_rounds=5,
            break_condition=break_cond,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        with pytest.raises(ValueError, match="[Rr]egex"):
            await _run_loop(loop, state, blocks)

    @pytest.mark.asyncio
    async def test_break_condition_evaluates_against_last_inner_block_output(self):
        """Break condition should evaluate against the last inner block's output by default."""
        from runsight_core import LoopBlock
        from runsight_core.conditions.engine import Condition

        # Two inner blocks: first always outputs "working", second outputs "DONE" on call 2
        first = TrackingBlock("first_block")
        second = KeywordBlock("second_block", keyword_on_call=2)
        blocks = {"first_block": first, "second_block": second}

        # Condition checks second_block (last inner) output for "DONE"
        break_cond = Condition(eval_key="second_block", operator="contains", value="DONE")

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["first_block", "second_block"],
            max_rounds=5,
            break_condition=break_cond,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        result_state = await _run_loop(loop, state, blocks)

        # Round 1: second_block="working..." -> no break
        # Round 2: second_block="DONE: finished" -> break!
        second_calls = result_state.shared_memory.get("second_block_calls", [])
        assert len(second_calls) == 2, f"Expected 2 rounds, got {len(second_calls)}"


# ==============================================================================
# 6. Constructor accepts break_condition parameter
# ==============================================================================
