"""LoopBlock carry-context propagation modes, source filtering, and inject keys."""

from __future__ import annotations

import pytest
from loop_carry_context_helpers import (
    ContextReaderBlock,
    CriticBlock,
    TrackingBlock,
    run_loop,
    seeded_state,
)


class TestCarryContextModeLast:
    """mode='last' carries only the previous round output."""

    @pytest.mark.asyncio
    async def test_last_mode_carries_previous_round_only(self):
        from runsight_core import LoopBlock
        from runsight_core.blocks.loop import CarryContextConfig

        config = CarryContextConfig(mode="last", inject_as="previous_round_context")
        reader = ContextReaderBlock("reader", read_key="previous_round_context")
        blocks = {"reader": reader}
        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["reader"],
            max_rounds=3,
            carry_context=config,
        )
        blocks["loop_block"] = loop

        result_state = await run_loop(loop, seeded_state("previous_round_context"), blocks)

        snapshots = result_state.shared_memory.get("reader_snapshots", [])
        assert len(snapshots) == 3
        assert snapshots[0] is None
        assert snapshots[1] is not None
        assert "reader" in snapshots[1]
        assert snapshots[2] is not None
        assert "reader" in snapshots[2]

    @pytest.mark.asyncio
    async def test_last_mode_without_source_filter_carries_all_inner_outputs(self):
        from runsight_core import LoopBlock
        from runsight_core.blocks.loop import CarryContextConfig

        config = CarryContextConfig(mode="last", source_blocks=None, inject_as="prev_ctx")
        writer = TrackingBlock("writer")
        critic = TrackingBlock("critic")
        reader = ContextReaderBlock("reader", read_key="prev_ctx")
        blocks = {"writer": writer, "critic": critic, "reader": reader}
        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["writer", "critic", "reader"],
            max_rounds=3,
            carry_context=config,
        )
        blocks["loop_block"] = loop

        result_state = await run_loop(loop, seeded_state("prev_ctx"), blocks)

        snapshots = result_state.shared_memory.get("reader_snapshots", [])
        assert snapshots[0] is None
        round_2_ctx = snapshots[1]
        assert round_2_ctx is not None
        assert "writer" in str(round_2_ctx)
        assert "critic" in str(round_2_ctx)


class TestCarryContextModeAll:
    """mode='all' carries accumulated history of prior rounds."""

    @pytest.mark.asyncio
    async def test_all_mode_accumulates_history(self):
        from runsight_core import LoopBlock
        from runsight_core.blocks.loop import CarryContextConfig

        config = CarryContextConfig(mode="all", inject_as="all_rounds_context")
        reader = ContextReaderBlock("reader", read_key="all_rounds_context")
        blocks = {"reader": reader}
        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["reader"],
            max_rounds=4,
            carry_context=config,
        )
        blocks["loop_block"] = loop

        result_state = await run_loop(loop, seeded_state("all_rounds_context"), blocks)

        snapshots = result_state.shared_memory.get("reader_snapshots", [])
        assert len(snapshots) == 4
        assert snapshots[0] is None
        assert snapshots[1] is not None
        round_3_ctx = snapshots[2]
        assert round_3_ctx is not None
        assert len(str(round_3_ctx)) > len(str(snapshots[1]))
        round_4_ctx = snapshots[3]
        assert round_4_ctx is not None
        assert len(str(round_4_ctx)) > len(str(round_3_ctx))

    @pytest.mark.asyncio
    async def test_all_mode_has_more_history_than_last_mode(self):
        from runsight_core import LoopBlock
        from runsight_core.blocks.loop import CarryContextConfig

        reader_all = ContextReaderBlock("reader", read_key="ctx")
        loop_all = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["reader"],
            max_rounds=3,
            carry_context=CarryContextConfig(mode="all", inject_as="ctx"),
        )
        blocks_all = {"reader": reader_all, "loop_block": loop_all}
        result_all = await run_loop(loop_all, seeded_state("ctx"), blocks_all)

        reader_last = ContextReaderBlock("reader", read_key="ctx")
        loop_last = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["reader"],
            max_rounds=3,
            carry_context=CarryContextConfig(mode="last", inject_as="ctx"),
        )
        blocks_last = {"reader": reader_last, "loop_block": loop_last}
        result_last = await run_loop(loop_last, seeded_state("ctx"), blocks_last)

        snapshots_all = result_all.shared_memory.get("reader_snapshots", [])
        snapshots_last = result_last.shared_memory.get("reader_snapshots", [])
        assert len(str(snapshots_all[2])) > len(str(snapshots_last[2]))


