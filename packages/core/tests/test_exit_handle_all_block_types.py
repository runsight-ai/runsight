"""Smoke coverage for loop exit-handle wiring.

Block-specific exit handles are owned by their dedicated suites. These tests
keep only generic LoopBlock integration paths that cross block output,
exit_conditions, and break_on_exit behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pytest
from runsight_core.block_io import BlockContext, BlockOutput
from runsight_core.blocks.base import BaseBlock
from runsight_core.blocks.loop import LoopBlock
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.workflow import Workflow


@dataclass
class ExitCondition:
    exit_handle: str
    contains: Optional[str] = None
    regex: Optional[str] = None


def _make_state() -> WorkflowState:
    return WorkflowState(results={}, metadata={}, shared_memory={}, execution_log=[])


def _make_workflow_with_loop(name: str, loop: LoopBlock, block: BaseBlock) -> Workflow:
    wf = Workflow(name)
    wf.add_block(loop)
    wf.add_block(block)
    wf.set_entry(loop.block_id)
    wf.add_transition(loop.block_id, None)
    return wf


class ExplicitExitBlock(BaseBlock):
    def __init__(self, block_id: str, output_text: str, exit_handle: str) -> None:
        super().__init__(block_id)
        self.context_access = "declared"
        self.output_text = output_text
        self._exit_handle = exit_handle

    async def execute(self, ctx: BlockContext) -> BlockOutput:
        return BlockOutput(output=self.output_text, exit_handle=self._exit_handle)


class RoundAwareOutputBlock(BaseBlock):
    def __init__(self, block_id: str, trigger_round: int, trigger_text: str) -> None:
        super().__init__(block_id)
        self.context_access = "declared"
        self.trigger_round = trigger_round
        self.trigger_text = trigger_text
        self.calls = 0

    async def execute(self, ctx: BlockContext) -> BlockOutput:
        self.calls += 1
        output = (
            f"Review result: {self.trigger_text}"
            if self.calls >= self.trigger_round
            else "Review result: NEEDS_REVISION"
        )
        return BlockOutput(output=output)


@pytest.mark.asyncio
async def test_exit_conditions_can_break_loop_after_block_output_matches():
    critic = RoundAwareOutputBlock("critic", trigger_round=2, trigger_text="APPROVED")
    critic.exit_conditions = [ExitCondition(contains="APPROVED", exit_handle="approved")]
    loop = LoopBlock(
        "condition_loop",
        inner_block_refs=["critic"],
        max_rounds=5,
        break_on_exit="approved",
    )
    wf = _make_workflow_with_loop("condition_loop_workflow", loop, critic)

    final = await wf.run(_make_state())

    loop_meta = final.shared_memory["__loop__condition_loop"]
    assert loop_meta["broke_early"] is True
    assert loop_meta["rounds_completed"] == 2
    assert final.results["critic"].exit_handle == "approved"


@pytest.mark.asyncio
async def test_explicit_exit_handle_takes_precedence_inside_loop():
    block = ExplicitExitBlock("gate", output_text="Result: PASS", exit_handle="explicit_gate")
    block.exit_conditions = [ExitCondition(contains="PASS", exit_handle="condition_match")]
    loop = LoopBlock(
        "precedence_loop",
        inner_block_refs=["gate"],
        max_rounds=5,
        break_on_exit="explicit_gate",
    )
    wf = _make_workflow_with_loop("explicit_exit_precedence_workflow", loop, block)

    final = await wf.run(_make_state())

    loop_meta = final.shared_memory["__loop__precedence_loop"]
    assert loop_meta["broke_early"] is True
    assert loop_meta["rounds_completed"] == 1
    gate_result = final.results["gate"]
    assert isinstance(gate_result, BlockResult)
    assert gate_result.exit_handle == "explicit_gate"
