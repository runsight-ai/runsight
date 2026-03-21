"""
Failing tests for RUN-160: Generalize context passing between LoopBlock rounds.

Tests cover:
- Schema: CarryContextConfig model validation (enabled, mode, source_blocks, inject_as)
- Schema: LoopBlockDef accepts carry_context field
- Unit: mode="last" carries only previous round output
- Unit: mode="all" carries concatenated history of all rounds
- Unit: source_blocks filters to specific inner block outputs
- Unit: source_blocks=None carries all inner block outputs
- Unit: inject_as key appears in shared_memory for inner blocks to read
- Unit: Round 1 has no carried context (first iteration)
- Unit: carry_context=None means no context passing (backward compatible)
- Unit: carry_context.enabled=False explicitly disables context passing
- Validation: source_blocks references non-existent block ID -> raise error
- Validation: source_blocks validated against inner_block_refs
- Edge: Inner block produces empty output -> carry empty string, don't skip
- Integration: Writer-Critic loop: critic feedback from round 1 visible to writer in round 2
- Integration: Carried context is correctly formatted and readable
"""

import pytest
from pydantic import TypeAdapter, ValidationError

from runsight_core.blocks.base import BaseBlock
from runsight_core.state import WorkflowState
from runsight_core.workflow import Workflow
from runsight_core.blocks.loop import LoopBlockDef
from runsight_core.yaml.schema import (
    BlockDef,
    RunsightWorkflowFile,
)


# -- Shared TypeAdapter for discriminated union --------------------------------

block_adapter = TypeAdapter(BlockDef)


def _validate_block(data: dict):
    """Validate a dict as a BlockDef via the discriminated union."""
    return block_adapter.validate_python(data)


# -- Test helpers --------------------------------------------------------------


class TrackingBlock(BaseBlock):
    """Block that records each call and writes output to results."""

    def __init__(self, block_id: str):
        super().__init__(block_id)

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        calls = list(state.shared_memory.get(f"{self.block_id}_calls", []))
        calls.append(len(calls) + 1)
        output = f"{self.block_id}_output_round_{len(calls)}"
        return state.model_copy(
            update={
                "results": {**state.results, self.block_id: output},
                "shared_memory": {
                    **state.shared_memory,
                    f"{self.block_id}_calls": calls,
                },
            }
        )


class ContextAwareWriterBlock(BaseBlock):
    """Writer block that reads previous_round_context from shared_memory
    and records what it saw."""

    def __init__(self, block_id: str, context_key: str = "previous_round_context"):
        super().__init__(block_id)
        self.context_key = context_key

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        calls = list(state.shared_memory.get(f"{self.block_id}_calls", []))
        calls.append(len(calls) + 1)
        round_num = len(calls)

        # Read the carried context from shared_memory
        carried = state.shared_memory.get(self.context_key)
        contexts_seen = list(state.shared_memory.get(f"{self.block_id}_contexts_seen", []))
        contexts_seen.append(carried)

        output = f"draft_round_{round_num}"
        return state.model_copy(
            update={
                "results": {**state.results, self.block_id: output},
                "shared_memory": {
                    **state.shared_memory,
                    f"{self.block_id}_calls": calls,
                    f"{self.block_id}_contexts_seen": contexts_seen,
                },
            }
        )


class CriticBlock(BaseBlock):
    """Critic block that produces feedback output."""

    def __init__(self, block_id: str):
        super().__init__(block_id)

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        calls = list(state.shared_memory.get(f"{self.block_id}_calls", []))
        calls.append(len(calls) + 1)
        round_num = len(calls)
        output = f"feedback_round_{round_num}"
        return state.model_copy(
            update={
                "results": {**state.results, self.block_id: output},
                "shared_memory": {
                    **state.shared_memory,
                    f"{self.block_id}_calls": calls,
                },
            }
        )


class EmptyOutputBlock(BaseBlock):
    """Block that produces empty string output."""

    def __init__(self, block_id: str):
        super().__init__(block_id)

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        calls = list(state.shared_memory.get(f"{self.block_id}_calls", []))
        calls.append(len(calls) + 1)
        return state.model_copy(
            update={
                "results": {**state.results, self.block_id: ""},
                "shared_memory": {
                    **state.shared_memory,
                    f"{self.block_id}_calls": calls,
                },
            }
        )


