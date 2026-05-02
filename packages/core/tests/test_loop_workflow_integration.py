"""LoopBlock schema, parsing, execution, and workflow integration behavior."""

from __future__ import annotations

import pytest
from pydantic import TypeAdapter
from runsight_core.blocks.base import BaseBlock
from runsight_core.state import WorkflowState
from runsight_core.workflow import Workflow
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


class TestLoopBlockWorkflowIntegration:
    """LoopBlock works correctly when executed through Workflow.run()."""

    @pytest.mark.asyncio
    async def test_workflow_passes_blocks_to_loop_execute(self):
        """Workflow.run() should pass blocks=self._blocks to LoopBlock.execute() via kwargs."""
        from runsight_core import LoopBlock

        inner = TrackingBlock("inner_block")
        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["inner_block"],
            max_rounds=2,
        )

        wf = Workflow(name="loop_runtime_workflow")
        wf.add_block(inner)
        wf.add_block(loop)
        wf.add_transition("loop_block", None)
        wf.set_entry("loop_block")

        state = WorkflowState()
        result_state = await wf.run(state)

        # Inner block should have been called 2 times
        calls = result_state.shared_memory.get("inner_block_calls", [])
        assert len(calls) == 2

    @pytest.mark.asyncio
    async def test_isinstance_check_uses_loop_block(self):
        """Workflow runner should use isinstance(block, LoopBlock), not RetryBlock."""
        from runsight_core import LoopBlock

        inner = TrackingBlock("inner_block")
        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["inner_block"],
            max_rounds=1,
        )

        wf = Workflow(name="loop_instance_workflow")
        wf.add_block(inner)
        wf.add_block(loop)
        wf.add_transition("loop_block", None)
        wf.set_entry("loop_block")

        state = WorkflowState()
        # Should not raise — workflow should recognize LoopBlock and pass kwargs
        result_state = await wf.run(state)
        assert "inner_block" in result_state.results

    @pytest.mark.asyncio
    async def test_step_wrapped_loop_receives_workflow_infra_and_declared_inputs(self):
        """A Step-wrapped LoopBlock must keep declared inputs and workflow runtime infra."""
        from runsight_core import LoopBlock
        from runsight_core.primitives import Step
        from runsight_core.state import BlockResult

        class CapturingLoopBlock(LoopBlock):
            def __init__(self):
                super().__init__(
                    block_id="loop_block",
                    inner_block_refs=["inner_block"],
                    max_rounds=1,
                )
                self.received_inputs = None

            async def execute(self, ctx):
                self.received_inputs = dict(ctx.inputs)
                return await super().execute(ctx)

        class CapturingInnerBlock(BaseBlock):
            def __init__(self):
                super().__init__(block_id="inner_block")
                self.context_access = "declared"
                self.received_inputs = None
                self.calls: list[int] = []

            async def execute(self, ctx):
                from runsight_core.block_io import BlockOutput

                self.received_inputs = dict(ctx.inputs)
                self.calls.append(len(self.calls) + 1)
                return BlockOutput(
                    output="inner",
                    shared_memory_updates={"inner_block_calls": list(self.calls)},
                )

        inner = CapturingInnerBlock()
        loop = CapturingLoopBlock()
        step = Step(block=loop, declared_inputs={"data": "source"})

        wf = Workflow(name="step_wrapped_loop_wf")
        wf.add_block(inner)
        wf.add_block(step)
        wf.add_transition("loop_block", None)
        wf.set_entry("loop_block")

        state = WorkflowState(results={"source": BlockResult(output="declared value")})
        result_state = await wf.run(state)

        assert loop.received_inputs is not None
        assert loop.received_inputs["data"] == "declared value"
        assert "blocks" in loop.received_inputs
        assert "ctx" in loop.received_inputs
        assert inner.received_inputs is not None
        assert inner.received_inputs["data"] == "declared value"
        calls = result_state.shared_memory.get("inner_block_calls", [])
        assert len(calls) == 1


# ===========================================================================
# 5. Integration tests — writer + critic pattern
# ===========================================================================


class TestLoopBlockWriterCriticIntegration:
    """Integration: Two blocks inside LoopBlock in writer + critic pattern for 3 rounds."""

    @pytest.mark.asyncio
    async def test_writer_critic_three_rounds(self):
        """Writer + critic pattern: 3 rounds produces 3 drafts and 3 feedbacks."""
        from runsight_core import LoopBlock

        writer = WriterBlock("writer")
        critic = CriticBlock("critic")
        blocks = {"writer": writer, "critic": critic}

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["writer", "critic"],
            max_rounds=3,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        result_state = await _run_loop(loop, state, blocks)

        drafts = result_state.shared_memory.get("drafts", [])
        feedback = result_state.shared_memory.get("feedback", [])

        assert len(drafts) == 3, f"Expected 3 drafts, got {len(drafts)}: {drafts}"
        assert len(feedback) == 3, f"Expected 3 feedback, got {len(feedback)}: {feedback}"

    @pytest.mark.asyncio
    async def test_writer_critic_workflow_integration(self):
        """Full workflow integration: LoopBlock as entry, writer+critic pattern, 3 rounds."""
        from runsight_core import LoopBlock

        writer = WriterBlock("writer")
        critic = CriticBlock("critic")
        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["writer", "critic"],
            max_rounds=3,
        )

        wf = Workflow(name="writer_critic_wf")
        wf.add_block(writer)
        wf.add_block(critic)
        wf.add_block(loop)
        wf.add_transition("loop_block", None)
        wf.set_entry("loop_block")

        state = WorkflowState()
        result_state = await wf.run(state)

        drafts = result_state.shared_memory.get("drafts", [])
        feedback = result_state.shared_memory.get("feedback", [])

        assert len(drafts) == 3
        assert len(feedback) == 3

    @pytest.mark.asyncio
    async def test_loop_result_stored_under_loop_block_id(self):
        """LoopBlock should store its own result in state.results[loop_block_id]."""
        from runsight_core import LoopBlock

        inner = TrackingBlock("inner_block")
        blocks = {"inner_block": inner}

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["inner_block"],
            max_rounds=2,
        )
        blocks["loop_block"] = loop

        state = WorkflowState()
        result_state = await _run_loop(loop, state, blocks)

        assert "loop_block" in result_state.results


# ===========================================================================
# 6. __init__.py exports
# ===========================================================================
