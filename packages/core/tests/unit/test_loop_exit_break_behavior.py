"""LoopBlock exit-handle control tests.

The suite covers retry and break routing inside loops, mid-round skipping,
source-level exception-handling governance, break-condition compatibility,
metadata, schema fields, parser wiring, and carry_context propagation.
"""

import pytest
from conftest import block_output_from_state, execute_loop_for_test
from pydantic import TypeAdapter
from runsight_core.blocks.base import BaseBlock
from runsight_core.blocks.loop import LoopBlock
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.yaml.schema import BlockDef

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class TrackingBlock(BaseBlock):
    """Block that records each call in shared_memory under its block_id."""

    def __init__(self, block_id: str):
        super().__init__(block_id)
        self.context_access = "declared"
        self.calls: list[int] = []

    async def execute(self, ctx):
        state = ctx.state_snapshot
        self.calls.append(len(self.calls) + 1)
        next_state = state.model_copy(
            update={
                "results": {
                    **state.results,
                    self.block_id: BlockResult(output=f"call_{len(self.calls)}"),
                },
                "shared_memory": {
                    **state.shared_memory,
                    f"{self.block_id}_calls": list(self.calls),
                },
            }
        )
        return block_output_from_state(self.block_id, state, next_state)


class ExitHandleBlock(BaseBlock):
    """Block that returns a BlockResult with a configurable exit_handle.

    Returns exit_handle=None for the first (threshold - 1) calls,
    then returns the configured exit_handle from call number `threshold` onward.
    """

    def __init__(self, block_id: str, exit_handle: str, threshold: int = 1):
        super().__init__(block_id)
        self.context_access = "declared"
        self._exit_handle = exit_handle
        self._threshold = threshold
        self.calls: list[int] = []

    async def execute(self, ctx):
        state = ctx.state_snapshot
        self.calls.append(len(self.calls) + 1)
        call_num = len(self.calls)

        if call_num >= self._threshold:
            handle = self._exit_handle
        else:
            handle = None

        next_state = state.model_copy(
            update={
                "results": {
                    **state.results,
                    self.block_id: BlockResult(
                        output=f"call_{call_num}_handle_{handle}",
                        exit_handle=handle,
                    ),
                },
                "shared_memory": {
                    **state.shared_memory,
                    f"{self.block_id}_calls": list(self.calls),
                },
            }
        )
        return block_output_from_state(self.block_id, state, next_state)


block_adapter = TypeAdapter(BlockDef)


def _validate_block(data: dict):
    """Validate a dict as a BlockDef via the discriminated union."""
    return block_adapter.validate_python(data)


# ==============================================================================
# retry_on_exit starts the next loop round
# ==============================================================================


class TestBreakOnExit:
    """When a block returns exit_handle matching break_on_exit, the loop exits."""

    @pytest.mark.asyncio
    async def test_pass_exit_handle_triggers_break(self):
        """Gate returning exit_handle='pass' with break_on_exit='pass' -> loop exits early."""
        writer = TrackingBlock("writer")
        # Gate returns exit_handle="pass" starting from call 2
        gate = ExitHandleBlock("gate", exit_handle="pass", threshold=2)
        blocks = {"writer": writer, "gate": gate}

        loop = LoopBlock(
            block_id="review_loop",
            inner_block_refs=["writer", "gate"],
            max_rounds=5,
            break_on_exit="pass",
        )
        blocks["review_loop"] = loop

        state = WorkflowState()
        result_state = await execute_loop_for_test(loop, state, blocks=blocks)

        # Round 1: gate returns exit_handle=None (threshold not met) -> continue
        # Round 2: gate returns exit_handle="pass" -> break!
        gate_calls = result_state.shared_memory.get("gate_calls", [])
        writer_calls = result_state.shared_memory.get("writer_calls", [])
        assert len(gate_calls) == 2, f"Expected 2 gate calls, got {len(gate_calls)}"
        assert len(writer_calls) == 2, f"Expected 2 writer calls, got {len(writer_calls)}"

    @pytest.mark.asyncio
    async def test_break_on_exit_immediate_round_1(self):
        """Gate returning matching exit_handle on round 1 -> loop exits after single round."""
        writer = TrackingBlock("writer")
        gate = ExitHandleBlock("gate", exit_handle="pass", threshold=1)
        blocks = {"writer": writer, "gate": gate}

        loop = LoopBlock(
            block_id="review_loop",
            inner_block_refs=["writer", "gate"],
            max_rounds=5,
            break_on_exit="pass",
        )
        blocks["review_loop"] = loop

        state = WorkflowState()
        result_state = await execute_loop_for_test(loop, state, blocks=blocks)

        gate_calls = result_state.shared_memory.get("gate_calls", [])
        assert len(gate_calls) == 1, (
            f"Expected 1 gate call (break on round 1), got {len(gate_calls)}"
        )

    @pytest.mark.asyncio
    async def test_non_matching_exit_handle_does_not_trigger_break(self):
        """An exit_handle that does not match break_on_exit does not trigger early exit."""
        writer = TrackingBlock("writer")
        # Gate returns "fail", but break_on_exit is "pass"
        gate = ExitHandleBlock("gate", exit_handle="fail", threshold=1)
        blocks = {"writer": writer, "gate": gate}

        loop = LoopBlock(
            block_id="review_loop",
            inner_block_refs=["writer", "gate"],
            max_rounds=3,
            break_on_exit="pass",
        )
        blocks["review_loop"] = loop

        state = WorkflowState()
        result_state = await execute_loop_for_test(loop, state, blocks=blocks)

        # All 3 rounds should complete because "fail" != "pass"
        gate_calls = result_state.shared_memory.get("gate_calls", [])
        assert len(gate_calls) == 3, f"Expected 3 gate calls, got {len(gate_calls)}"


