"""
Tests for block implementations.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from runsight_core.state import BlockResult, WorkflowState
from runsight_core.primitives import Soul, Task
from runsight_core.runner import ExecutionResult
from runsight_core.blocks.implementations import (
    LinearBlock,
    FanOutBlock,
    SynthesizeBlock,
)


@pytest.fixture
def mock_runner():
    """Mock RunsightTeamRunner with controlled outputs."""
    runner = MagicMock()
    runner.execute_task = AsyncMock()
    return runner


@pytest.fixture
def sample_soul():
    """Sample soul for testing."""
    return Soul(id="test_soul", role="Tester", system_prompt="You test things.")


@pytest.mark.asyncio
async def test_linear_block_execution(mock_runner, sample_soul):
    """AC-5: LinearBlock executes task and stores result."""
    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="t1", soul_id="test_soul", output="Test output"
    )

    block = LinearBlock("linear1", sample_soul, mock_runner)
    task = Task(id="t1", instruction="Test task")
    state = WorkflowState(current_task=task)

    result_state = await block.execute(state)

    assert result_state.results["linear1"].output == "Test output"
    assert len(result_state.execution_log) == 1
    assert "[Block linear1]" in result_state.execution_log[0]["content"]
    assert "Completed: Test output" in result_state.execution_log[0]["content"]
    mock_runner.execute_task.assert_called_once_with(task, sample_soul)


@pytest.mark.asyncio
async def test_linear_block_none_task(mock_runner, sample_soul):
    """LinearBlock raises ValueError if current_task is None."""
    block = LinearBlock("linear1", sample_soul, mock_runner)
    state = WorkflowState(current_task=None)

    with pytest.raises(ValueError, match="current_task is None"):
        await block.execute(state)


@pytest.mark.asyncio
async def test_linear_block_message_truncation(mock_runner, sample_soul):
    """LinearBlock truncates long outputs in message log."""
    # Create a very long output (300 chars)
    long_output = "A" * 300

    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="t1", soul_id="test_soul", output=long_output
    )

    block = LinearBlock("linear1", sample_soul, mock_runner)
    task = Task(id="t1", instruction="Test task")
    state = WorkflowState(current_task=task)

    result_state = await block.execute(state)

    # Full output stored in results
    assert result_state.results["linear1"].output == long_output
    assert len(result_state.results["linear1"].output) == 300

    # But message content is truncated to 200 chars + "..."
    message_content = result_state.execution_log[0]["content"]
    assert "..." in message_content
    # The truncated part should be 200 chars of "A" plus the "..." suffix
    assert "A" * 200 + "..." in message_content


@pytest.mark.asyncio
async def test_linear_block_preserves_existing_results(mock_runner, sample_soul):
    """LinearBlock preserves existing results when adding new ones."""
    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="t1", soul_id="test_soul", output="New output"
    )

    block = LinearBlock("linear1", sample_soul, mock_runner)
    task = Task(id="t1", instruction="Test task")
    state = WorkflowState(
        current_task=task, results={"previous_block": BlockResult(output="Previous output")}
    )

    result_state = await block.execute(state)

    # Both old and new results should be present
    assert result_state.results["previous_block"].output == "Previous output"
    assert result_state.results["linear1"].output == "New output"


@pytest.mark.asyncio
async def test_linear_block_preserves_existing_messages(mock_runner, sample_soul):
    """LinearBlock appends to existing messages."""
    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="t1", soul_id="test_soul", output="Output"
    )

    block = LinearBlock("linear1", sample_soul, mock_runner)
    task = Task(id="t1", instruction="Test task")
    existing_messages = [{"role": "system", "content": "Previous message"}]
    state = WorkflowState(current_task=task, execution_log=existing_messages)

    result_state = await block.execute(state)

    # Should have 2 messages: existing + new
    assert len(result_state.execution_log) == 2
    assert result_state.execution_log[0]["content"] == "Previous message"
    assert "[Block linear1]" in result_state.execution_log[1]["content"]


@pytest.mark.asyncio
async def test_fanout_block_parallel(mock_runner):
    """AC-6: FanOutBlock executes multiple souls in parallel."""
    souls = [
        Soul(id="s1", role="R1", system_prompt="P1"),
        Soul(id="s2", role="R2", system_prompt="P2"),
        Soul(id="s3", role="R3", system_prompt="P3"),
    ]

    mock_runner.execute_task.side_effect = [
        ExecutionResult(task_id="t1", soul_id="s1", output="Output from s1"),
        ExecutionResult(task_id="t1", soul_id="s2", output="Output from s2"),
        ExecutionResult(task_id="t1", soul_id="s3", output="Output from s3"),
    ]

    block = FanOutBlock("fanout1", souls, mock_runner)
    task = Task(id="t1", instruction="Review this")
    state = WorkflowState(current_task=task)

    result_state = await block.execute(state)

    # Verify JSON output format
    outputs = json.loads(result_state.results["fanout1"].output)
    assert len(outputs) == 3
    assert outputs[0] == {"soul_id": "s1", "output": "Output from s1"}
    assert outputs[1] == {"soul_id": "s2", "output": "Output from s2"}
    assert outputs[2] == {"soul_id": "s3", "output": "Output from s3"}

    # Verify all souls called
    assert mock_runner.execute_task.call_count == 3


@pytest.mark.asyncio
async def test_fanout_block_empty_souls(mock_runner):
    """FanOutBlock raises ValueError for empty souls list (tech lead issue #6)."""
    with pytest.raises(ValueError, match="souls list cannot be empty"):
        FanOutBlock("fanout1", [], mock_runner)


@pytest.mark.asyncio
async def test_synthesize_block_combination(mock_runner, sample_soul):
    """AC-7: SynthesizeBlock combines multiple inputs."""
    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="synth_task", soul_id="test_soul", output="Synthesized result combining both inputs"
    )

    block = SynthesizeBlock("synth1", ["block_a", "block_b"], sample_soul, mock_runner)
    state = WorkflowState(
        results={
            "block_a": BlockResult(output="Output A"),
            "block_b": BlockResult(output="Output B"),
        }
    )

    result_state = await block.execute(state)

    assert result_state.results["synth1"].output == "Synthesized result combining both inputs"

    # Verify synthesis task includes both inputs
    call_args = mock_runner.execute_task.call_args
    task_arg = call_args[0][0]  # First positional arg is Task
    assert "Output A" in task_arg.instruction
    assert "Output B" in task_arg.instruction


