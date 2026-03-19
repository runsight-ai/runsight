"""
Integration tests for cross-feature boundaries after branch merge.

Tests verify that features merged from different branches work correctly together:
1. MessageBusBlock ↔ RouterBlock: consensus passing and evaluator flexibility
2. Workflow-level integration with multiple blocks
3. Type safety: Verify import structure in primitives.py doesn't break integrations
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from runsight_core.state import WorkflowState
from runsight_core.primitives import Soul, Task
from runsight_core.blocks.base import BaseBlock
from runsight_core.blocks.implementations import (
    MessageBusBlock,
    RouterBlock,
)
from runsight_core.runner import ExecutionResult
from runsight_core.workflow import Workflow


# ===== Mock Blocks =====


class MockConsensusAnalyzerBlock(BaseBlock):
    """Mock block that analyzes MessageBus consensus - simulates downstream consumer."""

    def __init__(self, block_id: str, messagebus_id: str):
        super().__init__(block_id)
        self.messagebus_id = messagebus_id

    async def execute(self, state: WorkflowState) -> WorkflowState:
        # Read consensus from shared_memory (same key format as RouterBlock uses)
        consensus_key = f"{self.messagebus_id}_consensus"
        if consensus_key not in state.shared_memory:
            raise ValueError(f"Missing consensus key: {consensus_key}")

        consensus = state.shared_memory[consensus_key]
        analysis = f"Analyzed consensus: {len(consensus)} chars"

        return state.model_copy(
            update={
                "results": {**state.results, self.block_id: analysis},
                "messages": state.messages
                + [{"role": "system", "content": f"[Block {self.block_id}] {analysis}"}],
            }
        )


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
    # Setup MessageBusBlock to provide consensus
    mock_runner.execute_task.side_effect = [
        ExecutionResult(task_id="t1", soul_id="agent1", output="Strong agreement"),
        ExecutionResult(task_id="t2", soul_id="agent2", output="Consensus reached"),
        # Router Soul evaluation
        ExecutionResult(task_id="route", soul_id="router", output="approved"),
    ]

    messagebus = MessageBusBlock(
        "messagebus2",
        [test_souls["agent1"], test_souls["agent2"]],
        iterations=1,
        runner=mock_runner,
    )

    # Test 1: Callable evaluator (reads from shared_memory)
    def evaluate_consensus_callable(state: WorkflowState) -> str:
        consensus = state.shared_memory.get("messagebus2_consensus", "")
        return "approved" if "consensus" in consensus.lower() else "rejected"

    router_callable = RouterBlock("router_callable", evaluate_consensus_callable, runner=None)

    # Test 2: Soul evaluator (LLM decision)
    router_soul = RouterBlock("router_soul", test_souls["router"], runner=mock_runner)

    # Execute workflow
    state = WorkflowState(current_task=Task(id="task2", instruction="Make decision"))
    state = await messagebus.execute(state)

    # Verify callable evaluator works
    state_callable = await router_callable.execute(state)
    assert state_callable.results["router_callable"] == "approved"
    assert state_callable.metadata["router_callable_decision"] == "approved"

    # Verify Soul evaluator works
    state_soul = await router_soul.execute(state)
    assert state_soul.results["router_soul"] == "approved"
    assert state_soul.metadata["router_soul_decision"] == "approved"

    # Verify both types can coexist in same workflow
    assert "router_callable" in state_callable.results
    assert "router_soul" in state_soul.results


# ===== PRIORITY 2: Cross-Feature Interaction Tests =====


@pytest.mark.asyncio
async def test_messagebus_consensus_multiple_consumers(mock_runner, test_souls):
    """
    Test MessageBusBlock consensus can be consumed by multiple downstream blocks.

    Verifies:
    - Consensus stored in shared_memory is accessible to all downstream blocks
    - RouterBlock and custom blocks can both read consensus
    - No race conditions or data corruption
    """
    mock_runner.execute_task.side_effect = [
        ExecutionResult(task_id="t1", soul_id="agent1", output="Proposal alpha"),
        ExecutionResult(task_id="t2", soul_id="agent2", output="Proposal beta"),
    ]

    messagebus = MessageBusBlock(
        "messagebus3",
        [test_souls["agent1"], test_souls["agent2"]],
        iterations=1,
        runner=mock_runner,
    )

    # Consumer 1: RouterBlock with callable
    def route_decision(state: WorkflowState) -> str:
        consensus = state.shared_memory.get("messagebus3_consensus", "")
        return "proceed" if "beta" in consensus.lower() else "halt"

    router = RouterBlock("router3", route_decision, runner=None)

    # Consumer 2: Custom analyzer block
    analyzer = MockConsensusAnalyzerBlock("analyzer3", "messagebus3")

    # Execute workflow
    state = WorkflowState(current_task=Task(id="task4", instruction="Discuss proposal"))
    state = await messagebus.execute(state)

    # Both consumers should access same consensus
    consensus = state.shared_memory["messagebus3_consensus"]
    assert "Proposal beta" in consensus  # Last agent's output

    # Consumer 1: RouterBlock
    state_router = await router.execute(state)
    assert state_router.results["router3"] == "proceed"

    # Consumer 2: Analyzer
    state_analyzer = await analyzer.execute(state)
    assert "Analyzed consensus" in state_analyzer.results["analyzer3"]

    # Verify consensus unchanged by consumers
    assert state_router.shared_memory["messagebus3_consensus"] == consensus
    assert state_analyzer.shared_memory["messagebus3_consensus"] == consensus


# ===== PRIORITY 3: Complex Multi-Block Integration Tests =====


@pytest.mark.asyncio
async def test_workflow_integration_with_all_advanced_blocks(mock_runner, test_souls):
    """
    Workflow-level integration test with MessageBus and Router.

    Verifies:
    - Workflow correctly orchestrates MessageBus → Router transition
    - State flows correctly through Workflow.run()
    - All blocks execute in correct order
    """
    mock_runner.execute_task.side_effect = [
        ExecutionResult(task_id="t1", soul_id="agent1", output="Consensus item 1"),
        ExecutionResult(task_id="t2", soul_id="agent2", output="Consensus item 2"),
    ]

    # Build Workflow
    wf = Workflow("integration_test")

    messagebus = MessageBusBlock(
        "mb", [test_souls["agent1"], test_souls["agent2"]], iterations=1, runner=mock_runner
    )

    def route_logic(state: WorkflowState) -> str:
        consensus = state.shared_memory.get("mb_consensus", "")
        return "approved" if "item 2" in consensus else "rejected"

    router = RouterBlock("rt", route_logic, runner=None)

    wf.add_block(messagebus).add_block(router)
    wf.add_transition("mb", "rt").add_transition("rt", None)
    wf.set_entry("mb")

    # Validate and execute
    errors = wf.validate()
    assert errors == [], f"Workflow validation failed: {errors}"

    initial_state = WorkflowState(current_task=Task(id="task6", instruction="Run integration"))
    final_state = await wf.run(initial_state)

    # Verify execution order and results
    assert "mb" in final_state.results
    assert "rt" in final_state.results
    assert final_state.results["rt"] == "approved"

    # Verify transcript structure
    transcript = json.loads(final_state.results["mb"])
    assert len(transcript) == 1  # 1 iteration
    assert len(transcript[0]["contributions"]) == 2  # 2 agents

    # Verify consensus routing
    assert final_state.shared_memory["mb_consensus"] == "Consensus item 2"
    assert final_state.metadata["rt_decision"] == "approved"