class TestCarryContextSourceBlocks:
    """source_blocks filters which inner block outputs are carried."""

    @pytest.mark.asyncio
    async def test_source_blocks_filters_to_specific_block(self):
        from runsight_core import LoopBlock
        from runsight_core.blocks.loop import CarryContextConfig

        config = CarryContextConfig(
            mode="last",
            source_blocks=["critic"],
            inject_as="feedback",
        )
        writer = TrackingBlock("writer")
        critic = CriticBlock("critic")
        reader = ContextReaderBlock("reader", read_key="feedback")
        blocks = {"writer": writer, "critic": critic, "reader": reader}
        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["writer", "critic", "reader"],
            max_rounds=3,
            carry_context=config,
        )
        blocks["loop_block"] = loop

        result_state = await run_loop(loop, seeded_state("feedback"), blocks)

        round_2_ctx = result_state.shared_memory.get("reader_snapshots", [])[1]
        assert round_2_ctx is not None
        assert "critic" in str(round_2_ctx) or "feedback" in str(round_2_ctx)
        assert "writer_output" not in str(round_2_ctx)

    @pytest.mark.asyncio
    async def test_source_blocks_none_carries_all_inner_outputs(self):
        from runsight_core import LoopBlock
        from runsight_core.blocks.loop import CarryContextConfig

        config = CarryContextConfig(mode="last", source_blocks=None, inject_as="all_ctx")
        writer = TrackingBlock("writer")
        critic = CriticBlock("critic")
        reader = ContextReaderBlock("reader", read_key="all_ctx")
        blocks = {"writer": writer, "critic": critic, "reader": reader}
        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["writer", "critic", "reader"],
            max_rounds=3,
            carry_context=config,
        )
        blocks["loop_block"] = loop

        result_state = await run_loop(loop, seeded_state("all_ctx"), blocks)

        round_2_ctx = result_state.shared_memory.get("reader_snapshots", [])[1]
        assert round_2_ctx is not None
        assert "writer" in str(round_2_ctx)
        assert "critic" in str(round_2_ctx)

    @pytest.mark.asyncio
    async def test_source_blocks_multiple_specific_blocks(self):
        from runsight_core import LoopBlock
        from runsight_core.blocks.loop import CarryContextConfig

        config = CarryContextConfig(
            mode="last",
            source_blocks=["draft_block", "publish_block"],
            inject_as="ctx",
        )
        draft_block = TrackingBlock("draft_block")
        review_block = TrackingBlock("review_block")
        publish_block = TrackingBlock("publish_block")
        reader = ContextReaderBlock("reader", read_key="ctx")
        blocks = {
            "draft_block": draft_block,
            "review_block": review_block,
            "publish_block": publish_block,
            "reader": reader,
        }
        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["draft_block", "review_block", "publish_block", "reader"],
            max_rounds=2,
            carry_context=config,
        )
        blocks["loop_block"] = loop

        result_state = await run_loop(loop, seeded_state("ctx"), blocks)

        round_2_ctx = result_state.shared_memory.get("reader_snapshots", [])[1]
        assert round_2_ctx is not None
        assert "draft_block" in str(round_2_ctx)
        assert "publish_block" in str(round_2_ctx)
        assert "review_block" not in str(round_2_ctx)


class TestCarryContextInjectAs:
    """inject_as controls the shared-memory key visible to inner blocks."""

    @pytest.mark.asyncio
    async def test_default_inject_key_is_written(self):
        from runsight_core import LoopBlock
        from runsight_core.blocks.loop import CarryContextConfig

        inner = TrackingBlock("inner")
        blocks = {"inner": inner}
        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["inner"],
            max_rounds=2,
            carry_context=CarryContextConfig(),
        )
        blocks["loop_block"] = loop

        result_state = await run_loop(loop, seeded_state(), blocks)

        assert "previous_round_context" in result_state.shared_memory

    @pytest.mark.asyncio
    async def test_custom_inject_key_is_written_without_default_key(self):
        from runsight_core import LoopBlock
        from runsight_core.blocks.loop import CarryContextConfig

        inner = TrackingBlock("inner")
        blocks = {"inner": inner}
        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["inner"],
            max_rounds=2,
            carry_context=CarryContextConfig(inject_as="feedback"),
        )
        blocks["loop_block"] = loop

        result_state = await run_loop(loop, seeded_state(), blocks)

        assert "feedback" in result_state.shared_memory
        assert result_state.shared_memory.get("previous_round_context") is None
