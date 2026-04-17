"""
Failing tests for RUN-184: Wire ArtifactStore into WorkflowState + injection points.

Tests cover:
1. WorkflowState.artifact_store field (Optional, default None, excluded from serialization)
2. WorkflowBlock child state propagation (same artifact_store reference)
3. LoopBlock round sharing (same artifact_store across rounds via shallow copy)
4. DispatchBlock parallel sharing (same artifact_store across parallel tasks)
5. Programmatic usage (explicit construction, default None)
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from runsight_core.blocks.base import BaseBlock
from runsight_core.state import WorkflowState

# ── Test helpers ───────────────────────────────────────────────────────────


class ArtifactCapturingBlock(BaseBlock):
    """Block that captures state.artifact_store into shared_memory for assertion."""

    _captures: dict[str, int | None] = {}

    def __init__(self, block_id: str):
        super().__init__(block_id)
        self.context_access = "declared"

    async def execute(self, ctx):
        from runsight_core.block_io import BlockOutput

        state = ctx.state_snapshot
        self._captures[self.block_id] = id(state.artifact_store) if state.artifact_store else None
        return BlockOutput(
            output="done",
            shared_memory_updates={"artifact_store_captures": dict(self._captures)},
        )


class RoundTrackingBlock(BaseBlock):
    """Block that records artifact_store id per call, useful for LoopBlock tests."""

    def __init__(self, block_id: str):
        super().__init__(block_id)
        self.context_access = "declared"
        self.store_ids: list[int | None] = []

    async def execute(self, ctx):
        from runsight_core.block_io import BlockOutput

        state = ctx.state_snapshot
        self.store_ids.append(id(state.artifact_store) if state.artifact_store else None)
        return BlockOutput(
            output=f"call_{len(self.store_ids)}",
            shared_memory_updates={f"{self.block_id}_store_ids": list(self.store_ids)},
        )


# ==============================================================================
# 1. WorkflowState.artifact_store field
# ==============================================================================


class TestWorkflowStateArtifactStoreField:
    """Tests for the artifact_store field on WorkflowState."""

    def test_artifact_store_field_exists(self):
        """WorkflowState should have an 'artifact_store' in model_fields."""
        assert "artifact_store" in WorkflowState.model_fields

    def test_artifact_store_default_is_none(self):
        """WorkflowState() should default artifact_store to None."""
        state = WorkflowState()
        assert state.artifact_store is None

    def test_artifact_store_accepts_in_memory_store(self):
        """WorkflowState should accept an InMemoryArtifactStore instance."""
        from runsight_core.artifacts import InMemoryArtifactStore

        store = InMemoryArtifactStore(run_id="test-run")
        state = WorkflowState(artifact_store=store)
        assert state.artifact_store is store

    def test_artifact_store_accessible_on_instance(self):
        """state.artifact_store should be directly accessible."""
        from runsight_core.artifacts import InMemoryArtifactStore

        store = InMemoryArtifactStore(run_id="test-run")
        state = WorkflowState(artifact_store=store)
        assert state.artifact_store.run_id == "test-run"

    def test_model_dump_excludes_artifact_store(self):
        """state.model_dump() should NOT include artifact_store."""
        from runsight_core.artifacts import InMemoryArtifactStore

        store = InMemoryArtifactStore(run_id="test-run")
        state = WorkflowState(artifact_store=store)
        dumped = state.model_dump()
        assert "artifact_store" not in dumped

    def test_model_dump_json_succeeds(self):
        """state.model_dump_json() should succeed without errors."""
        from runsight_core.artifacts import InMemoryArtifactStore

        store = InMemoryArtifactStore(run_id="test-run")
        state = WorkflowState(artifact_store=store)
        json_str = state.model_dump_json()
        assert isinstance(json_str, str)
        assert "artifact_store" not in json_str

    def test_model_dump_json_succeeds_with_none(self):
        """state.model_dump_json() should succeed when artifact_store is None."""
        state = WorkflowState()
        json_str = state.model_dump_json()
        assert isinstance(json_str, str)

    def test_model_copy_preserves_artifact_store_reference(self):
        """state.model_copy() should shallow-copy artifact_store (same object reference)."""
        from runsight_core.artifacts import InMemoryArtifactStore

        store = InMemoryArtifactStore(run_id="test-run")
        state = WorkflowState(artifact_store=store)
        copied = state.model_copy(update={"total_tokens": 42})
        assert copied.artifact_store is store

    def test_model_copy_update_other_fields_keeps_store(self):
        """Updating unrelated fields via model_copy preserves artifact_store."""
        from runsight_core.artifacts import InMemoryArtifactStore

        store = InMemoryArtifactStore(run_id="test-run")
        state = WorkflowState(artifact_store=store, total_cost_usd=1.0)
        copied = state.model_copy(update={"results": {"block1": "output"}, "total_cost_usd": 2.0})
        assert copied.artifact_store is store
        assert copied.total_cost_usd == 2.0

    def test_model_dump_roundtrip_loses_artifact_store(self):
        """model_dump() -> WorkflowState(**dump) should work but artifact_store is lost."""
        from runsight_core.artifacts import InMemoryArtifactStore

        store = InMemoryArtifactStore(run_id="test-run")
        state = WorkflowState(artifact_store=store)
        dumped = state.model_dump()
        restored = WorkflowState(**dumped)
        assert restored.artifact_store is None

    def test_artifact_store_none_does_not_error(self):
        """Creating WorkflowState with artifact_store=None explicitly works."""
        state = WorkflowState(artifact_store=None)
        assert state.artifact_store is None


# ==============================================================================
# 2. WorkflowBlock propagation — child state gets parent's artifact_store
# ==============================================================================


class TestWorkflowBlockArtifactStorePropagation:
    """WorkflowBlock._map_inputs should propagate artifact_store to child state."""

    def test_child_state_has_parent_artifact_store(self):
        """Child state created by _map_inputs should carry parent's artifact_store."""
        from runsight_core import WorkflowBlock
        from runsight_core.artifacts import InMemoryArtifactStore
        from runsight_core.workflow import Workflow

        store = InMemoryArtifactStore(run_id="parent-run")
        parent_state = WorkflowState(
            artifact_store=store,
            shared_memory={"topic": "AI"},
        )

        child_wf = Workflow(name="child_wf")
        block = WorkflowBlock(
            block_id="sub",
            child_workflow=child_wf,
            inputs={"shared_memory.topic": "shared_memory.topic"},
            outputs={},
        )

        child_state = block._map_inputs(parent_state, block.inputs)
        assert child_state.artifact_store is store

    @pytest.mark.asyncio
    async def test_child_workflow_receives_artifact_store_during_execution(self):
        """Full WorkflowBlock.execute() propagates artifact_store to child workflow."""
        from runsight_core import WorkflowBlock
        from runsight_core.artifacts import InMemoryArtifactStore

        store = InMemoryArtifactStore(run_id="parent-run")
        parent_state = WorkflowState(
            artifact_store=store,
            shared_memory={"topic": "AI"},
        )

        # Mock child workflow that captures the state it receives
        mock_child_wf = AsyncMock()
        mock_child_wf.name = "child_wf"
        child_final = WorkflowState(total_cost_usd=0.0, total_tokens=0)
        mock_child_wf.run = AsyncMock(return_value=child_final)

        block = WorkflowBlock(
            block_id="sub",
            child_workflow=mock_child_wf,
            inputs={"shared_memory.topic": "shared_memory.topic"},
            outputs={},
        )

        from runsight_core.block_io import build_block_context

        ctx = build_block_context(block, parent_state)
        await block.execute(ctx)

        # Verify the child state passed to child_wf.run had the artifact_store
        call_args = mock_child_wf.run.call_args
        child_state_arg = call_args[0][0]
        assert child_state_arg.artifact_store is store

    @pytest.mark.asyncio
    async def test_returned_parent_state_keeps_artifact_store(self):
        """After WorkflowBlock.execute(), the returned parent state still has artifact_store."""
        from runsight_core import WorkflowBlock
        from runsight_core.artifacts import InMemoryArtifactStore

        store = InMemoryArtifactStore(run_id="parent-run")
        parent_state = WorkflowState(
            artifact_store=store,
            shared_memory={"topic": "AI"},
        )

        mock_child_wf = AsyncMock()
        mock_child_wf.name = "child_wf"
        child_final = WorkflowState(total_cost_usd=0.0, total_tokens=0)
        mock_child_wf.run = AsyncMock(return_value=child_final)

        block = WorkflowBlock(
            block_id="sub",
            child_workflow=mock_child_wf,
            inputs={},
            outputs={},
        )

        from runsight_core.block_io import BlockOutput, apply_block_output, build_block_context

        ctx = build_block_context(block, parent_state)
        raw = await block.execute(ctx)
        if isinstance(raw, WorkflowState):
            result_state = raw
        elif isinstance(raw, BlockOutput):
            result_state = apply_block_output(parent_state, block.block_id, raw)
        else:
            result_state = parent_state
        assert result_state.artifact_store is store