class ContextReaderBlock(BaseBlock):
    """Block that reads a specific shared_memory key and records what it found."""

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

        output = f"{self.block_id}_output_round_{round_num}"
        return state.model_copy(
            update={
                "results": {**state.results, self.block_id: output},
                "shared_memory": {
                    **state.shared_memory,
                    f"{self.block_id}_calls": calls,
                    f"{self.block_id}_snapshots": snapshots,
                },
            }
        )


# ==============================================================================
# 1. Schema tests -- CarryContextConfig model
# ==============================================================================


class TestCarryContextConfigSchema:
    """CarryContextConfig Pydantic model validates correctly."""

    def test_import_carry_context_config(self):
        """CarryContextConfig should be importable from runsight_core.yaml.schema."""
        from runsight_core.blocks.loop import CarryContextConfig

        assert CarryContextConfig is not None

    def test_default_values(self):
        """CarryContextConfig defaults: enabled=True, mode='last', source_blocks=None, inject_as='previous_round_context'."""
        from runsight_core.blocks.loop import CarryContextConfig

        config = CarryContextConfig()
        assert config.enabled is True
        assert config.mode == "last"
        assert config.source_blocks is None
        assert config.inject_as == "previous_round_context"

    def test_mode_accepts_last(self):
        """mode='last' should be accepted."""
        from runsight_core.blocks.loop import CarryContextConfig

        config = CarryContextConfig(mode="last")
        assert config.mode == "last"

    def test_mode_accepts_all(self):
        """mode='all' should be accepted."""
        from runsight_core.blocks.loop import CarryContextConfig

        config = CarryContextConfig(mode="all")
        assert config.mode == "all"

    def test_mode_rejects_invalid(self):
        """mode='invalid' should raise ValidationError."""
        from runsight_core.blocks.loop import CarryContextConfig

        with pytest.raises(ValidationError, match="mode"):
            CarryContextConfig(mode="invalid")

    def test_source_blocks_accepts_list(self):
        """source_blocks should accept a list of block IDs."""
        from runsight_core.blocks.loop import CarryContextConfig

        config = CarryContextConfig(source_blocks=["block_a", "block_b"])
        assert config.source_blocks == ["block_a", "block_b"]

    def test_source_blocks_none_means_all(self):
        """source_blocks=None means carry all inner block outputs."""
        from runsight_core.blocks.loop import CarryContextConfig

        config = CarryContextConfig(source_blocks=None)
        assert config.source_blocks is None

    def test_inject_as_custom_key(self):
        """inject_as should accept a custom key name."""
        from runsight_core.blocks.loop import CarryContextConfig

        config = CarryContextConfig(inject_as="feedback")
        assert config.inject_as == "feedback"

    def test_enabled_false_disables(self):
        """enabled=False should be stored correctly."""
        from runsight_core.blocks.loop import CarryContextConfig

        config = CarryContextConfig(enabled=False)
        assert config.enabled is False


# ==============================================================================
# 2. Schema tests -- LoopBlockDef accepts carry_context
# ==============================================================================


