"""
Failing tests for RUN-876: LoopBlock — delete carry_context-to-current_task hack.

Acceptance Criteria:
- LoopBlock no longer references state.current_task
- Carry context still flows through shared_memory to inner blocks
- Loop-based E2E tests pass

Current hack (lines ~159-216 in loop.py):
    if state.current_task is not None:
        ... serialise carry_context_str ...
        ... call fit_to_budget ...
        state = state.model_copy(update={"current_task": state.current_task.model_copy(...)})

After fix:
- Lines 159-216 deleted entirely
- No `current_task` references in loop.py
- Carry context only flows via shared_memory (which LinearBlock reads via _resolved_inputs)
"""

import inspect

import pytest
from conftest import block_output_from_state, execute_loop_for_test
from runsight_core.blocks.base import BaseBlock
from runsight_core.blocks.loop import CarryContextConfig, LoopBlock
from runsight_core.state import BlockResult, WorkflowState

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


class EchoBlock(BaseBlock):
    """Block that writes a fixed string to results."""

    def __init__(self, block_id: str, output: str = "echo_output"):
        super().__init__(block_id)
        self.context_access = "all"
        self._output = output

    async def execute(self, ctx):
        state = ctx.state_snapshot
        next_state = state.model_copy(
            update={
                "results": {
                    **state.results,
                    self.block_id: BlockResult(output=self._output),
                }
            }
        )
        return block_output_from_state(self.block_id, state, next_state)


class SharedMemoryReaderBlock(BaseBlock):
    """Block that records what it reads from shared_memory each round."""

    def __init__(self, block_id: str, key: str = "previous_round_context"):
        super().__init__(block_id)
        self.context_access = "all"
        self.key = key
        self.seen: list = []

    async def execute(self, ctx):
        state = ctx.state_snapshot
        value = state.shared_memory.get(self.key)
        self.seen.append(value)
        next_state = state.model_copy(
            update={
                "results": {
                    **state.results,
                    self.block_id: BlockResult(output=f"round_{len(self.seen)}"),
                }
            }
        )
        return block_output_from_state(self.block_id, state, next_state)


class AccumulatingWriterBlock(BaseBlock):
    """Writes incrementing output each round so carry_context accumulates."""

    def __init__(self, block_id: str):
        super().__init__(block_id)
        self.context_access = "all"
        self._round = 0

    async def execute(self, ctx):
        state = ctx.state_snapshot
        self._round += 1
        next_state = state.model_copy(
            update={
                "results": {
                    **state.results,
                    self.block_id: BlockResult(output=f"round_{self._round}_output"),
                }
            }
        )
        return block_output_from_state(self.block_id, state, next_state)


def _make_loop(
    block_id: str,
    inner_refs: list,
    max_rounds: int = 3,
    carry: CarryContextConfig | None = None,
) -> LoopBlock:
    return LoopBlock(
        block_id=block_id,
        inner_block_refs=inner_refs,
        max_rounds=max_rounds,
        carry_context=carry,
    )


# ===========================================================================
# 1. Source-level: no current_task reference in loop.py
# ===========================================================================


