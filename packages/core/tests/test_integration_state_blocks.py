"""
Integration tests for WorkflowState and Block implementations.

Tests the interaction between WorkflowState, BaseBlock, and concrete block
implementations, focusing on state immutability and proper data flow.

Updated for RUN-879: Task removed. LinearBlock reads _resolved_inputs from
shared_memory; runner.execute(instruction, context, soul) is the canonical API.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from runsight_core import LinearBlock
from runsight_core.blocks.base import BaseBlock
from runsight_core.primitives import Soul
from runsight_core.runner import ExecutionResult
from runsight_core.state import BlockResult, WorkflowState


@pytest.fixture
def mock_runner():
    """Mock RunsightTeamRunner for integration tests."""
    runner = MagicMock()
    runner.execute = AsyncMock()
    return runner


@pytest.fixture
def test_soul():
    """Test soul for integration tests."""
    return Soul(
        id="integration_soul",
        kind="soul",
        name="Integration Soul",
        role="Integration Tester",
        system_prompt="Test integration.",
    )


@pytest.mark.asyncio
async def test_state_immutability_across_block_execution(mock_runner, test_soul):
    """
    INTEGRATION: Verify WorkflowState immutability when passed through LinearBlock.execute().

    This tests the critical contract that blocks must create new state instances
    via model_copy() rather than mutating the input state.
    """
    mock_runner.execute.return_value = ExecutionResult(
        task_id="t1", soul_id="integration_soul", output="Integration output"
    )

    block = LinearBlock("block1", test_soul, mock_runner)

    # Original state with pre-existing data
    original_state = WorkflowState(
        results={"previous": BlockResult(output="data")},
        execution_log=[{"role": "system", "content": "Original message"}],
        shared_memory={"key": "value"},
        metadata={"execution_id": "test123"},
    )

    # Execute block
    new_state = await block.execute(original_state)

    # CRITICAL: Original state must be unchanged (immutability)
    assert original_state.results == {"previous": BlockResult(output="data")}
    assert len(original_state.execution_log) == 1
    assert original_state.shared_memory == {"key": "value"}
    assert original_state.metadata == {"execution_id": "test123"}

    # New state should have updates
    assert new_state.results == {
        "previous": BlockResult(output="data"),
        "block1": BlockResult(output="Integration output"),
    }
    assert len(new_state.execution_log) == 2

    # Verify they are different instances
    assert original_state is not new_state
    assert id(original_state) != id(new_state)


@pytest.mark.asyncio
async def test_workflow_state_task_primitive_integration(mock_runner, test_soul):
    """
    INTEGRATION: Verify runner.execute() is called with (instruction, context, soul).

    After RUN-879, Task is deleted. LinearBlock reads _resolved_inputs from shared_memory.
    runner.execute(instruction, context, soul) receives string args.
    """
    mock_runner.execute.return_value = ExecutionResult(
        task_id="integration_task", soul_id="integration_soul", output="Result"
    )

    block = LinearBlock("block1", test_soul, mock_runner)
    state = WorkflowState(
        shared_memory={
            "_resolved_inputs": {"instruction": "Test instruction", "context": "Test context"}
        }
    )

    await block.execute(state)

    # Verify runner.execute was called with (instruction, context, soul)
    call_args = mock_runner.execute.call_args
    actual_instruction = call_args[0][0]  # First positional argument
    actual_soul = call_args[0][2]  # Third positional argument

    assert isinstance(actual_instruction, str)
    assert actual_soul == test_soul


@pytest.mark.asyncio
async def test_execution_result_to_state_results_mapping(mock_runner, test_soul):
    """
    INTEGRATION: Verify ExecutionResult.output correctly maps to WorkflowState.results.

    Tests the data transformation: Runner.ExecutionResult -> State.results[block_id]
    """
    execution_output = "This is the execution output from the runner"

    mock_runner.execute.return_value = ExecutionResult(
        task_id="t1",
        soul_id="integration_soul",
        output=execution_output,
        metadata={"duration": 1.5},
    )

    block = LinearBlock("test_block", test_soul, mock_runner)
    state = WorkflowState()

    result_state = await block.execute(state)

    # Verify exact output mapping
    assert result_state.results["test_block"].output == execution_output
    assert result_state.results["test_block"].output == mock_runner.execute.return_value.output


@pytest.mark.asyncio
async def test_soul_primitive_integration_with_block(mock_runner):
    """
    INTEGRATION: Verify Soul primitive correctly integrates with LinearBlock.

    Tests that Soul attributes (id, role, system_prompt) are properly preserved
    when passed through LinearBlock to the runner.
    """
    soul = Soul(
        id="detailed_soul",
        kind="soul",
        name="Detailed Soul",
        role="Senior Engineer",
        system_prompt="You are a senior engineer with expertise in testing.",
        tools=["test_tool"],
    )

    mock_runner.execute.return_value = ExecutionResult(
        task_id="t1", soul_id="detailed_soul", output="Output"
    )

    block = LinearBlock("block1", soul, mock_runner)
    state = WorkflowState()

    await block.execute(state)

    # Verify the exact soul was passed to runner
    call_args = mock_runner.execute.call_args
    actual_soul = call_args[0][2]

    assert actual_soul == soul
    assert actual_soul.id == "detailed_soul"
    assert actual_soul.role == "Senior Engineer"
    assert actual_soul.system_prompt == "You are a senior engineer with expertise in testing."
    assert actual_soul.tools == ["test_tool"]


@pytest.mark.asyncio
async def test_baseblock_contract_enforcement(mock_runner, test_soul):
    """
    INTEGRATION: Verify BaseBlock abstract contract is enforced by concrete implementations.

    Tests that LinearBlock properly inherits from BaseBlock and maintains the contract:
    - block_id initialization
    - execute() returns WorkflowState
    - output stored in state.results[block_id]
    """
    mock_runner.execute.return_value = ExecutionResult(
        task_id="t1", soul_id="integration_soul", output="Output"
    )

    block = LinearBlock("contract_block", test_soul, mock_runner)

    # Verify BaseBlock contract: block_id is set
    assert isinstance(block, BaseBlock)
    assert hasattr(block, "block_id")
    assert block.block_id == "contract_block"

    # Verify BaseBlock contract: execute() exists and is async
    assert hasattr(block, "execute")
    assert callable(block.execute)

    # Verify BaseBlock contract: execute returns WorkflowState with results[block_id]
    state = WorkflowState()
    result = await block.execute(state)

    assert isinstance(result, WorkflowState)
    assert "contract_block" in result.results


@pytest.mark.asyncio
async def test_multi_block_state_accumulation(mock_runner, test_soul):
    """
    INTEGRATION: Verify state correctly accumulates results across multiple block executions.

    Simulates a workflow where multiple blocks execute sequentially, each adding to state.
    """
    # Block 1 execution
    mock_runner.execute.return_value = ExecutionResult(
        task_id="t1", soul_id="integration_soul", output="Block 1 output"
    )

    block1 = LinearBlock("block1", test_soul, mock_runner)
    state = WorkflowState()

    state = await block1.execute(state)

    # Block 2 execution
    mock_runner.execute.return_value = ExecutionResult(
        task_id="t2", soul_id="integration_soul", output="Block 2 output"
    )

    block2 = LinearBlock("block2", test_soul, mock_runner)
    state = await block2.execute(state)

    # Block 3 execution
    mock_runner.execute.return_value = ExecutionResult(
        task_id="t3", soul_id="integration_soul", output="Block 3 output"
    )

    block3 = LinearBlock("block3", test_soul, mock_runner)
    state = await block3.execute(state)

    # Verify all block outputs accumulated
    assert state.results == {
        "block1": BlockResult(output="Block 1 output"),
        "block2": BlockResult(output="Block 2 output"),
        "block3": BlockResult(output="Block 3 output"),
    }

    # Verify all messages accumulated
    assert len(state.execution_log) == 3
    assert "[Block block1]" in state.execution_log[0]["content"]
    assert "[Block block2]" in state.execution_log[1]["content"]
    assert "[Block block3]" in state.execution_log[2]["content"]


@pytest.mark.asyncio
async def test_state_messages_integration_with_truncation(mock_runner, test_soul):
    """
    INTEGRATION: Verify message truncation logic works correctly with state.execution_log.

    Tests that LinearBlock's truncation (200 char limit for messages) works properly
    while full output is preserved in state.results.
    """
    # Create output that exceeds 200 characters
    long_output = "X" * 250

    mock_runner.execute.return_value = ExecutionResult(
        task_id="t1", soul_id="integration_soul", output=long_output
    )

    block = LinearBlock("block1", test_soul, mock_runner)
    state = WorkflowState()

    result_state = await block.execute(state)

    # Full output in results
    assert result_state.results["block1"].output == long_output
    assert len(result_state.results["block1"].output) == 250

    # Truncated in messages
    message_content = result_state.execution_log[0]["content"]
    assert "..." in message_content
    assert "X" * 200 in message_content
    assert len(result_state.results["block1"].output) > 200  # results has full version