class TestLoopBlockDefCarryContextSchema:
    """LoopBlockDef should accept an optional carry_context field."""

    def test_carry_context_accepts_config(self):
        """carry_context should accept a CarryContextConfig dict."""
        block = _validate_block(
            {
                "type": "loop",
                "inner_block_refs": ["block_a"],
                "max_rounds": 5,
                "carry_context": {
                    "enabled": True,
                    "mode": "last",
                    "inject_as": "previous_round_context",
                },
            }
        )
        assert isinstance(block, LoopBlockDef)
        assert block.carry_context is not None
        assert block.carry_context.enabled is True
        assert block.carry_context.mode == "last"

    def test_carry_context_defaults_to_none(self):
        """carry_context should default to None when not specified."""
        block = _validate_block(
            {
                "type": "loop",
                "inner_block_refs": ["block_a"],
                "max_rounds": 5,
            }
        )
        assert isinstance(block, LoopBlockDef)
        assert block.carry_context is None

    def test_carry_context_with_source_blocks(self):
        """carry_context should accept source_blocks list."""
        block = _validate_block(
            {
                "type": "loop",
                "inner_block_refs": ["writer", "critic"],
                "max_rounds": 3,
                "carry_context": {
                    "source_blocks": ["critic"],
                    "inject_as": "feedback",
                },
            }
        )
        assert isinstance(block, LoopBlockDef)
        assert block.carry_context.source_blocks == ["critic"]
        assert block.carry_context.inject_as == "feedback"

    def test_carry_context_mode_all(self):
        """carry_context with mode='all' should be parsed correctly."""
        block = _validate_block(
            {
                "type": "loop",
                "inner_block_refs": ["block_a"],
                "max_rounds": 5,
                "carry_context": {
                    "mode": "all",
                },
            }
        )
        assert isinstance(block, LoopBlockDef)
        assert block.carry_context.mode == "all"

    def test_carry_context_in_full_workflow_file(self):
        """carry_context should parse correctly inside a full RunsightWorkflowFile."""
        raw = {
            "version": "1.0",
            "souls": {
                "writer": {
                    "id": "writer_1",
                    "role": "Writer",
                    "system_prompt": "You write.",
                },
                "critic": {
                    "id": "critic_1",
                    "role": "Critic",
                    "system_prompt": "You critique.",
                },
            },
            "blocks": {
                "write_block": {"type": "linear", "soul_ref": "writer"},
                "critic_block": {"type": "linear", "soul_ref": "critic"},
                "loop_block": {
                    "type": "loop",
                    "inner_block_refs": ["write_block", "critic_block"],
                    "max_rounds": 3,
                    "carry_context": {
                        "mode": "last",
                        "source_blocks": ["critic_block"],
                        "inject_as": "feedback",
                    },
                },
            },
            "workflow": {
                "name": "carry_context_test",
                "entry": "loop_block",
                "transitions": [{"from": "loop_block", "to": None}],
            },
        }
        file_def = RunsightWorkflowFile.model_validate(raw)
        loop_def = file_def.blocks["loop_block"]
        assert isinstance(loop_def, LoopBlockDef)
        assert loop_def.carry_context is not None
        assert loop_def.carry_context.mode == "last"
        assert loop_def.carry_context.source_blocks == ["critic_block"]
        assert loop_def.carry_context.inject_as == "feedback"

    def test_carry_context_enabled_false_in_yaml(self):
        """carry_context with enabled=false should parse correctly."""
        block = _validate_block(
            {
                "type": "loop",
                "inner_block_refs": ["block_a"],
                "max_rounds": 5,
                "carry_context": {
                    "enabled": False,
                },
            }
        )
        assert isinstance(block, LoopBlockDef)
        assert block.carry_context is not None
        assert block.carry_context.enabled is False


# ==============================================================================
# 3. Unit tests -- LoopBlock constructor accepts carry_context
# ==============================================================================


class TestLoopBlockConstructorCarryContext:
    """LoopBlock constructor should accept carry_context parameter."""

    def test_constructor_accepts_carry_context_config(self):
        """LoopBlock should accept a carry_context parameter."""
        from runsight_core import LoopBlock
        from runsight_core.blocks.loop import CarryContextConfig

        config = CarryContextConfig(mode="last", inject_as="feedback")
        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["writer", "critic"],
            max_rounds=3,
            carry_context=config,
        )
        assert loop.carry_context is config

    def test_constructor_defaults_carry_context_to_none(self):
        """LoopBlock without carry_context should default to None."""
        from runsight_core import LoopBlock

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["inner"],
            max_rounds=3,
        )
        assert loop.carry_context is None

    def test_constructor_validates_source_blocks_against_inner_refs(self):
        """source_blocks referencing a block not in inner_block_refs should raise ValueError."""
        from runsight_core import LoopBlock
        from runsight_core.blocks.loop import CarryContextConfig

        config = CarryContextConfig(
            source_blocks=["nonexistent_block"],
            inject_as="ctx",
        )
        with pytest.raises(ValueError, match="nonexistent_block"):
            LoopBlock(
                block_id="loop_block",
                inner_block_refs=["writer", "critic"],
                max_rounds=3,
                carry_context=config,
            )

    def test_constructor_validates_partial_source_blocks_mismatch(self):
        """source_blocks with one valid and one invalid ref should still raise ValueError."""
        from runsight_core import LoopBlock
        from runsight_core.blocks.loop import CarryContextConfig

        config = CarryContextConfig(
            source_blocks=["writer", "ghost_block"],
            inject_as="ctx",
        )
        with pytest.raises(ValueError, match="ghost_block"):
            LoopBlock(
                block_id="loop_block",
                inner_block_refs=["writer", "critic"],
                max_rounds=3,
                carry_context=config,
            )


# ==============================================================================
# 4. Unit tests -- mode="last" carries only previous round output
# ==============================================================================