class TestNoCurrentTaskReferenceInSource:
    """loop.py must not reference state.current_task anywhere after the fix."""

    def test_loop_source_does_not_reference_current_task(self):
        """loop.py source must not contain the string 'current_task'."""
        import runsight_core.blocks.loop as loop_module

        source = inspect.getsource(loop_module)
        assert "current_task" not in source, (
            "loop.py still references 'current_task'. The hack at lines 159-216 must be deleted."
        )

    def test_loop_source_does_not_import_fit_to_budget(self):
        """loop.py must not import fit_to_budget (only used in the hack)."""
        import runsight_core.blocks.loop as loop_module

        source = inspect.getsource(loop_module)
        # fit_to_budget was imported inside the hack block — must be gone
        assert "fit_to_budget" not in source, (
            "loop.py still references 'fit_to_budget'. "
            "This was only used in the current_task hack (lines 159-216)."
        )

    def test_loop_source_does_not_import_context_budget_request(self):
        """loop.py must not import ContextBudgetRequest (only used in the hack)."""
        import runsight_core.blocks.loop as loop_module

        source = inspect.getsource(loop_module)
        assert "ContextBudgetRequest" not in source, (
            "loop.py still references 'ContextBudgetRequest'. "
            "This was only used in the current_task hack (lines 159-216)."
        )

    def test_loop_source_does_not_import_litellm_token_counter(self):
        """loop.py must not import litellm_token_counter (only used in the hack)."""
        import runsight_core.blocks.loop as loop_module

        source = inspect.getsource(loop_module)
        assert "litellm_token_counter" not in source, (
            "loop.py still references 'litellm_token_counter'. "
            "This was only used in the current_task hack (lines 159-216)."
        )

    def test_loop_source_does_not_mutate_task_context(self):
        """loop.py must not contain task_context variable or .context update."""
        import runsight_core.blocks.loop as loop_module

        source = inspect.getsource(loop_module)
        assert "task_context" not in source, (
            "loop.py still has 'task_context'. "
            "The hack that mutates current_task.context must be removed."
        )

    def test_loop_source_does_not_contain_carry_context_str(self):
        """loop.py must not contain carry_context_str variable (part of the hack)."""
        import runsight_core.blocks.loop as loop_module

        source = inspect.getsource(loop_module)
        assert "carry_context_str" not in source, (
            "loop.py still has 'carry_context_str'. "
            "This was part of the current_task mutation hack."
        )


# ===========================================================================
# 2. LoopBlock works when state.current_task is None
# ===========================================================================


class TestLoopWorksWithNoneCurrentTask:
    """LoopBlock must run without error when state.current_task is None."""

    @pytest.mark.asyncio
    async def test_loop_runs_when_current_task_is_none(self):
        """LoopBlock must complete successfully when current_task is None."""
        inner = EchoBlock("inner1", output="result")
        loop = _make_loop("loop1", ["inner1"], max_rounds=2)
        state = WorkflowState()

        result_state = await execute_loop_for_test(loop, state, blocks={"inner1": inner})

        assert "loop1" in result_state.results
        assert result_state.results["loop1"].output == "completed_2_rounds"

    @pytest.mark.asyncio
    async def test_loop_with_carry_context_works_when_current_task_is_none(self):
        """LoopBlock with carry_context must work when current_task is None."""
        inner = EchoBlock("writer", output="draft v1")
        carry = CarryContextConfig(enabled=True, mode="last", inject_as="previous_round_context")
        loop = _make_loop("loop1", ["writer"], max_rounds=2, carry=carry)
        state = WorkflowState()

        result_state = await execute_loop_for_test(loop, state, blocks={"writer": inner})

        assert "loop1" in result_state.results
        # carry_context must land in shared_memory regardless of current_task
        assert "previous_round_context" in result_state.shared_memory

    @pytest.mark.asyncio
    async def test_loop_does_not_raise_on_none_current_task_with_carry_context_all(self):
        """mode='all' with current_task=None must not raise."""
        inner = EchoBlock("writer", output="text")
        carry = CarryContextConfig(enabled=True, mode="all", inject_as="all_rounds")
        loop = _make_loop("loop1", ["writer"], max_rounds=3, carry=carry)
        state = WorkflowState()

        result_state = await execute_loop_for_test(loop, state, blocks={"writer": inner})

        assert "all_rounds" in result_state.shared_memory
        assert isinstance(result_state.shared_memory["all_rounds"], list)
        assert len(result_state.shared_memory["all_rounds"]) == 3


# ===========================================================================
# 3. carry_context still injects into shared_memory (canonical path preserved)
# ===========================================================================


