"""LoopBlock schema, parsing, execution, and workflow integration behavior."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from pydantic import TypeAdapter, ValidationError
from runsight_core.blocks.base import BaseBlock
from runsight_core.state import WorkflowState
from runsight_core.yaml.schema import (
    BlockDef,
)

# ── Shared TypeAdapter for discriminated union ─────────────────────────────

block_adapter = TypeAdapter(BlockDef)


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


def _validate_block(data: dict):
    """Validate a dict as a BlockDef via the discriminated union."""
    return block_adapter.validate_python(data)


# ── Test helpers ───────────────────────────────────────────────────────────


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


class FailingBlock(BaseBlock):
    """Block that always raises RuntimeError."""

    def __init__(self, block_id: str):
        super().__init__(block_id)
        self.context_access = "declared"

    async def execute(self, ctx):
        raise RuntimeError(f"Block {self.block_id} failed")


class WriterBlock(BaseBlock):
    """Simulates a writer agent: appends a draft to shared_memory."""

    def __init__(self, block_id: str):
        super().__init__(block_id)
        self.context_access = "declared"
        self.declared_inputs = {"round_num": "shared_memory.loop_block_round"}
        self.drafts: list[str] = []

    async def execute(self, ctx):
        from runsight_core.block_io import BlockOutput

        round_num = ctx.inputs.get("round_num", 0)
        self.drafts.append(f"draft_round_{round_num}")
        return BlockOutput(
            output=f"draft_round_{round_num}",
            shared_memory_updates={"drafts": list(self.drafts)},
        )


class CriticBlock(BaseBlock):
    """Simulates a critic agent: appends feedback to shared_memory."""

    def __init__(self, block_id: str):
        super().__init__(block_id)
        self.context_access = "declared"
        self.declared_inputs = {"round_num": "shared_memory.loop_block_round"}
        self.feedback: list[str] = []

    async def execute(self, ctx):
        from runsight_core.block_io import BlockOutput

        round_num = ctx.inputs.get("round_num", 0)
        self.feedback.append(f"feedback_round_{round_num}")
        return BlockOutput(
            output=f"feedback_round_{round_num}",
            shared_memory_updates={"feedback": list(self.feedback)},
        )


# ===========================================================================
# 1. LoopBlockDef schema — model validation
# ===========================================================================


class TestLoopBlockSingleRef:
    """LoopBlock with 1 inner block ref runs max_rounds times."""

    @pytest.mark.asyncio
    async def test_single_ref_runs_max_rounds_times(self):
        """A LoopBlock with 1 inner ref and max_rounds=3 should execute the inner block 3 times."""
        from runsight_core import LoopBlock

        inner = TrackingBlock("inner_block")
        blocks = {"inner_block": inner, "loop_block": None}  # placeholder for loop

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["inner_block"],
            max_rounds=3,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        result_state = await _run_loop(loop, state, blocks)

        # Inner block should have been called 3 times
        calls = result_state.shared_memory.get("inner_block_calls", [])
        assert len(calls) == 3

    @pytest.mark.asyncio
    async def test_single_ref_default_max_rounds(self):
        """Default max_rounds=5 should execute the inner block 5 times."""
        from runsight_core import LoopBlock

        inner = TrackingBlock("inner_block")
        blocks = {"inner_block": inner}

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["inner_block"],
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        result_state = await _run_loop(loop, state, blocks)

        calls = result_state.shared_memory.get("inner_block_calls", [])
        assert len(calls) == 5

    @pytest.mark.asyncio
    async def test_break_condition_reads_block_result_output_not_str(self):
        """LoopBlock break conditions evaluate the inner BlockResult.output."""
        from runsight_core import LoopBlock
        from runsight_core.block_io import BlockOutput
        from runsight_core.conditions.engine import Condition
        from runsight_core.state import BlockResult

        class OutputBlock(BaseBlock):
            async def execute(self, ctx):
                return BlockOutput(output="REAL_OUTPUT")

        inner = OutputBlock("inner_block")
        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["inner_block"],
            max_rounds=5,
            break_condition=Condition(
                eval_key="result",
                operator="contains",
                value="REAL_OUTPUT",
            ),
        )

        with patch.object(BlockResult, "__str__", return_value="PATCHED_STR"):
            state = await _run_loop(
                loop,
                WorkflowState(),
                {"inner_block": inner, "loop_block": loop},
            )

        loop_meta = state.shared_memory.get("__loop__loop_block", {})
        assert loop_meta.get("broke_early") is True
        assert loop_meta.get("rounds_completed") == 1


class TestLoopBlockMultiRef:
    """LoopBlock with multiple inner block refs runs all sequentially per round."""

    @pytest.mark.asyncio
    async def test_three_refs_sequential_per_round(self):
        """3 inner refs with max_rounds=2 should produce 6 total executions (3 per round)."""
        from runsight_core import LoopBlock

        draft_block = TrackingBlock("draft_block")
        review_block = TrackingBlock("review_block")
        publish_block = TrackingBlock("publish_block")
        blocks = {
            "draft_block": draft_block,
            "review_block": review_block,
            "publish_block": publish_block,
        }

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["draft_block", "review_block", "publish_block"],
            max_rounds=2,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        result_state = await _run_loop(loop, state, blocks)

        # Each block should have been called exactly 2 times (once per round)
        assert len(result_state.shared_memory.get("draft_block_calls", [])) == 2
        assert len(result_state.shared_memory.get("review_block_calls", [])) == 2
        assert len(result_state.shared_memory.get("publish_block_calls", [])) == 2


class TestLoopBlockMaxRoundsOne:
    """LoopBlock with max_rounds=1 runs inner blocks exactly once (no loop)."""

    @pytest.mark.asyncio
    async def test_max_rounds_one_runs_once(self):
        """max_rounds=1 means inner blocks execute exactly once."""
        from runsight_core import LoopBlock

        inner = TrackingBlock("inner_block")
        blocks = {"inner_block": inner}

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["inner_block"],
            max_rounds=1,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        result_state = await _run_loop(loop, state, blocks)

        calls = result_state.shared_memory.get("inner_block_calls", [])
        assert len(calls) == 1


class TestLoopBlockRoundCounter:
    """Round counter in shared_memory increments correctly."""

    @pytest.mark.asyncio
    async def test_round_counter_increments(self):
        """shared_memory should contain the current round number, incrementing each round."""
        from runsight_core import LoopBlock

        inner = TrackingBlock("inner_block")
        blocks = {"inner_block": inner}

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["inner_block"],
            max_rounds=3,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        result_state = await _run_loop(loop, state, blocks)

        # The round counter key should reflect completed rounds
        # Exact key name: "loop_block_round" or similar — implementation decides
        # but it must be present and equal to the final round number
        round_key = "loop_block_round"
        assert round_key in result_state.shared_memory
        assert result_state.shared_memory[round_key] == 3

    @pytest.mark.asyncio
    async def test_round_counter_available_to_inner_blocks(self):
        """Inner blocks should be able to read the current round from shared_memory."""
        from runsight_core import LoopBlock

        class RoundReaderBlock(BaseBlock):
            """Block that reads the current loop round from shared_memory."""

            def __init__(self, block_id: str):
                super().__init__(block_id)
                self.context_access = "declared"
                self.declared_inputs = {"current_round": "shared_memory.loop_block_round"}
                self.rounds_seen: list[int] = []

            async def execute(self, ctx):
                from runsight_core.block_io import BlockOutput

                current_round = ctx.inputs.get("current_round", -1)
                self.rounds_seen.append(current_round)
                return BlockOutput(
                    output="ok",
                    shared_memory_updates={"rounds_seen": list(self.rounds_seen)},
                )

        reader = RoundReaderBlock("reader_block")
        blocks = {"reader_block": reader}

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["reader_block"],
            max_rounds=3,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        result_state = await _run_loop(loop, state, blocks)

        rounds_seen = result_state.shared_memory.get("rounds_seen", [])
        assert len(rounds_seen) == 3
        # Rounds should be 1, 2, 3 (1-indexed)
        assert rounds_seen == [1, 2, 3]


class TestLoopBlockErrorHandling:
    """Error cases: empty refs, invalid ref, self-reference, inner failure."""

    def test_constructor_rejects_empty_refs(self):
        """LoopBlock constructor should reject empty inner_block_refs."""
        from runsight_core import LoopBlock

        with pytest.raises((ValueError, ValidationError)):
            LoopBlock(
                block_id="loop_block",
                inner_block_refs=[],
                max_rounds=3,
            )

    @pytest.mark.asyncio
    async def test_invalid_ref_raises_at_runtime(self):
        """Referencing a block ID that doesn't exist in the blocks dict should raise at runtime."""
        from runsight_core import LoopBlock

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["nonexistent_block"],
            max_rounds=3,
        )

        state = WorkflowState()
        # The blocks dict does NOT contain "nonexistent_block"
        with pytest.raises((ValueError, KeyError), match="nonexistent_block"):
            await _run_loop(loop, state, {"loop_block": loop})

    def test_self_reference_rejected(self):
        """LoopBlock referencing itself in inner_block_refs should be detected and rejected."""
        from runsight_core import LoopBlock

        with pytest.raises(ValueError, match="self-reference|itself|circular"):
            LoopBlock(
                block_id="loop_block",
                inner_block_refs=["loop_block"],
                max_rounds=3,
            )

    def test_self_reference_among_other_refs_rejected(self):
        """LoopBlock including itself among other refs should also be rejected."""
        from runsight_core import LoopBlock

        with pytest.raises(ValueError, match="self-reference|itself|circular"):
            LoopBlock(
                block_id="loop_block",
                inner_block_refs=["draft_block", "loop_block", "review_block"],
                max_rounds=3,
            )

    @pytest.mark.asyncio
    async def test_inner_block_failure_propagates(self):
        """If an inner block fails mid-round, the error should propagate immediately."""
        from runsight_core import LoopBlock

        good_block = TrackingBlock("good_block")
        bad_block = FailingBlock("bad_block")
        blocks = {"good_block": good_block, "bad_block": bad_block}

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["good_block", "bad_block"],
            max_rounds=3,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        with pytest.raises(RuntimeError, match="Block bad_block failed"):
            await _run_loop(loop, state, blocks)

    @pytest.mark.asyncio
    async def test_shared_block_across_multiple_loops(self):
        """A single block referenced by multiple LoopBlocks should be allowed."""
        from runsight_core import LoopBlock

        shared_inner = TrackingBlock("shared_block")
        blocks = {"shared_block": shared_inner}

        loop_a = LoopBlock(
            block_id="loop_a",
            inner_block_refs=["shared_block"],
            max_rounds=2,
        )
        loop_b = LoopBlock(
            block_id="loop_b",
            inner_block_refs=["shared_block"],
            max_rounds=3,
        )
        blocks["loop_a"] = loop_a
        blocks["loop_b"] = loop_b

        state = WorkflowState()
        state = await _run_loop(loop_a, state, blocks)
        state = await _run_loop(loop_b, state, blocks)

        # shared_block should have been called 2 + 3 = 5 times total
        calls = state.shared_memory.get("shared_block_calls", [])
        assert len(calls) == 5


# ===========================================================================
# 3. YAML parsing tests — single-pass parser
# ===========================================================================
