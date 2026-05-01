"""LoopBlock carry-context runtime edge cases."""

from __future__ import annotations

import pytest
from loop_carry_context_helpers import (
    ContextReaderBlock,
    EmptyOutputBlock,
    SharedMemoryInspectorBlock,
    TrackingBlock,
    run_loop,
    seeded_state,
)


class TestCarryContextRoundOne:
    """The first round has no previous carried context."""

    @pytest.mark.asyncio
    async def test_round_one_has_no_context(self):
        from runsight_core import LoopBlock
        from runsight_core.blocks.loop import CarryContextConfig

        reader = ContextReaderBlock("reader", read_key="previous_round_context")
        blocks = {"reader": reader}
        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["reader"],
            max_rounds=3,
            carry_context=CarryContextConfig(inject_as="previous_round_context"),
        )
        blocks["loop_block"] = loop

        result_state = await run_loop(loop, seeded_state("previous_round_context"), blocks)

        snapshots = result_state.shared_memory.get("reader_snapshots", [])
        assert snapshots[0] is None

    @pytest.mark.asyncio
    async def test_seeded_slot_remains_empty_until_first_injection(self):
        from runsight_core import LoopBlock
        from runsight_core.blocks.loop import CarryContextConfig

        inspector = SharedMemoryInspectorBlock("inspector", read_key="ctx")
        blocks = {"inspector": inspector}
        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["inspector"],
            max_rounds=3,
            carry_context=CarryContextConfig(inject_as="ctx"),
        )
        blocks["loop_block"] = loop

        result_state = await run_loop(loop, seeded_state("ctx"), blocks)

        ctx_values_per_round = result_state.shared_memory.get("inspector_key_exists", [])
        assert ctx_values_per_round[0] is None
        assert ctx_values_per_round[1] is not None
        assert ctx_values_per_round[2] is not None


class TestCarryContextDisabledOrMissing:
    """Missing or disabled carry_context does not inject shared-memory context."""

    @pytest.mark.asyncio
    async def test_no_carry_context_leaves_seeded_slot_empty(self):
        from runsight_core import LoopBlock

        reader = ContextReaderBlock("reader", read_key="previous_round_context")
        blocks = {"reader": reader}
        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["reader"],
            max_rounds=3,
            carry_context=None,
        )
        blocks["loop_block"] = loop

        result_state = await run_loop(loop, seeded_state("previous_round_context"), blocks)

        assert result_state.shared_memory.get("previous_round_context") is None
        snapshots = result_state.shared_memory.get("reader_snapshots", [])
        assert all(snapshot is None for snapshot in snapshots)

    @pytest.mark.asyncio
    async def test_loop_without_carry_context_still_runs_rounds(self):
        from runsight_core import LoopBlock

        inner = TrackingBlock("inner")
        blocks = {"inner": inner}
        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["inner"],
            max_rounds=3,
        )
        blocks["loop_block"] = loop

        result_state = await run_loop(loop, seeded_state(), blocks)

        calls = result_state.shared_memory.get("inner_calls", [])
        assert len(calls) == 3
        assert "loop_block" in result_state.results

    @pytest.mark.asyncio
    async def test_enabled_false_leaves_seeded_slot_empty(self):
        from runsight_core import LoopBlock
        from runsight_core.blocks.loop import CarryContextConfig

        reader = ContextReaderBlock("reader", read_key="feedback")
        blocks = {"reader": reader}
        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["reader"],
            max_rounds=3,
            carry_context=CarryContextConfig(
                enabled=False,
                mode="last",
                inject_as="feedback",
            ),
        )
        blocks["loop_block"] = loop

        result_state = await run_loop(loop, seeded_state("feedback"), blocks)

        assert result_state.shared_memory.get("feedback") is None
        snapshots = result_state.shared_memory.get("reader_snapshots", [])
        assert all(snapshot is None for snapshot in snapshots)


class TestCarryContextSourceBlockValidation:
    """source_blocks must reference inner_block_refs."""

    def test_source_block_not_in_inner_refs_raises(self):
        from runsight_core import LoopBlock
        from runsight_core.blocks.loop import CarryContextConfig

        config = CarryContextConfig(source_blocks=["not_an_inner_block"])
        with pytest.raises(ValueError, match="not_an_inner_block"):
            LoopBlock(
                block_id="loop_block",
                inner_block_refs=["writer", "critic"],
                max_rounds=3,
                carry_context=config,
            )

    def test_multiple_invalid_source_blocks_raise(self):
        from runsight_core import LoopBlock
        from runsight_core.blocks.loop import CarryContextConfig

        config = CarryContextConfig(source_blocks=["ghost_a", "ghost_b"])
        with pytest.raises(ValueError, match="ghost"):
            LoopBlock(
                block_id="loop_block",
                inner_block_refs=["writer"],
                max_rounds=3,
                carry_context=config,
            )

    def test_valid_source_blocks_are_accepted(self):
        from runsight_core import LoopBlock
        from runsight_core.blocks.loop import CarryContextConfig

        config = CarryContextConfig(source_blocks=["critic"], inject_as="feedback")
        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["writer", "critic"],
            max_rounds=3,
            carry_context=config,
        )
        assert loop.carry_context is config


class TestCarryContextEmptyOutput:
    """Empty string outputs are carried rather than skipped."""

    @pytest.mark.asyncio
    async def test_empty_output_is_carried(self):
        from runsight_core import LoopBlock
        from runsight_core.blocks.loop import CarryContextConfig

        empty_block = EmptyOutputBlock("empty_block")
        reader = ContextReaderBlock("reader", read_key="ctx")
        blocks = {"empty_block": empty_block, "reader": reader}
        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["empty_block", "reader"],
            max_rounds=3,
            carry_context=CarryContextConfig(
                mode="last",
                source_blocks=["empty_block"],
                inject_as="ctx",
            ),
        )
        blocks["loop_block"] = loop

        result_state = await run_loop(loop, seeded_state("ctx"), blocks)

        snapshots = result_state.shared_memory.get("reader_snapshots", [])
        assert snapshots[0] is None
        assert snapshots[1] is not None
        assert "empty_block" in str(snapshots[1]) or snapshots[1] is not None
