"""
Failing tests for RUN-269: LoopBlock break_on_exit / retry_on_exit, remove GateError catch.

LoopBlock reads inner block exit_handle for loop control. No exception catching.

Tests cover:
- AC1: Gate returns exit_handle="fail" -> loop retries (skips remaining inner blocks immediately)
- AC2: Gate returns exit_handle="pass" -> loop exits early (skips remaining inner blocks immediately)
- AC3: Mid-loop exit: gate is block 2 of 3, returns matching exit_handle -> block 3 does NOT execute
- AC4: No GateError import or catch in LoopBlock source
- AC5: break_condition still works for non-exit-based loops
- AC6: max_rounds still enforced with retry_on_exit
- AC7: Loop metadata (rounds_completed, broke_early) still correct with exit_handle control
- AC8: break_on_exit/retry_on_exit fields on LoopBlockDef (not BaseBlockDef)
- Parser: break_on_exit/retry_on_exit wired from LoopBlockDef to LoopBlock constructor
"""

import inspect

import pytest
from pydantic import TypeAdapter
from runsight_core.blocks.base import BaseBlock
from runsight_core.blocks.loop import CarryContextConfig, LoopBlock, LoopBlockDef
from runsight_core.primitives import Task
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.yaml.schema import BaseBlockDef, BlockDef

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class TrackingBlock(BaseBlock):
    """Block that records each call in shared_memory under its block_id."""

    def __init__(self, block_id: str):
        super().__init__(block_id)

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        calls = list(state.shared_memory.get(f"{self.block_id}_calls", []))
        calls.append(len(calls) + 1)
        return state.model_copy(
            update={
                "results": {
                    **state.results,
                    self.block_id: BlockResult(output=f"call_{len(calls)}"),
                },
                "shared_memory": {
                    **state.shared_memory,
                    f"{self.block_id}_calls": calls,
                },
            }
        )


class ExitHandleBlock(BaseBlock):
    """Block that returns a BlockResult with a configurable exit_handle.

    Returns exit_handle=None for the first (threshold - 1) calls,
    then returns the configured exit_handle from call number `threshold` onward.
    """

    def __init__(self, block_id: str, exit_handle: str, threshold: int = 1):
        super().__init__(block_id)
        self._exit_handle = exit_handle
        self._threshold = threshold

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        calls = list(state.shared_memory.get(f"{self.block_id}_calls", []))
        calls.append(len(calls) + 1)
        call_num = len(calls)

        if call_num >= self._threshold:
            handle = self._exit_handle
        else:
            handle = None

        return state.model_copy(
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
                    f"{self.block_id}_calls": calls,
                },
            }
        )


block_adapter = TypeAdapter(BlockDef)


def _validate_block(data: dict):
    """Validate a dict as a BlockDef via the discriminated union."""
    return block_adapter.validate_python(data)


# ==============================================================================
# AC1: Gate returns exit_handle="fail" -> loop retries (next round)
# ==============================================================================


