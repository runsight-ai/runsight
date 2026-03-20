"""
Failing tests for RUN-195: LoopBlock carry_context + BlockResult compatibility.

Bug: LoopBlock.execute() collects round outputs via:
    round_outputs = {sid: state.results.get(sid) for sid in source_ids}
Since RUN-178, state.results contains BlockResult objects (not raw strings).
The carry_context code passes these BlockResult objects directly into
shared_memory[inject_as] and carry_history, instead of extracting .output.

Tests cover:
- mode="last": shared_memory[inject_as] values must be strings, not BlockResult
- mode="all": accumulated carry_history entries must be strings, not BlockResult
- BlockResult with artifact_ref: only .output is carried, artifact_ref is NOT
- carry_history across N rounds contains only strings (memory-efficient)
- Source block not yet executed (returns None) is preserved as None
"""

from typing import Any, Dict, List

import pytest

from runsight_core.blocks.base import BaseBlock
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.yaml.schema import CarryContextConfig


# ==============================================================================
# Test helpers — blocks that produce BlockResult (matching real-world behavior)
# ==============================================================================


class BlockResultProducer(BaseBlock):
    """Inner block that writes a BlockResult into state.results, like real blocks do."""

    def __init__(self, block_id: str, output_prefix: str = "output"):
        super().__init__(block_id)
        self.output_prefix = output_prefix

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        calls = list(state.shared_memory.get(f"{self.block_id}_calls", []))
        calls.append(len(calls) + 1)
        round_num = len(calls)

        output_text = f"{self.output_prefix}_round_{round_num}"
        return state.model_copy(
            update={
                "results": {
                    **state.results,
                    self.block_id: BlockResult(output=output_text),
                },
                "shared_memory": {
                    **state.shared_memory,
                    f"{self.block_id}_calls": calls,
                },
            }
        )


class BlockResultWithArtifact(BaseBlock):
    """Inner block that writes a BlockResult with artifact_ref and metadata."""

    def __init__(self, block_id: str, artifact_ref: str = "s3://bucket/artifact.json"):
        super().__init__(block_id)
        self.artifact_ref = artifact_ref

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        calls = list(state.shared_memory.get(f"{self.block_id}_calls", []))
        calls.append(len(calls) + 1)
        round_num = len(calls)

        output_text = f"artifact_output_round_{round_num}"
        return state.model_copy(
            update={
                "results": {
                    **state.results,
                    self.block_id: BlockResult(
                        output=output_text,
                        artifact_ref=self.artifact_ref,
                        artifact_type="json",
                        metadata={"size_bytes": 1024, "round": round_num},
                    ),
                },
                "shared_memory": {
                    **state.shared_memory,
                    f"{self.block_id}_calls": calls,
                },
            }
        )


class ContextSnapshotBlock(BaseBlock):
    """Block that snapshots what it sees in shared_memory[read_key] each round.

    Produces a BlockResult to match real-world behavior.
    """

    def __init__(self, block_id: str, read_key: str = "previous_round_context"):
        super().__init__(block_id)
        self.read_key = read_key

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        calls = list(state.shared_memory.get(f"{self.block_id}_calls", []))
        calls.append(len(calls) + 1)
        round_num = len(calls)

        context_value = state.shared_memory.get(self.read_key)
        snapshots = list(state.shared_memory.get(f"{self.block_id}_snapshots", []))
        snapshots.append(context_value)

        output_text = f"{self.block_id}_output_round_{round_num}"
        return state.model_copy(
            update={
                "results": {
                    **state.results,
                    self.block_id: BlockResult(output=output_text),
                },
                "shared_memory": {
                    **state.shared_memory,
                    f"{self.block_id}_calls": calls,
                    f"{self.block_id}_snapshots": snapshots,
                },
            }
        )


# ==============================================================================
# 1. mode="last" — carried values must be strings, not BlockResult
# ==============================================================================


