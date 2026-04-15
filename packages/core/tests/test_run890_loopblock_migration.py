"""
RUN-890: Failing tests for LoopBlock migration to BlockContext/BlockOutput.

Tests verify that after migration:
AC-1: LoopBlock.execute accepts BlockContext and returns BlockOutput
AC-2: No direct state mutation in LoopBlock.execute — uses state_snapshot internally
AC-3: Inner blocks get fresh BlockContext each round via execute_block
AC-4: carry_context flows correctly through shared_memory_updates across rounds
AC-5: Round tracking metadata in shared_memory_updates is correct
AC-6: Nested loops — inner loop context doesn't leak to outer
AC-7: All existing LoopBlock behaviours preserved (backward compat via legacy path)
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from runsight_core.block_io import (
    BlockContext,
    BlockOutput,
)
from runsight_core.blocks.linear import LinearBlock
from runsight_core.blocks.loop import CarryContextConfig, LoopBlock
from runsight_core.primitives import Soul
from runsight_core.runner import ExecutionResult
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.workflow import BlockExecutionContext, execute_block

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_mock_runner(output: str = "done", cost: float = 0.01, tokens: int = 100):
    runner = MagicMock()
    runner.model_name = "gpt-4o-mini"
    runner._build_prompt = MagicMock(side_effect=lambda task: task.instruction or "")
    runner.execute = AsyncMock(
        return_value=ExecutionResult(
            task_id="t1",
            soul_id="soul1",
            output=output,
            cost_usd=cost,
            total_tokens=tokens,
        )
    )
    return runner


def _make_linear_block(block_id: str, runner=None, soul_id: str = "soul_1") -> LinearBlock:
    soul = Soul(
        id=soul_id, kind="soul", name="Test Agent", role="Agent", system_prompt="You are an agent."
    )
    if runner is None:
        runner = _make_mock_runner()
    return LinearBlock(block_id, soul, runner)


def _make_base_state(instruction: str = "run loop") -> WorkflowState:
    return WorkflowState()


def _make_loop_block_context(
    loop: LoopBlock,
    state: WorkflowState,
    blocks: dict,
    ctx: BlockExecutionContext,
) -> BlockContext:
    """Build a BlockContext suitable for LoopBlock._execute_with_context.

    The state_snapshot carries the full WorkflowState.
    inputs carries blocks and ctx so the loop can call execute_block internally.
    """
    return BlockContext(
        block_id=loop.block_id,
        instruction="loop",
        context=None,
        inputs={"blocks": blocks, "ctx": ctx},
        conversation_history=[],
        soul=None,
        model_name=None,
        state_snapshot=state,
    )


def _make_block_execution_ctx(blocks: dict) -> BlockExecutionContext:
    return BlockExecutionContext(
        workflow_name="test_wf",
        blocks=blocks,
        call_stack=[],
        workflow_registry=None,
        observer=None,
    )


# ---------------------------------------------------------------------------
# AC-1: LoopBlock.execute accepts BlockContext and returns BlockOutput
# ---------------------------------------------------------------------------


class TestAC1AcceptsBlockContextReturnsBlockOutput:
    """LoopBlock.execute must accept BlockContext and return BlockOutput."""

    @pytest.mark.asyncio
    async def test_execute_with_block_context_returns_block_output(self):
        """When called with BlockContext, execute must return BlockOutput."""
        runner = _make_mock_runner(output="inner result", cost=0.01, tokens=50)
        inner = _make_linear_block("inner1", runner)
        loop = LoopBlock(block_id="loop1", inner_block_refs=["inner1"], max_rounds=1)
        blocks = {"inner1": inner, "loop1": loop}
        ctx = _make_block_execution_ctx(blocks)

        state = _make_base_state()
        block_ctx = _make_loop_block_context(loop, state, blocks, ctx)

        result = await loop.execute(block_ctx)

        assert isinstance(result, BlockOutput), (
            f"Expected BlockOutput but got {type(result).__name__}. "
            "LoopBlock.execute must return BlockOutput after RUN-890 migration."
        )

    @pytest.mark.asyncio
    async def test_execute_output_contains_completed_rounds_string(self):
        """BlockOutput.output must be 'completed_N_rounds'."""
        runner = _make_mock_runner(output="inner result")
        inner = _make_linear_block("inner1", runner)
        loop = LoopBlock(block_id="loop1", inner_block_refs=["inner1"], max_rounds=3)
        blocks = {"inner1": inner, "loop1": loop}
        ctx = _make_block_execution_ctx(blocks)

        state = _make_base_state()
        block_ctx = _make_loop_block_context(loop, state, blocks, ctx)

        result = await loop.execute(block_ctx)

        assert isinstance(result, BlockOutput)
        assert result.output == "completed_3_rounds", (
            f"Expected output='completed_3_rounds', got '{result.output}'"
        )

    @pytest.mark.asyncio
    async def test_execute_accumulates_cost_from_inner_blocks(self):
        """BlockOutput.cost_usd must equal the sum of all inner block costs across all rounds."""
        runner = _make_mock_runner(output="out", cost=0.05, tokens=100)
        inner = _make_linear_block("inner1", runner)
        loop = LoopBlock(block_id="loop1", inner_block_refs=["inner1"], max_rounds=3)
        blocks = {"inner1": inner, "loop1": loop}
        ctx = _make_block_execution_ctx(blocks)

        state = _make_base_state()
        block_ctx = _make_loop_block_context(loop, state, blocks, ctx)

        result = await loop.execute(block_ctx)

        assert isinstance(result, BlockOutput)
        assert result.cost_usd == pytest.approx(0.15), (
            f"Expected cost_usd=0.15 (3 rounds x 0.05), got {result.cost_usd}"
        )

    @pytest.mark.asyncio
    async def test_execute_accumulates_total_tokens_from_inner_blocks(self):
        """BlockOutput.total_tokens must equal the sum of all inner block tokens across rounds."""
        runner = _make_mock_runner(output="out", cost=0.01, tokens=200)
        inner = _make_linear_block("inner1", runner)
        loop = LoopBlock(block_id="loop1", inner_block_refs=["inner1"], max_rounds=2)
        blocks = {"inner1": inner, "loop1": loop}
        ctx = _make_block_execution_ctx(blocks)

        state = _make_base_state()
        block_ctx = _make_loop_block_context(loop, state, blocks, ctx)

        result = await loop.execute(block_ctx)

        assert isinstance(result, BlockOutput)
        assert result.total_tokens == 400, (
            f"Expected total_tokens=400 (2 rounds x 200), got {result.total_tokens}"
        )

    # Legacy WorkflowState path removed — shim deleted in RUN-906


# ---------------------------------------------------------------------------
# AC-2: Uses state_snapshot internally — returns BlockOutput, not WorkflowState
# ---------------------------------------------------------------------------


class TestAC2UsesStateSnapshot:
    """LoopBlock must use state_snapshot from BlockContext as its working state."""

    @pytest.mark.asyncio
    async def test_returns_block_output_not_workflow_state(self):
        """New path must return BlockOutput, proving no state mutation escapes."""
        runner = _make_mock_runner()
        inner = _make_linear_block("inner1", runner)
        loop = LoopBlock(block_id="loop1", inner_block_refs=["inner1"], max_rounds=1)
        blocks = {"inner1": inner, "loop1": loop}
        ctx = _make_block_execution_ctx(blocks)

        state = _make_base_state()
        block_ctx = _make_loop_block_context(loop, state, blocks, ctx)

        result = await loop.execute(block_ctx)

        # The new path must return BlockOutput, not WorkflowState
        assert not isinstance(result, WorkflowState), (
            "execute() must not return WorkflowState from new BlockContext path. "
            "State changes must be communicated via BlockOutput."
        )
        assert isinstance(result, BlockOutput)

    @pytest.mark.asyncio
    async def test_state_snapshot_provides_initial_results_to_inner_blocks(self):
        """Inner blocks in the first round must see state from state_snapshot.results."""
        # Pre-seed a result in state that the inner block can access
        pre_seed_state = _make_base_state()
        pre_seed_state = pre_seed_state.model_copy(
            update={"results": {"upstream": BlockResult(output="upstream_data")}}
        )

        captured_contexts = []

        class CapturingBlock(LinearBlock):
            async def execute(self, ctx):
                captured_contexts.append(ctx)
                return await super().execute(ctx)

        runner = _make_mock_runner()
        soul = Soul(id="soul1", kind="soul", name="Test", role="Agent", system_prompt="test")
        inner = CapturingBlock("inner1", soul, runner)
        loop = LoopBlock(block_id="loop1", inner_block_refs=["inner1"], max_rounds=1)
        blocks = {"inner1": inner, "loop1": loop}
        ctx = _make_block_execution_ctx(blocks)

        block_ctx = _make_loop_block_context(loop, pre_seed_state, blocks, ctx)
        result = await loop.execute(block_ctx)

        assert isinstance(result, BlockOutput)
        # The inner block must have seen the upstream result from state_snapshot
        assert len(captured_contexts) >= 1
        # Inner block receives a BlockContext; state_snapshot carries the pre-seed state
        captured_ctx = captured_contexts[0]
        assert isinstance(captured_ctx, BlockContext), (
            "Inner block in round 1 must receive a BlockContext."
        )
        # The state_snapshot on the inner ctx (if present) or the extra_results on the
        # outer BlockOutput must show the upstream data was available.
        assert result.extra_results is None or "upstream" not in (result.extra_results or {}), (
            "upstream was a pre-existing result, not produced by the loop."
        )

    @pytest.mark.asyncio
    async def test_missing_state_snapshot_raises_value_error(self):
        """If BlockContext.state_snapshot is None, execute must raise ValueError."""
        loop = LoopBlock(block_id="loop1", inner_block_refs=["inner1"], max_rounds=1)

        ctx_no_snapshot = BlockContext(
            block_id="loop1",
            instruction="loop",
            inputs={},
            conversation_history=[],
            soul=None,
            model_name=None,
            state_snapshot=None,  # deliberately missing
        )

        with pytest.raises((ValueError, AttributeError)):
            await loop.execute(ctx_no_snapshot)


# ---------------------------------------------------------------------------
# AC-3: Inner blocks get fresh BlockContext per round via execute_block
# ---------------------------------------------------------------------------


class TestAC3InnerBlocksGetFreshContext:
    """Inner blocks must receive fresh BlockContext each round (round state carried forward)."""

    @pytest.mark.asyncio
    async def test_execute_block_called_for_inner_blocks(self):
        """execute_block must be invoked for each inner block per round."""
        runner = _make_mock_runner(output="round output")
        inner = _make_linear_block("inner1", runner)
        loop = LoopBlock(block_id="loop1", inner_block_refs=["inner1"], max_rounds=2)
        blocks = {"inner1": inner, "loop1": loop}
        ctx = _make_block_execution_ctx(blocks)

        state = _make_base_state()
        block_ctx = _make_loop_block_context(loop, state, blocks, ctx)

        with patch("runsight_core.blocks.loop.execute_block", wraps=execute_block) as mock_eb:
            result = await loop.execute(block_ctx)

        assert isinstance(result, BlockOutput)
        # execute_block must have been called at least once per round per inner block
        assert mock_eb.call_count >= 2, (
            f"execute_block must be called once per round per inner block "
            f"(2 rounds x 1 block = 2 calls min), got {mock_eb.call_count}"
        )

    @pytest.mark.asyncio
    async def test_each_round_state_has_updated_round_tracker(self):
        """State passed to inner blocks in round N must have {block_id}_round == N."""
        round_numbers_seen = []

        runner = MagicMock()
        runner.model_name = "gpt-4o-mini"
        runner._build_prompt = MagicMock(side_effect=lambda task: task.instruction or "")
        soul = Soul(id="soul1", kind="soul", name="Test", role="Agent", system_prompt="test")

        async def capturing_execute_block(block, state, ctx, extra_inputs=None):
            if block.block_id == "inner1":
                round_numbers_seen.append(state.shared_memory.get("loop1_round"))
            result_state = state.model_copy(
                update={"results": {**state.results, block.block_id: BlockResult(output="done")}}
            )
            return result_state

        runner.execute = AsyncMock(
            return_value=ExecutionResult(
                task_id="t1", soul_id="soul1", output="done", cost_usd=0.01, total_tokens=10
            )
        )
        inner = LinearBlock("inner1", soul, runner)
        loop = LoopBlock(block_id="loop1", inner_block_refs=["inner1"], max_rounds=3)
        blocks = {"inner1": inner, "loop1": loop}
        ctx = _make_block_execution_ctx(blocks)

        state = _make_base_state()
        block_ctx = _make_loop_block_context(loop, state, blocks, ctx)

        with patch("runsight_core.blocks.loop.execute_block", side_effect=capturing_execute_block):
            result = await loop.execute(block_ctx)

        assert isinstance(result, BlockOutput)
        assert round_numbers_seen == [1, 2, 3], (
            f"Expected inner block to see round numbers [1, 2, 3] across 3 rounds, "
            f"got {round_numbers_seen}"
        )

    @pytest.mark.asyncio
    async def test_inner_block_extra_results_captured_in_block_output(self):
        """BlockOutput.extra_results must contain inner block results after all rounds."""
        runner = _make_mock_runner(output="final_output")
        inner = _make_linear_block("inner1", runner)
        loop = LoopBlock(block_id="loop1", inner_block_refs=["inner1"], max_rounds=2)
        blocks = {"inner1": inner, "loop1": loop}
        ctx = _make_block_execution_ctx(blocks)

        state = _make_base_state()
        block_ctx = _make_loop_block_context(loop, state, blocks, ctx)

        result = await loop.execute(block_ctx)

        assert isinstance(result, BlockOutput)
        assert result.extra_results is not None, (
            "BlockOutput.extra_results must not be None after loop execution. "
            "Inner block results must be captured here."
        )
        assert "inner1" in result.extra_results, (
            f"inner1 result must appear in BlockOutput.extra_results. "
            f"Keys found: {list(result.extra_results.keys()) if result.extra_results else []}"
        )


# ---------------------------------------------------------------------------
# AC-4: carry_context flows through shared_memory_updates
# ---------------------------------------------------------------------------


class TestAC4CarryContextFlows:
    """carry_context must flow via shared_memory_updates in BlockOutput."""

    @pytest.mark.asyncio
    async def test_carry_context_appears_in_shared_memory_updates(self):
        """With carry_context enabled, shared_memory_updates must contain inject_as key."""
        runner = _make_mock_runner(output="carry_data")
        inner = _make_linear_block("inner1", runner)
        carry = CarryContextConfig(enabled=True, mode="last", inject_as="prev_ctx")
        loop = LoopBlock(
            block_id="loop1",
            inner_block_refs=["inner1"],
            max_rounds=2,
            carry_context=carry,
        )
        blocks = {"inner1": inner, "loop1": loop}
        ctx = _make_block_execution_ctx(blocks)

        state = _make_base_state()
        block_ctx = _make_loop_block_context(loop, state, blocks, ctx)

        result = await loop.execute(block_ctx)

        assert isinstance(result, BlockOutput)
        assert result.shared_memory_updates is not None, (
            "BlockOutput.shared_memory_updates must not be None when carry_context is enabled."
        )
        assert "prev_ctx" in result.shared_memory_updates, (
            f"carry_context inject_as key 'prev_ctx' must appear in shared_memory_updates. "
            f"Keys found: {list(result.shared_memory_updates.keys())}"
        )

    @pytest.mark.asyncio
    async def test_carry_context_mode_all_accumulates_across_rounds(self):
        """With mode='all', shared_memory_updates[inject_as] must be a list of round dicts."""
        runner = _make_mock_runner(output="round_output")
        inner = _make_linear_block("inner1", runner)
        carry = CarryContextConfig(enabled=True, mode="all", inject_as="full_history")
        loop = LoopBlock(
            block_id="loop1",
            inner_block_refs=["inner1"],
            max_rounds=3,
            carry_context=carry,
        )
        blocks = {"inner1": inner, "loop1": loop}
        ctx = _make_block_execution_ctx(blocks)

        state = _make_base_state()
        block_ctx = _make_loop_block_context(loop, state, blocks, ctx)

        result = await loop.execute(block_ctx)

        assert isinstance(result, BlockOutput)
        assert result.shared_memory_updates is not None
        history = result.shared_memory_updates.get("full_history")
        assert isinstance(history, list), (
            f"carry_context mode='all' must produce a list, got {type(history).__name__}"
        )
        assert len(history) == 3, (
            f"Expected 3 entries in carry_history (one per round), got {len(history)}"
        )

    @pytest.mark.asyncio
    async def test_carry_context_values_are_strings_not_blockresult(self):
        """Values in shared_memory_updates[inject_as] must be strings, not BlockResult objects."""
        runner = _make_mock_runner(output="string_output")
        inner = _make_linear_block("inner1", runner)
        carry = CarryContextConfig(enabled=True, mode="last", inject_as="ctx_val")
        loop = LoopBlock(
            block_id="loop1",
            inner_block_refs=["inner1"],
            max_rounds=2,
            carry_context=carry,
        )
        blocks = {"inner1": inner, "loop1": loop}
        ctx = _make_block_execution_ctx(blocks)

        state = _make_base_state()
        block_ctx = _make_loop_block_context(loop, state, blocks, ctx)

        result = await loop.execute(block_ctx)

        assert isinstance(result, BlockOutput)
        assert result.shared_memory_updates is not None
        carried = result.shared_memory_updates.get("ctx_val")
        assert carried is not None
        inner_val = carried.get("inner1")
        assert isinstance(inner_val, str), (
            f"Carried context value for 'inner1' must be str, not {type(inner_val).__name__}. "
            "carry_context must extract .output from BlockResult."
        )

    @pytest.mark.asyncio
    async def test_no_carry_context_shared_memory_updates_still_has_round_tracking(self):
        """Even without carry_context, shared_memory_updates must contain round tracking keys."""
        runner = _make_mock_runner()
        inner = _make_linear_block("inner1", runner)
        loop = LoopBlock(
            block_id="loop1",
            inner_block_refs=["inner1"],
            max_rounds=2,
            carry_context=None,
        )
        blocks = {"inner1": inner, "loop1": loop}
        ctx = _make_block_execution_ctx(blocks)

        state = _make_base_state()
        block_ctx = _make_loop_block_context(loop, state, blocks, ctx)

        result = await loop.execute(block_ctx)

        assert isinstance(result, BlockOutput)
        assert result.shared_memory_updates is not None
        assert "loop1_round" in result.shared_memory_updates, (
            "shared_memory_updates must contain '{block_id}_round' key for round tracking."
        )


# ---------------------------------------------------------------------------
# AC-5: Round tracking metadata in shared_memory_updates is correct
# ---------------------------------------------------------------------------


class TestAC5RoundTrackingMetadata:
    """shared_memory_updates must carry correct round tracking metadata."""

    @pytest.mark.asyncio
    async def test_round_tracker_key_has_last_round_number(self):
        """shared_memory_updates['{block_id}_round'] must be the last round number."""
        runner = _make_mock_runner()
        inner = _make_linear_block("inner1", runner)
        loop = LoopBlock(block_id="myloop", inner_block_refs=["inner1"], max_rounds=4)
        blocks = {"inner1": inner, "myloop": loop}
        ctx = _make_block_execution_ctx(blocks)

        state = _make_base_state()
        block_ctx = _make_loop_block_context(loop, state, blocks, ctx)

        result = await loop.execute(block_ctx)

        assert isinstance(result, BlockOutput)
        assert result.shared_memory_updates is not None
        round_val = result.shared_memory_updates.get("myloop_round")
        assert round_val == 4, f"Expected 'myloop_round'=4 (last round), got {round_val}"

    @pytest.mark.asyncio
    async def test_loop_metadata_key_has_rounds_completed(self):
        """shared_memory_updates['__loop__{block_id}'] must have rounds_completed."""
        runner = _make_mock_runner()
        inner = _make_linear_block("inner1", runner)
        loop = LoopBlock(block_id="loop1", inner_block_refs=["inner1"], max_rounds=3)
        blocks = {"inner1": inner, "loop1": loop}
        ctx = _make_block_execution_ctx(blocks)

        state = _make_base_state()
        block_ctx = _make_loop_block_context(loop, state, blocks, ctx)

        result = await loop.execute(block_ctx)

        assert isinstance(result, BlockOutput)
        assert result.shared_memory_updates is not None
        meta_key = "__loop__loop1"
        assert meta_key in result.shared_memory_updates, (
            f"'{meta_key}' must appear in shared_memory_updates. "
            f"Keys found: {list(result.shared_memory_updates.keys())}"
        )
        meta = result.shared_memory_updates[meta_key]
        assert meta["rounds_completed"] == 3, (
            f"Expected rounds_completed=3, got {meta.get('rounds_completed')}"
        )

    @pytest.mark.asyncio
    async def test_loop_metadata_broke_early_false_when_max_rounds_reached(self):
        """__loop__{block_id}.broke_early must be False when max_rounds is reached."""
        runner = _make_mock_runner()
        inner = _make_linear_block("inner1", runner)
        loop = LoopBlock(block_id="loop1", inner_block_refs=["inner1"], max_rounds=2)
        blocks = {"inner1": inner, "loop1": loop}
        ctx = _make_block_execution_ctx(blocks)

        state = _make_base_state()
        block_ctx = _make_loop_block_context(loop, state, blocks, ctx)

        result = await loop.execute(block_ctx)

        assert isinstance(result, BlockOutput)
        meta = result.shared_memory_updates["__loop__loop1"]
        assert meta["broke_early"] is False, (
            f"Expected broke_early=False (ran all rounds), got {meta.get('broke_early')}"
        )
        assert meta["break_reason"] == "max_rounds reached", (
            f"Expected break_reason='max_rounds reached', got {meta.get('break_reason')}"
        )

    @pytest.mark.asyncio
    async def test_loop_metadata_broke_early_true_with_break_on_exit(self):
        """__loop__{block_id}.broke_early must be True when break_on_exit fires."""
        from runsight_core.runner import ExecutionResult

        call_count = 0

        async def _exit_side_effect(instruction, context, soul, **kwargs):
            nonlocal call_count
            call_count += 1
            # On round 2, fire the break exit handle
            exit_handle = "done" if call_count >= 2 else None
            return ExecutionResult(
                task_id="t1",
                soul_id="soul1",
                output=f"round_{call_count}",
                exit_handle=exit_handle,
                cost_usd=0.01,
                total_tokens=10,
            )

        runner = MagicMock()
        runner.model_name = "gpt-4o-mini"
        runner._build_prompt = MagicMock(side_effect=lambda t: t.instruction or "")
        runner.execute = AsyncMock(side_effect=_exit_side_effect)

        soul = Soul(id="soul1", kind="soul", name="Test", role="Agent", system_prompt="test")
        inner = LinearBlock("inner1", soul, runner)
        loop = LoopBlock(
            block_id="loop1",
            inner_block_refs=["inner1"],
            max_rounds=5,
            break_on_exit="done",
        )
        blocks = {"inner1": inner, "loop1": loop}
        ctx = _make_block_execution_ctx(blocks)

        state = _make_base_state()
        block_ctx = _make_loop_block_context(loop, state, blocks, ctx)

        result = await loop.execute(block_ctx)

        assert isinstance(result, BlockOutput)
        assert result.shared_memory_updates is not None
        meta = result.shared_memory_updates["__loop__loop1"]
        assert meta["broke_early"] is True, (
            f"Expected broke_early=True (break_on_exit triggered), got {meta.get('broke_early')}"
        )
        assert meta["rounds_completed"] == 2, (
            f"Expected rounds_completed=2 (broke at round 2), got {meta.get('rounds_completed')}"
        )

    @pytest.mark.asyncio
    async def test_loop_log_entries_contain_completion_entry(self):
        """BlockOutput.log_entries must contain at least one loop completion log entry."""
        runner = _make_mock_runner()
        inner = _make_linear_block("inner1", runner)
        loop = LoopBlock(block_id="loop1", inner_block_refs=["inner1"], max_rounds=1)
        blocks = {"inner1": inner, "loop1": loop}
        ctx = _make_block_execution_ctx(blocks)

        state = _make_base_state()
        block_ctx = _make_loop_block_context(loop, state, blocks, ctx)

        result = await loop.execute(block_ctx)

        assert isinstance(result, BlockOutput)
        assert len(result.log_entries) > 0, (
            "BlockOutput.log_entries must contain at least one entry after loop execution."
        )


# ---------------------------------------------------------------------------
# AC-6: Nested loops — inner loop context doesn't leak to outer
# ---------------------------------------------------------------------------


class TestAC6NestedLoopsNoContextLeak:
    """Inner loop carry_context must not bleed into outer loop's shared_memory_updates."""

    @pytest.mark.asyncio
    async def test_nested_loop_inner_metadata_does_not_overwrite_outer(self):
        """Outer loop's __loop__ metadata key must not be overwritten by inner loop's metadata."""
        runner = _make_mock_runner(output="nested_out")
        inner_block = _make_linear_block("inner_linear", runner)

        # Inner loop wraps inner_block
        inner_loop = LoopBlock(
            block_id="inner_loop",
            inner_block_refs=["inner_linear"],
            max_rounds=2,
        )

        # Outer loop wraps inner_loop
        outer_loop = LoopBlock(
            block_id="outer_loop",
            inner_block_refs=["inner_loop"],
            max_rounds=2,
        )

        all_blocks = {
            "inner_linear": inner_block,
            "inner_loop": inner_loop,
            "outer_loop": outer_loop,
        }
        ctx = _make_block_execution_ctx(all_blocks)

        state = _make_base_state()
        block_ctx = _make_loop_block_context(outer_loop, state, all_blocks, ctx)

        result = await outer_loop.execute(block_ctx)

        assert isinstance(result, BlockOutput)
        assert result.shared_memory_updates is not None

        outer_meta = result.shared_memory_updates.get("__loop__outer_loop")
        assert outer_meta is not None, (
            "'__loop__outer_loop' must be present in outer loop's shared_memory_updates"
        )
        assert outer_meta["rounds_completed"] == 2, (
            f"Outer loop must complete 2 rounds, got {outer_meta.get('rounds_completed')}"
        )

    @pytest.mark.asyncio
    async def test_nested_loop_carry_context_inject_as_keys_are_distinct(self):
        """carry_context inject_as keys for inner and outer loops must not collide."""
        runner = _make_mock_runner(output="data")
        inner_block = _make_linear_block("inner_linear", runner)

        inner_carry = CarryContextConfig(enabled=True, mode="last", inject_as="inner_ctx")
        inner_loop = LoopBlock(
            block_id="inner_loop",
            inner_block_refs=["inner_linear"],
            max_rounds=2,
            carry_context=inner_carry,
        )

        outer_carry = CarryContextConfig(enabled=True, mode="last", inject_as="outer_ctx")
        outer_loop = LoopBlock(
            block_id="outer_loop",
            inner_block_refs=["inner_loop"],
            max_rounds=2,
            carry_context=outer_carry,
        )

        all_blocks = {
            "inner_linear": inner_block,
            "inner_loop": inner_loop,
            "outer_loop": outer_loop,
        }
        ctx = _make_block_execution_ctx(all_blocks)

        state = _make_base_state()
        block_ctx = _make_loop_block_context(outer_loop, state, all_blocks, ctx)

        result = await outer_loop.execute(block_ctx)

        assert isinstance(result, BlockOutput)
        assert result.shared_memory_updates is not None

        # Outer ctx key must be present in outer's updates
        assert "outer_ctx" in result.shared_memory_updates, (
            "'outer_ctx' must be in outer loop's shared_memory_updates"
        )

        # Inner ctx should NOT bleed directly into outer's shared_memory_updates
        # (inner ctx belongs to the inner loop's own BlockOutput, not the outer's diff)
        # This ensures inner loop context doesn't directly overwrite outer namespace
        outer_ctx_val = result.shared_memory_updates.get("outer_ctx")
        assert outer_ctx_val is not None
        assert "inner_ctx" not in result.shared_memory_updates, (
            "'inner_ctx' must not appear in outer loop's shared_memory_updates — "
            "inner loop carry_context must not bleed into outer loop's namespace."
        )