class TestRetryOnExit:
    """When an inner block returns exit_handle matching retry_on_exit, the loop
    should skip remaining inner blocks and proceed to the next round."""

    @pytest.mark.asyncio
    async def test_fail_exit_handle_triggers_retry(self):
        """Gate returning exit_handle='fail' with retry_on_exit='fail' -> skips to next round."""
        worker = TrackingBlock("worker")
        # Gate always returns exit_handle="fail"
        gate = ExitHandleBlock("gate", exit_handle="fail", threshold=1)
        blocks = {"worker": worker, "gate": gate}

        loop = LoopBlock(
            block_id="loop1",
            inner_block_refs=["worker", "gate"],
            max_rounds=3,
            retry_on_exit="fail",
        )
        blocks["loop1"] = loop

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        # Worker and gate should each be called 3 times (once per round)
        worker_calls = result_state.shared_memory.get("worker_calls", [])
        gate_calls = result_state.shared_memory.get("gate_calls", [])
        assert len(worker_calls) == 3, f"Expected 3 worker calls, got {len(worker_calls)}"
        assert len(gate_calls) == 3, f"Expected 3 gate calls, got {len(gate_calls)}"

    @pytest.mark.asyncio
    async def test_retry_on_exit_skips_remaining_inner_blocks(self):
        """When retry_on_exit triggers mid-round, remaining inner blocks are skipped."""
        block_a = TrackingBlock("block_a")
        # Gate returns "fail" immediately -> triggers retry
        gate = ExitHandleBlock("gate", exit_handle="fail", threshold=1)
        block_c = TrackingBlock("block_c")
        blocks = {"block_a": block_a, "gate": gate, "block_c": block_c}

        loop = LoopBlock(
            block_id="loop1",
            inner_block_refs=["block_a", "gate", "block_c"],
            max_rounds=2,
            retry_on_exit="fail",
        )
        blocks["loop1"] = loop

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        # block_a executes each round (before gate), gate executes each round,
        # but block_c should NEVER execute (comes after gate, and gate triggers retry)
        block_a_calls = result_state.shared_memory.get("block_a_calls", [])
        gate_calls = result_state.shared_memory.get("gate_calls", [])
        block_c_calls = result_state.shared_memory.get("block_c_calls", [])

        assert len(block_a_calls) == 2, f"Expected 2 block_a calls, got {len(block_a_calls)}"
        assert len(gate_calls) == 2, f"Expected 2 gate calls, got {len(gate_calls)}"
        assert len(block_c_calls) == 0, (
            f"Expected 0 block_c calls (skipped by retry), got {len(block_c_calls)}"
        )

    @pytest.mark.asyncio
    async def test_non_matching_exit_handle_does_not_trigger_retry(self):
        """An exit_handle that does NOT match retry_on_exit should NOT trigger retry."""
        worker = TrackingBlock("worker")
        # Gate returns exit_handle="pass", but retry_on_exit is "fail"
        gate = ExitHandleBlock("gate", exit_handle="pass", threshold=1)
        blocks = {"worker": worker, "gate": gate}

        loop = LoopBlock(
            block_id="loop1",
            inner_block_refs=["worker", "gate"],
            max_rounds=3,
            retry_on_exit="fail",  # does NOT match "pass"
        )
        blocks["loop1"] = loop

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        # Since "pass" != "fail", retry_on_exit should NOT trigger.
        # The loop should still complete normally without retry logic interfering.
        worker_calls = result_state.shared_memory.get("worker_calls", [])
        assert len(worker_calls) == 3, f"Expected 3 worker calls, got {len(worker_calls)}"


# ==============================================================================
# AC2: Gate returns exit_handle="pass" -> loop exits early
# ==============================================================================


class TestBreakOnExit:
    """When an inner block returns exit_handle matching break_on_exit, the loop
    should exit immediately (broke_early=True)."""

    @pytest.mark.asyncio
    async def test_pass_exit_handle_triggers_break(self):
        """Gate returning exit_handle='pass' with break_on_exit='pass' -> loop exits early."""
        worker = TrackingBlock("worker")
        # Gate returns exit_handle="pass" starting from call 2
        gate = ExitHandleBlock("gate", exit_handle="pass", threshold=2)
        blocks = {"worker": worker, "gate": gate}

        loop = LoopBlock(
            block_id="loop1",
            inner_block_refs=["worker", "gate"],
            max_rounds=5,
            break_on_exit="pass",
        )
        blocks["loop1"] = loop

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        # Round 1: gate returns exit_handle=None (threshold not met) -> continue
        # Round 2: gate returns exit_handle="pass" -> break!
        gate_calls = result_state.shared_memory.get("gate_calls", [])
        worker_calls = result_state.shared_memory.get("worker_calls", [])
        assert len(gate_calls) == 2, f"Expected 2 gate calls, got {len(gate_calls)}"
        assert len(worker_calls) == 2, f"Expected 2 worker calls, got {len(worker_calls)}"

    @pytest.mark.asyncio
    async def test_break_on_exit_immediate_round_1(self):
        """Gate returning matching exit_handle on round 1 -> loop exits after single round."""
        worker = TrackingBlock("worker")
        gate = ExitHandleBlock("gate", exit_handle="pass", threshold=1)
        blocks = {"worker": worker, "gate": gate}

        loop = LoopBlock(
            block_id="loop1",
            inner_block_refs=["worker", "gate"],
            max_rounds=5,
            break_on_exit="pass",
        )
        blocks["loop1"] = loop

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        gate_calls = result_state.shared_memory.get("gate_calls", [])
        assert len(gate_calls) == 1, (
            f"Expected 1 gate call (break on round 1), got {len(gate_calls)}"
        )

    @pytest.mark.asyncio
    async def test_non_matching_exit_handle_does_not_trigger_break(self):
        """An exit_handle that does NOT match break_on_exit should NOT trigger early exit."""
        worker = TrackingBlock("worker")
        # Gate returns "fail", but break_on_exit is "pass"
        gate = ExitHandleBlock("gate", exit_handle="fail", threshold=1)
        blocks = {"worker": worker, "gate": gate}

        loop = LoopBlock(
            block_id="loop1",
            inner_block_refs=["worker", "gate"],
            max_rounds=3,
            break_on_exit="pass",  # does NOT match "fail"
        )
        blocks["loop1"] = loop

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        # All 3 rounds should complete because "fail" != "pass"
        gate_calls = result_state.shared_memory.get("gate_calls", [])
        assert len(gate_calls) == 3, f"Expected 3 gate calls, got {len(gate_calls)}"