class TestCarryContextFlowsViaSharedMemory:
    """The canonical shared_memory injection (lines ~150-157) must still work."""

    @pytest.mark.asyncio
    async def test_carry_context_mode_last_injects_into_shared_memory(self):
        """After each round, inject_as key is set in shared_memory with last round outputs."""
        inner = EchoBlock("writer", output="writer_output")
        carry = CarryContextConfig(enabled=True, mode="last", inject_as="previous_round_context")
        loop = _make_loop("loop1", ["writer"], max_rounds=2, carry=carry)
        state = WorkflowState()

        result_state = await execute_loop_for_test(loop, state, blocks={"writer": inner})

        assert "previous_round_context" in result_state.shared_memory
        ctx = result_state.shared_memory["previous_round_context"]
        # mode=last: dict of {block_id: output}
        assert isinstance(ctx, dict)
        assert "writer" in ctx
        assert ctx["writer"] == "writer_output"

    @pytest.mark.asyncio
    async def test_carry_context_mode_all_accumulates_history(self):
        """mode='all' shared_memory value grows to a list with one entry per round."""
        inner = AccumulatingWriterBlock("writer")
        carry = CarryContextConfig(enabled=True, mode="all", inject_as="round_history")
        loop = _make_loop("loop1", ["writer"], max_rounds=3, carry=carry)
        state = WorkflowState()

        result_state = await execute_loop_for_test(loop, state, blocks={"writer": inner})

        history = result_state.shared_memory.get("round_history")
        assert isinstance(history, list), (
            f"Expected list for mode='all', got {type(history)}: {history}"
        )
        assert len(history) == 3, f"Expected 3 rounds in history, got {len(history)}"

    @pytest.mark.asyncio
    async def test_carry_context_disabled_does_not_inject(self):
        """carry_context.enabled=False: inject_as key must NOT appear in shared_memory."""
        inner = EchoBlock("writer", output="output")
        carry = CarryContextConfig(enabled=False, inject_as="should_not_appear")
        loop = _make_loop("loop1", ["writer"], max_rounds=2, carry=carry)
        state = WorkflowState()

        result_state = await execute_loop_for_test(loop, state, blocks={"writer": inner})

        assert "should_not_appear" not in result_state.shared_memory

    @pytest.mark.asyncio
    async def test_carry_context_none_does_not_inject(self):
        """carry_context=None: no context key injected at all."""
        inner = EchoBlock("writer", output="output")
        loop = _make_loop("loop1", ["writer"], max_rounds=2, carry=None)
        state = WorkflowState()

        result_state = await execute_loop_for_test(loop, state, blocks={"writer": inner})

        assert "previous_round_context" not in result_state.shared_memory

    @pytest.mark.asyncio
    async def test_carry_context_inject_as_custom_key(self):
        """Custom inject_as key appears in shared_memory."""
        inner = EchoBlock("critic", output="critique")
        carry = CarryContextConfig(enabled=True, mode="last", inject_as="critic_feedback")
        loop = _make_loop("loop1", ["critic"], max_rounds=1, carry=carry)
        state = WorkflowState()

        result_state = await execute_loop_for_test(loop, state, blocks={"critic": inner})

        assert "critic_feedback" in result_state.shared_memory


# ===========================================================================
# 4. Inner blocks receive carry_context via shared_memory (not current_task)
# ===========================================================================


class TestInnerBlocksReceiveCarryViaSharedMemory:
    """Inner blocks must see carry_context in shared_memory, not in current_task."""

    @pytest.mark.asyncio
    async def test_inner_block_reads_carry_context_from_shared_memory_round2(self):
        """On round 2, inner block sees previous round's output in shared_memory."""
        reader = SharedMemoryReaderBlock("reader", key="previous_round_context")
        carry = CarryContextConfig(enabled=True, mode="last", inject_as="previous_round_context")
        loop = _make_loop("loop1", ["reader"], max_rounds=2, carry=carry)
        state = WorkflowState()

        await execute_loop_for_test(loop, state, blocks={"reader": reader})

        # Round 1: no previous context yet
        assert reader.seen[0] is None, (
            f"Round 1 should see None (no prior context), got: {reader.seen[0]}"
        )
        # Round 2: must see the context injected from round 1
        assert reader.seen[1] is not None, (
            "Round 2 must see carry_context from round 1 in shared_memory"
        )

    @pytest.mark.asyncio
    async def test_inner_block_does_not_rely_on_current_task_for_context(self):
        """After Task deletion, carry_context must flow via shared_memory only.
        Inner blocks do not see current_task at all (it's been removed from WorkflowState)."""
        shared_memory_values_seen: list = []

        class ContextSpyBlock(BaseBlock):
            async def execute(self, ctx):
                state = ctx.state_snapshot
                shared_memory_values_seen.append(state.shared_memory.get("previous_round_context"))
                next_state = state.model_copy(
                    update={
                        "results": {
                            **state.results,
                            self.block_id: BlockResult(output="spy_output"),
                        }
                    }
                )
                return block_output_from_state(self.block_id, state, next_state)

        spy = ContextSpyBlock("spy")
        spy.context_access = "all"
        carry = CarryContextConfig(enabled=True, mode="last", inject_as="previous_round_context")
        loop = _make_loop("loop1", ["spy"], max_rounds=3, carry=carry)
        state = WorkflowState()

        await execute_loop_for_test(loop, state, blocks={"spy": spy})

        # Round 1: no previous context yet
        assert shared_memory_values_seen[0] is None
        # Rounds 2+: carry_context must appear in shared_memory
        for round_idx, val in enumerate(shared_memory_values_seen[1:], start=2):
            assert val is not None, f"Round {round_idx}: carry_context missing from shared_memory"

    @pytest.mark.asyncio
    async def test_carry_context_visible_in_shared_memory_not_task(self):
        """carry_context data appears in shared_memory key (current_task is deleted)."""
        inner = EchoBlock("writer", output="important output")
        carry = CarryContextConfig(enabled=True, mode="last", inject_as="ctx_key")
        loop = _make_loop("loop1", ["writer"], max_rounds=2, carry=carry)
        state = WorkflowState()

        result_state = await execute_loop_for_test(loop, state, blocks={"writer": inner})

        # Carry context must be in shared_memory
        assert "ctx_key" in result_state.shared_memory
        assert result_state.shared_memory["ctx_key"] is not None


