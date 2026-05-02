"""LoopBlock schema, parsing, execution, and workflow integration behavior."""

from __future__ import annotations

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


class TestLoopBlockDefSchema:
    """LoopBlockDef Pydantic model validates correctly via discriminated union."""

    def test_loop_type_discriminator_resolves(self):
        """type='loop' should resolve to LoopBlockDef in the BlockDef union."""
        from runsight_core.blocks.loop import LoopBlockDef

        block = _validate_block(
            {"type": "loop", "inner_block_refs": ["draft_block", "review_block"]}
        )
        assert isinstance(block, LoopBlockDef)

    def test_loop_default_max_rounds(self):
        """LoopBlockDef default max_rounds should be 5."""
        from runsight_core.blocks.loop import LoopBlockDef

        block = _validate_block({"type": "loop", "inner_block_refs": ["draft_block"]})
        assert isinstance(block, LoopBlockDef)
        assert block.max_rounds == 5

    def test_loop_custom_max_rounds(self):
        """LoopBlockDef should accept a custom max_rounds value."""
        from runsight_core.blocks.loop import LoopBlockDef

        block = _validate_block(
            {"type": "loop", "inner_block_refs": ["draft_block"], "max_rounds": 10}
        )
        assert isinstance(block, LoopBlockDef)
        assert block.max_rounds == 10

    def test_loop_inner_block_refs_stored(self):
        """inner_block_refs should be stored as list[str]."""

        block = _validate_block(
            {"type": "loop", "inner_block_refs": ["draft_block", "review_block", "publish_block"]}
        )
        assert block.inner_block_refs == ["draft_block", "review_block", "publish_block"]

    def test_loop_max_rounds_minimum_1(self):
        """max_rounds must be >= 1."""
        with pytest.raises(ValidationError, match="max_rounds"):
            _validate_block({"type": "loop", "inner_block_refs": ["draft_block"], "max_rounds": 0})

    def test_loop_max_rounds_maximum_50(self):
        """max_rounds must be <= 50."""
        with pytest.raises(ValidationError, match="max_rounds"):
            _validate_block({"type": "loop", "inner_block_refs": ["draft_block"], "max_rounds": 51})

    def test_loop_empty_inner_block_refs_rejected(self):
        """Empty inner_block_refs should raise a validation error."""
        with pytest.raises(ValidationError):
            _validate_block({"type": "loop", "inner_block_refs": []})

    def test_loop_missing_inner_block_refs_rejected(self):
        """Missing inner_block_refs should raise a validation error."""
        with pytest.raises(ValidationError, match="inner_block_refs"):
            _validate_block({"type": "loop"})

    def test_retry_type_no_longer_in_union(self):
        """type='retry' should NOT be in the BlockDef discriminated union anymore."""
        with pytest.raises(ValidationError):
            _validate_block({"type": "retry", "inner_block_ref": "some_block", "max_retries": 3})

    def test_loop_supports_retry_config(self):
        """LoopBlockDef should support the inherited retry_config field."""
        from runsight_core.blocks.loop import LoopBlockDef

        block = _validate_block(
            {
                "type": "loop",
                "inner_block_refs": ["draft_block"],
                "retry_config": {"max_attempts": 2, "backoff": "fixed"},
            }
        )
        assert isinstance(block, LoopBlockDef)
        assert block.retry_config is not None
        assert block.retry_config.max_attempts == 2


# ===========================================================================
# 2. LoopBlock unit tests — execution behavior
# ===========================================================================


class TestLoopBlockExports:
    """LoopBlock should be exported from runsight_core package."""

    def test_loop_block_importable_from_implementations(self):
        """LoopBlock should be importable from runsight_core.blocks.implementations."""
        from runsight_core import LoopBlock

        assert LoopBlock is not None

    def test_loop_block_importable_from_package(self):
        """LoopBlock should be in runsight_core.__all__ and importable from the package."""
        import runsight_core

        assert hasattr(runsight_core, "LoopBlock")

    def test_retry_block_removed_from_exports(self):
        """RetryBlock should no longer be exported from runsight_core."""
        import runsight_core

        assert "RetryBlock" not in runsight_core.__all__

    def test_loop_block_def_importable_from_schema(self):
        """LoopBlockDef should be importable from runsight_core.yaml.schema."""
        from runsight_core.blocks.loop import LoopBlockDef

        assert LoopBlockDef is not None

    def test_retry_block_def_removed_from_schema(self):
        """RetryBlockDef should no longer exist in runsight_core.yaml.schema."""
        import runsight_core.yaml.schema as schema

        assert not hasattr(schema, "RetryBlockDef")