# ==============================================================================
# AC3: Mid-loop exit — gate is block 2 of 3, block 3 does NOT execute
# ==============================================================================


class TestMidLoopExit:
    """If gate is block 2 of 3 and returns a matching exit_handle, block 3
    must NOT execute in that round."""

    @pytest.mark.asyncio
    async def test_break_on_exit_mid_loop_skips_block_3(self):
        """break_on_exit: gate is block 2 of 3 -> block 3 never executes on break round."""
        block_a = TrackingBlock("block_a")
        gate = ExitHandleBlock("gate", exit_handle="pass", threshold=1)
        block_c = TrackingBlock("block_c")
        blocks = {"block_a": block_a, "gate": gate, "block_c": block_c}

        loop = LoopBlock(
            block_id="loop1",
            inner_block_refs=["block_a", "gate", "block_c"],
            max_rounds=3,
            break_on_exit="pass",
        )
        blocks["loop1"] = loop

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        # Round 1: block_a runs, gate returns "pass" -> break! block_c never runs
        block_a_calls = result_state.shared_memory.get("block_a_calls", [])
        gate_calls = result_state.shared_memory.get("gate_calls", [])
        block_c_calls = result_state.shared_memory.get("block_c_calls", [])

        assert len(block_a_calls) == 1, f"Expected 1 block_a call, got {len(block_a_calls)}"
        assert len(gate_calls) == 1, f"Expected 1 gate call, got {len(gate_calls)}"
        assert len(block_c_calls) == 0, (
            f"Expected 0 block_c calls (mid-loop break), got {len(block_c_calls)}"
        )

    @pytest.mark.asyncio
    async def test_retry_on_exit_mid_loop_skips_block_3(self):
        """retry_on_exit: gate is block 2 of 3 -> block 3 never executes on retry rounds."""
        block_a = TrackingBlock("block_a")
        # Gate returns "fail" on all calls -> retry every round
        gate = ExitHandleBlock("gate", exit_handle="fail", threshold=1)
        block_c = TrackingBlock("block_c")
        blocks = {"block_a": block_a, "gate": gate, "block_c": block_c}

        loop = LoopBlock(
            block_id="loop1",
            inner_block_refs=["block_a", "gate", "block_c"],
            max_rounds=3,
            retry_on_exit="fail",
        )
        blocks["loop1"] = loop

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        # All 3 rounds: block_a runs, gate returns "fail" -> retry, block_c skipped
        block_a_calls = result_state.shared_memory.get("block_a_calls", [])
        gate_calls = result_state.shared_memory.get("gate_calls", [])
        block_c_calls = result_state.shared_memory.get("block_c_calls", [])

        assert len(block_a_calls) == 3, f"Expected 3 block_a calls, got {len(block_a_calls)}"
        assert len(gate_calls) == 3, f"Expected 3 gate calls, got {len(gate_calls)}"
        assert len(block_c_calls) == 0, (
            f"Expected 0 block_c calls (retry skips remaining), got {len(block_c_calls)}"
        )

    @pytest.mark.asyncio
    async def test_mid_loop_break_after_retry_rounds(self):
        """Gate fails first 2 rounds (retry), passes on round 3 (break). Block_c never runs."""
        block_a = TrackingBlock("block_a")
        # Gate returns "fail" for calls 1-2, "pass" on call 3
        gate = ExitHandleBlock("gate", exit_handle="pass", threshold=3)
        # For calls before threshold, exit_handle=None — we need a more nuanced mock
        block_c = TrackingBlock("block_c")
        blocks = {"block_a": block_a, "gate": gate, "block_c": block_c}

        loop = LoopBlock(
            block_id="loop1",
            inner_block_refs=["block_a", "gate", "block_c"],
            max_rounds=5,
            break_on_exit="pass",
        )
        blocks["loop1"] = loop

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        # Rounds 1-2: gate exit_handle=None -> block_c runs normally
        # Round 3: gate exit_handle="pass" -> break! block_c skipped this round
        block_a_calls = result_state.shared_memory.get("block_a_calls", [])
        gate_calls = result_state.shared_memory.get("gate_calls", [])
        block_c_calls = result_state.shared_memory.get("block_c_calls", [])

        assert len(block_a_calls) == 3, f"Expected 3 block_a calls, got {len(block_a_calls)}"
        assert len(gate_calls) == 3, f"Expected 3 gate calls, got {len(gate_calls)}"
        # block_c runs on rounds 1-2 (no exit_handle match), but NOT round 3 (break)
        assert len(block_c_calls) == 2, (
            f"Expected 2 block_c calls (ran rounds 1-2, skipped round 3), got {len(block_c_calls)}"
        )