# ===========================================================================
# 5. Multiple rounds — carry_context accumulates correctly via shared_memory
# ===========================================================================


class TestMultipleRoundsCarryAccumulation:
    """carry_context must correctly accumulate across multiple rounds via shared_memory."""

    @pytest.mark.asyncio
    async def test_mode_last_carries_most_recent_round_only(self):
        """mode='last': final shared_memory value reflects the last round, not earlier ones."""
        writer = AccumulatingWriterBlock("writer")
        carry = CarryContextConfig(enabled=True, mode="last", inject_as="last_ctx")
        loop = _make_loop("loop1", ["writer"], max_rounds=3, carry=carry)
        state = WorkflowState()

        result_state = await execute_loop_for_test(loop, state, blocks={"writer": writer})

        last_ctx = result_state.shared_memory["last_ctx"]
        assert isinstance(last_ctx, dict)
        # mode=last after 3 rounds: value should reflect round_3_output
        assert last_ctx.get("writer") == "round_3_output", (
            f"mode='last' after 3 rounds must show round_3_output, got: {last_ctx}"
        )

    @pytest.mark.asyncio
    async def test_mode_all_grows_by_one_per_round(self):
        """mode='all': history list has exactly max_rounds entries after completion."""
        writer = AccumulatingWriterBlock("writer")
        carry = CarryContextConfig(enabled=True, mode="all", inject_as="history")
        loop = _make_loop("loop1", ["writer"], max_rounds=4, carry=carry)
        state = WorkflowState()

        result_state = await execute_loop_for_test(loop, state, blocks={"writer": writer})

        history = result_state.shared_memory["history"]
        assert len(history) == 4, f"Expected 4 history entries, got {len(history)}: {history}"

    @pytest.mark.asyncio
    async def test_mode_all_round_entries_contain_correct_outputs(self):
        """mode='all': each entry in history list contains the block output for that round."""
        writer = AccumulatingWriterBlock("writer")
        carry = CarryContextConfig(enabled=True, mode="all", inject_as="history")
        loop = _make_loop("loop1", ["writer"], max_rounds=3, carry=carry)
        state = WorkflowState()

        result_state = await execute_loop_for_test(loop, state, blocks={"writer": writer})

        history = result_state.shared_memory["history"]
        assert history[0]["writer"] == "round_1_output", f"Round 1 wrong: {history[0]}"
        assert history[1]["writer"] == "round_2_output", f"Round 2 wrong: {history[1]}"
        assert history[2]["writer"] == "round_3_output", f"Round 3 wrong: {history[2]}"

    @pytest.mark.asyncio
    async def test_carry_context_from_round1_visible_to_inner_block_in_round2(self):
        """Inner block in round 2 must see carry_context populated from round 1."""
        seen_in_round: dict = {}

        class RoundCapture(BaseBlock):
            def __init__(self, bid):
                super().__init__(bid)
                self.context_access = "all"
                self._r = 0

            async def execute(self, ctx):
                state = ctx.state_snapshot
                self._r += 1
                seen_in_round[self._r] = state.shared_memory.get("prev", "NOT_SET")
                next_state = state.model_copy(
                    update={
                        "results": {
                            **state.results,
                            self.block_id: BlockResult(output=f"out{self._r}"),
                        }
                    }
                )
                return block_output_from_state(self.block_id, state, next_state)

        capturer = RoundCapture("capturer")
        carry = CarryContextConfig(enabled=True, mode="last", inject_as="prev")
        loop = _make_loop("loop1", ["capturer"], max_rounds=3, carry=carry)
        state = WorkflowState()

        await execute_loop_for_test(loop, state, blocks={"capturer": capturer})

        # Round 1: nothing carried yet
        assert seen_in_round[1] == "NOT_SET", (
            f"Round 1 should not have 'prev' in shared_memory, got: {seen_in_round[1]}"
        )
        # Round 2: carry from round 1
        assert seen_in_round[2] != "NOT_SET", "Round 2 must see carry_context from round 1"
        round2_ctx = seen_in_round[2]
        assert isinstance(round2_ctx, dict)
        assert round2_ctx.get("capturer") == "out1", (
            f"Round 2 carry must reflect round 1 output 'out1', got: {round2_ctx}"
        )
        # Round 3: carry from round 2
        assert seen_in_round[3] != "NOT_SET"
        round3_ctx = seen_in_round[3]
        assert round3_ctx.get("capturer") == "out2", (
            f"Round 3 carry must reflect round 2 output 'out2', got: {round3_ctx}"
        )


