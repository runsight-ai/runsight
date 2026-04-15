"""
Tests for RUN-163: Verify RetryBlock -> LoopBlock migration is complete.

Validates:
1. LoopBlock integration tests replace removed RetryBlock integration tests:
   - LoopBlock in full workflow with upstream block (chain pattern)
   - LoopBlock with retry_config in full workflow (retry-on-error + loop-for-iteration)
2. LoopBlock state flow between rounds
"""

import pytest
from runsight_core import (
    LoopBlock,
)
from runsight_core.block_io import BlockContext, BlockOutput
from runsight_core.blocks.base import BaseBlock
from runsight_core.state import WorkflowState
from runsight_core.workflow import Workflow
from runsight_core.yaml.schema import RetryConfig

# ── Test helpers ──────────────────────────────────────────────────────────


class TrackingBlock(BaseBlock):
    """Block that records each call in shared_memory under its block_id."""

    def __init__(self, block_id: str):
        super().__init__(block_id)

    async def execute(self, ctx: BlockContext) -> BlockOutput:
        state = ctx.state_snapshot
        calls = list(state.shared_memory.get(f"{self.block_id}_calls", []))
        calls.append(len(calls) + 1)
        return BlockOutput(
            output=f"call_{len(calls)}",
            shared_memory_updates={f"{self.block_id}_calls": calls},
        )


class WriterBlock(BaseBlock):
    """Simulates a writer agent: appends a draft to shared_memory."""

    def __init__(self, block_id: str):
        super().__init__(block_id)

    async def execute(self, ctx: BlockContext) -> BlockOutput:
        state = ctx.state_snapshot
        drafts = list(state.shared_memory.get("drafts", []))
        round_num = state.shared_memory.get("loop_block_round", 0)
        drafts.append(f"draft_round_{round_num}")
        return BlockOutput(
            output=f"draft_round_{round_num}",
            shared_memory_updates={"drafts": drafts},
        )


class CriticBlock(BaseBlock):
    """Simulates a critic agent: appends feedback to shared_memory."""

    def __init__(self, block_id: str):
        super().__init__(block_id)

    async def execute(self, ctx: BlockContext) -> BlockOutput:
        state = ctx.state_snapshot
        feedback = list(state.shared_memory.get("feedback", []))
        round_num = state.shared_memory.get("loop_block_round", 0)
        feedback.append(f"feedback_round_{round_num}")
        return BlockOutput(
            output=f"feedback_round_{round_num}",
            shared_memory_updates={"feedback": feedback},
        )


class FailNTimesThenSucceed(BaseBlock):
    """Block that fails N times, then succeeds on attempt N+1."""

    def __init__(self, block_id: str, fail_count: int, error_cls: type = RuntimeError):
        super().__init__(block_id)
        self._fail_count = fail_count
        self._error_cls = error_cls
        self._call_count = 0

    async def execute(self, ctx: BlockContext) -> BlockOutput:
        self._call_count += 1
        if self._call_count <= self._fail_count:
            raise self._error_cls(f"fail #{self._call_count}")
        return BlockOutput(output=f"ok on attempt {self._call_count}")


# ===========================================================================
# 1. LoopBlock in full workflow with upstream block (chain pattern)
# ===========================================================================


class TestLoopBlockUpstreamWorkflowIntegration:
    """LoopBlock works correctly in a full workflow combined with upstream block.

    Pattern: upstream (tracking) -> LoopBlock (iterative refinement)
    This replaces the RetryBlock integration test that was removed from
    test_integration_advanced_blocks.py.
    """

    @pytest.mark.asyncio
    async def test_upstream_then_loop_block_workflow(self):
        """Integration: Upstream block produces output, LoopBlock iterates on refinement.

        Full workflow: upstream -> loop_block(writer, critic) -> terminal
        Uses Workflow.run() for real orchestration.
        """
        # Build workflow
        wf = Workflow("upstream_loop_workflow")

        # Upstream block for initial output
        upstream = TrackingBlock("upstream1")

        # Writer and critic blocks for loop
        writer = WriterBlock("writer")
        critic = CriticBlock("critic")

        # LoopBlock iterates writer + critic for 2 rounds
        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["writer", "critic"],
            max_rounds=2,
        )

        wf.add_block(upstream)
        wf.add_block(writer)
        wf.add_block(critic)
        wf.add_block(loop)
        wf.add_transition("upstream1", "loop_block")
        wf.add_transition("loop_block", None)
        wf.set_entry("upstream1")

        errors = wf.validate()
        assert errors == [], f"Workflow validation failed: {errors}"

        initial_state = WorkflowState()
        final_state = await wf.run(initial_state)

        # Upstream should have produced a result
        assert "upstream1" in final_state.results

        # LoopBlock should have executed writer + critic for 2 rounds
        assert "loop_block" in final_state.results
        drafts = final_state.shared_memory.get("drafts", [])
        feedback = final_state.shared_memory.get("feedback", [])
        assert len(drafts) == 2, f"Expected 2 drafts, got {len(drafts)}"
        assert len(feedback) == 2, f"Expected 2 feedback, got {len(feedback)}"

        # Loop metadata should be present
        meta_key = "__loop__loop_block"
        assert meta_key in final_state.shared_memory
        assert final_state.shared_memory[meta_key]["rounds_completed"] == 2


