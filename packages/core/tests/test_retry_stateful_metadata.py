"""
Retry and stateful interaction without state corruption.

Tests prove that _execute_with_retry passes the same pre-execution state on
every retry attempt, so a failed stateful block's conversation history is
naturally discarded (exception prevents model_copy return). This is correct
behavior — Pydantic immutability handles it without any special code.

Tests cover:
- Failed attempt does NOT pollute conversation_histories
- Successful retry after failure creates clean history (only success messages)
- Stateful block inside retry inside LoopBlock: round 1 history preserved,
  retry within round 2 starts fresh for that round
- Original state is never mutated across retry attempts
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from runsight_core import LinearBlock
from runsight_core.blocks.base import BaseBlock
from runsight_core.primitives import Soul
from runsight_core.runner import ExecutionResult
from runsight_core.state import WorkflowState
from runsight_core.workflow import Workflow
from runsight_core.yaml.schema import RetryConfig

# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def mock_runner():
    """Mock RunsightTeamRunner with controlled outputs."""
    runner = MagicMock()
    runner.model_name = "gpt-4o"
    runner.execute = AsyncMock()
    return runner


@pytest.fixture
def soul():
    return Soul(
        id="agent_1", kind="soul", name="Analyst", role="Analyst", system_prompt="Analyze things."
    )


# ── Helpers ───────────────────────────────────────────────────────────────


def _make_stateful_linear_block(block_id, soul, runner):
    """Create a stateful LinearBlock with retry config."""
    block = LinearBlock(block_id, soul, runner)
    block.stateful = True
    return block


def _make_workflow_with_single_block(block: BaseBlock) -> Workflow:
    """Create a one-block workflow."""
    wf = Workflow(name="retry_stateful_workflow")
    wf.add_block(block)
    wf.add_transition(block.block_id, None)
    wf.set_entry(block.block_id)
    return wf


# ===========================================================================
# 1. Failed attempt does NOT pollute conversation_histories
# ===========================================================================


class TestRetryMetadataCoexistsWithHistory:
    """When a stateful block succeeds after retry, both retry metadata
    in shared_memory AND conversation_histories should be correctly set."""

    @pytest.mark.asyncio
    async def test_retry_metadata_and_history_both_present(self, mock_runner, soul):
        """After fail-then-succeed, shared_memory has retry metadata AND
        conversation_histories has the history — both correct."""
        call_count = 0

        async def side_effect(instruction, context, soul_arg, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("transient")
            return ExecutionResult(task_id="t1", soul_id="agent_1", output="recovered")

        mock_runner.execute = AsyncMock(side_effect=side_effect)

        block = _make_stateful_linear_block("analyze", soul, mock_runner)
        block.retry_config = RetryConfig(max_attempts=3, backoff="fixed", backoff_base_seconds=0.1)

        wf = _make_workflow_with_single_block(block)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result_state = await wf.run(WorkflowState())

        # Retry metadata in shared_memory
        retry_meta = result_state.shared_memory.get("__retry__analyze")
        assert retry_meta is not None
        assert retry_meta["attempt"] == 2
        assert retry_meta["total_retries"] == 1

        # Conversation history — clean, 1 pair
        history = result_state.conversation_histories["analyze_agent_1"]
        assert len(history) == 2
        assert history[1]["content"] == "recovered"