# ==============================================================================
# 3. LoopBlock — same artifact_store across all rounds (shallow copy)
# ==============================================================================


class TestLoopBlockArtifactStoreSharing:
    """LoopBlock rounds should share the same artifact_store reference."""

    @pytest.mark.asyncio
    async def test_loop_block_rounds_share_same_store(self):
        """All rounds of a LoopBlock should see the same artifact_store object."""
        from runsight_core import LoopBlock
        from runsight_core.artifacts import InMemoryArtifactStore

        store = InMemoryArtifactStore(run_id="loop-run")
        tracker = RoundTrackingBlock("tracker")

        loop = LoopBlock(
            block_id="my_loop",
            inner_block_refs=["tracker"],
            max_rounds=3,
        )

        from runsight_core.block_io import BlockContext, BlockOutput, apply_block_output

        state = WorkflowState(artifact_store=store)
        ctx = BlockContext(
            block_id=loop.block_id,
            instruction="loop",
            inputs={"blocks": {"tracker": tracker, "my_loop": loop}},
            state_snapshot=state,
        )
        raw = await loop.execute(ctx)
        result = (
            apply_block_output(state, loop.block_id, raw) if isinstance(raw, BlockOutput) else raw
        )

        store_ids = result.shared_memory["tracker_store_ids"]
        assert len(store_ids) == 3
        # All rounds should reference the same store object
        assert all(sid == id(store) for sid in store_ids)

    @pytest.mark.asyncio
    async def test_loop_block_final_state_has_artifact_store(self):
        """LoopBlock final state should still have the artifact_store."""
        from runsight_core import LoopBlock
        from runsight_core.artifacts import InMemoryArtifactStore

        store = InMemoryArtifactStore(run_id="loop-run")
        tracker = RoundTrackingBlock("tracker")

        loop = LoopBlock(
            block_id="my_loop",
            inner_block_refs=["tracker"],
            max_rounds=2,
        )

        from runsight_core.block_io import BlockContext, BlockOutput, apply_block_output

        state = WorkflowState(artifact_store=store)
        ctx = BlockContext(
            block_id=loop.block_id,
            instruction="loop",
            inputs={"blocks": {"tracker": tracker, "my_loop": loop}},
            state_snapshot=state,
        )
        raw = await loop.execute(ctx)
        result = (
            apply_block_output(state, loop.block_id, raw) if isinstance(raw, BlockOutput) else raw
        )

        assert result.artifact_store is store


