"""
Tests for block implementations.
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from runsight_core import (
    DispatchBlock,
    LinearBlock,
    SynthesizeBlock,
)
from runsight_core.primitives import Soul
from runsight_core.runner import ExecutionResult
from runsight_core.state import BlockResult, WorkflowState


@pytest.fixture
def mock_runner():
    """Mock RunsightTeamRunner with controlled outputs."""
    runner = MagicMock()
    runner.execute = AsyncMock()
    runner.execute = AsyncMock()
    return runner


@pytest.fixture
def sample_soul():
    """Sample soul for testing."""
    return Soul(id="test_soul", role="Tester", system_prompt="You test things.")


@pytest.mark.asyncio
async def test_linear_block_execution(mock_runner, sample_soul):
    """AC-5: LinearBlock executes task and stores result."""
    mock_runner.execute.return_value = ExecutionResult(
        task_id="t1", soul_id="test_soul", output="Test output"
    )

    block = LinearBlock("linear1", sample_soul, mock_runner)
    state = WorkflowState(shared_memory={"_resolved_inputs": {"upstream": "Test task"}})

    result_state = await block.execute(state)

    assert result_state.results["linear1"].output == "Test output"
    assert len(result_state.execution_log) == 1
    assert "[Block linear1]" in result_state.execution_log[0]["content"]
    assert "Completed: Test output" in result_state.execution_log[0]["content"]
    assert mock_runner.execute.called


@pytest.mark.asyncio
async def test_linear_block_none_task(mock_runner, sample_soul):
    """LinearBlock works even when current_task is None (reads _resolved_inputs instead)."""
    mock_runner.execute.return_value = ExecutionResult(
        task_id="t1", soul_id="test_soul", output="output"
    )
    block = LinearBlock("linear1", sample_soul, mock_runner)
    state = WorkflowState(current_task=None)

    result_state = await block.execute(state)
    assert "linear1" in result_state.results


@pytest.mark.asyncio
async def test_linear_block_message_truncation(mock_runner, sample_soul):
    """LinearBlock truncates long outputs in message log."""
    # Create a very long output (300 chars)
    long_output = "A" * 300

    mock_runner.execute.return_value = ExecutionResult(
        task_id="t1", soul_id="test_soul", output=long_output
    )

    block = LinearBlock("linear1", sample_soul, mock_runner)
    state = WorkflowState(shared_memory={"_resolved_inputs": {"upstream": "Test task"}})

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
    mock_runner.execute.return_value = ExecutionResult(
        task_id="t1", soul_id="test_soul", output="New output"
    )

    block = LinearBlock("linear1", sample_soul, mock_runner)
    state = WorkflowState(
        shared_memory={"_resolved_inputs": {"upstream": "Test task"}},
        results={"previous_block": BlockResult(output="Previous output")},
    )

    result_state = await block.execute(state)

    # Both old and new results should be present
    assert result_state.results["previous_block"].output == "Previous output"
    assert result_state.results["linear1"].output == "New output"


@pytest.mark.asyncio
async def test_linear_block_preserves_existing_messages(mock_runner, sample_soul):
    """LinearBlock appends to existing messages."""
    mock_runner.execute.return_value = ExecutionResult(
        task_id="t1", soul_id="test_soul", output="Output"
    )

    block = LinearBlock("linear1", sample_soul, mock_runner)
    existing_messages = [{"role": "system", "content": "Previous message"}]
    state = WorkflowState(
        shared_memory={"_resolved_inputs": {"upstream": "Test task"}},
        execution_log=existing_messages,
    )

    result_state = await block.execute(state)

    # Should have 2 messages: existing + new
    assert len(result_state.execution_log) == 2
    assert result_state.execution_log[0]["content"] == "Previous message"
    assert "[Block linear1]" in result_state.execution_log[1]["content"]


@pytest.mark.asyncio
async def test_dispatch_block_parallel(mock_runner):
    """AC-6: DispatchBlock executes multiple branches in parallel."""
    from runsight_core.blocks.dispatch import DispatchBranch

    souls = [
        Soul(id="s1", role="R1", system_prompt="P1"),
        Soul(id="s2", role="R2", system_prompt="P2"),
        Soul(id="s3", role="R3", system_prompt="P3"),
    ]
    branches = [
        DispatchBranch(exit_id=f"exit_{s.id}", label=s.role, soul=s, task_instruction="Review this")
        for s in souls
    ]

    mock_runner.execute.side_effect = [
        ExecutionResult(task_id="t1", soul_id="s1", output="Output from s1"),
        ExecutionResult(task_id="t1", soul_id="s2", output="Output from s2"),
        ExecutionResult(task_id="t1", soul_id="s3", output="Output from s3"),
    ]

    block = DispatchBlock("dispatch1", branches, mock_runner)
    state = WorkflowState()

    result_state = await block.execute(state)

    # Verify JSON output format (now uses exit_id instead of soul_id)
    outputs = json.loads(result_state.results["dispatch1"].output)
    assert len(outputs) == 3
    assert outputs[0] == {"exit_id": "exit_s1", "output": "Output from s1"}
    assert outputs[1] == {"exit_id": "exit_s2", "output": "Output from s2"}
    assert outputs[2] == {"exit_id": "exit_s3", "output": "Output from s3"}

    # Verify all branches called
    assert mock_runner.execute.call_count == 3


@pytest.mark.asyncio
async def test_dispatch_block_empty_branches(mock_runner):
    """DispatchBlock raises ValueError for empty branches list."""
    with pytest.raises(ValueError, match="branches"):
        DispatchBlock("dispatch1", [], mock_runner)


@pytest.mark.asyncio
async def test_synthesize_block_combination(mock_runner, sample_soul):
    """AC-7: SynthesizeBlock combines multiple inputs."""
    mock_runner.model_name = "gpt-4o"
    mock_runner.execute.return_value = ExecutionResult(
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

    # Verify synthesis includes both inputs in context arg to runner.execute
    call_args = mock_runner.execute.call_args
    context_arg = call_args[0][1]  # Second positional arg is context
    assert "Output A" in context_arg
    assert "Output B" in context_arg


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
    mock_runner.execute.return_value = ExecutionResult(
        task_id="t1", soul_id="test_soul", output="Test output", cost_usd=0.25, total_tokens=500
    )

    block = LinearBlock("linear1", sample_soul, mock_runner)
    state = WorkflowState(
        shared_memory={"_resolved_inputs": {"upstream": "Test task"}},
        total_cost_usd=0.1,
        total_tokens=100,
    )

    result_state = await block.execute(state)

    # Verify cost and token aggregation
    assert result_state.total_cost_usd == 0.35  # 0.1 + 0.25
    assert result_state.total_tokens == 600  # 100 + 500
