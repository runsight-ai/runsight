"""LoopBlock exit-handle control tests.

The suite covers retry and break routing inside loops, mid-round skipping,
source-level exception-handling governance, break-condition compatibility,
metadata, schema fields, parser wiring, and carry_context propagation.
"""

import inspect

import pytest
from conftest import block_output_from_state, execute_loop_for_test
from pydantic import TypeAdapter
from runsight_core.blocks.base import BaseBlock
from runsight_core.blocks.loop import CarryContextConfig, LoopBlock, LoopBlockDef
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.yaml.schema import BaseBlockDef, BlockDef

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


class TestNoGateErrorInLoopBlock:
    """LoopBlock source code must not contain any GateError references or
    exception-based gate handling."""

    def test_no_gate_error_in_source(self):
        """LoopBlock source code must not reference GateError."""
        source = inspect.getsource(LoopBlock)
        assert "GateError" not in source, "LoopBlock source still references GateError"

    def test_no_except_with_hasattr_state_pattern(self):
        """LoopBlock source must not use the `except Exception ... hasattr(e, 'state')` pattern."""
        source = inspect.getsource(LoopBlock)
        assert 'hasattr(e, "state")' not in source, (
            "LoopBlock source still uses hasattr(e, 'state') exception pattern"
        )
        assert "hasattr(e, 'state')" not in source, (
            "LoopBlock source still uses hasattr(e, 'state') exception pattern"
        )

    def test_no_broad_exception_catch_in_execute(self):
        """LoopBlock.execute() must not have a bare `except Exception` block."""
        source = inspect.getsource(LoopBlock.execute)
        assert "except Exception" not in source, (
            "LoopBlock.execute() still has a broad 'except Exception' catch"
        )

    def test_no_last_gate_error_variable(self):
        """LoopBlock source must not use a 'last_gate_error' variable."""
        source = inspect.getsource(LoopBlock)
        assert "last_gate_error" not in source, (
            "LoopBlock source still references 'last_gate_error' variable"
        )


# ==============================================================================
# break_condition still works for non-exit-based loops
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


class TestLoopMetadataWithExitHandle:
    """Loop metadata in shared_memory must correctly reflect exit_handle behavior."""

    @pytest.mark.asyncio
    async def test_metadata_on_break_on_exit(self):
        """When break_on_exit fires, metadata should show broke_early=True and correct rounds."""
        writer = TrackingBlock("writer")
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

        meta = result_state.shared_memory.get("__loop__review_loop")
        assert meta is not None, "Loop metadata not found in shared_memory"
        assert meta["broke_early"] is True
        assert meta["rounds_completed"] == 2

    @pytest.mark.asyncio
    async def test_metadata_on_retry_exhaustion(self):
        """When retry_on_exit fires every round and max_rounds exhausted,
        metadata should show broke_early=False."""
        writer = TrackingBlock("writer")
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

        meta = result_state.shared_memory.get("__loop__review_loop")
        assert meta is not None, "Loop metadata not found in shared_memory"
        assert meta["broke_early"] is False
        assert meta["rounds_completed"] == 3

    @pytest.mark.asyncio
    async def test_metadata_break_reason_on_exit_handle(self):
        """When break_on_exit fires, break_reason should indicate exit_handle-based break."""
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

        meta = result_state.shared_memory.get("__loop__review_loop")
        assert meta is not None
        assert meta["broke_early"] is True
        # break_reason should indicate exit_handle (not "condition met")
        assert (
            "exit" in meta.get("break_reason", "").lower()
            or "handle" in meta.get("break_reason", "").lower()
        ), f"Expected break_reason to reference exit_handle, got: {meta.get('break_reason')}"


class ContextPayloadBlock(BaseBlock):
    """Block that emits structured output for carry_context propagation tests."""

    def __init__(self, block_id: str, *, trace_path: str):
        super().__init__(block_id)
        self.context_access = "declared"
        self._trace_path = trace_path
        self.calls: list[int] = []

    async def execute(self, ctx):
        state = ctx.state_snapshot
        self.calls.append(len(self.calls) + 1)
        call_num = len(self.calls)
        next_state = state.model_copy(
            update={
                "results": {
                    **state.results,
                    self.block_id: BlockResult(
                        output=f'{{"trace_path":"{self._trace_path}","round":{call_num}}}'
                    ),
                },
                "shared_memory": {
                    **state.shared_memory,
                    f"{self.block_id}_calls": list(self.calls),
                },
            }
        )
        return block_output_from_state(self.block_id, state, next_state)