# ==============================================================================
# Mid-loop exit skips later inner blocks
# ==============================================================================


class TestMidLoopExit:
    """If a gate returns a matching exit_handle, later inner blocks are skipped."""

    @pytest.mark.asyncio
    async def test_break_on_exit_mid_loop_skips_later_blocks(self):
        """break_on_exit skips blocks after the matching gate."""
        draft_step = TrackingBlock("draft_step")
        gate = ExitHandleBlock("gate", exit_handle="pass", threshold=1)
        publish_step = TrackingBlock("publish_step")
        blocks = {"draft_step": draft_step, "gate": gate, "publish_step": publish_step}

        loop = LoopBlock(
            block_id="review_loop",
            inner_block_refs=["draft_step", "gate", "publish_step"],
            max_rounds=3,
            break_on_exit="pass",
        )
        blocks["review_loop"] = loop

        state = WorkflowState()
        result_state = await execute_loop_for_test(loop, state, blocks=blocks)

        # Round 1: draft_step runs, gate returns "pass" -> break! publish_step never runs
        draft_step_calls = result_state.shared_memory.get("draft_step_calls", [])
        gate_calls = result_state.shared_memory.get("gate_calls", [])
        publish_step_calls = result_state.shared_memory.get("publish_step_calls", [])

        assert len(draft_step_calls) == 1, (
            f"Expected 1 draft_step call, got {len(draft_step_calls)}"
        )
        assert len(gate_calls) == 1, f"Expected 1 gate call, got {len(gate_calls)}"
        assert len(publish_step_calls) == 0, (
            f"Expected 0 publish_step calls (mid-loop break), got {len(publish_step_calls)}"
        )

    @pytest.mark.asyncio
    async def test_retry_on_exit_mid_loop_skips_later_blocks(self):
        """retry_on_exit skips blocks after the matching gate."""
        draft_step = TrackingBlock("draft_step")
        # Gate returns "fail" on all calls -> retry every round
        gate = ExitHandleBlock("gate", exit_handle="fail", threshold=1)
        publish_step = TrackingBlock("publish_step")
        blocks = {"draft_step": draft_step, "gate": gate, "publish_step": publish_step}

        loop = LoopBlock(
            block_id="review_loop",
            inner_block_refs=["draft_step", "gate", "publish_step"],
            max_rounds=3,
            retry_on_exit="fail",
        )
        blocks["review_loop"] = loop

        state = WorkflowState()
        result_state = await execute_loop_for_test(loop, state, blocks=blocks)

        # All 3 rounds: draft_step runs, gate returns "fail" -> retry, publish_step skipped
        draft_step_calls = result_state.shared_memory.get("draft_step_calls", [])
        gate_calls = result_state.shared_memory.get("gate_calls", [])
        publish_step_calls = result_state.shared_memory.get("publish_step_calls", [])

        assert len(draft_step_calls) == 3, (
            f"Expected 3 draft_step calls, got {len(draft_step_calls)}"
        )
        assert len(gate_calls) == 3, f"Expected 3 gate calls, got {len(gate_calls)}"
        assert len(publish_step_calls) == 0, (
            f"Expected 0 publish_step calls (retry skips remaining), got {len(publish_step_calls)}"
        )

    @pytest.mark.asyncio
    async def test_mid_loop_break_after_nonmatching_rounds(self):
        """Gate produces no exit handle for two rounds, then breaks on round three."""
        draft_step = TrackingBlock("draft_step")
        # Gate returns no exit handle for calls 1-2, then returns "pass" on call 3.
        gate = ExitHandleBlock("gate", exit_handle="pass", threshold=3)
        # For calls before threshold, exit_handle=None.
        publish_step = TrackingBlock("publish_step")
        blocks = {"draft_step": draft_step, "gate": gate, "publish_step": publish_step}

        loop = LoopBlock(
            block_id="review_loop",
            inner_block_refs=["draft_step", "gate", "publish_step"],
            max_rounds=5,
            break_on_exit="pass",
        )
        blocks["review_loop"] = loop

        state = WorkflowState()
        result_state = await execute_loop_for_test(loop, state, blocks=blocks)

        # Rounds 1-2: gate exit_handle=None -> publish_step runs normally
        # Round 3: gate exit_handle="pass" -> break! publish_step skipped this round
        draft_step_calls = result_state.shared_memory.get("draft_step_calls", [])
        gate_calls = result_state.shared_memory.get("gate_calls", [])
        publish_step_calls = result_state.shared_memory.get("publish_step_calls", [])

        assert len(draft_step_calls) == 3, (
            f"Expected 3 draft_step calls, got {len(draft_step_calls)}"
        )
        assert len(gate_calls) == 3, f"Expected 3 gate calls, got {len(gate_calls)}"
        # publish_step runs on rounds 1-2, then is skipped on the break round.
        assert len(publish_step_calls) == 2, (
            f"Expected 2 publish_step calls (ran rounds 1-2, skipped round 3), got {len(publish_step_calls)}"
        )


