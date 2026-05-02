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


class TestRetryOnExit:
    """When a block returns exit_handle matching retry_on_exit, the loop retries."""

    @pytest.mark.asyncio
    async def test_fail_exit_handle_triggers_retry(self):
        """Gate returning exit_handle='fail' with retry_on_exit='fail' -> skips to next round."""
        writer = TrackingBlock("writer")
        # Gate always returns exit_handle="fail"
        gate = ExitHandleBlock("gate", exit_handle="fail", threshold=1)
        blocks = {"writer": writer, "gate": gate}

        loop = LoopBlock(
            block_id="review_loop",
            inner_block_refs=["writer", "gate"],
            max_rounds=3,
            retry_on_exit="fail",
        )
        blocks["review_loop"] = loop

        state = WorkflowState()
        result_state = await execute_loop_for_test(loop, state, blocks=blocks)

        # Writer and gate should each be called once per round.
        writer_calls = result_state.shared_memory.get("writer_calls", [])
        gate_calls = result_state.shared_memory.get("gate_calls", [])
        assert len(writer_calls) == 3, f"Expected 3 writer calls, got {len(writer_calls)}"
        assert len(gate_calls) == 3, f"Expected 3 gate calls, got {len(gate_calls)}"

    @pytest.mark.asyncio
    async def test_retry_on_exit_skips_remaining_inner_blocks(self):
        """When retry_on_exit triggers mid-round, remaining inner blocks are skipped."""
        draft_step = TrackingBlock("draft_step")
        # Gate returns "fail" immediately -> triggers retry
        gate = ExitHandleBlock("gate", exit_handle="fail", threshold=1)
        publish_step = TrackingBlock("publish_step")
        blocks = {"draft_step": draft_step, "gate": gate, "publish_step": publish_step}

        loop = LoopBlock(
            block_id="review_loop",
            inner_block_refs=["draft_step", "gate", "publish_step"],
            max_rounds=2,
            retry_on_exit="fail",
        )
        blocks["review_loop"] = loop

        state = WorkflowState()
        result_state = await execute_loop_for_test(loop, state, blocks=blocks)

        # draft_step executes each round (before gate), gate executes each round,
        # publish_step is skipped because it comes after the retrying gate.
        draft_step_calls = result_state.shared_memory.get("draft_step_calls", [])
        gate_calls = result_state.shared_memory.get("gate_calls", [])
        publish_step_calls = result_state.shared_memory.get("publish_step_calls", [])

        assert len(draft_step_calls) == 2, (
            f"Expected 2 draft_step calls, got {len(draft_step_calls)}"
        )
        assert len(gate_calls) == 2, f"Expected 2 gate calls, got {len(gate_calls)}"
        assert len(publish_step_calls) == 0, (
            f"Expected 0 publish_step calls (skipped by retry), got {len(publish_step_calls)}"
        )

    @pytest.mark.asyncio
    async def test_non_matching_exit_handle_does_not_trigger_retry(self):
        """An exit_handle that does not match retry_on_exit does not trigger retry."""
        writer = TrackingBlock("writer")
        # Gate returns exit_handle="pass", but retry_on_exit is "fail"
        gate = ExitHandleBlock("gate", exit_handle="pass", threshold=1)
        blocks = {"writer": writer, "gate": gate}

        loop = LoopBlock(
            block_id="review_loop",
            inner_block_refs=["writer", "gate"],
            max_rounds=3,
            retry_on_exit="fail",
        )
        blocks["review_loop"] = loop

        state = WorkflowState()
        result_state = await execute_loop_for_test(loop, state, blocks=blocks)

        # Since "pass" != "fail", retry_on_exit should not trigger.
        # The loop should still complete normally without retry logic interfering.
        writer_calls = result_state.shared_memory.get("writer_calls", [])
        assert len(writer_calls) == 3, f"Expected 3 writer calls, got {len(writer_calls)}"


# ==============================================================================
# break_on_exit exits the loop early
# ==============================================================================