# ==============================================================================
# AC4: No GateError import or catch in LoopBlock source
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
# AC5: break_condition still works for non-exit-based loops
# ==============================================================================


class TestBreakConditionStillWorks:
    """break_condition (the original condition-based loop exit) must still work
    independently of break_on_exit/retry_on_exit."""

    @pytest.mark.asyncio
    async def test_break_condition_without_exit_handle_fields(self):
        """break_condition should work even when break_on_exit/retry_on_exit are None."""
        from runsight_core.conditions.engine import Condition

        inner = TrackingBlock("inner")
        blocks = {"inner": inner}

        # Break when output contains "call_3"
        break_cond = Condition(eval_key="inner", operator="contains", value="call_3")

        loop = LoopBlock(
            block_id="loop1",
            inner_block_refs=["inner"],
            max_rounds=5,
            break_condition=break_cond,
        )
        blocks["loop1"] = loop

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        calls = result_state.shared_memory.get("inner_calls", [])
        assert len(calls) == 3, f"Expected 3 calls (break on call_3), got {len(calls)}"

    @pytest.mark.asyncio
    async def test_break_condition_coexists_with_break_on_exit(self):
        """Both break_condition and break_on_exit can be set. break_on_exit should
        take precedence when it fires first (checked per-block, not per-round)."""
        from runsight_core.conditions.engine import Condition

        worker = TrackingBlock("worker")
        # Gate returns exit_handle="pass" on call 2
        gate = ExitHandleBlock("gate", exit_handle="pass", threshold=2)
        blocks = {"worker": worker, "gate": gate}

        # break_condition would fire on round 5 (never reached)
        break_cond = Condition(eval_key="gate", operator="contains", value="NEVER_MATCHES")

        loop = LoopBlock(
            block_id="loop1",
            inner_block_refs=["worker", "gate"],
            max_rounds=5,
            break_condition=break_cond,
            break_on_exit="pass",
        )
        blocks["loop1"] = loop

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        # break_on_exit="pass" should fire on round 2 (gate threshold=2)
        gate_calls = result_state.shared_memory.get("gate_calls", [])
        assert len(gate_calls) == 2, (
            f"Expected 2 gate calls (break_on_exit fired), got {len(gate_calls)}"
        )


