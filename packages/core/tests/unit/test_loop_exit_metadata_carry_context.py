"""LoopBlock exit-handle control tests.

The suite covers retry and break routing inside loops, mid-round skipping,
source-level exception-handling governance, break-condition compatibility,
metadata, schema fields, parser wiring, and carry_context propagation.
"""

import pytest
from conftest import block_output_from_state, execute_loop_for_test
from pydantic import TypeAdapter
from runsight_core.blocks.base import BaseBlock
from runsight_core.blocks.loop import CarryContextConfig, LoopBlock
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.yaml.schema import BlockDef

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class TrackingBlock(BaseBlock):
    """Block that records each call in shared_memory under its block_id."""

    def __init__(self, block_id: str):
        super().__init__(block_id)
        self.context_access = "declared"
        self.calls: list[int] = []

    async def execute(self, ctx):
        state = ctx.state_snapshot
        self.calls.append(len(self.calls) + 1)
        next_state = state.model_copy(
            update={
                "results": {
                    **state.results,
                    self.block_id: BlockResult(output=f"call_{len(self.calls)}"),
                },
                "shared_memory": {
                    **state.shared_memory,
                    f"{self.block_id}_calls": list(self.calls),
                },
            }
        )
        return block_output_from_state(self.block_id, state, next_state)


class ExitHandleBlock(BaseBlock):
    """Block that returns a BlockResult with a configurable exit_handle.

    Returns exit_handle=None for the first (threshold - 1) calls,
    then returns the configured exit_handle from call number `threshold` onward.
    """

    def __init__(self, block_id: str, exit_handle: str, threshold: int = 1):
        super().__init__(block_id)
        self.context_access = "declared"
        self._exit_handle = exit_handle
        self._threshold = threshold
        self.calls: list[int] = []

    async def execute(self, ctx):
        state = ctx.state_snapshot
        self.calls.append(len(self.calls) + 1)
        call_num = len(self.calls)

        if call_num >= self._threshold:
            handle = self._exit_handle
        else:
            handle = None

        next_state = state.model_copy(
            update={
                "results": {
                    **state.results,
                    self.block_id: BlockResult(
                        output=f"call_{call_num}_handle_{handle}",
                        exit_handle=handle,
                    ),
                },
                "shared_memory": {
                    **state.shared_memory,
                    f"{self.block_id}_calls": list(self.calls),
                },
            }
        )
        return block_output_from_state(self.block_id, state, next_state)


block_adapter = TypeAdapter(BlockDef)


def _validate_block(data: dict):
    """Validate a dict as a BlockDef via the discriminated union."""
    return block_adapter.validate_python(data)


# ==============================================================================
# retry_on_exit starts the next loop round
# ==============================================================================


class TestLoopMetadataWithExitHandle:
    """Loop metadata in shared_memory must correctly reflect exit_handle behavior."""

    @pytest.mark.asyncio
    async def test_metadata_on_break_on_exit(self):
        """When break_on_exit fires, metadata should show broke_early=True and correct rounds."""
        writer = TrackingBlock("writer")
        gate = ExitHandleBlock("gate", exit_handle="pass", threshold=2)
        blocks = {"writer": writer, "gate": gate}

        loop = LoopBlock(
            block_id="review_loop",
            inner_block_refs=["writer", "gate"],
            max_rounds=5,
            break_on_exit="pass",
        )
        blocks["review_loop"] = loop

        state = WorkflowState()
        result_state = await execute_loop_for_test(loop, state, blocks=blocks)

        meta = result_state.shared_memory.get("__loop__review_loop")
        assert meta is not None, "Loop metadata not found in shared_memory"
        assert meta["broke_early"] is True
        assert meta["rounds_completed"] == 2

    @pytest.mark.asyncio
    async def test_metadata_on_retry_exhaustion(self):
        """When retry_on_exit fires every round and max_rounds exhausted,
        metadata should show broke_early=False."""
        writer = TrackingBlock("writer")
        gate = ExitHandleBlock("gate", exit_handle="fail", threshold=1)
        blocks = {"writer": writer, "gate": gate}

        loop = LoopBlock(
            block_id="review_loop",
            inner_block_refs=["writer", "gate"],
            max_rounds=3,
            retry_on_exit="fail",
        )
        blocks["review_loop"] = loop

        state = WorkflowState()
        result_state = await execute_loop_for_test(loop, state, blocks=blocks)

        meta = result_state.shared_memory.get("__loop__review_loop")
        assert meta is not None, "Loop metadata not found in shared_memory"
        assert meta["broke_early"] is False
        assert meta["rounds_completed"] == 3

    @pytest.mark.asyncio
    async def test_metadata_break_reason_on_exit_handle(self):
        """When break_on_exit fires, break_reason should indicate exit_handle-based break."""
        writer = TrackingBlock("writer")
        gate = ExitHandleBlock("gate", exit_handle="pass", threshold=1)
        blocks = {"writer": writer, "gate": gate}

        loop = LoopBlock(
            block_id="review_loop",
            inner_block_refs=["writer", "gate"],
            max_rounds=5,
            break_on_exit="pass",
        )
        blocks["review_loop"] = loop

        state = WorkflowState()
        result_state = await execute_loop_for_test(loop, state, blocks=blocks)

        meta = result_state.shared_memory.get("__loop__review_loop")
        assert meta is not None
        assert meta["broke_early"] is True
        # break_reason should indicate exit_handle (not "condition met")
        assert (
            "exit" in meta.get("break_reason", "").lower()
            or "handle" in meta.get("break_reason", "").lower()
        ), f"Expected break_reason to reference exit_handle, got: {meta.get('break_reason')}"


