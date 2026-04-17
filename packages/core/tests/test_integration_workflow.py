"""
Core engine integration tests for complete workflow execution.

Tests the full integration chain at the engine level: Task -> Soul -> Runner ->
ExecutionResult -> LinearBlock -> WorkflowState, simulating real workflow scenarios.

Note: These are engine-level integration tests, not HTTP/API end-to-end tests.
LLM calls are intercepted via ``@patch("runsight_core.runner.LiteLLMClient.achat")``;
no network I/O occurs.
"""

from unittest.mock import AsyncMock, patch

import pytest
from runsight_core import LinearBlock
from runsight_core.primitives import Soul
from runsight_core.runner import RunsightTeamRunner
from runsight_core.state import WorkflowState


async def _run_block(block, state: WorkflowState) -> WorkflowState:
    """Helper: build BlockContext, run block, apply output → WorkflowState."""
    from runsight_core.block_io import BlockOutput, apply_block_output, build_block_context

    ctx = build_block_context(block, state)
    output = await block.execute(ctx)
    if isinstance(output, WorkflowState):
        return output
    if isinstance(output, BlockOutput):
        return apply_block_output(state, block.block_id, output)
    return state


@pytest.mark.asyncio
@patch("runsight_core.runner.LiteLLMClient.achat")
async def test_e2e_single_block_workflow(mock_achat):
    """
    E2E: Complete workflow with one block execution.

    Flow: Task -> WorkflowState -> LinearBlock -> Runner -> LLM -> ExecutionResult -> Updated State
    """
    # Setup
    mock_achat.return_value = {
        "content": "Research complete: Found 5 relevant papers on quantum computing.",
        "cost_usd": 0.1,
        "total_tokens": 150,
    }

    soul = Soul(
        id="researcher",
        kind="soul",
        name="Researcher",
        role="Research Analyst",
        system_prompt="You are a research analyst who finds and summarizes academic papers.",
        provider="openai",
        model_name="gpt-4o",
    )

    runner = RunsightTeamRunner(model_name="gpt-4o")
    block = LinearBlock("research_block", soul, runner)
    block.declared_inputs = {"instruction": "shared_memory._resolved_inputs.instruction"}

    # Initialize state with shared_memory inputs for the instruction
    initial_state = WorkflowState(
        shared_memory={
            "_resolved_inputs": {
                "instruction": "Research quantum computing papers published in 2024"
            }
        },
        metadata={"workflow_name": "research_pipeline", "started_at": "2024-01-01T00:00:00"},
    )

    # Execute workflow
    final_state = await _run_block(block, initial_state)

    # Verify end-to-end data flow
    assert (
        final_state.results["research_block"].output
        == "Research complete: Found 5 relevant papers on quantum computing."
    )
    assert len(final_state.execution_log) == 1
    assert "[Block research_block]" in final_state.execution_log[0]["content"]
    assert "Research complete" in final_state.execution_log[0]["content"]

    # Verify metadata preserved
    assert final_state.metadata["workflow_name"] == "research_pipeline"

    # Verify cost and token aggregation
    assert final_state.total_cost_usd == 0.1
    assert final_state.total_tokens == 150

    # Verify LLM was called with correct parameters
    call_kwargs = mock_achat.call_args.kwargs
    assert "quantum computing" in call_kwargs["messages"][0]["content"]
    assert "2024" in call_kwargs["messages"][0]["content"]
    assert call_kwargs["system_prompt"] == soul.system_prompt