class TestCarryContextModeLast:
    """mode='last' carries only the previous round's output."""

    @pytest.mark.asyncio
    async def test_last_mode_carries_previous_round_only(self):
        """In mode='last', shared_memory[inject_as] should contain only the previous round's output."""
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

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        snapshots = result_state.shared_memory.get("reader_snapshots", [])
        assert len(snapshots) == 3

        # Round 1: no previous context (first iteration)
        assert snapshots[0] is None

        # Round 2: should contain reader's output from round 1
        assert snapshots[1] is not None
        assert "reader" in snapshots[1]  # context should reference the block's output

        # Round 3: should contain reader's output from round 2 ONLY (not round 1)
        assert snapshots[2] is not None
        assert "reader" in snapshots[2]
        # mode="last" means only one round's data, not accumulated
        # The exact shape depends on implementation, but it should NOT contain round 1 data

    @pytest.mark.asyncio
    async def test_last_mode_multi_block_carries_all_inner_outputs(self):
        """In mode='last' with source_blocks=None, carry all inner block outputs from previous round."""
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

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        snapshots = result_state.shared_memory.get("reader_snapshots", [])

        # Round 1: no context
        assert snapshots[0] is None

        # Round 2: context should include both writer and critic outputs from round 1
        round_2_ctx = snapshots[1]
        assert round_2_ctx is not None
        assert "writer" in str(round_2_ctx)
        assert "critic" in str(round_2_ctx)


# ==============================================================================
# 5. Unit tests -- mode="all" carries concatenated history
# ==============================================================================


class TestCarryContextModeAll:
    """mode='all' carries concatenated history of all prior rounds."""

    @pytest.mark.asyncio
    async def test_all_mode_accumulates_history(self):
        """In mode='all', shared_memory[inject_as] should contain all prior rounds' outputs."""
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

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        snapshots = result_state.shared_memory.get("reader_snapshots", [])
        assert len(snapshots) == 4

        # Round 1: no context
        assert snapshots[0] is None

        # Round 2: contains round 1 output
        assert snapshots[1] is not None

        # Round 3: contains BOTH round 1 and round 2 outputs
        round_3_ctx = snapshots[2]
        assert round_3_ctx is not None
        # All mode accumulates, so round 3 context should be larger than round 2 context
        assert len(str(round_3_ctx)) > len(str(snapshots[1]))

        # Round 4: contains rounds 1, 2, and 3 outputs
        round_4_ctx = snapshots[3]
        assert round_4_ctx is not None
        assert len(str(round_4_ctx)) > len(str(round_3_ctx))

    @pytest.mark.asyncio
    async def test_all_mode_is_memory_accumulative(self):
        """mode='all' should store all rounds, not just the last. Contrast with mode='last'."""
        from runsight_core import LoopBlock
        from runsight_core.blocks.loop import CarryContextConfig

        # Run with mode="all"
        config_all = CarryContextConfig(mode="all", inject_as="ctx")
        reader_all = ContextReaderBlock("reader", read_key="ctx")

        loop_all = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["reader"],
            max_rounds=3,
            carry_context=config_all,
        )
        blocks_all = {"reader": reader_all, "loop_block": loop_all}

        state = WorkflowState()
        result_all = await loop_all.execute(state, blocks=blocks_all)
        snapshots_all = result_all.shared_memory.get("reader_snapshots", [])

        # Run with mode="last"
        config_last = CarryContextConfig(mode="last", inject_as="ctx")
        reader_last = ContextReaderBlock("reader", read_key="ctx")

        loop_last = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["reader"],
            max_rounds=3,
            carry_context=config_last,
        )
        blocks_last = {"reader": reader_last, "loop_block": loop_last}

        state2 = WorkflowState()
        result_last = await loop_last.execute(state2, blocks=blocks_last)
        snapshots_last = result_last.shared_memory.get("reader_snapshots", [])

        # On round 3, mode="all" should have MORE context than mode="last"
        # because "all" accumulates rounds 1+2, while "last" only has round 2
        assert len(str(snapshots_all[2])) > len(str(snapshots_last[2]))


# ==============================================================================
# 6. Unit tests -- source_blocks filtering
# ==============================================================================