class TestCarryContextLastModeBlockResult:
    """mode='last' with BlockResult-producing blocks must carry string values."""

    @pytest.mark.asyncio
    async def test_last_mode_values_are_strings_not_blockresult(self):
        """shared_memory[inject_as] dict values should be strings, not BlockResult objects."""
        from runsight_core.blocks.implementations import LoopBlock

        config = CarryContextConfig(mode="last", inject_as="prev_ctx")

        producer = BlockResultProducer("producer", output_prefix="produced")
        blocks: Dict[str, BaseBlock] = {"producer": producer}

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["producer"],
            max_rounds=2,
            carry_context=config,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        # After 2 rounds, inject_as key should exist
        carried = result_state.shared_memory["prev_ctx"]
        assert carried is not None

        # The carried dict maps source block IDs to their outputs
        # BUG: currently carries BlockResult objects instead of strings
        producer_value = carried["producer"]
        assert isinstance(producer_value, str), (
            f"Expected string in carried context, got {type(producer_value).__name__}. "
            f"carry_context must extract .output from BlockResult."
        )
        assert producer_value == "produced_round_2"

    @pytest.mark.asyncio
    async def test_last_mode_multi_source_all_strings(self):
        """With multiple source blocks, all values in the carried dict must be strings."""
        from runsight_core.blocks.implementations import LoopBlock

        config = CarryContextConfig(
            mode="last",
            source_blocks=None,  # carry all inner blocks
            inject_as="round_ctx",
        )

        writer = BlockResultProducer("writer", output_prefix="draft")
        critic = BlockResultProducer("critic", output_prefix="feedback")
        blocks: Dict[str, BaseBlock] = {"writer": writer, "critic": critic}

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["writer", "critic"],
            max_rounds=2,
            carry_context=config,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        carried = result_state.shared_memory["round_ctx"]

        for block_id in ["writer", "critic"]:
            value = carried[block_id]
            assert isinstance(value, str), (
                f"Expected string for '{block_id}' in carried context, got {type(value).__name__}"
            )
            assert "BlockResult" not in repr(value)

    @pytest.mark.asyncio
    async def test_last_mode_reader_sees_strings(self):
        """A downstream block reading carried context should see string values, not BlockResult."""
        from runsight_core.blocks.implementations import LoopBlock

        config = CarryContextConfig(
            mode="last",
            source_blocks=["producer"],
            inject_as="feedback",
        )

        producer = BlockResultProducer("producer", output_prefix="data")
        reader = ContextSnapshotBlock("reader", read_key="feedback")
        blocks: Dict[str, BaseBlock] = {"producer": producer, "reader": reader}

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["producer", "reader"],
            max_rounds=3,
            carry_context=config,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        snapshots = result_state.shared_memory.get("reader_snapshots", [])
        assert len(snapshots) == 3

        # Round 1: no context yet
        assert snapshots[0] is None

        # Rounds 2 and 3: the reader should see a dict with string values
        for round_idx in [1, 2]:
            ctx = snapshots[round_idx]
            assert ctx is not None
            producer_val = ctx["producer"]
            assert isinstance(producer_val, str), (
                f"Round {round_idx + 1}: expected string, got {type(producer_val).__name__}"
            )


# ==============================================================================
# 2. mode="all" — accumulated history entries must be strings, not BlockResult
# ==============================================================================