# ==============================================================================
# LoopBlock source does not use exception-based gate control
# ==============================================================================


class TestBreakConditionStillWorks:
    """break_condition (the original condition-based loop exit) must still work
    independently of break_on_exit/retry_on_exit."""

    @pytest.mark.asyncio
    async def test_break_condition_without_exit_handle_fields(self):
        """break_condition should work even when break_on_exit/retry_on_exit are None."""
        from runsight_core.conditions.engine import Condition

        draft = TrackingBlock("draft")
        blocks = {"draft": draft}

        # Break when output contains "call_3"
        break_cond = Condition(eval_key="draft", operator="contains", value="call_3")

        loop = LoopBlock(
            block_id="review_loop",
            inner_block_refs=["draft"],
            max_rounds=5,
            break_condition=break_cond,
        )
        blocks["review_loop"] = loop

        state = WorkflowState()
        result_state = await execute_loop_for_test(loop, state, blocks=blocks)

        calls = result_state.shared_memory.get("draft_calls", [])
        assert len(calls) == 3, f"Expected 3 calls (break on call_3), got {len(calls)}"

    @pytest.mark.asyncio
    async def test_break_condition_coexists_with_break_on_exit(self):
        """Both break_condition and break_on_exit can be set. break_on_exit should
        take precedence when it fires first (checked per-block, not per-round)."""
        from runsight_core.conditions.engine import Condition

        writer = TrackingBlock("writer")
        # Gate returns exit_handle="pass" on call 2
        gate = ExitHandleBlock("gate", exit_handle="pass", threshold=2)
        blocks = {"writer": writer, "gate": gate}

        # break_condition would fire on round 5 (never reached)
        break_cond = Condition(eval_key="gate", operator="contains", value="no matching output")

        loop = LoopBlock(
            block_id="review_loop",
            inner_block_refs=["writer", "gate"],
            max_rounds=5,
            break_condition=break_cond,
            break_on_exit="pass",
        )
        blocks["review_loop"] = loop

        state = WorkflowState()
        result_state = await execute_loop_for_test(loop, state, blocks=blocks)

        # break_on_exit="pass" should fire on round 2 (gate threshold=2)
        gate_calls = result_state.shared_memory.get("gate_calls", [])
        assert len(gate_calls) == 2, (
            f"Expected 2 gate calls (break_on_exit fired), got {len(gate_calls)}"
        )


# ==============================================================================
# max_rounds is enforced with retry_on_exit
# ==============================================================================
