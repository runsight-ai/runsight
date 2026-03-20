"""
Tests for RUN-163: Verify RetryBlock -> LoopBlock migration is complete.

Validates:
1. No stale RetryBlock comments remain in migrated test files
2. LoopBlock integration tests replace removed RetryBlock integration tests:
   - LoopBlock in full workflow with upstream block (chain pattern)
   - LoopBlock in cross-feature workflow (LoopBlock + Router conditional branching)
   - LoopBlock with retry_config in full workflow (retry-on-error + loop-for-iteration)
3. LoopBlock nested workflow integration (sub-workflow inside loop)
4. LoopBlock + TeamLeadBlock failure analysis pattern (loop exhaustion -> analysis)
"""

import subprocess
from pathlib import Path

import pytest
from unittest.mock import AsyncMock, MagicMock

from runsight_core.blocks.base import BaseBlock
from runsight_core.blocks.implementations import (
    LoopBlock,
    RouterBlock,
    TeamLeadBlock,
)
from runsight_core.primitives import Soul, Task
from runsight_core.runner import ExecutionResult
from runsight_core.state import WorkflowState
from runsight_core.workflow import Workflow
from runsight_core.yaml.schema import RetryConfig


REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent  # runsight/
LIBS_TESTS = REPO_ROOT / "libs" / "core" / "tests"


# ── Test helpers ──────────────────────────────────────────────────────────


class TrackingBlock(BaseBlock):
    """Block that records each call in shared_memory under its block_id."""

    def __init__(self, block_id: str):
        super().__init__(block_id)

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        calls = list(state.shared_memory.get(f"{self.block_id}_calls", []))
        calls.append(len(calls) + 1)
        return state.model_copy(
            update={
                "results": {**state.results, self.block_id: f"call_{len(calls)}"},
                "shared_memory": {
                    **state.shared_memory,
                    f"{self.block_id}_calls": calls,
                },
            }
        )


class WriterBlock(BaseBlock):
    """Simulates a writer agent: appends a draft to shared_memory."""

    def __init__(self, block_id: str):
        super().__init__(block_id)

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        drafts = list(state.shared_memory.get("drafts", []))
        round_num = state.shared_memory.get("loop_block_round", 0)
        drafts.append(f"draft_round_{round_num}")
        return state.model_copy(
            update={
                "results": {**state.results, self.block_id: f"draft_round_{round_num}"},
                "shared_memory": {**state.shared_memory, "drafts": drafts},
            }
        )


class CriticBlock(BaseBlock):
    """Simulates a critic agent: appends feedback to shared_memory."""

    def __init__(self, block_id: str):
        super().__init__(block_id)

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        feedback = list(state.shared_memory.get("feedback", []))
        round_num = state.shared_memory.get("loop_block_round", 0)
        feedback.append(f"feedback_round_{round_num}")
        return state.model_copy(
            update={
                "results": {
                    **state.results,
                    self.block_id: f"feedback_round_{round_num}",
                },
                "shared_memory": {**state.shared_memory, "feedback": feedback},
            }
        )


class FailNTimesThenSucceed(BaseBlock):
    """Block that fails N times, then succeeds on attempt N+1."""

    def __init__(self, block_id: str, fail_count: int, error_cls: type = RuntimeError):
        super().__init__(block_id)
        self._fail_count = fail_count
        self._error_cls = error_cls
        self._call_count = 0

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        self._call_count += 1
        if self._call_count <= self._fail_count:
            raise self._error_cls(f"fail #{self._call_count}")
        return state.model_copy(
            update={
                "results": {
                    **state.results,
                    self.block_id: f"ok on attempt {self._call_count}",
                }
            }
        )


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def mock_runner():
    """Mock RunsightTeamRunner with controlled outputs."""
    runner = MagicMock()
    runner.execute_task = AsyncMock()
    return runner


@pytest.fixture
def sample_souls():
    """Sample souls for testing."""
    return {
        "agent1": Soul(id="agent1", role="Agent 1", system_prompt="You are agent 1."),
        "agent2": Soul(id="agent2", role="Agent 2", system_prompt="You are agent 2."),
        "advisor": Soul(
            id="team_lead",
            role="Team Lead",
            system_prompt="You analyze failures and provide recommendations.",
        ),
    }