class ContextPayloadBlock(BaseBlock):
    """Block that emits structured output for carry_context propagation tests."""

    def __init__(self, block_id: str, *, trace_path: str):
        super().__init__(block_id)
        self.context_access = "declared"
        self._trace_path = trace_path
        self.calls: list[int] = []

    async def execute(self, ctx):
        state = ctx.state_snapshot
        self.calls.append(len(self.calls) + 1)
        call_num = len(self.calls)
        next_state = state.model_copy(
            update={
                "results": {
                    **state.results,
                    self.block_id: BlockResult(
                        output=f'{{"trace_path":"{self._trace_path}","round":{call_num}}}'
                    ),
                },
                "shared_memory": {
                    **state.shared_memory,
                    f"{self.block_id}_calls": list(self.calls),
                },
            }
        )
        return block_output_from_state(self.block_id, state, next_state)


class TestCarryContextWithExitHandle:
    """carry_context must still propagate on break/retry exit-handle paths."""

    @pytest.mark.asyncio
    async def test_retry_on_exit_still_updates_carry_context_and_task_context(self):
        source = ContextPayloadBlock(
            "source",
            trace_path="fixture_outputs/provider-trace-primary.md",
        )
        gate = ExitHandleBlock("gate", exit_handle="fail", threshold=1)
        blocks = {"source": source, "gate": gate}

        loop = LoopBlock(
            block_id="review_loop",
            inner_block_refs=["source", "gate"],
            max_rounds=2,
            retry_on_exit="fail",
            carry_context=CarryContextConfig(
                mode="all",
                source_blocks=["source"],
                inject_as="ctx",
            ),
        )
        blocks["review_loop"] = loop

        state = WorkflowState()
        result_state = await execute_loop_for_test(loop, state, blocks=blocks)

        carried = result_state.shared_memory.get("ctx")
        assert isinstance(carried, list)
        assert len(carried) == 2
        assert "provider-trace-primary.md" in str(carried)

    @pytest.mark.asyncio
    async def test_break_on_exit_still_updates_carry_context_and_task_context(self):
        source = ContextPayloadBlock(
            "source",
            trace_path="fixture_outputs/provider-trace-secondary.md",
        )
        gate = ExitHandleBlock("gate", exit_handle="pass", threshold=1)
        blocks = {"source": source, "gate": gate}

        loop = LoopBlock(
            block_id="review_loop",
            inner_block_refs=["source", "gate"],
            max_rounds=3,
            break_on_exit="pass",
            carry_context=CarryContextConfig(
                mode="last",
                source_blocks=["source"],
                inject_as="ctx",
            ),
        )
        blocks["review_loop"] = loop

        state = WorkflowState()
        result_state = await execute_loop_for_test(loop, state, blocks=blocks)

        carried = result_state.shared_memory.get("ctx")
        assert isinstance(carried, dict)
        assert "provider-trace-secondary.md" in str(carried)


# ==============================================================================
# break_on_exit and retry_on_exit are LoopBlockDef fields
# ==============================================================================
