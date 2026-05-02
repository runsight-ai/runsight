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


class TestLoopBlockIntegrationKeywordBreak:
    """Inner block output contains keyword -> break condition triggers."""

    @pytest.mark.asyncio
    async def test_keyword_in_output_triggers_break(self):
        """When inner block output contains 'DONE', break condition with 'contains' triggers."""
        from runsight_core import LoopBlock
        from runsight_core.conditions.engine import Condition

        # KeywordBlock outputs "DONE: finished" on call 3
        inner = KeywordBlock("agent_block", keyword_on_call=3)
        blocks = {"agent_block": inner}

        break_cond = Condition(eval_key="agent_block", operator="contains", value="DONE")

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["agent_block"],
            max_rounds=5,
            break_condition=break_cond,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        result_state = await _run_loop(loop, state, blocks)

        calls = result_state.shared_memory.get("agent_block_calls", [])
        assert len(calls) == 3
        assert result_state.shared_memory["__loop__loop_block"]["broke_early"] is True


class TestLoopBlockIntegrationGateBreak:
    """GateBlock PASS -> break condition triggers exit."""

    @pytest.mark.asyncio
    async def test_gate_pass_triggers_break(self):
        """When gate block outputs 'PASS', break condition triggers loop exit."""
        from runsight_core import LoopBlock
        from runsight_core.conditions.engine import Condition

        worker = TrackingBlock("worker")
        gate = GatePassBlock("gate", pass_on_round=3)
        blocks = {"worker": worker, "gate": gate}

        # Break when gate output starts with "PASS"
        break_cond = Condition(eval_key="gate", operator="starts_with", value="PASS")

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["worker", "gate"],
            max_rounds=5,
            break_condition=break_cond,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        result_state = await _run_loop(loop, state, blocks)

        # Round 1: gate="FAIL: not ready" -> no break
        # Round 2: gate="FAIL: not ready" -> no break
        # Round 3: gate="PASS" -> break!
        gate_calls = result_state.shared_memory.get("gate_calls", [])
        worker_calls = result_state.shared_memory.get("worker_calls", [])
        assert len(gate_calls) == 3, f"Expected gate called 3 times, got {len(gate_calls)}"
        assert len(worker_calls) == 3, f"Expected worker called 3 times, got {len(worker_calls)}"
        assert result_state.shared_memory["__loop__loop_block"]["broke_early"] is True


class TestLoopBlockIntegrationComplexConditionGroup:
    """Complex condition group works as break condition in integration context."""

    @pytest.mark.asyncio
    async def test_complex_and_group_with_multi_block_loop(self):
        """AND group with multiple inner blocks: condition evaluated against last block's output."""
        from runsight_core import LoopBlock
        from runsight_core.conditions.engine import Condition, ConditionGroup

        worker = TrackingBlock("worker")
        scorer = JsonOutputBlock("scorer")
        blocks = {"worker": worker, "scorer": scorer}

        # Break when score >= 60 AND status == "complete" (happens on round 3)
        break_cond = ConditionGroup(
            conditions=[
                Condition(eval_key="score", operator="gte", value=60),
                Condition(eval_key="status", operator="equals", value="complete"),
            ],
            combinator="and",
        )

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["worker", "scorer"],
            max_rounds=5,
            break_condition=break_cond,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        result_state = await _run_loop(loop, state, blocks)

        scorer_calls = result_state.shared_memory.get("scorer_calls", [])
        assert len(scorer_calls) == 3
        assert result_state.shared_memory["__loop__loop_block"]["broke_early"] is True
        assert result_state.shared_memory["__loop__loop_block"]["rounds_completed"] == 3


# ==============================================================================
# 5. Edge cases
# ==============================================================================