# ===========================================================================
# 1. Stale RetryBlock comments — must be cleaned up
# ===========================================================================


class TestStaleRetryBlockComments:
    """Stale RetryBlock comments from migration should be cleaned up.

    DoD: "All comment references like '# TestRetryBlock: removed (RUN-158)' and
    'Note: RetryBlock tests removed' should be cleaned up."
    """

    def test_no_stale_retryblock_comment_in_integration_advanced_blocks(self):
        """test_integration_advanced_blocks.py should not contain stale
        'Note: RetryBlock tests removed' comment."""
        content = (LIBS_TESTS / "test_integration_advanced_blocks.py").read_text()
        assert "RetryBlock tests removed" not in content, (
            "Stale 'RetryBlock tests removed' comment still present "
            "in test_integration_advanced_blocks.py — clean up the migration comment"
        )

    def test_no_stale_retryblock_comment_in_integration_cross_feature(self):
        """test_integration_cross_feature_boundaries.py should not contain stale
        'Note: RetryBlock tests removed' comment."""
        content = (LIBS_TESTS / "test_integration_cross_feature_boundaries.py").read_text()
        assert "RetryBlock tests removed" not in content, (
            "Stale 'RetryBlock tests removed' comment still present "
            "in test_integration_cross_feature_boundaries.py — clean up the migration comment"
        )

    def test_no_stale_retryblock_comment_in_yaml_parser(self):
        """test_yaml_parser.py should not contain stale
        '# TestRetryBlock: removed (RUN-158)' comment."""
        content = (LIBS_TESTS / "test_yaml_parser.py").read_text()
        assert "TestRetryBlock: removed" not in content, (
            "Stale 'TestRetryBlock: removed (RUN-158)' comment still present "
            "in test_yaml_parser.py — clean up the migration comment"
        )

    def test_no_retryblock_stale_comments_in_any_test_file(self):
        """No test file should contain stale RetryBlock migration comments.

        Allowed references: negative assertions in test_loop_block.py and
        test_loop_exports_schema.py that verify RetryBlock was removed.
        """
        result = subprocess.run(
            ["grep", "-rn", "--include=*.py", "RetryBlock", str(LIBS_TESTS)],
            capture_output=True,
            text=True,
        )
        hits = result.stdout.strip().splitlines()

        # Filter out allowed references:
        # - test_loop_block.py: negative assertions ("RetryBlock should no longer be exported")
        # - test_loop_exports_schema.py: negative assertions and codebase grep tests
        # - this test file itself
        stale_hits = []
        allowed_files = {
            "test_loop_block.py",
            "test_loop_exports_schema.py",
            "test_retryblock_migration.py",
        }
        for hit in hits:
            if not hit:
                continue
            filename = Path(hit.split(":")[0]).name
            if filename in allowed_files:
                continue
            stale_hits.append(hit)

        assert not stale_hits, (
            "Stale RetryBlock references found in test files "
            "(not in allowed negative-assertion files):\n" + "\n".join(stale_hits)
        )


# ===========================================================================
# 2. LoopBlock in full workflow with upstream block (chain pattern)
#    Replaces: removed RetryBlock integration test in test_integration_advanced_blocks.py
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

        initial_state = WorkflowState(
            current_task=Task(id="refine", instruction="Refine the output")
        )
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
# 3. LoopBlock + Router conditional branching (cross-feature)
#    Replaces: removed RetryBlock cross-feature test in
#    test_integration_cross_feature_boundaries.py
# ===========================================================================