class TestCarryContextWithExitHandle:
    """carry_context must still propagate on break/retry exit-handle paths."""

    @pytest.mark.asyncio
    async def test_retry_on_exit_still_updates_carry_context_and_task_context(self):
        source = ContextPayloadBlock(
            "source",
            trace_path="fixture_outputs/provider-trace-primary.md",
        )
        gate = ExitHandleBlock("gate", exit_handle="fail", threshold=1)
        blocks = {"source": source, "gate": gate}

        loop = LoopBlock(
            block_id="review_loop",
            inner_block_refs=["source", "gate"],
            max_rounds=2,
            retry_on_exit="fail",
            carry_context=CarryContextConfig(
                mode="all",
                source_blocks=["source"],
                inject_as="ctx",
            ),
        )
        blocks["review_loop"] = loop

        state = WorkflowState()
        result_state = await execute_loop_for_test(loop, state, blocks=blocks)

        carried = result_state.shared_memory.get("ctx")
        assert isinstance(carried, list)
        assert len(carried) == 2
        assert "provider-trace-primary.md" in str(carried)

    @pytest.mark.asyncio
    async def test_break_on_exit_still_updates_carry_context_and_task_context(self):
        source = ContextPayloadBlock(
            "source",
            trace_path="fixture_outputs/provider-trace-secondary.md",
        )
        gate = ExitHandleBlock("gate", exit_handle="pass", threshold=1)
        blocks = {"source": source, "gate": gate}

        loop = LoopBlock(
            block_id="review_loop",
            inner_block_refs=["source", "gate"],
            max_rounds=3,
            break_on_exit="pass",
            carry_context=CarryContextConfig(
                mode="last",
                source_blocks=["source"],
                inject_as="ctx",
            ),
        )
        blocks["review_loop"] = loop

        state = WorkflowState()
        result_state = await execute_loop_for_test(loop, state, blocks=blocks)

        carried = result_state.shared_memory.get("ctx")
        assert isinstance(carried, dict)
        assert "provider-trace-secondary.md" in str(carried)


# ==============================================================================
# break_on_exit and retry_on_exit are LoopBlockDef fields
# ==============================================================================


class TestLoopBlockDefExitHandleFields:
    """LoopBlockDef must have break_on_exit and retry_on_exit fields.
    BaseBlockDef must not have these fields."""

    def test_loop_block_def_has_break_on_exit(self):
        """LoopBlockDef should have an optional break_on_exit field."""
        assert "break_on_exit" in LoopBlockDef.model_fields, (
            "LoopBlockDef missing 'break_on_exit' field"
        )

    def test_loop_block_def_has_retry_on_exit(self):
        """LoopBlockDef should have an optional retry_on_exit field."""
        assert "retry_on_exit" in LoopBlockDef.model_fields, (
            "LoopBlockDef missing 'retry_on_exit' field"
        )

    def test_base_block_def_does_not_have_break_on_exit(self):
        """BaseBlockDef should not have break_on_exit (loop-specific field)."""
        assert "break_on_exit" not in BaseBlockDef.model_fields, (
            "break_on_exit should be on LoopBlockDef, not BaseBlockDef"
        )

    def test_base_block_def_does_not_have_retry_on_exit(self):
        """BaseBlockDef should not have retry_on_exit (loop-specific field)."""
        assert "retry_on_exit" not in BaseBlockDef.model_fields, (
            "retry_on_exit should be on LoopBlockDef, not BaseBlockDef"
        )

    def test_break_on_exit_defaults_to_none(self):
        """break_on_exit should default to None."""
        block = _validate_block(
            {
                "type": "loop",
                "inner_block_refs": ["draft_step"],
            }
        )
        assert isinstance(block, LoopBlockDef)
        assert block.break_on_exit is None

    def test_retry_on_exit_defaults_to_none(self):
        """retry_on_exit should default to None."""
        block = _validate_block(
            {
                "type": "loop",
                "inner_block_refs": ["draft_step"],
            }
        )
        assert isinstance(block, LoopBlockDef)
        assert block.retry_on_exit is None

    def test_break_on_exit_accepts_string(self):
        """break_on_exit should accept a string value."""
        block = _validate_block(
            {
                "type": "loop",
                "inner_block_refs": ["draft_step"],
                "break_on_exit": "pass",
            }
        )
        assert isinstance(block, LoopBlockDef)
        assert block.break_on_exit == "pass"

    def test_retry_on_exit_accepts_string(self):
        """retry_on_exit should accept a string value."""
        block = _validate_block(
            {
                "type": "loop",
                "inner_block_refs": ["draft_step"],
                "retry_on_exit": "fail",
            }
        )
        assert isinstance(block, LoopBlockDef)
        assert block.retry_on_exit == "fail"

    def test_both_fields_set_simultaneously(self):
        """Both break_on_exit and retry_on_exit can be set at the same time."""
        block = _validate_block(
            {
                "type": "loop",
                "inner_block_refs": ["draft_step"],
                "break_on_exit": "pass",
                "retry_on_exit": "fail",
            }
        )
        assert isinstance(block, LoopBlockDef)
        assert block.break_on_exit == "pass"
        assert block.retry_on_exit == "fail"


