"""
Integration tests for advanced blocks interaction patterns.

Tests key integration patterns:
1. MessageBusBlock → RouterBlock: Multi-agent consensus workflows demonstrating
   how MessageBus produces consensus that Router then evaluates for routing decision.

Uses real Workflow execution with mocked runner.execute_task calls.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from runsight_core.state import WorkflowState
from runsight_core.primitives import Soul, Task
from runsight_core.blocks.implementations import (
    MessageBusBlock,
    RouterBlock,
)
from runsight_core.runner import ExecutionResult
from runsight_core.workflow import Workflow


# ===== Fixtures =====


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
        "router_judge": Soul(
            id="router_judge",
            role="Router Judge",
            system_prompt="You evaluate consensus and make decisions.",
        ),
        "advisor": Soul(
            id="team_lead",
            role="Team Lead",
            system_prompt="You analyze failures and provide recommendations.",
        ),
    }


# ===== MessageBus → Router Integration Tests =====


@pytest.mark.asyncio
async def test_messagebus_router_workflow(mock_runner, sample_souls):
    """
    AC-1: Integration test demonstrating MessageBus → Router workflow.
    - MessageBusBlock produces consensus in shared_memory
    - RouterBlock reads consensus via callable evaluator from shared_memory
    - Final state contains both messagebus transcript and router decision
    - Uses real Workflow execution without mocks (Workflow.add_block, Workflow.run)
    """
    # Setup mock responses for MessageBusBlock (2 souls × 2 iterations = 4 calls)
    call_count = [0]

    def create_messagebus_result(*args, **kwargs):
        call_count[0] += 1
        task = args[0]
        soul = args[1]
        return ExecutionResult(
            task_id=task.id,
            soul_id=soul.id,
            output=f"Contribution from {soul.id} - call {call_count[0]}",
        )

    mock_runner.execute_task.side_effect = create_messagebus_result

    # Build Workflow with MessageBusBlock → RouterBlock
    wf = Workflow("messagebus_router_workflow")

    # Create MessageBusBlock with 2 souls, 2 iterations
    messagebus_block = MessageBusBlock(
        "messagebus1",
        [sample_souls["agent1"], sample_souls["agent2"]],
        iterations=2,
        runner=mock_runner,
    )

    # Create RouterBlock with callable evaluator that reads consensus from shared_memory
    def evaluate_consensus(state: WorkflowState) -> str:
        """Callable evaluator that checks consensus content from MessageBusBlock."""
        consensus = state.shared_memory.get("messagebus1_consensus", "")
        # Make a decision based on consensus content
        if "call 4" in consensus:  # Last contribution from last round
            return "approved"
        else:
            return "rejected"

    router_block = RouterBlock("router1", evaluate_consensus, runner=None)

    # Add blocks to workflow
    wf.add_block(messagebus_block).add_block(router_block)
    wf.add_transition("messagebus1", "router1").add_transition("router1", None)
    wf.set_entry("messagebus1")

    # Validate workflow
    errors = wf.validate()
    assert errors == [], f"Workflow validation failed: {errors}"

    # Execute workflow
    initial_state = WorkflowState(
        current_task=Task(id="discussion", instruction="Discuss the proposal")
    )
    final_state = await wf.run(initial_state)

    # Verify MessageBusBlock executed and stored transcript
    assert "messagebus1" in final_state.results
    transcript = json.loads(final_state.results["messagebus1"])
    assert len(transcript) == 2  # 2 iterations
    assert len(transcript[0]["contributions"]) == 2  # 2 souls
    assert len(transcript[1]["contributions"]) == 2  # 2 souls

    # Verify consensus stored in shared_memory
    assert "messagebus1_consensus" in final_state.shared_memory
    expected_consensus = transcript[-1]["contributions"][-1]["output"]
    assert final_state.shared_memory["messagebus1_consensus"] == expected_consensus
    assert "call 4" in expected_consensus  # Last call

    # Verify RouterBlock executed and made decision
    assert "router1" in final_state.results
    assert final_state.results["router1"] == "approved"
    assert final_state.metadata["router1_decision"] == "approved"

    # Verify both blocks produced messages
    assert len(final_state.messages) == 2
    assert "[Block messagebus1]" in final_state.messages[0]["content"]
    assert "2 agents × 2 rounds" in final_state.messages[0]["content"]
    assert "[Block router1]" in final_state.messages[1]["content"]
    assert "RouterBlock decision: approved" in final_state.messages[1]["content"]

    # Verify runner was called 4 times (2 souls × 2 iterations)
    assert mock_runner.execute_task.call_count == 4


@pytest.mark.asyncio
async def test_messagebus_router_with_soul_evaluator(mock_runner, sample_souls):
    """
    Additional test: MessageBus → Router workflow using Soul evaluator instead of Callable.
    Demonstrates RouterBlock can use LLM to evaluate consensus.
    """
    # Setup mock responses
    call_count = [0]

    def create_result(*args, **kwargs):
        call_count[0] += 1
        task = args[0]
        soul = args[1]
        if soul.id == "router_judge":
            # Router judge makes decision
            return ExecutionResult(
                task_id=task.id, soul_id=soul.id, output="approved - consensus is strong"
            )
        else:
            # MessageBus agents
            return ExecutionResult(
                task_id=task.id, soul_id=soul.id, output=f"Opinion from {soul.id}"
            )

    mock_runner.execute_task.side_effect = create_result

    # Build Workflow
    wf = Workflow("messagebus_router_soul_workflow")

    messagebus_block = MessageBusBlock(
        "messagebus2",
        [sample_souls["agent1"], sample_souls["agent2"]],
        iterations=2,
        runner=mock_runner,
    )

    # RouterBlock with Soul evaluator (uses LLM to decide)
    router_block = RouterBlock("router2", sample_souls["router_judge"], runner=mock_runner)

    wf.add_block(messagebus_block).add_block(router_block)
    wf.add_transition("messagebus2", "router2").add_transition("router2", None)
    wf.set_entry("messagebus2")

    # Execute
    initial_state = WorkflowState(
        current_task=Task(id="discussion2", instruction="Evaluate the discussion consensus")
    )
    final_state = await wf.run(initial_state)

    # Verify MessageBusBlock executed
    assert "messagebus2" in final_state.results
    assert "messagebus2_consensus" in final_state.shared_memory

    # Verify RouterBlock used Soul evaluator and made decision
    assert "router2" in final_state.results
    assert "approved" in final_state.results["router2"]
    assert "approved" in final_state.metadata["router2_decision"]

    # Verify runner called 5 times: 4 for messagebus (2 souls × 2 iterations) + 1 for router
    assert mock_runner.execute_task.call_count == 5