class TestLoopBlockRouterCrossFeatureIntegration:
    """LoopBlock works with RouterBlock in cross-feature workflow.

    Pattern: LoopBlock (iterates) -> Router (decides based on loop output)
    This replaces the RetryBlock cross-feature test that was removed from
    test_integration_cross_feature_boundaries.py.
    """

    @pytest.mark.asyncio
    async def test_loop_then_router_workflow(self):
        """Integration: LoopBlock iterates, Router decides based on loop result.

        Full workflow: loop_block(worker) -> router -> terminal
        Router reads loop metadata from shared_memory to make decision.
        """
        worker = TrackingBlock("worker")
        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["worker"],
            max_rounds=3,
        )

        def evaluate_loop_result(state: WorkflowState) -> str:
            """Callable evaluator: reads loop metadata and decides."""
            meta = state.shared_memory.get("__loop__loop_block", {})
            rounds = meta.get("rounds_completed", 0)
            return "approved" if rounds >= 3 else "rejected"

        router = RouterBlock("router1", evaluate_loop_result, runner=None)

        wf = Workflow("loop_router_workflow")
        wf.add_block(worker)
        wf.add_block(loop)
        wf.add_block(router)
        wf.add_transition("loop_block", "router1")
        wf.add_transition("router1", None)
        wf.set_entry("loop_block")

        errors = wf.validate()
        assert errors == [], f"Workflow validation failed: {errors}"

        final_state = await wf.run(WorkflowState())

        # LoopBlock should have run 3 rounds
        worker_calls = final_state.shared_memory.get("worker_calls", [])
        assert len(worker_calls) == 3

        # Router should have decided "approved" based on loop completing 3 rounds
        assert "router1" in final_state.results
        assert final_state.results["router1"].output == "approved"
        assert final_state.metadata["router1_decision"] == "approved"

    @pytest.mark.asyncio
    async def test_loop_with_break_then_router_workflow(self):
        """Integration: LoopBlock breaks early, Router reads break metadata.

        Full workflow: loop_block(keyword_worker) -> router -> terminal
        Router should see broke_early=True and decide accordingly.
        """
        from runsight_core.conditions.engine import Condition

        class KeywordWorker(BaseBlock):
            """Outputs 'DONE' on round 2."""

            def __init__(self, block_id: str):
                super().__init__(block_id)

            async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
                calls = list(state.shared_memory.get(f"{self.block_id}_calls", []))
                calls.append(len(calls) + 1)
                output = "DONE: finished" if len(calls) >= 2 else "working..."
                return state.model_copy(
                    update={
                        "results": {**state.results, self.block_id: output},
                        "shared_memory": {
                            **state.shared_memory,
                            f"{self.block_id}_calls": calls,
                        },
                    }
                )

        worker = KeywordWorker("keyword_worker")
        break_cond = Condition(eval_key="keyword_worker", operator="contains", value="DONE")
        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["keyword_worker"],
            max_rounds=5,
            break_condition=break_cond,
        )

        def evaluate_break_status(state: WorkflowState) -> str:
            """Decides based on whether loop broke early."""
            meta = state.shared_memory.get("__loop__loop_block", {})
            return "early_exit" if meta.get("broke_early") else "full_run"

        router = RouterBlock("router1", evaluate_break_status, runner=None)

        wf = Workflow("loop_break_router_workflow")
        wf.add_block(worker)
        wf.add_block(loop)
        wf.add_block(router)
        wf.add_transition("loop_block", "router1")
        wf.add_transition("router1", None)
        wf.set_entry("loop_block")

        errors = wf.validate()
        assert errors == [], f"Workflow validation failed: {errors}"

        final_state = await wf.run(WorkflowState())

        # Loop should have broken early on round 2
        meta = final_state.shared_memory.get("__loop__loop_block", {})
        assert meta["broke_early"] is True
        assert meta["rounds_completed"] == 2

        # Router should see the early exit
        assert final_state.results["router1"].output == "early_exit"


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

        NOTE: The retry_config on inner blocks is applied by the Workflow runner,
        not by the LoopBlock itself. Since LoopBlock calls inner_block.execute()
        directly (not through the workflow runner), retry_config on inner blocks
        inside a loop is NOT automatically applied.

        This test verifies the gap: the inner block's retry_config is ignored
        inside a LoopBlock, and the inner block failure propagates.
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

        # The inner block fails on first call. LoopBlock calls execute() directly
        # without retry wrapper, so the error propagates.
        # This test documents the current behavior: retry_config on inner blocks
        # inside a loop is NOT applied by LoopBlock.
        with pytest.raises(RuntimeError, match="fail #1"):
            await wf.run(WorkflowState())

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

            async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
                FailOnFirstLoopAttempt.attempt_count += 1
                if FailOnFirstLoopAttempt.attempt_count <= 1:
                    raise RuntimeError("transient error")
                return state.model_copy(
                    update={
                        "results": {
                            **state.results,
                            self.block_id: f"ok_attempt_{FailOnFirstLoopAttempt.attempt_count}",
                        }
                    }
                )

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
# 5. LoopBlock + TeamLeadBlock: loop exhaustion -> failure analysis
#    Replaces pattern from removed RetryBlock tests that tested
#    retry exhaustion followed by error analysis.
# ===========================================================================