# ==============================================================================
# 4. DispatchBlock — same artifact_store across parallel tasks
# ==============================================================================


class TestDispatchBlockArtifactStoreSharing:
    """DispatchBlock parallel executions should see the same artifact_store."""

    @pytest.mark.asyncio
    async def test_dispatch_state_preserves_artifact_store(self):
        """DispatchBlock returned state should still have the artifact_store."""
        from unittest.mock import AsyncMock, Mock

        from runsight_core import DispatchBlock
        from runsight_core.artifacts import InMemoryArtifactStore
        from runsight_core.primitives import Soul

        store = InMemoryArtifactStore(run_id="dispatch-run")

        soul1 = Soul(id="writer", kind="soul", name="Writer", role="Writer", system_prompt="Write.")
        soul2 = Soul(
            id="critic", kind="soul", name="Critic", role="Critic", system_prompt="Critique."
        )

        mock_runner = AsyncMock()
        mock_result = Mock()
        mock_result.soul_id = "writer"
        mock_result.output = "output"
        mock_result.cost_usd = 0.01
        mock_result.total_tokens = 10
        mock_runner.execute = AsyncMock(return_value=mock_result)

        from runsight_core.blocks.dispatch import DispatchBranch

        branches = [
            DispatchBranch(
                exit_id="writer", label="Writer", soul=soul1, task_instruction="Do work"
            ),
            DispatchBranch(
                exit_id="critic", label="Critic", soul=soul2, task_instruction="Do work"
            ),
        ]
        block = DispatchBlock(block_id="dispatch", branches=branches, runner=mock_runner)

        from runsight_core.block_io import BlockOutput, apply_block_output, build_block_context

        state = WorkflowState(
            artifact_store=store,
        )
        ctx = build_block_context(block, state)
        raw = await block.execute(ctx)
        result = (
            apply_block_output(state, block.block_id, raw) if isinstance(raw, BlockOutput) else raw
        )
        assert result.artifact_store is store


