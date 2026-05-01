"""Shared LoopBlock carry-context test fakes and state helpers."""

from __future__ import annotations

from typing import Any

from runsight_core.block_io import BlockContext, BlockOutput, apply_block_output
from runsight_core.blocks.base import BaseBlock
from runsight_core.state import WorkflowState


def seeded_state(*shared_memory_keys: str) -> WorkflowState:
    """Build a WorkflowState with declared shared-memory keys seeded to None."""
    return WorkflowState(shared_memory={key: None for key in shared_memory_keys})


async def run_loop(
    loop: BaseBlock, state: WorkflowState, blocks: dict[str, BaseBlock]
) -> WorkflowState:
    """Run a LoopBlock-style block and apply its output to the provided state."""
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


class TrackingBlock(BaseBlock):
    """Block that records each call and writes a round-specific output."""

    def __init__(self, block_id: str):
        super().__init__(block_id)
        self.context_access = "declared"
        self._calls: list[int] = []

    async def execute(self, ctx: BlockContext) -> BlockOutput:
        self._calls.append(len(self._calls) + 1)
        output = f"{self.block_id}_output_round_{len(self._calls)}"
        return BlockOutput(
            output=output,
            shared_memory_updates={f"{self.block_id}_calls": list(self._calls)},
        )


class ContextAwareWriterBlock(BaseBlock):
    """Writer block that records the carried context it sees each round."""

    def __init__(self, block_id: str, context_key: str = "previous_round_context"):
        super().__init__(block_id)
        self.context_access = "declared"
        self.context_key = context_key
        self.declared_inputs = {context_key: f"shared_memory.{context_key}"}
        self._calls: list[int] = []
        self._contexts_seen: list[Any] = []

    async def execute(self, ctx: BlockContext) -> BlockOutput:
        self._calls.append(len(self._calls) + 1)
        round_num = len(self._calls)
        carried = ctx.state_snapshot.shared_memory.get(self.context_key)
        self._contexts_seen.append(carried)

        return BlockOutput(
            output=f"draft_round_{round_num}",
            shared_memory_updates={
                f"{self.block_id}_calls": list(self._calls),
                f"{self.block_id}_contexts_seen": list(self._contexts_seen),
            },
        )


class CriticBlock(BaseBlock):
    """Critic block that produces round-specific feedback."""

    def __init__(self, block_id: str):
        super().__init__(block_id)
        self.context_access = "declared"
        self._calls: list[int] = []

    async def execute(self, ctx: BlockContext) -> BlockOutput:
        self._calls.append(len(self._calls) + 1)
        round_num = len(self._calls)
        return BlockOutput(
            output=f"feedback_round_{round_num}",
            shared_memory_updates={f"{self.block_id}_calls": list(self._calls)},
        )


class EmptyOutputBlock(BaseBlock):
    """Block that produces an empty string output."""

    def __init__(self, block_id: str):
        super().__init__(block_id)
        self.context_access = "declared"
        self._calls: list[int] = []

    async def execute(self, ctx: BlockContext) -> BlockOutput:
        self._calls.append(len(self._calls) + 1)
        return BlockOutput(
            output="",
            shared_memory_updates={f"{self.block_id}_calls": list(self._calls)},
        )


class ContextReaderBlock(BaseBlock):
    """Block that records the value of one shared-memory key each round."""

    def __init__(self, block_id: str, read_key: str = "previous_round_context"):
        super().__init__(block_id)
        self.context_access = "declared"
        self.read_key = read_key
        self.declared_inputs = {read_key: f"shared_memory.{read_key}"}
        self._calls: list[int] = []
        self._snapshots: list[Any] = []

    async def execute(self, ctx: BlockContext) -> BlockOutput:
        self._calls.append(len(self._calls) + 1)
        round_num = len(self._calls)
        context_value = ctx.state_snapshot.shared_memory.get(self.read_key)
        self._snapshots.append(context_value)

        return BlockOutput(
            output=f"{self.block_id}_output_round_{round_num}",
            shared_memory_updates={
                f"{self.block_id}_calls": list(self._calls),
                f"{self.block_id}_snapshots": list(self._snapshots),
            },
        )


class SharedMemoryInspectorBlock(BaseBlock):
    """Block that captures a declared shared-memory key before each round."""

    def __init__(self, block_id: str, read_key: str):
        super().__init__(block_id)
        self.context_access = "declared"
        self.read_key = read_key
        self.declared_inputs = {read_key: f"shared_memory.{read_key}"}
        self._calls: list[int] = []
        self._ctx_values: list[Any] = []

    async def execute(self, ctx: BlockContext) -> BlockOutput:
        self._calls.append(len(self._calls) + 1)
        round_num = len(self._calls)
        self._ctx_values.append(ctx.state_snapshot.shared_memory.get(self.read_key))

        return BlockOutput(
            output=f"round_{round_num}",
            shared_memory_updates={
                f"{self.block_id}_calls": list(self._calls),
                f"{self.block_id}_key_exists": list(self._ctx_values),
            },
        )


class NullSoulOutputBlock(BaseBlock):
    """Block that exposes soul=None and still participates in carry_context."""

    def __init__(self, block_id: str):
        super().__init__(block_id)
        self.context_access = "declared"
        self.soul = None
        self._calls: list[int] = []

    async def execute(self, ctx: BlockContext) -> BlockOutput:
        self._calls.append(len(self._calls) + 1)
        return BlockOutput(
            output=f"{self.block_id}_output",
            shared_memory_updates={f"{self.block_id}_calls": list(self._calls)},
        )