class TestLoopBlockTeamLeadIntegration:
    """LoopBlock exhaustion followed by TeamLeadBlock failure analysis.

    Pattern: loop_block -> teamlead (analyzes loop results)
    This replaces the old RetryBlock -> TeamLeadBlock integration pattern.
    """

    @pytest.mark.asyncio
    async def test_loop_exhaustion_then_teamlead_analysis(self, mock_runner, sample_souls):
        """Integration: LoopBlock runs all rounds, TeamLeadBlock analyzes the results.

        Full workflow: loop_block(writer, critic) -> teamlead -> terminal
        TeamLeadBlock reads loop metadata and feedback to produce recommendation.
        """
        # Setup
        writer = WriterBlock("writer")
        critic = CriticBlock("critic")

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["writer", "critic"],
            max_rounds=3,
        )

        # TeamLeadBlock reads feedback from shared_memory
        mock_runner.execute_task.return_value = ExecutionResult(
            task_id="analysis",
            soul_id="team_lead",
            output="Root cause: Critic feedback shows no convergence after 3 rounds.",
        )

        teamlead = TeamLeadBlock(
            block_id="teamlead1",
            failure_context_keys=["feedback"],
            team_lead_soul=sample_souls["advisor"],
            runner=mock_runner,
        )

        wf = Workflow("loop_teamlead_workflow")
        wf.add_block(writer)
        wf.add_block(critic)
        wf.add_block(loop)
        wf.add_block(teamlead)
        wf.add_transition("loop_block", "teamlead1")
        wf.add_transition("teamlead1", None)
        wf.set_entry("loop_block")

        errors = wf.validate()
        assert errors == [], f"Workflow validation failed: {errors}"

        final_state = await wf.run(WorkflowState())

        # LoopBlock should have run 3 rounds
        drafts = final_state.shared_memory.get("drafts", [])
        feedback = final_state.shared_memory.get("feedback", [])
        assert len(drafts) == 3
        assert len(feedback) == 3

        # TeamLeadBlock should have produced a recommendation
        assert "teamlead1" in final_state.results
        assert "Root cause" in final_state.results["teamlead1"].output
        assert "teamlead1_recommendation" in final_state.shared_memory

        # TeamLeadBlock should have been called with feedback context
        call_args = mock_runner.execute_task.call_args
        task_arg = call_args[0][0]
        assert "feedback" in task_arg.instruction


# ===========================================================================
# 6. LoopBlock in multi-block workflow with all advanced blocks
#    Full workflow: upstream -> loop(writer, critic) -> router -> terminal
#    Replaces the combined advanced blocks integration from removed test
# ===========================================================================