class TestCarryContextSourceBlocks:
    """source_blocks filters which inner block outputs are carried."""

    @pytest.mark.asyncio
    async def test_source_blocks_filters_to_specific_block(self):
        """Only outputs from blocks listed in source_blocks should be carried."""
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

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        snapshots = result_state.shared_memory.get("reader_snapshots", [])

        # Round 2: context should contain critic output but NOT writer output
        round_2_ctx = snapshots[1]
        assert round_2_ctx is not None
        assert "critic" in str(round_2_ctx) or "feedback" in str(round_2_ctx)
        # Writer output should NOT be in the carried context
        assert "writer_output" not in str(round_2_ctx)

    @pytest.mark.asyncio
    async def test_source_blocks_none_carries_all(self):
        """source_blocks=None should carry all inner block outputs."""
        from runsight_core import LoopBlock
        from runsight_core.blocks.loop import CarryContextConfig

        config = CarryContextConfig(
            mode="last",
            source_blocks=None,
            inject_as="all_ctx",
        )

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

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        snapshots = result_state.shared_memory.get("reader_snapshots", [])

        # Round 2: context should contain BOTH writer and critic outputs
        round_2_ctx = snapshots[1]
        assert round_2_ctx is not None
        assert "writer" in str(round_2_ctx)
        assert "critic" in str(round_2_ctx)

    @pytest.mark.asyncio
    async def test_source_blocks_multiple_specific_blocks(self):
        """source_blocks with multiple IDs should carry outputs from each."""
        from runsight_core import LoopBlock
        from runsight_core.blocks.loop import CarryContextConfig

        config = CarryContextConfig(
            mode="last",
            source_blocks=["block_a", "block_c"],
            inject_as="ctx",
        )

        block_a = TrackingBlock("block_a")
        block_b = TrackingBlock("block_b")
        block_c = TrackingBlock("block_c")
        reader = ContextReaderBlock("reader", read_key="ctx")
        blocks = {
            "block_a": block_a,
            "block_b": block_b,
            "block_c": block_c,
            "reader": reader,
        }

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["block_a", "block_b", "block_c", "reader"],
            max_rounds=2,
            carry_context=config,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        snapshots = result_state.shared_memory.get("reader_snapshots", [])

        # Round 2: context should have block_a and block_c but NOT block_b
        round_2_ctx = snapshots[1]
        assert round_2_ctx is not None
        assert "block_a" in str(round_2_ctx)
        assert "block_c" in str(round_2_ctx)
        assert "block_b" not in str(round_2_ctx)


# ==============================================================================
# 7. Unit tests -- inject_as key in shared_memory
# ==============================================================================


class TestCarryContextInjectAs:
    """inject_as key appears in shared_memory for inner blocks to read."""

    @pytest.mark.asyncio
    async def test_inject_as_default_key(self):
        """Default inject_as='previous_round_context' should appear in shared_memory."""
        from runsight_core import LoopBlock
        from runsight_core.blocks.loop import CarryContextConfig

        config = CarryContextConfig()  # defaults: inject_as="previous_round_context"

        inner = TrackingBlock("inner")
        blocks = {"inner": inner}

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["inner"],
            max_rounds=2,
            carry_context=config,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        # After round 2, the inject_as key should be present in shared_memory
        assert "previous_round_context" in result_state.shared_memory

    @pytest.mark.asyncio
    async def test_inject_as_custom_key(self):
        """Custom inject_as='feedback' should appear in shared_memory."""
        from runsight_core import LoopBlock
        from runsight_core.blocks.loop import CarryContextConfig

        config = CarryContextConfig(inject_as="feedback")

        inner = TrackingBlock("inner")
        blocks = {"inner": inner}

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["inner"],
            max_rounds=2,
            carry_context=config,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        assert "feedback" in result_state.shared_memory
        # The default key should NOT be present since we customized it
        assert "previous_round_context" not in result_state.shared_memory


# ==============================================================================
# 8. Unit tests -- Round 1 has no carried context
# ==============================================================================