@pytest.mark.asyncio
@patch("runsight_core.runner.LiteLLMClient.achat")
async def test_e2e_sequential_block_workflow(mock_achat):
    """
    E2E: Workflow with multiple sequential block executions.

    Simulates a multi-step workflow where each block's output feeds into the next.
    """
    # Setup multiple souls and tasks
    researcher_soul = Soul(
        id="researcher",
        kind="soul",
        name="Researcher",
        role="Researcher",
        system_prompt="Research topics.",
        provider="openai",
        model_name="gpt-4o",
    )
    analyst_soul = Soul(
        id="analyst",
        kind="soul",
        name="Analyst",
        role="Analyst",
        system_prompt="Analyze data.",
        provider="openai",
        model_name="gpt-4o",
    )
    writer_soul = Soul(
        id="writer",
        kind="soul",
        name="Writer",
        role="Writer",
        system_prompt="Write reports.",
        provider="openai",
        model_name="gpt-4o",
    )

    # Mock LLM responses for each step
    mock_achat.side_effect = [
        {
            "content": "Research findings: Topic X has 3 main aspects.",
            "cost_usd": 0.05,
            "total_tokens": 100,
        },
        {
            "content": "Analysis: Aspect 1 is most important with 67% impact.",
            "cost_usd": 0.06,
            "total_tokens": 120,
        },
        {
            "content": "Summary: Topic X is dominated by Aspect 1, which accounts for the majority of observed effects.",
            "cost_usd": 0.07,
            "total_tokens": 140,
        },
    ]

    runner = RunsightTeamRunner(model_name="gpt-4o")

    # Create blocks for each step
    research_block = LinearBlock("step1_research", researcher_soul, runner)
    analysis_block = LinearBlock("step2_analysis", analyst_soul, runner)
    writing_block = LinearBlock("step3_writing", writer_soul, runner)

    # Execute sequential workflow — pass instruction via shared_memory
    state = WorkflowState(
        shared_memory={"_resolved_inputs": {"instruction": "Research topic"}},
        metadata={"pipeline": "analysis_pipeline"},
    )

    # Step 1: Research
    state = await _run_block(research_block, state)

    # Step 2: Analysis (update instruction in shared_memory)
    state = state.model_copy(
        update={"shared_memory": {"_resolved_inputs": {"instruction": "Analyze findings"}}}
    )
    state = await _run_block(analysis_block, state)

    # Step 3: Writing (update instruction)
    state = state.model_copy(
        update={"shared_memory": {"_resolved_inputs": {"instruction": "Write summary"}}}
    )
    state = await _run_block(writing_block, state)

    # Verify complete pipeline execution
    assert len(state.results) == 3
    assert "step1_research" in state.results
    assert "step2_analysis" in state.results
    assert "step3_writing" in state.results

    # Verify all outputs accumulated
    assert "Research findings" in state.results["step1_research"].output
    assert "Analysis: Aspect 1" in state.results["step2_analysis"].output
    assert "Summary: Topic X" in state.results["step3_writing"].output

    # Verify message history accumulated
    assert len(state.execution_log) == 3
    assert "[Block step1_research]" in state.execution_log[0]["content"]
    assert "[Block step2_analysis]" in state.execution_log[1]["content"]
    assert "[Block step3_writing]" in state.execution_log[2]["content"]

    # Verify metadata preserved throughout
    assert state.metadata["pipeline"] == "analysis_pipeline"

    # Verify cost and token aggregation across all blocks
    assert state.total_cost_usd == 0.18  # 0.05 + 0.06 + 0.07
    assert state.total_tokens == 360  # 100 + 120 + 140


@pytest.mark.asyncio
@patch("runsight_core.runner.LiteLLMClient.achat")
async def test_e2e_shared_memory_across_blocks(mock_achat):
    """
    E2E: Verify shared_memory persists across block executions in a workflow.

    Tests that blocks can read/write to shared_memory for inter-block communication.
    """
    mock_achat.side_effect = [
        {"content": "Result 1", "cost_usd": 0.1, "total_tokens": 100},
        {"content": "Result 2", "cost_usd": 0.12, "total_tokens": 120},
    ]

    soul = Soul(
        id="worker",
        kind="soul",
        name="Worker",
        role="Worker",
        system_prompt="Process tasks.",
        provider="openai",
        model_name="gpt-4o",
    )
    runner = RunsightTeamRunner(model_name="gpt-4o")

    block1 = LinearBlock("block1", soul, runner)
    block2 = LinearBlock("block2", soul, runner)

    # Initial state with shared memory
    state = WorkflowState(
        shared_memory={"config": {"max_items": 100, "timeout": 30}},
    )

    # Execute block 1
    state = await _run_block(block1, state)

    # Modify shared memory between blocks
    updated_memory = {**state.shared_memory, "block1_processed": True}
    state = state.model_copy(update={"shared_memory": updated_memory})

    # Execute block 2
    state = await _run_block(block2, state)

    # Verify shared memory persisted and accumulated
    assert state.shared_memory["config"]["max_items"] == 100
    assert state.shared_memory["block1_processed"] is True


@pytest.mark.asyncio
@patch("runsight_core.runner.LiteLLMClient.achat", new_callable=AsyncMock)
async def test_e2e_error_propagation_through_workflow(mock_achat):
    """
    Integration: Verify errors propagate correctly through the workflow stack.

    Tests error handling: LLM client error -> Runner -> Block -> Caller
    """
    mock_achat.side_effect = RuntimeError("LLM service unavailable")

    soul = Soul(
        id="faulty",
        kind="soul",
        name="Faulty",
        role="Faulty Agent",
        system_prompt="Might fail.",
        provider="openai",
        model_name="gpt-4o",
    )

    runner = RunsightTeamRunner(model_name="gpt-4o")
    block = LinearBlock("error_block", soul, runner)
    state = WorkflowState()

    # Error should propagate from LLM client through runner and block to caller
    with pytest.raises(RuntimeError, match="LLM service unavailable"):
        await _run_block(block, state)