class TestLoopBlockMultiBlockWorkflowIntegration:
    """Full workflow integration: Upstream -> LoopBlock -> Router.

    This is the comprehensive replacement for removed RetryBlock integration
    tests across test_integration_advanced_blocks.py and
    test_integration_cross_feature_boundaries.py.
    """

    @pytest.mark.asyncio
    async def test_upstream_loop_router_full_workflow(self):
        """End-to-end workflow: Upstream -> LoopBlock(writer, critic) -> Router.

        Upstream: produces initial output
        LoopBlock: iterates writer + critic for refinement
        Router: evaluates loop result for final decision

        Uses real Workflow.run() orchestration.
        """
        # Build workflow
        wf = Workflow("full_integration_workflow")

        upstream = TrackingBlock("upstream1")

        writer = WriterBlock("writer")
        critic = CriticBlock("critic")
        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["writer", "critic"],
            max_rounds=2,
        )

        def evaluate_quality(state: WorkflowState) -> str:
            """Callable evaluator: approves if loop completed all rounds."""
            meta = state.shared_memory.get("__loop__loop_block", {})
            return "approved" if meta.get("rounds_completed", 0) >= 2 else "needs_work"

        router = RouterBlock("router1", evaluate_quality, runner=None)

        wf.add_block(upstream)
        wf.add_block(writer)
        wf.add_block(critic)
        wf.add_block(loop)
        wf.add_block(router)
        wf.add_transition("upstream1", "loop_block")
        wf.add_transition("loop_block", "router1")
        wf.add_transition("router1", None)
        wf.set_entry("upstream1")

        errors = wf.validate()
        assert errors == [], f"Workflow validation failed: {errors}"

        initial_state = WorkflowState(
            current_task=Task(id="process", instruction="Process and refine")
        )
        final_state = await wf.run(initial_state)

        # Verify all blocks executed in sequence
        assert "upstream1" in final_state.results
        assert "loop_block" in final_state.results
        assert "router1" in final_state.results

        # LoopBlock completed 2 rounds
        drafts = final_state.shared_memory.get("drafts", [])
        feedback = final_state.shared_memory.get("feedback", [])
        assert len(drafts) == 2
        assert len(feedback) == 2

        # Router approved based on loop completion
        assert final_state.results["router1"].output == "approved"
        assert final_state.metadata["router1_decision"] == "approved"

        # Router block produced message
        block_messages = [m["content"] for m in final_state.execution_log]
        has_router_msg = any("[Block router1]" in m for m in block_messages)
        assert has_router_msg, "Router block message not found"


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

            async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
                previous = state.results.get(self.block_id, "")
                new_output = f"{previous}|round_{state.shared_memory.get('loop_block_round', 0)}"
                return state.model_copy(
                    update={"results": {**state.results, self.block_id: new_output}}
                )

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
        accum_result = final_state.results.get("accum_block", "")
        assert "|round_1" in accum_result
        assert "|round_2" in accum_result
        assert "|round_3" in accum_result


# ===========================================================================
# 8. LoopBlock with conditional transition after break
#    LoopBlock -> conditional router based on break status
# ===========================================================================


class TestLoopBlockConditionalTransition:
    """LoopBlock result feeds into conditional transition based on loop outcome."""

    @pytest.mark.asyncio
    async def test_conditional_transition_after_loop_early_break(self):
        """LoopBlock breaks early -> conditional transition picks 'early_exit' path.

        Uses Router with conditional transitions (not just callable evaluator).
        """
        from runsight_core.conditions.engine import Condition

        class KeywordBlock(BaseBlock):
            """Outputs DONE on call 2."""

            def __init__(self, block_id: str):
                super().__init__(block_id)

            async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
                calls = list(state.shared_memory.get(f"{self.block_id}_calls", []))
                calls.append(len(calls) + 1)
                output = "DONE" if len(calls) >= 2 else "working"
                return state.model_copy(
                    update={
                        "results": {**state.results, self.block_id: output},
                        "shared_memory": {
                            **state.shared_memory,
                            f"{self.block_id}_calls": calls,
                        },
                    }
                )

        worker = KeywordBlock("worker")
        break_cond = Condition(eval_key="worker", operator="contains", value="DONE")
        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["worker"],
            max_rounds=5,
            break_condition=break_cond,
        )

        def route_on_break(state: WorkflowState) -> str:
            meta = state.shared_memory.get("__loop__loop_block", {})
            return "early_exit" if meta.get("broke_early") else "full_run"

        router = RouterBlock("router1", route_on_break, runner=None)

        early_handler = TrackingBlock("early_handler")
        full_handler = TrackingBlock("full_handler")

        wf = Workflow("conditional_loop_wf")
        wf.add_block(worker)
        wf.add_block(loop)
        wf.add_block(router)
        wf.add_block(early_handler)
        wf.add_block(full_handler)
        wf.add_transition("loop_block", "router1")
        wf.add_conditional_transition(
            "router1",
            {"early_exit": "early_handler", "full_run": "full_handler"},
        )
        wf.add_transition("early_handler", None)
        wf.add_transition("full_handler", None)
        wf.set_entry("loop_block")

        errors = wf.validate()
        assert errors == [], f"Workflow validation failed: {errors}"

        final_state = await wf.run(WorkflowState())

        # Loop broke early on round 2
        assert final_state.shared_memory["__loop__loop_block"]["broke_early"] is True

        # Router decided early_exit
        assert final_state.results["router1"].output == "early_exit"

        # Early handler was executed, full handler was NOT
        assert "early_handler" in final_state.results
        assert "full_handler" not in final_state.results