# ==============================================================================
# AC6: max_rounds still enforced with retry_on_exit
# ==============================================================================


class TestMaxRoundsEnforced:
    """max_rounds must still be respected even when retry_on_exit is active."""

    @pytest.mark.asyncio
    async def test_max_rounds_caps_retry_on_exit(self):
        """If retry_on_exit fires every round, loop must still stop at max_rounds."""
        worker = TrackingBlock("worker")
        # Gate always returns "fail" -> retry_on_exit fires every round
        gate = ExitHandleBlock("gate", exit_handle="fail", threshold=1)
        blocks = {"worker": worker, "gate": gate}

        loop = LoopBlock(
            block_id="loop1",
            inner_block_refs=["worker", "gate"],
            max_rounds=4,
            retry_on_exit="fail",
        )
        blocks["loop1"] = loop

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        gate_calls = result_state.shared_memory.get("gate_calls", [])
        assert len(gate_calls) == 4, (
            f"Expected exactly 4 gate calls (max_rounds), got {len(gate_calls)}"
        )

    @pytest.mark.asyncio
    async def test_max_rounds_1_with_retry_on_exit(self):
        """max_rounds=1 should execute only once even with retry_on_exit."""
        worker = TrackingBlock("worker")
        gate = ExitHandleBlock("gate", exit_handle="fail", threshold=1)
        blocks = {"worker": worker, "gate": gate}

        loop = LoopBlock(
            block_id="loop1",
            inner_block_refs=["worker", "gate"],
            max_rounds=1,
            retry_on_exit="fail",
        )
        blocks["loop1"] = loop

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        gate_calls = result_state.shared_memory.get("gate_calls", [])
        assert len(gate_calls) == 1, f"Expected 1 gate call (max_rounds=1), got {len(gate_calls)}"


# ==============================================================================
# AC7: Loop metadata (rounds_completed, broke_early) correct with exit_handle
# ==============================================================================


class TestLoopMetadataWithExitHandle:
    """Loop metadata in shared_memory must correctly reflect exit_handle behavior."""

    @pytest.mark.asyncio
    async def test_metadata_on_break_on_exit(self):
        """When break_on_exit fires, metadata should show broke_early=True and correct rounds."""
        worker = TrackingBlock("worker")
        gate = ExitHandleBlock("gate", exit_handle="pass", threshold=2)
        blocks = {"worker": worker, "gate": gate}

        loop = LoopBlock(
            block_id="loop1",
            inner_block_refs=["worker", "gate"],
            max_rounds=5,
            break_on_exit="pass",
        )
        blocks["loop1"] = loop

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        meta = result_state.shared_memory.get("__loop__loop1")
        assert meta is not None, "Loop metadata not found in shared_memory"
        assert meta["broke_early"] is True
        assert meta["rounds_completed"] == 2

    @pytest.mark.asyncio
    async def test_metadata_on_retry_exhaustion(self):
        """When retry_on_exit fires every round and max_rounds exhausted,
        metadata should show broke_early=False."""
        worker = TrackingBlock("worker")
        gate = ExitHandleBlock("gate", exit_handle="fail", threshold=1)
        blocks = {"worker": worker, "gate": gate}

        loop = LoopBlock(
            block_id="loop1",
            inner_block_refs=["worker", "gate"],
            max_rounds=3,
            retry_on_exit="fail",
        )
        blocks["loop1"] = loop

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        meta = result_state.shared_memory.get("__loop__loop1")
        assert meta is not None, "Loop metadata not found in shared_memory"
        assert meta["broke_early"] is False
        assert meta["rounds_completed"] == 3

    @pytest.mark.asyncio
    async def test_metadata_break_reason_on_exit_handle(self):
        """When break_on_exit fires, break_reason should indicate exit_handle-based break."""
        worker = TrackingBlock("worker")
        gate = ExitHandleBlock("gate", exit_handle="pass", threshold=1)
        blocks = {"worker": worker, "gate": gate}

        loop = LoopBlock(
            block_id="loop1",
            inner_block_refs=["worker", "gate"],
            max_rounds=5,
            break_on_exit="pass",
        )
        blocks["loop1"] = loop

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        meta = result_state.shared_memory.get("__loop__loop1")
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
        self._trace_path = trace_path

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        calls = list(state.shared_memory.get(f"{self.block_id}_calls", []))
        calls.append(len(calls) + 1)
        call_num = len(calls)
        return state.model_copy(
            update={
                "results": {
                    **state.results,
                    self.block_id: BlockResult(
                        output=f'{{"trace_path":"{self._trace_path}","round":{call_num}}}'
                    ),
                },
                "shared_memory": {
                    **state.shared_memory,
                    f"{self.block_id}_calls": calls,
                },
            }
        )