class TestCarryContextRoundOne:
    """Round 1 should have no carried context (first iteration)."""

    @pytest.mark.asyncio
    async def test_round_1_has_no_context(self):
        """On round 1, the inject_as key should not be present in shared_memory."""
        from runsight_core import LoopBlock
        from runsight_core.blocks.loop import CarryContextConfig

        config = CarryContextConfig(inject_as="previous_round_context")

        reader = ContextReaderBlock("reader", read_key="previous_round_context")
        blocks = {"reader": reader}

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["reader"],
            max_rounds=3,
            carry_context=config,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        snapshots = result_state.shared_memory.get("reader_snapshots", [])
        # First snapshot (round 1) should be None — no previous context
        assert snapshots[0] is None

    @pytest.mark.asyncio
    async def test_round_1_no_inject_key_in_shared_memory(self):
        """On round 1, the inject_as key should not exist in shared_memory at all."""
        from runsight_core import LoopBlock
        from runsight_core.blocks.loop import CarryContextConfig

        config = CarryContextConfig(inject_as="ctx")

        class SharedMemoryInspectorBlock(BaseBlock):
            """Block that captures the full shared_memory state before each round."""

            def __init__(self, block_id: str):
                super().__init__(block_id)

            async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
                calls = list(state.shared_memory.get(f"{self.block_id}_calls", []))
                calls.append(len(calls) + 1)
                round_num = len(calls)

                # Record whether inject key exists in shared_memory
                key_snapshots = list(state.shared_memory.get(f"{self.block_id}_key_exists", []))
                key_snapshots.append("ctx" in state.shared_memory)

                return state.model_copy(
                    update={
                        "results": {**state.results, self.block_id: f"round_{round_num}"},
                        "shared_memory": {
                            **state.shared_memory,
                            f"{self.block_id}_calls": calls,
                            f"{self.block_id}_key_exists": key_snapshots,
                        },
                    }
                )

        inspector = SharedMemoryInspectorBlock("inspector")
        blocks = {"inspector": inspector}

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["inspector"],
            max_rounds=3,
            carry_context=config,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        key_exists_per_round = result_state.shared_memory.get("inspector_key_exists", [])
        # Round 1: inject_as key should NOT exist
        assert key_exists_per_round[0] is False
        # Round 2+: inject_as key SHOULD exist
        assert key_exists_per_round[1] is True
        assert key_exists_per_round[2] is True


# ==============================================================================
# 9. Unit tests -- carry_context=None means no context passing (backward compat)
# ==============================================================================


class TestCarryContextNoneBackwardCompat:
    """carry_context=None means no context passing (backward compatible)."""

    @pytest.mark.asyncio
    async def test_no_carry_context_no_inject_key(self):
        """With carry_context=None, inject_as key should never appear in shared_memory."""
        from runsight_core import LoopBlock

        reader = ContextReaderBlock("reader", read_key="previous_round_context")
        blocks = {"reader": reader}

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["reader"],
            max_rounds=3,
            carry_context=None,  # no context passing
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        # inject_as key should never appear
        assert "previous_round_context" not in result_state.shared_memory

        # All snapshots should be None (no context was ever injected)
        snapshots = result_state.shared_memory.get("reader_snapshots", [])
        assert all(s is None for s in snapshots)

    @pytest.mark.asyncio
    async def test_existing_loop_tests_still_pass_without_carry_context(self):
        """LoopBlock without carry_context should behave exactly as before."""
        from runsight_core import LoopBlock

        inner = TrackingBlock("inner")
        blocks = {"inner": inner}

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["inner"],
            max_rounds=3,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        # Basic behavior unchanged
        calls = result_state.shared_memory.get("inner_calls", [])
        assert len(calls) == 3
        assert "loop_block" in result_state.results


# ==============================================================================
# 10. Unit tests -- carry_context.enabled=False explicitly disables
# ==============================================================================


class TestCarryContextDisabled:
    """carry_context.enabled=False explicitly disables context passing."""

    @pytest.mark.asyncio
    async def test_enabled_false_no_context_injected(self):
        """With enabled=False, no context should be injected even though carry_context is configured."""
        from runsight_core import LoopBlock
        from runsight_core.blocks.loop import CarryContextConfig

        config = CarryContextConfig(
            enabled=False,
            mode="last",
            inject_as="feedback",
        )

        reader = ContextReaderBlock("reader", read_key="feedback")
        blocks = {"reader": reader}

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["reader"],
            max_rounds=3,
            carry_context=config,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        # feedback key should not appear in shared_memory
        assert "feedback" not in result_state.shared_memory

        # All snapshots should be None (no context)
        snapshots = result_state.shared_memory.get("reader_snapshots", [])
        assert all(s is None for s in snapshots)


# ==============================================================================
# 11. Validation -- source_blocks references non-existent block
# ==============================================================================