# ==============================================================================
# Constructor: LoopBlock accepts break_on_exit / retry_on_exit
# ==============================================================================


class TestLoopBlockConstructorExitHandleParams:
    """LoopBlock constructor must accept break_on_exit and retry_on_exit parameters."""

    def test_constructor_accepts_break_on_exit(self):
        """LoopBlock should accept break_on_exit parameter."""
        loop = LoopBlock(
            block_id="review_loop",
            inner_block_refs=["draft_step"],
            max_rounds=3,
            break_on_exit="pass",
        )
        assert loop.break_on_exit == "pass"

    def test_constructor_accepts_retry_on_exit(self):
        """LoopBlock should accept retry_on_exit parameter."""
        loop = LoopBlock(
            block_id="review_loop",
            inner_block_refs=["draft_step"],
            max_rounds=3,
            retry_on_exit="fail",
        )
        assert loop.retry_on_exit == "fail"

    def test_constructor_defaults_exit_handle_fields_to_none(self):
        """break_on_exit and retry_on_exit should default to None."""
        loop = LoopBlock(
            block_id="review_loop",
            inner_block_refs=["draft_step"],
            max_rounds=3,
        )
        assert loop.break_on_exit is None
        assert loop.retry_on_exit is None


# ==============================================================================
# Parser: break_on_exit / retry_on_exit wired from LoopBlockDef to LoopBlock
# ==============================================================================


class TestParserWiresExitHandleFields:
    """Parser must wire break_on_exit and retry_on_exit from LoopBlockDef
    to LoopBlock constructor via the build() function."""

    def test_build_passes_break_on_exit(self):
        """build() should pass break_on_exit from block_def to LoopBlock."""
        from runsight_core.blocks.loop import build

        block_def = LoopBlockDef(
            type="loop",
            inner_block_refs=["draft_step"],
            max_rounds=3,
            break_on_exit="pass",
        )
        loop = build("review_loop", block_def, {}, None, {})
        assert loop.break_on_exit == "pass"

    def test_build_passes_retry_on_exit(self):
        """build() should pass retry_on_exit from block_def to LoopBlock."""
        from runsight_core.blocks.loop import build

        block_def = LoopBlockDef(
            type="loop",
            inner_block_refs=["draft_step"],
            max_rounds=3,
            retry_on_exit="fail",
        )
        loop = build("review_loop", block_def, {}, None, {})
        assert loop.retry_on_exit == "fail"

    def test_build_defaults_exit_fields_to_none(self):
        """build() with no exit handle fields should produce a LoopBlock with both as None."""
        from runsight_core.blocks.loop import build

        block_def = LoopBlockDef(
            type="loop",
            inner_block_refs=["draft_step"],
            max_rounds=3,
        )
        loop = build("review_loop", block_def, {}, None, {})
        assert loop.break_on_exit is None
        assert loop.retry_on_exit is None

    def test_full_yaml_parsing_with_exit_handle_fields(self):
        """Full YAML parsing should wire break_on_exit and retry_on_exit to LoopBlock."""
        from runsight_core.yaml.parser import parse_workflow_yaml

        yaml_str = """
version: "1.0"
id: loop_exit_handle_fixture
kind: workflow
souls:
  writer:
    id: writer
    kind: soul
    name: Writer
    role: Writer
    system_prompt: "You write."
  reviewer:
    id: reviewer
    kind: soul
    name: Reviewer
    role: Reviewer
    system_prompt: "You review."
blocks:
  write_block:
    type: linear
    soul_ref: writer
  gate_block:
    type: gate
    soul_ref: reviewer
    eval_key: write_block
  loop_block:
    type: loop
    inner_block_refs:
      - write_block
      - gate_block
    max_rounds: 5
    break_on_exit: "pass"
    retry_on_exit: "fail"
workflow:
  id: loop_exit_handle_parse
  kind: workflow
  name: loop_exit_handle_parse
  entry: loop_block
  transitions:
    - from: loop_block
      to:
"""
        wf = parse_workflow_yaml(yaml_str)
        loop = wf.blocks.get("loop_block")
        assert isinstance(loop, LoopBlock)
        assert loop.break_on_exit == "pass"
        assert loop.retry_on_exit == "fail"


# ==============================================================================
# Combined: break_on_exit + retry_on_exit together
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