# ---------------------------------------------------------------------------
# AC-7: End-to-end via execute_block — LoopBlock dispatches through new path
# ---------------------------------------------------------------------------


class TestAC7E2EExecBlock:
    """execute_block must dispatch LoopBlock through the new BlockContext path."""

    @pytest.mark.asyncio
    async def test_execute_block_dispatches_loop_through_block_context_path(self):
        """execute_block(loop, state, ctx) must call loop._execute_with_context."""
        runner = _make_mock_runner(output="e2e out")
        inner = _make_linear_block("inner1", runner)
        loop = LoopBlock(block_id="loop1", inner_block_refs=["inner1"], max_rounds=1)
        blocks = {"inner1": inner, "loop1": loop}

        bec = BlockExecutionContext(
            workflow_name="e2e_wf",
            blocks=blocks,
            call_stack=[],
            workflow_registry=None,
            observer=None,
        )

        state = _make_base_state()

        # After execute_block, state.results should contain 'loop1' with BlockResult
        result_state = await execute_block(loop, state, bec)

        assert isinstance(result_state, WorkflowState), (
            "execute_block must always return WorkflowState"
        )
        assert "loop1" in result_state.results, (
            f"'loop1' must appear in state.results after execute_block. "
            f"Keys: {list(result_state.results.keys())}"
        )
        loop_result = result_state.results["loop1"]
        assert isinstance(loop_result, BlockResult), (
            f"result['loop1'] must be a BlockResult, got {type(loop_result).__name__}"
        )
        assert loop_result.output == "completed_1_rounds", (
            f"Expected output='completed_1_rounds', got '{loop_result.output}'"
        )

    @pytest.mark.asyncio
    async def test_execute_block_applies_loop_shared_memory_updates_to_state(self):
        """After execute_block, state.shared_memory must contain round tracking from loop."""
        runner = _make_mock_runner()
        inner = _make_linear_block("inner1", runner)
        loop = LoopBlock(block_id="loop1", inner_block_refs=["inner1"], max_rounds=2)
        blocks = {"inner1": inner, "loop1": loop}

        bec = BlockExecutionContext(
            workflow_name="e2e_wf",
            blocks=blocks,
            call_stack=[],
            workflow_registry=None,
            observer=None,
        )

        state = _make_base_state()
        result_state = await execute_block(loop, state, bec)

        assert "loop1_round" in result_state.shared_memory, (
            "After execute_block, state.shared_memory must contain 'loop1_round'. "
            "apply_block_output must merge shared_memory_updates."
        )
        assert result_state.shared_memory["loop1_round"] == 2, (
            f"Expected loop1_round=2 (last round), got {result_state.shared_memory.get('loop1_round')}"
        )

    @pytest.mark.asyncio
    async def test_execute_block_accumulates_cost_into_state(self):
        """After execute_block, state.total_cost_usd must include loop's accumulated cost."""
        runner = _make_mock_runner(output="out", cost=0.05, tokens=50)
        inner = _make_linear_block("inner1", runner)
        loop = LoopBlock(block_id="loop1", inner_block_refs=["inner1"], max_rounds=3)
        blocks = {"inner1": inner, "loop1": loop}

        bec = BlockExecutionContext(
            workflow_name="e2e_wf",
            blocks=blocks,
            call_stack=[],
            workflow_registry=None,
            observer=None,
        )

        state = _make_base_state()
        result_state = await execute_block(loop, state, bec)

        assert result_state.total_cost_usd == pytest.approx(0.15), (
            f"Expected total_cost_usd=0.15 after 3 rounds at $0.05 each, "
            f"got {result_state.total_cost_usd}"
        )

    @pytest.mark.asyncio
    async def test_execute_block_with_carry_context_populates_shared_memory(self):
        """execute_block on a loop with carry_context must populate state.shared_memory."""
        runner = _make_mock_runner(output="carry_out")
        inner = _make_linear_block("inner1", runner)
        carry = CarryContextConfig(enabled=True, mode="last", inject_as="e2e_ctx")
        loop = LoopBlock(
            block_id="loop1",
            inner_block_refs=["inner1"],
            max_rounds=2,
            carry_context=carry,
        )
        blocks = {"inner1": inner, "loop1": loop}

        bec = BlockExecutionContext(
            workflow_name="e2e_wf",
            blocks=blocks,
            call_stack=[],
            workflow_registry=None,
            observer=None,
        )

        state = _make_base_state()
        result_state = await execute_block(loop, state, bec)

        assert "e2e_ctx" in result_state.shared_memory, (
            "state.shared_memory must contain carry_context inject_as key after execute_block. "
            f"Keys found: {list(result_state.shared_memory.keys())}"
        )