# ===========================================================================
# 4. LoopBlock with retry_config — retry-on-error + loop-for-iteration
#    Tests that retry_config and loop max_rounds coexist correctly
# ===========================================================================


class TestLoopBlockWithRetryConfig:
    """LoopBlock with retry_config on an inner block: retry handles transient errors,
    loop handles iteration. They must coexist correctly in the workflow runner."""

    @pytest.mark.asyncio
    async def test_inner_block_with_retry_config_in_loop_workflow(self):
        """LoopBlock wraps an inner block that has retry_config set.

        The inner block fails once per round but succeeds on retry.
        The loop should still complete all rounds because retry recovers the error.
        """
        inner = FailNTimesThenSucceed("inner_block", fail_count=1)
        inner.retry_config = RetryConfig(max_attempts=3, backoff="fixed", backoff_base_seconds=0.1)

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["inner_block"],
            max_rounds=2,
        )

        wf = Workflow(name="loop_retry_wf")
        wf.add_block(inner)
        wf.add_block(loop)
        wf.add_transition("loop_block", None)
        wf.set_entry("loop_block")

        from unittest.mock import AsyncMock, patch

        with patch("asyncio.sleep", new_callable=AsyncMock) as sleep_mock:
            final_state = await wf.run(WorkflowState())

        retry_meta = final_state.shared_memory.get("__retry__inner_block")
        assert retry_meta is not None
        assert retry_meta["attempt"] == 2
        assert retry_meta["total_retries"] == 1
        assert sleep_mock.await_count == 1
        assert inner._call_count == 3
        assert final_state.results["inner_block"].output == "ok on attempt 3"
        assert final_state.results["loop_block"].output == "completed_2_rounds"

    @pytest.mark.asyncio
    async def test_loop_block_itself_with_retry_config_in_workflow(self):
        """LoopBlock itself with retry_config: the entire loop retries on failure.

        If an inner block fails and the LoopBlock has retry_config, the workflow
        runner should retry the entire LoopBlock execution.
        """
        # This inner block fails on the first call but succeeds on the second.
        # Since LoopBlock re-creates state from scratch on retry, the counter
        # resets each time the LoopBlock is retried.

        class FailOnFirstLoopAttempt(BaseBlock):
            """Fails when it has never been called before (first LoopBlock attempt),
            succeeds on subsequent LoopBlock retries."""

            attempt_count = 0  # class-level to persist across LoopBlock retries

            def __init__(self, block_id: str):
                super().__init__(block_id)

            async def execute(self, ctx: BlockContext) -> BlockOutput:
                FailOnFirstLoopAttempt.attempt_count += 1
                if FailOnFirstLoopAttempt.attempt_count <= 1:
                    raise RuntimeError("transient error")
                return BlockOutput(output=f"ok_attempt_{FailOnFirstLoopAttempt.attempt_count}")

        # Reset class-level counter
        FailOnFirstLoopAttempt.attempt_count = 0

        inner = FailOnFirstLoopAttempt("inner_block")

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["inner_block"],
            max_rounds=1,
        )
        loop.retry_config = RetryConfig(max_attempts=3, backoff="fixed", backoff_base_seconds=0.1)

        wf = Workflow(name="loop_with_retry_wf")
        wf.add_block(inner)
        wf.add_block(loop)
        wf.add_transition("loop_block", None)
        wf.set_entry("loop_block")

        from unittest.mock import AsyncMock, patch

        with patch("asyncio.sleep", new_callable=AsyncMock):
            final_state = await wf.run(WorkflowState())

        # LoopBlock should have completed (retried after first failure)
        assert "loop_block" in final_state.results
        assert FailOnFirstLoopAttempt.attempt_count == 2


# ===========================================================================
# 7. LoopBlock state isolation between rounds
#    Verifies that results from one round are visible in the next (no reset)
# ===========================================================================


class TestLoopBlockStateFlowBetweenRounds:
    """LoopBlock state flows correctly between rounds: results accumulate,
    inner blocks can read previous round outputs from state."""

    @pytest.mark.asyncio
    async def test_inner_block_reads_previous_round_output(self):
        """Inner block in round 2 can read its own result from round 1 in state.results."""

        class AccumulatingBlock(BaseBlock):
            """Reads own previous result and appends to it."""

            def __init__(self, block_id: str):
                super().__init__(block_id)

            async def execute(self, ctx: BlockContext) -> BlockOutput:
                state = ctx.state_snapshot
                previous_result = state.results.get(self.block_id)
                previous = previous_result.output if previous_result is not None else ""
                new_output = f"{previous}|round_{state.shared_memory.get('loop_block_round', 0)}"
                return BlockOutput(output=new_output)

        accum = AccumulatingBlock("accum_block")
        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["accum_block"],
            max_rounds=3,
        )

        wf = Workflow(name="state_flow_test")
        wf.add_block(accum)
        wf.add_block(loop)
        wf.add_transition("loop_block", None)
        wf.set_entry("loop_block")

        final_state = await wf.run(WorkflowState())

        # The accumulating block should have built up output across rounds
        accum_block_result = final_state.results.get("accum_block")
        assert accum_block_result is not None
        accum_result = accum_block_result.output
        assert "|round_1" in accum_result
        assert "|round_2" in accum_result
        assert "|round_3" in accum_result
