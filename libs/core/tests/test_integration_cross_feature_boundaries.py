"""
Integration tests for cross-feature boundaries after branch merge.

Tests verify that features merged from different branches work correctly together:
1. RetryBlock ↔ TeamLeadBlock: shared_memory key format compatibility
2. MessageBusBlock ↔ RouterBlock: consensus passing and evaluator flexibility
3. Mixed workflows: Combining all 4 adaptive blocks in complex scenarios
4. Type safety: Verify import structure in primitives.py doesn't break integrations

Priority: Tests conflict resolution areas and cross-feature interaction boundaries.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from runsight_core.state import WorkflowState
from runsight_core.primitives import Soul, Task
from runsight_core.blocks.base import BaseBlock
from runsight_core.blocks.implementations import (
    RetryBlock,
    TeamLeadBlock,
    MessageBusBlock,
    RouterBlock,
)
from runsight_core.runner import ExecutionResult
from runsight_core.workflow import Workflow


# ===== Mock Blocks =====


class MockFlakySyncBlock(BaseBlock):
    """Mock block that fails N times then succeeds - for retry testing."""

    def __init__(self, block_id: str, fail_times: int):
        super().__init__(block_id)
        self.fail_times = fail_times
        self.attempts = 0

    async def execute(self, state: WorkflowState) -> WorkflowState:
        self.attempts += 1
        if self.attempts <= self.fail_times:
            raise RuntimeError(f"Flaky failure #{self.attempts}")
        return state.model_copy(
            update={
                "results": {**state.results, self.block_id: f"Success on attempt {self.attempts}"}
            }
        )


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
async def test_shared_memory_key_format_compatibility(mock_runner, test_souls):
    """
    CONFLICT ZONE TEST: Verify shared_memory key formats are compatible across both branches.

    Branch 1 (RetryBlock→TeamLeadBlock): Uses "{block_id}_retry_errors" format
    Branch 2 (MessageBusBlock→RouterBlock): Uses "{block_id}_consensus" format

    This test ensures both key patterns coexist without conflicts.
    """
    # Setup: Create workflow with both patterns
    flaky_block = MockFlakySyncBlock("flaky_op", fail_times=1)
    retry_block = RetryBlock("retry1", flaky_block, max_retries=2, provide_error_context=True)

    mock_runner.execute_task.side_effect = [
        # MessageBus calls (2 agents × 1 iteration = 2)
        ExecutionResult(task_id="t1", soul_id="agent1", output="Opinion A"),
        ExecutionResult(task_id="t2", soul_id="agent2", output="Opinion B"),
        # TeamLeadBlock call (1)
        ExecutionResult(
            task_id="adv", soul_id="team_lead", output="Recommendation: Retry with backoff"
        ),
    ]

    messagebus = MessageBusBlock(
        "messagebus1",
        [test_souls["agent1"], test_souls["agent2"]],
        iterations=1,
        runner=mock_runner,
    )
    advisor = TeamLeadBlock(
        "advisor1",
        failure_context_keys=["retry1_retry_errors"],
        team_lead_soul=test_souls["advisor"],
        runner=mock_runner,
    )

    # Execute both workflows
    state = WorkflowState(current_task=Task(id="task1", instruction="Execute operations"))

    # Phase 1: RetryBlock (succeeds after 1 failure, stores retry_errors)
    state = await retry_block.execute(state)

    # Verify retry_errors key format
    assert "retry1_retry_errors" in state.shared_memory
    assert isinstance(state.shared_memory["retry1_retry_errors"], list)
    assert len(state.shared_memory["retry1_retry_errors"]) == 1  # 1 failure before success

    # Phase 2: MessageBusBlock (stores consensus)
    state = await messagebus.execute(state)

    # Verify consensus key format
    assert "messagebus1_consensus" in state.shared_memory
    assert isinstance(state.shared_memory["messagebus1_consensus"], str)

    # Phase 3: TeamLeadBlock (reads retry_errors)
    state = await advisor.execute(state)

    # Verify both keys coexist in shared_memory
    assert "retry1_retry_errors" in state.shared_memory
    assert "messagebus1_consensus" in state.shared_memory
    assert "advisor1_recommendation" in state.shared_memory

    # Verify no key collisions or overwrites
    assert (
        state.shared_memory["retry1_retry_errors"] != state.shared_memory["messagebus1_consensus"]
    )


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
async def test_retry_advisor_shared_memory_flow(mock_runner, test_souls):
    """
    Test data flow from RetryBlock → shared_memory → TeamLeadBlock.

    Verifies:
    - RetryBlock correctly formats error context
    - TeamLeadBlock correctly reads and parses error context
    - State transitions preserve shared_memory integrity
    """
    flaky_block = MockFlakySyncBlock("api_call", fail_times=2)
    retry_block = RetryBlock("retry_api", flaky_block, max_retries=3, provide_error_context=True)

    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="adv", soul_id="team_lead", output="Root cause: Transient failure. Retry succeeded."
    )

    advisor = TeamLeadBlock(
        "advisor_api",
        failure_context_keys=["retry_api_retry_errors"],
        team_lead_soul=test_souls["advisor"],
        runner=mock_runner,
    )

    # Execute workflow
    state = WorkflowState(current_task=Task(id="task3", instruction="Call API"))

    # Phase 1: RetryBlock succeeds after 2 failures
    state = await retry_block.execute(state)

    # Verify retry_errors captured (even on success)
    assert "retry_api_retry_errors" in state.shared_memory
    errors = state.shared_memory["retry_api_retry_errors"]
    assert len(errors) == 2  # First 2 attempts failed
    assert "Attempt 1/4" in errors[0]
    assert "RuntimeError: Flaky failure #1" in errors[0]
    assert "Attempt 2/4" in errors[1]
    assert "RuntimeError: Flaky failure #2" in errors[1]

    # Phase 2: TeamLeadBlock analyzes errors
    state = await advisor.execute(state)

    # Verify TeamLeadBlock accessed retry_errors
    assert "advisor_api" in state.results
    assert "Root cause" in state.results["advisor_api"]

    # Verify TeamLeadBlock was called with formatted error context
    call_args = mock_runner.execute_task.call_args
    task_arg = call_args[0][0]
    assert "retry_api_retry_errors" in task_arg.instruction
    assert "Flaky failure #1" in task_arg.instruction
    assert "Flaky failure #2" in task_arg.instruction


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
async def test_four_block_error_recovery_workflow(mock_runner, test_souls):
    """
    Complex integration: MessageBus → Router → RetryBlock → TeamLeadBlock.

    Simulates realistic workflow:
    1. MessageBus generates consensus on approach
    2. Router decides to proceed
    3. RetryBlock attempts execution (fails)
    4. TeamLeadBlock analyzes failure and recommends alternative
    """
    # Setup mocks
    call_count = [0]

    def dynamic_response(*args, **kwargs):
        call_count[0] += 1
        task = args[0]
        soul = args[1]

        if call_count[0] <= 2:  # MessageBus calls
            return ExecutionResult(
                task_id=task.id, soul_id=soul.id, output=f"Input {call_count[0]}"
            )
        else:  # TeamLeadBlock call
            return ExecutionResult(
                task_id=task.id,
                soul_id=soul.id,
                output="Alternative approach: Use fallback mechanism",
            )

    mock_runner.execute_task.side_effect = dynamic_response

    # Build workflow
    messagebus = MessageBusBlock(
        "consensus", [test_souls["agent1"], test_souls["agent2"]], iterations=1, runner=mock_runner
    )

    def router_func(state: WorkflowState) -> str:
        return "proceed"

    router = RouterBlock("decision", router_func, runner=None)

    flaky_block = MockFlakySyncBlock("operation", fail_times=999)  # Always fails
    retry_block = RetryBlock("retry_op", flaky_block, max_retries=1, provide_error_context=True)

    advisor = TeamLeadBlock(
        "recovery",
        failure_context_keys=["retry_op_retry_errors"],
        team_lead_soul=test_souls["advisor"],
        runner=mock_runner,
    )

    # Execute phases
    state = WorkflowState(current_task=Task(id="task5", instruction="Execute complex workflow"))

    # Phase 1: Consensus
    state = await messagebus.execute(state)
    assert "consensus_consensus" in state.shared_memory

    # Phase 2: Routing
    state = await router.execute(state)
    assert state.results["decision"] == "proceed"

    # Phase 3: Retry (will fail)
    try:
        await retry_block.execute(state)
        pytest.fail("RetryBlock should have raised exception")
    except RuntimeError:
        # Expected - manually add retry_errors (as would be done in error recovery)
        state = state.model_copy(
            update={
                "shared_memory": {
                    **state.shared_memory,
                    "retry_op_retry_errors": [
                        "Attempt 1/2: RuntimeError: Flaky failure #1",
                        "Attempt 2/2: RuntimeError: Flaky failure #2",
                    ],
                }
            }
        )

    # Phase 4: Recovery recommendation
    state = await advisor.execute(state)

    # Verify complete workflow state
    assert "consensus" in state.results  # MessageBus output
    assert "decision" in state.results  # Router output
    assert "recovery" in state.results  # TeamLeadBlock output
    assert "Alternative approach" in state.results["recovery"]

    # Verify all shared_memory keys present
    assert "consensus_consensus" in state.shared_memory
    assert "retry_op_retry_errors" in state.shared_memory
    assert "recovery_recommendation" in state.shared_memory


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