class TestCarryContextAllModeBlockResult:
    """mode='all' with BlockResult-producing blocks must carry string values in history."""

    @pytest.mark.asyncio
    async def test_all_mode_history_values_are_strings(self):
        """Each round entry in the history list should contain string values, not BlockResult."""
        from runsight_core.blocks.implementations import LoopBlock

        config = CarryContextConfig(mode="all", inject_as="history_ctx")

        producer = BlockResultProducer("producer", output_prefix="result")
        blocks: Dict[str, BaseBlock] = {"producer": producer}

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["producer"],
            max_rounds=3,
            carry_context=config,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        # mode="all" injects a list of dicts (one per round)
        history: List[Dict[str, Any]] = result_state.shared_memory["history_ctx"]
        assert isinstance(history, list)
        assert len(history) == 3  # one entry per round

        for round_idx, round_entry in enumerate(history):
            value = round_entry["producer"]
            assert isinstance(value, str), (
                f"Round {round_idx + 1}: expected string in carry_history, "
                f"got {type(value).__name__}. "
                f"carry_context must extract .output from BlockResult."
            )
            assert value == f"result_round_{round_idx + 1}"

    @pytest.mark.asyncio
    async def test_all_mode_reader_sees_string_history(self):
        """A downstream block should see string values in the accumulated history."""
        from runsight_core.blocks.implementations import LoopBlock

        config = CarryContextConfig(mode="all", inject_as="all_ctx")

        producer = BlockResultProducer("producer", output_prefix="text")
        reader = ContextSnapshotBlock("reader", read_key="all_ctx")
        blocks: Dict[str, BaseBlock] = {"producer": producer, "reader": reader}

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["producer", "reader"],
            max_rounds=3,
            carry_context=config,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        snapshots = result_state.shared_memory.get("reader_snapshots", [])

        # Round 3: history should have 2 entries (rounds 1 and 2)
        history_at_round_3 = snapshots[2]
        assert history_at_round_3 is not None
        assert isinstance(history_at_round_3, list)

        for entry in history_at_round_3:
            val = entry["producer"]
            assert isinstance(val, str), (
                f"Expected string in history entry, got {type(val).__name__}"
            )


# ==============================================================================
# 3. BlockResult with artifact_ref — only .output is carried
# ==============================================================================


class TestCarryContextArtifactRefExclusion:
    """carry_context must extract .output from BlockResult, excluding artifact_ref and metadata."""

    @pytest.mark.asyncio
    async def test_artifact_ref_not_in_carried_context_last_mode(self):
        """In mode='last', only .output should be carried — not artifact_ref or metadata."""
        from runsight_core.blocks.implementations import LoopBlock

        config = CarryContextConfig(
            mode="last",
            source_blocks=["artifact_block"],
            inject_as="ctx",
        )

        artifact_block = BlockResultWithArtifact(
            "artifact_block", artifact_ref="s3://bucket/data.json"
        )
        blocks: Dict[str, BaseBlock] = {"artifact_block": artifact_block}

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["artifact_block"],
            max_rounds=2,
            carry_context=config,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        carried = result_state.shared_memory["ctx"]
        value = carried["artifact_block"]

        # Must be a plain string (the .output), not a BlockResult or dict
        assert isinstance(value, str), (
            f"Expected string output, got {type(value).__name__}. "
            f"carry_context should extract .output from BlockResult, "
            f"not pass the whole object."
        )
        assert value == "artifact_output_round_2"

        # Verify artifact_ref is NOT anywhere in the carried value
        assert "s3://" not in str(carried)
        assert "artifact_ref" not in str(carried)
        assert "size_bytes" not in str(carried)

    @pytest.mark.asyncio
    async def test_artifact_ref_not_in_carried_context_all_mode(self):
        """In mode='all', history entries must contain .output strings, not BlockResult."""
        from runsight_core.blocks.implementations import LoopBlock

        config = CarryContextConfig(
            mode="all",
            source_blocks=["artifact_block"],
            inject_as="history",
        )

        artifact_block = BlockResultWithArtifact(
            "artifact_block", artifact_ref="s3://bucket/model.pt"
        )
        blocks: Dict[str, BaseBlock] = {"artifact_block": artifact_block}

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["artifact_block"],
            max_rounds=3,
            carry_context=config,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        history = result_state.shared_memory["history"]
        assert isinstance(history, list)

        for round_idx, entry in enumerate(history):
            value = entry["artifact_block"]
            assert isinstance(value, str), (
                f"Round {round_idx + 1}: expected string, got {type(value).__name__}"
            )
            # artifact_ref must not leak into carry_history
            assert "s3://" not in str(entry)
            assert "model.pt" not in str(entry)