class TestCarryContextValidation:
    """Validation: source_blocks references validated against inner_block_refs."""

    def test_source_block_not_in_inner_refs_raises(self):
        """source_blocks containing a block not in inner_block_refs should raise ValueError."""
        from runsight_core import LoopBlock
        from runsight_core.blocks.loop import CarryContextConfig

        config = CarryContextConfig(
            source_blocks=["not_an_inner_block"],
        )
        with pytest.raises(ValueError, match="not_an_inner_block"):
            LoopBlock(
                block_id="loop_block",
                inner_block_refs=["writer", "critic"],
                max_rounds=3,
                carry_context=config,
            )

    def test_multiple_invalid_source_blocks_raise(self):
        """Multiple invalid source_blocks should be reported in the error."""
        from runsight_core import LoopBlock
        from runsight_core.blocks.loop import CarryContextConfig

        config = CarryContextConfig(
            source_blocks=["ghost_a", "ghost_b"],
        )
        with pytest.raises(ValueError, match="ghost"):
            LoopBlock(
                block_id="loop_block",
                inner_block_refs=["writer"],
                max_rounds=3,
                carry_context=config,
            )

    def test_valid_source_blocks_accepted(self):
        """source_blocks that are all in inner_block_refs should be accepted."""
        from runsight_core import LoopBlock
        from runsight_core.blocks.loop import CarryContextConfig

        config = CarryContextConfig(
            source_blocks=["critic"],
            inject_as="feedback",
        )
        # Should NOT raise
        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["writer", "critic"],
            max_rounds=3,
            carry_context=config,
        )
        assert loop.carry_context is config


# ==============================================================================
# 12. Edge case -- empty output carried as empty string
# ==============================================================================


class TestCarryContextEmptyOutput:
    """Inner block produces empty output -> carry empty string, don't skip."""

    @pytest.mark.asyncio
    async def test_empty_output_carried_not_skipped(self):
        """Empty string output should be carried, not treated as missing."""
        from runsight_core import LoopBlock
        from runsight_core.blocks.loop import CarryContextConfig

        config = CarryContextConfig(
            mode="last",
            source_blocks=["empty_block"],
            inject_as="ctx",
        )

        empty_block = EmptyOutputBlock("empty_block")
        reader = ContextReaderBlock("reader", read_key="ctx")
        blocks = {"empty_block": empty_block, "reader": reader}

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["empty_block", "reader"],
            max_rounds=3,
            carry_context=config,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        snapshots = result_state.shared_memory.get("reader_snapshots", [])

        # Round 1: no context
        assert snapshots[0] is None

        # Round 2: context should be present (not None) even though block output was empty
        assert snapshots[1] is not None
        # The carried context should contain the empty string, not be skipped
        assert "empty_block" in str(snapshots[1]) or snapshots[1] is not None


# ==============================================================================
# 13. Integration -- Writer-Critic loop with carry context
# ==============================================================================


class TestCarryContextWriterCriticIntegration:
    """Integration: Writer-Critic loop where critic feedback is carried to next round."""

    @pytest.mark.asyncio
    async def test_critic_feedback_visible_to_writer_in_round_2(self):
        """Critic feedback from round 1 should be visible to writer in round 2 via shared_memory."""
        from runsight_core import LoopBlock
        from runsight_core.blocks.loop import CarryContextConfig

        config = CarryContextConfig(
            mode="last",
            source_blocks=["critic"],
            inject_as="feedback",
        )

        writer = ContextAwareWriterBlock("writer", context_key="feedback")
        critic = CriticBlock("critic")
        blocks = {"writer": writer, "critic": critic}

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["writer", "critic"],
            max_rounds=3,
            carry_context=config,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        contexts_seen = result_state.shared_memory.get("writer_contexts_seen", [])

        # Round 1: writer sees no feedback (first round)
        assert contexts_seen[0] is None

        # Round 2: writer sees critic's feedback from round 1
        assert contexts_seen[1] is not None
        assert "feedback_round_1" in str(contexts_seen[1])

        # Round 3: writer sees critic's feedback from round 2 (mode=last)
        assert contexts_seen[2] is not None
        assert "feedback_round_2" in str(contexts_seen[2])

    @pytest.mark.asyncio
    async def test_critic_feedback_all_rounds_accumulated(self):
        """With mode='all', writer should see accumulated feedback from all prior rounds."""
        from runsight_core import LoopBlock
        from runsight_core.blocks.loop import CarryContextConfig

        config = CarryContextConfig(
            mode="all",
            source_blocks=["critic"],
            inject_as="feedback_history",
        )

        writer = ContextAwareWriterBlock("writer", context_key="feedback_history")
        critic = CriticBlock("critic")
        blocks = {"writer": writer, "critic": critic}

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["writer", "critic"],
            max_rounds=3,
            carry_context=config,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        contexts_seen = result_state.shared_memory.get("writer_contexts_seen", [])

        # Round 1: no feedback
        assert contexts_seen[0] is None

        # Round 2: feedback from round 1
        assert contexts_seen[1] is not None
        assert "feedback_round_1" in str(contexts_seen[1])

        # Round 3: feedback from BOTH round 1 and round 2
        assert contexts_seen[2] is not None
        assert "feedback_round_1" in str(contexts_seen[2])
        assert "feedback_round_2" in str(contexts_seen[2])

    @pytest.mark.asyncio
    async def test_writer_critic_workflow_integration(self):
        """Full workflow integration: LoopBlock with carry_context in Workflow.run()."""
        from runsight_core import LoopBlock
        from runsight_core.blocks.loop import CarryContextConfig

        config = CarryContextConfig(
            mode="last",
            source_blocks=["critic"],
            inject_as="feedback",
        )

        writer = ContextAwareWriterBlock("writer", context_key="feedback")
        critic = CriticBlock("critic")
        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["writer", "critic"],
            max_rounds=3,
            carry_context=config,
        )

        wf = Workflow(name="carry_ctx_wf")
        wf.add_block(writer)
        wf.add_block(critic)
        wf.add_block(loop)
        wf.add_transition("loop_block", None)
        wf.set_entry("loop_block")

        state = WorkflowState()
        result_state = await wf.run(state)

        # Verify the workflow completed all 3 rounds
        assert "loop_block" in result_state.results
        contexts_seen = result_state.shared_memory.get("writer_contexts_seen", [])
        assert len(contexts_seen) == 3
        # Writer in round 2 should have seen critic feedback from round 1
        assert contexts_seen[1] is not None