class TestMaxRoundsEnforced:
    """max_rounds must still be respected even when retry_on_exit is active."""

    @pytest.mark.asyncio
    async def test_max_rounds_caps_retry_on_exit(self):
        """If retry_on_exit fires every round, loop must still stop at max_rounds."""
        writer = TrackingBlock("writer")
        # Gate always returns "fail" -> retry_on_exit fires every round
        gate = ExitHandleBlock("gate", exit_handle="fail", threshold=1)
        blocks = {"writer": writer, "gate": gate}

        loop = LoopBlock(
            block_id="review_loop",
            inner_block_refs=["writer", "gate"],
            max_rounds=4,
            retry_on_exit="fail",
        )
        blocks["review_loop"] = loop

        state = WorkflowState()
        result_state = await execute_loop_for_test(loop, state, blocks=blocks)

        gate_calls = result_state.shared_memory.get("gate_calls", [])
        assert len(gate_calls) == 4, (
            f"Expected exactly 4 gate calls (max_rounds), got {len(gate_calls)}"
        )

    @pytest.mark.asyncio
    async def test_max_rounds_1_with_retry_on_exit(self):
        """max_rounds=1 should execute only once even with retry_on_exit."""
        writer = TrackingBlock("writer")
        gate = ExitHandleBlock("gate", exit_handle="fail", threshold=1)
        blocks = {"writer": writer, "gate": gate}

        loop = LoopBlock(
            block_id="review_loop",
            inner_block_refs=["writer", "gate"],
            max_rounds=1,
            retry_on_exit="fail",
        )
        blocks["review_loop"] = loop

        state = WorkflowState()
        result_state = await execute_loop_for_test(loop, state, blocks=blocks)

        gate_calls = result_state.shared_memory.get("gate_calls", [])
        assert len(gate_calls) == 1, f"Expected 1 gate call (max_rounds=1), got {len(gate_calls)}"


# ==============================================================================
# Loop metadata records exit-handle behavior
# ==============================================================================


class TestCombinedBreakAndRetryOnExit:
    """When both break_on_exit and retry_on_exit are configured, the loop should
    handle both exit_handle values correctly."""

    @pytest.mark.asyncio
    async def test_retry_then_break(self):
        """Gate fails (retry) for rounds 1-2, then passes (break) on round 3."""

        class PhasedGate(BaseBlock):
            """Gate that returns 'fail' for first N calls, then 'pass'."""

            def __init__(self, block_id: str, pass_on_call: int = 3):
                super().__init__(block_id)
                self.context_access = "declared"
                self._pass_on_call = pass_on_call
                self.calls: list[int] = []

            async def execute(self, ctx):
                state = ctx.state_snapshot
                self.calls.append(len(self.calls) + 1)
                call_num = len(self.calls)

                if call_num >= self._pass_on_call:
                    handle = "pass"
                else:
                    handle = "fail"

                next_state = state.model_copy(
                    update={
                        "results": {
                            **state.results,
                            self.block_id: BlockResult(
                                output=f"call_{call_num}_{handle}",
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

        writer = TrackingBlock("writer")
        gate = PhasedGate("gate", pass_on_call=3)
        blocks = {"writer": writer, "gate": gate}

        loop = LoopBlock(
            block_id="review_loop",
            inner_block_refs=["writer", "gate"],
            max_rounds=5,
            break_on_exit="pass",
            retry_on_exit="fail",
        )
        blocks["review_loop"] = loop

        state = WorkflowState()
        result_state = await execute_loop_for_test(loop, state, blocks=blocks)

        # Round 1: gate="fail" -> retry
        # Round 2: gate="fail" -> retry
        # Round 3: gate="pass" -> break!
        gate_calls = result_state.shared_memory.get("gate_calls", [])
        assert len(gate_calls) == 3, f"Expected 3 gate calls, got {len(gate_calls)}"

        meta = result_state.shared_memory.get("__loop__review_loop")
        assert meta is not None
        assert meta["broke_early"] is True
        assert meta["rounds_completed"] == 3