class TestCarryContextWithExitHandle:
    """carry_context must still propagate on break/retry exit-handle paths."""

    @pytest.mark.asyncio
    async def test_retry_on_exit_still_updates_carry_context_and_task_context(self):
        source = ContextPayloadBlock(
            "source",
            trace_path="custom/outputs/provider-trace-primary.md",
        )
        gate = ExitHandleBlock("gate", exit_handle="fail", threshold=1)
        blocks = {"source": source, "gate": gate}

        loop = LoopBlock(
            block_id="loop1",
            inner_block_refs=["source", "gate"],
            max_rounds=2,
            retry_on_exit="fail",
            carry_context=CarryContextConfig(
                mode="all",
                source_blocks=["source"],
                inject_as="ctx",
            ),
        )
        blocks["loop1"] = loop

        state = WorkflowState(
            current_task=Task(id="task-1", instruction="write trace"),
        )
        result_state = await loop.execute(state, blocks=blocks)

        carried = result_state.shared_memory.get("ctx")
        assert isinstance(carried, list)
        assert len(carried) == 2
        assert "provider-trace-primary.md" in str(carried)
        assert result_state.current_task is not None
        assert "provider-trace-primary.md" in str(result_state.current_task.context)

    @pytest.mark.asyncio
    async def test_break_on_exit_still_updates_carry_context_and_task_context(self):
        source = ContextPayloadBlock(
            "source",
            trace_path="custom/outputs/provider-trace-secondary.md",
        )
        gate = ExitHandleBlock("gate", exit_handle="pass", threshold=1)
        blocks = {"source": source, "gate": gate}

        loop = LoopBlock(
            block_id="loop1",
            inner_block_refs=["source", "gate"],
            max_rounds=3,
            break_on_exit="pass",
            carry_context=CarryContextConfig(
                mode="last",
                source_blocks=["source"],
                inject_as="ctx",
            ),
        )
        blocks["loop1"] = loop

        state = WorkflowState(
            current_task=Task(id="task-2", instruction="write trace"),
        )
        result_state = await loop.execute(state, blocks=blocks)

        carried = result_state.shared_memory.get("ctx")
        assert isinstance(carried, dict)
        assert "provider-trace-secondary.md" in str(carried)
        assert result_state.current_task is not None
        assert "provider-trace-secondary.md" in str(result_state.current_task.context)


# ==============================================================================
# AC8: break_on_exit / retry_on_exit fields on LoopBlockDef (not BaseBlockDef)
# ==============================================================================


