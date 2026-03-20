"""
Integration tests for advanced blocks interaction patterns.

Tests key integration patterns:
1. RouterBlock with callable and Soul evaluators in workflow context.

Uses real Workflow execution with mocked runner.execute_task calls.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from runsight_core.state import WorkflowState
from runsight_core.primitives import Soul, Task
from runsight_core.blocks.implementations import (
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


# ===== Router Integration Tests =====


@pytest.mark.asyncio
async def test_router_callable_evaluator_workflow(mock_runner, sample_souls):
    """
    Integration test demonstrating Router workflow with callable evaluator.
    - RouterBlock reads state via callable evaluator
    - Final state contains router decision
    - Uses real Workflow execution
    """

    def evaluate_state(state: WorkflowState) -> str:
        """Callable evaluator that checks shared_memory."""
        data = state.shared_memory.get("input_data", "")
        if "approved" in data:
            return "approved"
        return "rejected"

    router_block = RouterBlock("router1", evaluate_state, runner=None)

    wf = Workflow("router_workflow")
    wf.add_block(router_block)
    wf.add_transition("router1", None)
    wf.set_entry("router1")

    errors = wf.validate()
    assert errors == [], f"Workflow validation failed: {errors}"

    initial_state = WorkflowState(
        current_task=Task(id="decision", instruction="Make a decision"),
        shared_memory={"input_data": "approved by committee"},
    )
    final_state = await wf.run(initial_state)

    assert "router1" in final_state.results
    assert final_state.results["router1"].output == "approved"
    assert final_state.metadata["router1_decision"] == "approved"

    assert len(final_state.messages) == 1
    assert "[Block router1]" in final_state.messages[0]["content"]
    assert "RouterBlock decision: approved" in final_state.messages[0]["content"]


@pytest.mark.asyncio
async def test_router_soul_evaluator_workflow(mock_runner, sample_souls):
    """
    Integration test: Router workflow using Soul evaluator.
    Demonstrates RouterBlock can use LLM to evaluate state.
    """
    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="route", soul_id="router_judge", output="approved - looks good"
    )

    router_block = RouterBlock("router2", sample_souls["router_judge"], runner=mock_runner)

    wf = Workflow("router_soul_workflow")
    wf.add_block(router_block)
    wf.add_transition("router2", None)
    wf.set_entry("router2")

    initial_state = WorkflowState(current_task=Task(id="decision2", instruction="Evaluate this"))
    final_state = await wf.run(initial_state)

    assert "router2" in final_state.results
    assert "approved" in final_state.results["router2"].output
    assert "approved" in final_state.metadata["router2_decision"]

    assert mock_runner.execute_task.call_count == 1
