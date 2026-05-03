"""LoopBlock writer-critic carry-context integration and formatting."""

from __future__ import annotations

import pytest
from loop_carry_context_helpers import (
    ContextAwareWriterBlock,
    ContextReaderBlock,
    CriticBlock,
    NullSoulOutputBlock,
    TrackingBlock,
    run_loop,
    seeded_state,
)
from runsight_core.workflow import Workflow


class TestWriterCriticCarryContextIntegration:
    """Writer sees critic feedback carried from previous rounds."""

    @pytest.mark.asyncio
    async def test_critic_feedback_visible_to_writer_in_following_rounds(self):
        from runsight_core import LoopBlock
        from runsight_core.blocks.loop import CarryContextConfig

        writer = ContextAwareWriterBlock("writer", context_key="feedback")
        critic = CriticBlock("critic")
        blocks = {"writer": writer, "critic": critic}
        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["writer", "critic"],
            max_rounds=3,
            carry_context=CarryContextConfig(
                mode="last",
                source_blocks=["critic"],
                inject_as="feedback",
            ),
        )
        blocks["loop_block"] = loop

        result_state = await run_loop(loop, seeded_state("feedback"), blocks)

        contexts_seen = result_state.shared_memory.get("writer_contexts_seen", [])
        assert contexts_seen[0] is None
        assert contexts_seen[1] is not None
        assert "feedback_round_1" in str(contexts_seen[1])
        assert contexts_seen[2] is not None
        assert "feedback_round_2" in str(contexts_seen[2])

    @pytest.mark.asyncio
    async def test_all_mode_accumulates_critic_feedback_for_writer(self):
        from runsight_core import LoopBlock
        from runsight_core.blocks.loop import CarryContextConfig

        writer = ContextAwareWriterBlock("writer", context_key="feedback_history")
        critic = CriticBlock("critic")
        blocks = {"writer": writer, "critic": critic}
        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["writer", "critic"],
            max_rounds=3,
            carry_context=CarryContextConfig(
                mode="all",
                source_blocks=["critic"],
                inject_as="feedback_history",
            ),
        )
        blocks["loop_block"] = loop

        result_state = await run_loop(loop, seeded_state("feedback_history"), blocks)

        contexts_seen = result_state.shared_memory.get("writer_contexts_seen", [])
        assert contexts_seen[0] is None
        assert contexts_seen[1] is not None
        assert "feedback_round_1" in str(contexts_seen[1])
        assert contexts_seen[2] is not None
        assert "feedback_round_1" in str(contexts_seen[2])
        assert "feedback_round_2" in str(contexts_seen[2])

    @pytest.mark.asyncio
    async def test_writer_critic_workflow_run_preserves_carry_context(self):
        from runsight_core import LoopBlock
        from runsight_core.blocks.loop import CarryContextConfig

        writer = ContextAwareWriterBlock("writer", context_key="feedback")
        critic = CriticBlock("critic")
        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["writer", "critic"],
            max_rounds=3,
            carry_context=CarryContextConfig(
                mode="last",
                source_blocks=["critic"],
                inject_as="feedback",
            ),
        )

        workflow = Workflow(name="carry_context_runtime_workflow")
        workflow.add_block(writer)
        workflow.add_block(critic)
        workflow.add_block(loop)
        workflow.add_transition("loop_block", None)
        workflow.set_entry("loop_block")

        result_state = await workflow.run(seeded_state("feedback"))

        assert "loop_block" in result_state.results
        contexts_seen = result_state.shared_memory.get("writer_contexts_seen", [])
        assert len(contexts_seen) == 3
        assert contexts_seen[1] is not None


class TestCarryContextFormat:
    """Carried context has stable, readable data shapes."""

    @pytest.mark.asyncio
    async def test_last_mode_context_is_dict_keyed_by_source_block_id(self):
        from runsight_core import LoopBlock
        from runsight_core.blocks.loop import CarryContextConfig

        writer = TrackingBlock("writer")
        critic = CriticBlock("critic")
        reader = ContextReaderBlock("reader", read_key="ctx")
        blocks = {"writer": writer, "critic": critic, "reader": reader}
        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["writer", "critic", "reader"],
            max_rounds=2,
            carry_context=CarryContextConfig(
                mode="last",
                source_blocks=["writer", "critic"],
                inject_as="ctx",
            ),
        )
        blocks["loop_block"] = loop

        result_state = await run_loop(loop, seeded_state("ctx"), blocks)

        round_2_ctx = result_state.shared_memory.get("reader_snapshots", [])[1]
        assert isinstance(round_2_ctx, dict)
        assert "writer" in round_2_ctx
        assert "critic" in round_2_ctx

    @pytest.mark.asyncio
    async def test_all_mode_context_is_list_of_round_dicts(self):
        from runsight_core import LoopBlock
        from runsight_core.blocks.loop import CarryContextConfig

        inner = TrackingBlock("inner")
        reader = ContextReaderBlock("reader", read_key="ctx")
        blocks = {"inner": inner, "reader": reader}
        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["inner", "reader"],
            max_rounds=3,
            carry_context=CarryContextConfig(mode="all", inject_as="ctx"),
        )
        blocks["loop_block"] = loop

        result_state = await run_loop(loop, seeded_state("ctx"), blocks)

        round_3_ctx = result_state.shared_memory.get("reader_snapshots", [])[2]
        assert isinstance(round_3_ctx, list)
        assert len(round_3_ctx) == 2

    @pytest.mark.asyncio
    async def test_last_mode_context_is_single_dict(self):
        from runsight_core import LoopBlock
        from runsight_core.blocks.loop import CarryContextConfig

        inner = TrackingBlock("inner")
        reader = ContextReaderBlock("reader", read_key="ctx")
        blocks = {"inner": inner, "reader": reader}
        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["inner", "reader"],
            max_rounds=3,
            carry_context=CarryContextConfig(mode="last", inject_as="ctx"),
        )
        blocks["loop_block"] = loop

        result_state = await run_loop(loop, seeded_state("ctx"), blocks)

        round_2_ctx = result_state.shared_memory.get("reader_snapshots", [])[1]
        assert isinstance(round_2_ctx, dict)
        assert not isinstance(round_2_ctx, list)

    @pytest.mark.asyncio
    async def test_null_soul_source_block_does_not_crash_carry_formatting(self):
        from runsight_core import LoopBlock
        from runsight_core.blocks.loop import CarryContextConfig

        null_soul = NullSoulOutputBlock("null_soul")
        reader = ContextReaderBlock("reader", read_key="ctx")
        blocks = {"null_soul": null_soul, "reader": reader}
        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["null_soul", "reader"],
            max_rounds=2,
            carry_context=CarryContextConfig(mode="last", inject_as="ctx"),
        )
        blocks["loop_block"] = loop

        result_state = await run_loop(loop, seeded_state("ctx"), blocks)

        assert result_state.shared_memory.get("ctx") is not None
        assert "null_soul_output" in str(result_state.shared_memory.get("ctx"))