class TestLoopBlockDefExitHandleFields:
    """LoopBlockDef must have break_on_exit and retry_on_exit fields.
    BaseBlockDef must NOT have these fields."""

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
        """BaseBlockDef should NOT have break_on_exit (loop-specific field)."""
        assert "break_on_exit" not in BaseBlockDef.model_fields, (
            "break_on_exit should be on LoopBlockDef, not BaseBlockDef"
        )

    def test_base_block_def_does_not_have_retry_on_exit(self):
        """BaseBlockDef should NOT have retry_on_exit (loop-specific field)."""
        assert "retry_on_exit" not in BaseBlockDef.model_fields, (
            "retry_on_exit should be on LoopBlockDef, not BaseBlockDef"
        )

    def test_break_on_exit_defaults_to_none(self):
        """break_on_exit should default to None."""
        block = _validate_block(
            {
                "type": "loop",
                "inner_block_refs": ["a"],
            }
        )
        assert isinstance(block, LoopBlockDef)
        assert block.break_on_exit is None

    def test_retry_on_exit_defaults_to_none(self):
        """retry_on_exit should default to None."""
        block = _validate_block(
            {
                "type": "loop",
                "inner_block_refs": ["a"],
            }
        )
        assert isinstance(block, LoopBlockDef)
        assert block.retry_on_exit is None

    def test_break_on_exit_accepts_string(self):
        """break_on_exit should accept a string value."""
        block = _validate_block(
            {
                "type": "loop",
                "inner_block_refs": ["a"],
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
                "inner_block_refs": ["a"],
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
                "inner_block_refs": ["a"],
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
            block_id="loop1",
            inner_block_refs=["a"],
            max_rounds=3,
            break_on_exit="pass",
        )
        assert loop.break_on_exit == "pass"

    def test_constructor_accepts_retry_on_exit(self):
        """LoopBlock should accept retry_on_exit parameter."""
        loop = LoopBlock(
            block_id="loop1",
            inner_block_refs=["a"],
            max_rounds=3,
            retry_on_exit="fail",
        )
        assert loop.retry_on_exit == "fail"

    def test_constructor_defaults_exit_handle_fields_to_none(self):
        """break_on_exit and retry_on_exit should default to None."""
        loop = LoopBlock(
            block_id="loop1",
            inner_block_refs=["a"],
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
            inner_block_refs=["a"],
            max_rounds=3,
            break_on_exit="pass",
        )
        loop = build("loop1", block_def, {}, None, {})
        assert loop.break_on_exit == "pass"

    def test_build_passes_retry_on_exit(self):
        """build() should pass retry_on_exit from block_def to LoopBlock."""
        from runsight_core.blocks.loop import build

        block_def = LoopBlockDef(
            type="loop",
            inner_block_refs=["a"],
            max_rounds=3,
            retry_on_exit="fail",
        )
        loop = build("loop1", block_def, {}, None, {})
        assert loop.retry_on_exit == "fail"

    def test_build_defaults_exit_fields_to_none(self):
        """build() with no exit handle fields should produce a LoopBlock with both as None."""
        from runsight_core.blocks.loop import build

        block_def = LoopBlockDef(
            type="loop",
            inner_block_refs=["a"],
            max_rounds=3,
        )
        loop = build("loop1", block_def, {}, None, {})
        assert loop.break_on_exit is None
        assert loop.retry_on_exit is None

    def test_full_yaml_parsing_with_exit_handle_fields(self):
        """Full YAML parsing should wire break_on_exit and retry_on_exit to LoopBlock."""
        from runsight_core.yaml.parser import parse_workflow_yaml

        yaml_str = """
version: "1.0"
id: inline_test_workflow
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
  id: exit_handle_parse_test
  kind: workflow
  name: exit_handle_parse_test
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
                self._pass_on_call = pass_on_call

            async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
                calls = list(state.shared_memory.get(f"{self.block_id}_calls", []))
                calls.append(len(calls) + 1)
                call_num = len(calls)

                if call_num >= self._pass_on_call:
                    handle = "pass"
                else:
                    handle = "fail"

                return state.model_copy(
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
                            f"{self.block_id}_calls": calls,
                        },
                    }
                )

        worker = TrackingBlock("worker")
        gate = PhasedGate("gate", pass_on_call=3)
        blocks = {"worker": worker, "gate": gate}

        loop = LoopBlock(
            block_id="loop1",
            inner_block_refs=["worker", "gate"],
            max_rounds=5,
            break_on_exit="pass",
            retry_on_exit="fail",
        )
        blocks["loop1"] = loop

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        # Round 1: gate="fail" -> retry
        # Round 2: gate="fail" -> retry
        # Round 3: gate="pass" -> break!
        gate_calls = result_state.shared_memory.get("gate_calls", [])
        assert len(gate_calls) == 3, f"Expected 3 gate calls, got {len(gate_calls)}"

        meta = result_state.shared_memory.get("__loop__loop1")
        assert meta is not None
        assert meta["broke_early"] is True
        assert meta["rounds_completed"] == 3
