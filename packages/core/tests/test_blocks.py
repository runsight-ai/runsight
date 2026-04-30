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
from runsight_core.block_io import apply_block_output, build_block_context
from runsight_core.primitives import Soul
from runsight_core.runner import ExecutionResult
from runsight_core.state import BlockResult, WorkflowState


@pytest.fixture
def mock_runner():
    """Mock RunsightTeamRunner with controlled outputs."""
    runner = MagicMock()
    runner.execute = AsyncMock()
    runner.model_name = "gpt-4o-mini"
    return runner


@pytest.fixture
def sample_soul():
    """Sample soul for testing."""
    return Soul(
        id="analysis_soul",
        kind="soul",
        name="Analyst",
        role="Analyst",
        system_prompt="Analyze the task.",
    )


@pytest.mark.asyncio
async def test_linear_block_execution(mock_runner, sample_soul):
    """LinearBlock executes a task and stores the result."""
    mock_runner.execute.return_value = ExecutionResult(
        task_id="analysis_task", soul_id="analysis_soul", output="Analysis output"
    )

    block = LinearBlock("analysis_block", sample_soul, mock_runner)
    state = WorkflowState(shared_memory={"_resolved_inputs": {"upstream": "Review task"}})

    ctx = build_block_context(block, state)
    output = await block.execute(ctx)
    result_state = apply_block_output(state, block.block_id, output)

    assert result_state.results["analysis_block"].output == "Analysis output"
    assert len(result_state.execution_log) == 1
    assert "[Block analysis_block]" in result_state.execution_log[0]["content"]
    assert "Completed: Analysis output" in result_state.execution_log[0]["content"]
    assert mock_runner.execute.called


@pytest.mark.asyncio
async def test_linear_block_none_task(mock_runner, sample_soul):
    """LinearBlock works even when current_task is None (reads _resolved_inputs instead)."""
    mock_runner.execute.return_value = ExecutionResult(
        task_id="empty_input_analysis_task", soul_id="analysis_soul", output="output"
    )
    block = LinearBlock("analysis_block", sample_soul, mock_runner)
    state = WorkflowState()

    ctx = build_block_context(block, state)
    output = await block.execute(ctx)
    result_state = apply_block_output(state, block.block_id, output)
    assert "analysis_block" in result_state.results


@pytest.mark.asyncio
async def test_linear_block_message_truncation(mock_runner, sample_soul):
    """LinearBlock truncates long outputs in message log."""
    # Create a very long output (300 chars)
    long_output = "A" * 300

    mock_runner.execute.return_value = ExecutionResult(
        task_id="long_output_analysis_task", soul_id="analysis_soul", output=long_output
    )

    block = LinearBlock("analysis_block", sample_soul, mock_runner)
    state = WorkflowState(shared_memory={"_resolved_inputs": {"upstream": "Review task"}})

    ctx = build_block_context(block, state)
    output = await block.execute(ctx)
    result_state = apply_block_output(state, block.block_id, output)

    # Full output stored in results
    assert result_state.results["analysis_block"].output == long_output
    assert len(result_state.results["analysis_block"].output) == 300

    # But message content is truncated to 200 chars + "..."
    message_content = result_state.execution_log[0]["content"]
    assert "..." in message_content
    # The truncated part should be 200 chars of "A" plus the "..." suffix
    assert "A" * 200 + "..." in message_content


@pytest.mark.asyncio
async def test_linear_block_preserves_existing_results(mock_runner, sample_soul):
    """LinearBlock preserves existing results when adding new ones."""
    mock_runner.execute.return_value = ExecutionResult(
        task_id="result_merge_analysis_task", soul_id="analysis_soul", output="New output"
    )

    block = LinearBlock("analysis_block", sample_soul, mock_runner)
    state = WorkflowState(
        shared_memory={"_resolved_inputs": {"upstream": "Review task"}},
        results={"previous_block": BlockResult(output="Previous output")},
    )

    ctx = build_block_context(block, state)
    output = await block.execute(ctx)
    result_state = apply_block_output(state, block.block_id, output)

    # Both old and new results should be present
    assert result_state.results["previous_block"].output == "Previous output"
    assert result_state.results["analysis_block"].output == "New output"


@pytest.mark.asyncio
async def test_linear_block_preserves_existing_messages(mock_runner, sample_soul):
    """LinearBlock appends to existing messages."""
    mock_runner.execute.return_value = ExecutionResult(
        task_id="log_append_analysis_task", soul_id="analysis_soul", output="Output"
    )

    block = LinearBlock("analysis_block", sample_soul, mock_runner)
    existing_messages = [{"role": "system", "content": "Previous message"}]
    state = WorkflowState(
        shared_memory={"_resolved_inputs": {"upstream": "Review task"}},
        execution_log=existing_messages,
    )

    ctx = build_block_context(block, state)
    output = await block.execute(ctx)
    result_state = apply_block_output(state, block.block_id, output)

    # Should have 2 messages: existing + new
    assert len(result_state.execution_log) == 2
    assert result_state.execution_log[0]["content"] == "Previous message"
    assert "[Block analysis_block]" in result_state.execution_log[1]["content"]