# ==============================================================================
# 4. carry_history internal list contains only strings
# ==============================================================================


class TestCarryHistoryContainsStrings:
    """carry_history (the internal accumulator) must contain strings, not BlockResult."""

    @pytest.mark.asyncio
    async def test_carry_history_values_are_strings_across_rounds(self):
        """After N rounds, every value in every carry_history entry should be a string."""
        from runsight_core.blocks.implementations import LoopBlock

        config = CarryContextConfig(mode="all", inject_as="full_history")

        producer = BlockResultProducer("producer", output_prefix="round_data")
        blocks: Dict[str, BaseBlock] = {"producer": producer}

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["producer"],
            max_rounds=5,
            carry_context=config,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        history = result_state.shared_memory["full_history"]
        assert len(history) == 5

        for round_idx, entry in enumerate(history):
            for block_id, value in entry.items():
                assert not isinstance(value, BlockResult), (
                    f"Round {round_idx + 1}, block '{block_id}': "
                    f"carry_history contains BlockResult object. "
                    f"Expected string."
                )
                assert isinstance(value, str), (
                    f"Round {round_idx + 1}, block '{block_id}': "
                    f"expected str, got {type(value).__name__}"
                )


# ==============================================================================
# 5. Edge case: source block not yet executed (None) is preserved
# ==============================================================================


class TestCarryContextNonePreserved:
    """When a source block has no result yet, None should be carried (not crash)."""

    @pytest.mark.asyncio
    async def test_missing_source_block_result_carries_none(self):
        """If source_blocks references a block whose result is missing, carry None."""
        from runsight_core.blocks.implementations import LoopBlock

        config = CarryContextConfig(
            mode="last",
            source_blocks=["ghost"],  # "ghost" is in inner_block_refs but never produces a result
            inject_as="ctx",
        )

        # A block that writes results under a DIFFERENT key than its own block_id
        class NoResultBlock(BaseBlock):
            async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
                # Deliberately does NOT write to state.results[self.block_id]
                return state

        ghost = NoResultBlock("ghost")
        blocks: Dict[str, BaseBlock] = {"ghost": ghost}

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["ghost"],
            max_rounds=2,
            carry_context=config,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        carried = result_state.shared_memory["ctx"]
        # ghost had no result, so its carried value should be None
        assert carried["ghost"] is None


# ==============================================================================
# 6. Mixed scenario: some blocks have artifact_ref, some don't
# ==============================================================================


class TestCarryContextMixedBlockResults:
    """Mix of BlockResult with and without artifact_ref — all should extract .output."""

    @pytest.mark.asyncio
    async def test_mixed_artifact_and_plain_blockresults(self):
        """Both plain and artifact BlockResults should have .output extracted."""
        from runsight_core.blocks.implementations import LoopBlock

        config = CarryContextConfig(
            mode="last",
            source_blocks=None,  # carry all
            inject_as="mixed_ctx",
        )

        plain_block = BlockResultProducer("plain", output_prefix="plain_out")
        artifact_block = BlockResultWithArtifact("rich", artifact_ref="gs://bucket/file")
        blocks: Dict[str, BaseBlock] = {"plain": plain_block, "rich": artifact_block}

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["plain", "rich"],
            max_rounds=2,
            carry_context=config,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        carried = result_state.shared_memory["mixed_ctx"]

        # Both values must be plain strings
        plain_val = carried["plain"]
        rich_val = carried["rich"]

        assert isinstance(plain_val, str), (
            f"plain block: expected str, got {type(plain_val).__name__}"
        )
        assert isinstance(rich_val, str), f"rich block: expected str, got {type(rich_val).__name__}"

        assert plain_val == "plain_out_round_2"
        assert rich_val == "artifact_output_round_2"

        # No BlockResult repr or artifact data should be in the carried context
        carried_str = str(carried)
        assert "BlockResult" not in carried_str
        assert "gs://bucket" not in carried_str
        assert "artifact_ref" not in carried_str