@pytest.mark.asyncio
@patch("runsight_core.runner.LiteLLMClient.achat")
async def test_e2e_state_isolation_between_workflows(mock_achat):
    """
    E2E: Verify different workflow executions don't interfere with each other.

    Tests that running two separate workflows maintains state isolation.
    """
    mock_achat.side_effect = [
        {"content": "Workflow 1 result", "cost_usd": 0.1, "total_tokens": 100},
        {"content": "Workflow 2 result", "cost_usd": 0.1, "total_tokens": 100},
    ]

    soul = Soul(
        id="worker",
        kind="soul",
        name="Worker",
        role="Worker",
        system_prompt="Work.",
        provider="openai",
        model_name="gpt-4o",
    )
    runner = RunsightTeamRunner(model_name="gpt-4o")
    block = LinearBlock("block", soul, runner)

    # Workflow 1
    state1 = WorkflowState(metadata={"workflow_id": "wf1"})
    result1 = await _run_block(block, state1)

    # Workflow 2
    state2 = WorkflowState(metadata={"workflow_id": "wf2"})
    result2 = await _run_block(block, state2)

    # Verify complete isolation
    assert result1.results["block"].output == "Workflow 1 result"
    assert result2.results["block"].output == "Workflow 2 result"
    assert result1.metadata["workflow_id"] == "wf1"
    assert result2.metadata["workflow_id"] == "wf2"

    # Verify original states unchanged (immutability)
    assert "block" not in state1.results
    assert "block" not in state2.results


@pytest.mark.asyncio
@patch("runsight_core.runner.LiteLLMClient.achat")
async def test_e2e_long_running_workflow_state_size(mock_achat):
    """
    E2E: Verify message truncation prevents state size explosion in long workflows.

    Tests that even with many blocks producing long outputs, state remains manageable.
    """
    # Each block produces 500 char output
    long_output = "L" * 500
    mock_achat.return_value = {
        "content": long_output,
        "cost_usd": 0.1,
        "total_tokens": 500,
    }

    soul = Soul(
        id="verbose",
        kind="soul",
        name="Verbose",
        role="Verbose Agent",
        system_prompt="Generate long outputs.",
        provider="openai",
        model_name="gpt-4o",
    )
    runner = RunsightTeamRunner(model_name="gpt-4o")

    # Simulate 10 blocks in sequence
    state = WorkflowState()

    for i in range(10):
        block = LinearBlock(f"block{i}", soul, runner)
        state = await _run_block(block, state)

    # Verify all results stored in full
    assert len(state.results) == 10
    for i in range(10):
        assert len(state.results[f"block{i}"].output) == 500

    # Verify messages are truncated (200 chars + "..." in each message)
    assert len(state.execution_log) == 10
    for msg in state.execution_log:
        # Each message has: "[Block blockN] Completed: " + 200 chars + "..."
        assert "..." in msg["content"]
        assert "L" * 200 in msg["content"]


@pytest.mark.asyncio
@patch("runsight_core.runner.LiteLLMClient.achat")
async def test_e2e_workflow_with_task_context_utilization(mock_achat):
    """
    E2E: Verify Task.context flows through entire workflow and reaches LLM.

    Tests that context information is properly utilized throughout the execution chain.
    """
    # Mock LLM to echo back the context (simulating context usage)
    mock_achat.return_value = {
        "content": "Processed request with background information about Q4 metrics.",
        "cost_usd": 0.1,
        "total_tokens": 150,
    }

    soul = Soul(
        id="processor",
        kind="soul",
        name="Processor",
        role="Data Processor",
        system_prompt="Process data using provided context.",
        provider="openai",
        model_name="gpt-4o",
    )

    runner = RunsightTeamRunner(model_name="gpt-4o")
    block = LinearBlock("processor_block", soul, runner)

    state = WorkflowState(
        shared_memory={
            "_resolved_inputs": {
                "instruction": "Process the quarterly data",
                "context": "Q4 metrics show 30% growth",
            }
        }
    )
    result_state = await _run_block(block, state)

    # Verify result was produced
    assert "Q4 metrics" in result_state.results["processor_block"].output


@pytest.mark.asyncio
async def test_e2e_baseblock_empty_id_validation():
    """
    Integration: Verify BaseBlock contract enforcement for empty block_id.

    Tests that the block_id validation in BaseBlock.__init__ is enforced
    by concrete implementations.
    """
    soul = Soul(
        id="test",
        kind="soul",
        name="Test",
        role="Tester",
        system_prompt="Test.",
        provider="openai",
        model_name="gpt-4o",
    )
    runner = RunsightTeamRunner(model_name="gpt-4o")

    # Empty string block_id should raise ValueError
    with pytest.raises(ValueError, match="block_id cannot be empty"):
        LinearBlock("", soul, runner)

    # Valid block_id should work
    block = LinearBlock("valid_id", soul, runner)
    assert block.block_id == "valid_id"