@pytest.mark.asyncio
async def test_dispatch_block_parallel(mock_runner):
    """DispatchBlock executes multiple branches in parallel."""
    from runsight_core.blocks.dispatch import DispatchBranch

    souls = [
        Soul(
            id="strategy_reviewer",
            kind="soul",
            name="Strategy Reviewer",
            role="Strategy",
            system_prompt="Review strategy risks.",
        ),
        Soul(
            id="quality_reviewer",
            kind="soul",
            name="Quality Reviewer",
            role="Quality",
            system_prompt="Review quality risks.",
        ),
        Soul(
            id="delivery_reviewer",
            kind="soul",
            name="Delivery Reviewer",
            role="Delivery",
            system_prompt="Review delivery risks.",
        ),
    ]
    exit_ids = ["strategy_exit", "quality_exit", "delivery_exit"]
    branches = [
        DispatchBranch(exit_id=exit_ids[i], label=s.role, soul=s, task_instruction="Review this")
        for i, s in enumerate(souls)
    ]

    mock_runner.execute.side_effect = [
        ExecutionResult(
            task_id="strategy_review", soul_id="strategy_reviewer", output="Strategy output"
        ),
        ExecutionResult(
            task_id="quality_review", soul_id="quality_reviewer", output="Quality output"
        ),
        ExecutionResult(
            task_id="delivery_review", soul_id="delivery_reviewer", output="Delivery output"
        ),
    ]

    block = DispatchBlock("parallel_review_dispatch", branches, mock_runner)
    state = WorkflowState()

    ctx = build_block_context(block, state)
    block_output = await block.execute(ctx)
    result_state = apply_block_output(state, block.block_id, block_output)

    # Verify JSON output format (now uses exit_id instead of soul_id)
    outputs = json.loads(result_state.results["parallel_review_dispatch"].output)
    assert len(outputs) == 3
    assert outputs[0] == {"exit_id": "strategy_exit", "output": "Strategy output"}
    assert outputs[1] == {"exit_id": "quality_exit", "output": "Quality output"}
    assert outputs[2] == {"exit_id": "delivery_exit", "output": "Delivery output"}

    # Verify all branches called
    assert mock_runner.execute.call_count == 3


@pytest.mark.asyncio
async def test_dispatch_block_empty_branches(mock_runner):
    """DispatchBlock raises ValueError for empty branches list."""
    with pytest.raises(ValueError, match="branches"):
        DispatchBlock("empty_review_dispatch", [], mock_runner)


@pytest.mark.asyncio
async def test_synthesize_block_combination(mock_runner, sample_soul):
    """SynthesizeBlock combines multiple inputs."""
    mock_runner.model_name = "gpt-4o"
    mock_runner.execute.return_value = ExecutionResult(
        task_id="risk_summary_task",
        soul_id="analysis_soul",
        output="Synthesized result combining both inputs",
    )

    block = SynthesizeBlock(
        "risk_summary_synthesizer",
        ["strategy_notes", "quality_notes"],
        sample_soul,
        mock_runner,
    )
    state = WorkflowState(
        results={
            "strategy_notes": BlockResult(output="Strategy notes"),
            "quality_notes": BlockResult(output="Quality notes"),
        }
    )

    ctx = build_block_context(block, state)
    output = await block.execute(ctx)
    result_state = apply_block_output(state, block.block_id, output)

    assert (
        result_state.results["risk_summary_synthesizer"].output
        == "Synthesized result combining both inputs"
    )

    # Verify synthesis includes both inputs in context arg to runner.execute
    call_args = mock_runner.execute.call_args
    context_arg = call_args[0][1]  # Second positional arg is context
    assert "Strategy notes" in context_arg
    assert "Quality notes" in context_arg


@pytest.mark.asyncio
async def test_synthesize_block_missing_input(mock_runner, sample_soul):
    """SynthesizeBlock raises ValueError for missing inputs."""
    block = SynthesizeBlock(
        "risk_summary_synthesizer",
        ["strategy_notes", "quality_notes"],
        sample_soul,
        mock_runner,
    )
    state = WorkflowState(results={"strategy_notes": BlockResult(output="Strategy notes")})

    with pytest.raises(ValueError, match="source result missing"):
        build_block_context(block, state)


@pytest.mark.asyncio
async def test_synthesize_block_empty_inputs(mock_runner, sample_soul):
    """SynthesizeBlock raises ValueError for empty input_block_ids."""
    with pytest.raises(ValueError, match="input_block_ids cannot be empty"):
        SynthesizeBlock("risk_summary_synthesizer", [], sample_soul, mock_runner)


@pytest.mark.asyncio
async def test_linear_block_aggregates_cost_and_tokens(mock_runner, sample_soul):
    """LinearBlock aggregates cost_usd and total_tokens in returned state."""
    mock_runner.execute.return_value = ExecutionResult(
        task_id="cost_tracking_analysis_task",
        soul_id="analysis_soul",
        output="Analysis output",
        cost_usd=0.25,
        total_tokens=500,
    )

    block = LinearBlock("analysis_block", sample_soul, mock_runner)
    state = WorkflowState(
        shared_memory={"_resolved_inputs": {"upstream": "Review task"}},
        total_cost_usd=0.1,
        total_tokens=100,
    )

    ctx = build_block_context(block, state)
    output = await block.execute(ctx)
    result_state = apply_block_output(state, block.block_id, output)

    # Verify cost and token aggregation
    assert result_state.total_cost_usd == 0.35  # 0.1 + 0.25
    assert result_state.total_tokens == 600  # 100 + 500