# ==============================================================================
# 5. Workflow.run() preserves artifact_store through full execution
# ==============================================================================


class TestWorkflowRunArtifactStorePropagation:
    """artifact_store should survive through a full Workflow.run() execution."""

    @pytest.mark.asyncio
    async def test_workflow_run_preserves_artifact_store(self):
        """Running a workflow with artifact_store in initial state preserves it."""
        from runsight_core.artifacts import InMemoryArtifactStore
        from runsight_core.workflow import Workflow

        store = InMemoryArtifactStore(run_id="wf-run")
        capturer = ArtifactCapturingBlock("cap")

        wf = Workflow(name="test_wf")
        wf.add_block(capturer)
        wf.set_entry("cap")
        wf.add_transition("cap", None)

        state = WorkflowState(artifact_store=store)
        result = await wf.run(state)

        # Block should have seen the artifact_store
        captures = result.shared_memory["artifact_store_captures"]
        assert captures["cap"] == id(store)
        assert result.artifact_store is store

    @pytest.mark.asyncio
    async def test_workflow_run_multi_block_same_store(self):
        """Multiple blocks in a workflow should all see the same artifact_store."""
        from runsight_core.artifacts import InMemoryArtifactStore
        from runsight_core.workflow import Workflow

        store = InMemoryArtifactStore(run_id="wf-run")
        cap1 = ArtifactCapturingBlock("cap1")
        cap2 = ArtifactCapturingBlock("cap2")

        wf = Workflow(name="test_wf")
        wf.add_block(cap1)
        wf.add_block(cap2)
        wf.set_entry("cap1")
        wf.add_transition("cap1", "cap2")
        wf.add_transition("cap2", None)

        state = WorkflowState(artifact_store=store)
        result = await wf.run(state)

        captures = result.shared_memory["artifact_store_captures"]
        assert captures["cap1"] == id(store)
        assert captures["cap2"] == id(store)

    @pytest.mark.asyncio
    async def test_workflow_run_without_artifact_store_works(self):
        """Running a workflow without artifact_store (None) should not error."""
        from runsight_core.workflow import Workflow

        capturer = ArtifactCapturingBlock("cap")
        wf = Workflow(name="test_wf")
        wf.add_block(capturer)
        wf.set_entry("cap")
        wf.add_transition("cap", None)

        state = WorkflowState()  # No artifact_store
        result = await wf.run(state)

        captures = result.shared_memory["artifact_store_captures"]
        assert captures["cap"] is None
        assert result.artifact_store is None
