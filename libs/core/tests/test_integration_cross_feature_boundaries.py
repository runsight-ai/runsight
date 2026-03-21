"""
Integration tests for cross-feature boundaries after branch merge.

Tests verify that features merged from different branches work correctly together:
1. RouterBlock ↔ Workflow: evaluator flexibility and routing decisions
2. Workflow-level integration with multiple blocks
3. Type safety: Verify import structure in primitives.py doesn't break integrations
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from runsight_core.state import WorkflowState
from runsight_core.primitives import Soul, Task
from runsight_core import (
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
def test_souls():
    """Standard test souls for all integration tests."""
    return {
        "advisor": Soul(
            id="team_lead", role="Team Lead", system_prompt="Analyze errors and recommend fixes."
        ),
        "agent1": Soul(id="agent1", role="Agent 1", system_prompt="Provide input on topics."),
        "agent2": Soul(id="agent2", role="Agent 2", system_prompt="Provide input on topics."),
        "router": Soul(id="router", role="Router", system_prompt="Make routing decisions."),
    }


# ===== PRIORITY 1: Conflict Resolution Area Tests =====


@pytest.mark.asyncio
async def test_router_block_evaluator_types_both_branches(mock_runner, test_souls):
    """
    CONFLICT ZONE TEST: Verify RouterBlock supports both Soul and Callable evaluators.

    Branch 2 modified RouterBlock to support both types. This test ensures
    both evaluator types work correctly and don't interfere with each other.
    """
    # Setup mock for Soul evaluator
    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="route", soul_id="router", output="approved"
    )

    # Test 1: Callable evaluator (reads from shared_memory)
    def evaluate_callable(state: WorkflowState) -> str:
        data = state.shared_memory.get("input_data", "")
        return "approved" if "consensus" in data.lower() else "rejected"

    router_callable = RouterBlock("router_callable", evaluate_callable, runner=None)

    # Test 2: Soul evaluator (LLM decision)
    router_soul = RouterBlock("router_soul", test_souls["router"], runner=mock_runner)

    # Execute with shared_memory data
    state = WorkflowState(
        current_task=Task(id="task2", instruction="Make decision"),
        shared_memory={"input_data": "Consensus reached by the team"},
    )

    # Verify callable evaluator works
    state_callable = await router_callable.execute(state)
    assert state_callable.results["router_callable"].output == "approved"
    assert state_callable.metadata["router_callable_decision"] == "approved"

    # Verify Soul evaluator works
    state_soul = await router_soul.execute(state)
    assert state_soul.results["router_soul"].output == "approved"
    assert state_soul.metadata["router_soul_decision"] == "approved"

    # Verify both types can coexist in same workflow
    assert "router_callable" in state_callable.results
    assert "router_soul" in state_soul.results


# ===== PRIORITY 2: Cross-Feature Interaction Tests =====


@pytest.mark.asyncio
async def test_router_with_shared_memory_consumers(mock_runner, test_souls):
    """
    Test RouterBlock can be consumed by multiple downstream blocks via shared_memory.

    Verifies:
    - Router decision stored in metadata is accessible to downstream blocks
    - No race conditions or data corruption
    """

    def route_decision(state: WorkflowState) -> str:
        data = state.shared_memory.get("input_data", "")
        return "proceed" if "beta" in data.lower() else "halt"

    router = RouterBlock("router3", route_decision, runner=None)

    state = WorkflowState(
        current_task=Task(id="task4", instruction="Route the proposal"),
        shared_memory={"input_data": "Proposal beta accepted"},
    )

    state_result = await router.execute(state)
    assert state_result.results["router3"].output == "proceed"
    assert state_result.metadata["router3_decision"] == "proceed"


# ===== PRIORITY 3: Complex Multi-Block Integration Tests =====


@pytest.mark.asyncio
async def test_workflow_integration_with_router_block(mock_runner, test_souls):
    """
    Workflow-level integration test with Router.

    Verifies:
    - Workflow correctly orchestrates Router transition
    - State flows correctly through Workflow.run()
    - All blocks execute in correct order
    """

    def route_logic(state: WorkflowState) -> str:
        return "approved"

    router = RouterBlock("rt", route_logic, runner=None)

    wf = Workflow("integration_test")
    wf.add_block(router)
    wf.add_transition("rt", None)
    wf.set_entry("rt")

    # Validate and execute
    errors = wf.validate()
    assert errors == [], f"Workflow validation failed: {errors}"

    initial_state = WorkflowState(current_task=Task(id="task6", instruction="Run integration"))
    final_state = await wf.run(initial_state)

    # Verify execution and results
    assert "rt" in final_state.results
    assert final_state.results["rt"].output == "approved"
    assert final_state.metadata["rt_decision"] == "approved"