@pytest.mark.asyncio
async def test_synthesize_block_missing_input(mock_runner, sample_soul):
    """SynthesizeBlock raises ValueError for missing inputs."""
    block = SynthesizeBlock("synth1", ["block_a", "block_b"], sample_soul, mock_runner)
    state = WorkflowState(results={"block_a": BlockResult(output="Output A")})  # Missing block_b

    with pytest.raises(ValueError, match="missing inputs: \\['block_b'\\]"):
        await block.execute(state)


@pytest.mark.asyncio
async def test_synthesize_block_empty_inputs(mock_runner, sample_soul):
    """SynthesizeBlock raises ValueError for empty input_block_ids (tech lead issue #5)."""
    with pytest.raises(ValueError, match="input_block_ids cannot be empty"):
        SynthesizeBlock("synth1", [], sample_soul, mock_runner)


@pytest.mark.asyncio
async def test_linear_block_aggregates_cost_and_tokens(mock_runner, sample_soul):
    """LinearBlock aggregates cost_usd and total_tokens in returned state."""
    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="t1", soul_id="test_soul", output="Test output", cost_usd=0.25, total_tokens=500
    )

    block = LinearBlock("linear1", sample_soul, mock_runner)
    task = Task(id="t1", instruction="Test task")
    state = WorkflowState(current_task=task, total_cost_usd=0.1, total_tokens=100)

    result_state = await block.execute(state)

    # Verify cost and token aggregation
    assert result_state.total_cost_usd == 0.35  # 0.1 + 0.25
    assert result_state.total_tokens == 600  # 100 + 500