# ===========================================================================
# 6. current_task not modified at all — state is immutable through the loop
# ===========================================================================


class TestCurrentTaskNotModified:
    """After Task deletion, LoopBlock has no current_task to modify.
    These tests verify loop completes correctly with carry_context config."""

    @pytest.mark.asyncio
    async def test_current_task_unchanged_after_loop_with_carry_context(self):
        """Loop with carry_context completes all rounds and injects into shared_memory."""
        inner = EchoBlock("inner1", output="some output")
        carry = CarryContextConfig(enabled=True, mode="last", inject_as="ctx")
        loop = _make_loop("loop1", ["inner1"], max_rounds=3, carry=carry)
        state = WorkflowState()

        result_state = await execute_loop_for_test(loop, state, blocks={"inner1": inner})

        meta = result_state.shared_memory.get("__loop__loop1", {})
        assert meta.get("rounds_completed") == 3, "Loop must complete all 3 rounds"
        assert "ctx" in result_state.shared_memory, (
            "carry_context must be injected into shared_memory['ctx']"
        )

    @pytest.mark.asyncio
    async def test_current_task_unchanged_with_mode_all(self):
        """mode='all' loop completes all rounds and injects list into shared_memory."""
        inner = EchoBlock("inner1", output="output")
        carry = CarryContextConfig(enabled=True, mode="all", inject_as="history")
        loop = _make_loop("loop1", ["inner1"], max_rounds=3, carry=carry)
        state = WorkflowState()

        result_state = await execute_loop_for_test(loop, state, blocks={"inner1": inner})

        meta = result_state.shared_memory.get("__loop__loop1", {})
        assert meta.get("rounds_completed") == 3
        assert isinstance(result_state.shared_memory.get("history"), list), (
            "mode='all' must store a list in shared_memory"
        )

    @pytest.mark.asyncio
    async def test_loop_without_current_task_completes_normally(self):
        """Loop with no current_task and carry_context enabled must complete all rounds."""
        inner = EchoBlock("inner1", output="result")
        carry = CarryContextConfig(enabled=True, mode="last", inject_as="ctx")
        loop = _make_loop("loop1", ["inner1"], max_rounds=5, carry=carry)
        state = WorkflowState()  # no current_task

        result_state = await execute_loop_for_test(loop, state, blocks={"inner1": inner})

        meta = result_state.shared_memory.get("__loop__loop1", {})
        assert meta.get("rounds_completed") == 5
        assert meta.get("break_reason") == "max_rounds reached"