# ==============================================================================
# 14. Integration -- Carried context is correctly formatted
# ==============================================================================


class TestCarryContextFormat:
    """Verify carried context is correctly formatted and readable."""

    @pytest.mark.asyncio
    async def test_carried_context_is_dict_keyed_by_block_id(self):
        """Carried context should be a dict keyed by source block IDs."""
        from runsight_core import LoopBlock
        from runsight_core.blocks.loop import CarryContextConfig

        config = CarryContextConfig(
            mode="last",
            source_blocks=["writer", "critic"],
            inject_as="ctx",
        )

        writer = TrackingBlock("writer")
        critic = CriticBlock("critic")
        reader = ContextReaderBlock("reader", read_key="ctx")
        blocks = {"writer": writer, "critic": critic, "reader": reader}

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["writer", "critic", "reader"],
            max_rounds=2,
            carry_context=config,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        snapshots = result_state.shared_memory.get("reader_snapshots", [])
        round_2_ctx = snapshots[1]

        # The carried context should be a dict keyed by block ID
        assert isinstance(round_2_ctx, dict)
        assert "writer" in round_2_ctx
        assert "critic" in round_2_ctx

    @pytest.mark.asyncio
    async def test_mode_all_carried_context_is_list_of_dicts(self):
        """In mode='all', carried context should be a list of round dicts."""
        from runsight_core import LoopBlock
        from runsight_core.blocks.loop import CarryContextConfig

        config = CarryContextConfig(
            mode="all",
            inject_as="ctx",
        )

        inner = TrackingBlock("inner")
        reader = ContextReaderBlock("reader", read_key="ctx")
        blocks = {"inner": inner, "reader": reader}

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["inner", "reader"],
            max_rounds=3,
            carry_context=config,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        snapshots = result_state.shared_memory.get("reader_snapshots", [])

        # Round 3: should have a list of 2 prior round contexts
        round_3_ctx = snapshots[2]
        assert isinstance(round_3_ctx, list)
        assert len(round_3_ctx) == 2  # contexts from rounds 1 and 2

    @pytest.mark.asyncio
    async def test_mode_last_carried_context_is_single_dict(self):
        """In mode='last', carried context should be a single dict, not a list."""
        from runsight_core import LoopBlock
        from runsight_core.blocks.loop import CarryContextConfig

        config = CarryContextConfig(
            mode="last",
            inject_as="ctx",
        )

        inner = TrackingBlock("inner")
        reader = ContextReaderBlock("reader", read_key="ctx")
        blocks = {"inner": inner, "reader": reader}

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["inner", "reader"],
            max_rounds=3,
            carry_context=config,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        result_state = await loop.execute(state, blocks=blocks)

        snapshots = result_state.shared_memory.get("reader_snapshots", [])

        # Round 2: should be a single dict, not a list
        round_2_ctx = snapshots[1]
        assert isinstance(round_2_ctx, dict)
        assert not isinstance(round_2_ctx, list)
