"""Integration coverage for block and Workflow interactions.

This suite verifies that LinearBlock, DispatchBlock, and SynthesizeBlock can be
instantiated together, share WorkflowState through Workflow execution, and
preserve state immutability/error propagation across multi-block flows.
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from conftest import execute_block_for_test
from runsight_core import (
    DispatchBlock,
    LinearBlock,
    SynthesizeBlock,
)
from runsight_core.blocks.dispatch import DispatchBranch
from runsight_core.primitives import Soul
from runsight_core.runner import ExecutionResult
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.workflow import Workflow


def _souls_to_branches(souls):
    """Convert a list of Soul objects to DispatchBranch objects for backwards compat."""
    return [
        DispatchBranch(exit_id=s.id, label=s.role, soul=s, task_instruction="Execute task")
        for s in souls
    ]


@pytest.fixture
def mock_runner():
    """Mock RunsightTeamRunner with controlled outputs."""
    runner = MagicMock()
    runner.model_name = None
    runner.execute = AsyncMock()
    return runner


@pytest.fixture
def workflow_souls():
    """Create workflow integration souls."""
    return {
        "researcher": Soul(
            id="researcher",
            kind="soul",
            name="Researcher",
            role="Researcher",
            system_prompt="Research topics",
        ),
        "coder": Soul(
            id="coder", kind="soul", name="Coder", role="Coder", system_prompt="Write code"
        ),
        "reviewer1": Soul(
            id="reviewer1",
            kind="soul",
            name="Reviewer 1",
            role="Reviewer 1",
            system_prompt="Review code",
        ),
        "reviewer2": Soul(
            id="reviewer2",
            kind="soul",
            name="Reviewer 2",
            role="Reviewer 2",
            system_prompt="Review code",
        ),
        "reviewer3": Soul(
            id="reviewer3",
            kind="soul",
            name="Reviewer 3",
            role="Reviewer 3",
            system_prompt="Review code",
        ),
        "synthesizer": Soul(
            id="synthesizer",
            kind="soul",
            name="Synthesizer",
            role="Synthesizer",
            system_prompt="Combine feedback",
        ),
    }


# ============================================================================
# Block construction and state-sharing coverage
# ============================================================================


@pytest.mark.asyncio
async def test_all_three_blocks_import_and_instantiate(mock_runner, workflow_souls):
    """Linear, Dispatch, and Synthesize blocks instantiate together."""
    # Verify all blocks can be instantiated without errors
    linear = LinearBlock("import_linear_block", workflow_souls["researcher"], mock_runner)
    assert linear.block_id == "import_linear_block"

    dispatch = DispatchBlock(
        "import_dispatch_block",
        _souls_to_branches([workflow_souls["reviewer1"], workflow_souls["reviewer2"]]),
        mock_runner,
    )
    assert dispatch.block_id == "import_dispatch_block"

    synthesize = SynthesizeBlock(
        "import_synthesis_block",
        ["synthesis_source_a", "synthesis_source_b"],
        workflow_souls["synthesizer"],
        mock_runner,
    )
    assert synthesize.block_id == "import_synthesis_block"


@pytest.mark.asyncio
async def test_blocks_share_state_correctly(mock_runner, workflow_souls):
    """Linear and Dispatch blocks share WorkflowState during sequential execution."""
    # Setup mock responses
    mock_runner.execute.side_effect = [
        ExecutionResult(task_id="research-task", soul_id="researcher", output="Research complete"),
        ExecutionResult(task_id="review-task", soul_id="reviewer1", output="Review A"),
        ExecutionResult(task_id="review-task", soul_id="reviewer2", output="Review B"),
    ]

    # Create initial state
    state = WorkflowState()

    # Execute LinearBlock
    linear = LinearBlock("research", workflow_souls["researcher"], mock_runner)
    state = await execute_block_for_test(linear, state)
    assert "research" in state.results
    assert state.results["research"].output == "Research complete"

    # Update task and execute DispatchBlock

    dispatch = DispatchBlock(
        "reviews",
        _souls_to_branches([workflow_souls["reviewer1"], workflow_souls["reviewer2"]]),
        mock_runner,
    )
    state = await execute_block_for_test(dispatch, state)

    # Verify state accumulation
    assert "research" in state.results  # Previous result preserved
    assert "reviews" in state.results  # New result added
    reviews_data = json.loads(state.results["reviews"].output)
    assert len(reviews_data) == 2


# ============================================================================
# Workflow orchestration across block types
# ============================================================================


@pytest.mark.asyncio
async def test_workflow_linear_to_dispatch_workflow(mock_runner, workflow_souls):
    """Workflow orchestrates Linear -> Dispatch with state propagation."""
    # Setup mock responses
    mock_runner.execute.side_effect = [
        ExecutionResult(
            task_id="research-pipeline-task", soul_id="researcher", output="Research findings"
        ),
        ExecutionResult(
            task_id="review-pipeline-task", soul_id="reviewer1", output="Critique from R1"
        ),
        ExecutionResult(
            task_id="review-pipeline-task", soul_id="reviewer2", output="Critique from R2"
        ),
        ExecutionResult(
            task_id="review-pipeline-task", soul_id="reviewer3", output="Critique from R3"
        ),
    ]

    # Build workflow
    wf = Workflow("research_review_pipeline")

    linear = LinearBlock("research", workflow_souls["researcher"], mock_runner)
    dispatch = DispatchBlock(
        "reviews",
        _souls_to_branches(
            [workflow_souls["reviewer1"], workflow_souls["reviewer2"], workflow_souls["reviewer3"]]
        ),
        mock_runner,
    )

    wf.add_block(linear).add_block(dispatch)
    wf.add_transition("research", "reviews").add_transition("reviews", None)
    wf.set_entry("research")

    # Validate workflow
    errors = wf.validate()
    assert errors == [], f"Workflow validation failed: {errors}"

    # Execute
    initial_state = WorkflowState()
    final_state = await wf.run(initial_state)

    # Verify both blocks executed
    assert "research" in final_state.results
    assert "reviews" in final_state.results

    # Verify Dispatch produced JSON with 3 reviews
    reviews = json.loads(final_state.results["reviews"].output)
    assert len(reviews) == 3
    assert reviews[0]["exit_id"] == "reviewer1"
    assert reviews[1]["exit_id"] == "reviewer2"
    assert reviews[2]["exit_id"] == "reviewer3"


@pytest.mark.asyncio
async def test_workflow_dispatch_to_synthesize_workflow(mock_runner, workflow_souls):
    """Workflow orchestrates Dispatch -> Synthesize using Dispatch JSON output."""
    # Setup mock responses
    mock_runner.execute.side_effect = [
        # Dispatch responses
        ExecutionResult(task_id="research-task", soul_id="reviewer1", output="Positive review"),
        ExecutionResult(task_id="research-task", soul_id="reviewer2", output="Critical review"),
        # Synthesize response
        ExecutionResult(
            task_id="synthesis-summary-task",
            soul_id="synthesizer",
            output="Combined: Mixed feedback overall",
        ),
    ]

    # Build workflow
    wf = Workflow("review_synthesis_pipeline")

    dispatch = DispatchBlock(
        "dispatch",
        _souls_to_branches([workflow_souls["reviewer1"], workflow_souls["reviewer2"]]),
        mock_runner,
    )
    synthesize = SynthesizeBlock(
        "synthesis", ["dispatch"], workflow_souls["synthesizer"], mock_runner
    )

    wf.add_block(dispatch).add_block(synthesize)
    wf.add_transition("dispatch", "synthesis").add_transition("synthesis", None)
    wf.set_entry("dispatch")

    # Execute
    initial_state = WorkflowState()
    final_state = await wf.run(initial_state)

    # Verify SynthesizeBlock received Dispatch output
    assert "dispatch" in final_state.results
    assert "synthesis" in final_state.results
    assert "Combined" in final_state.results["synthesis"].output

    # Verify synthesizer was called (dispatch results available as context)
    assert (
        mock_runner.execute.call_count >= 3
    )  # at least 3 calls: 2 dispatch branches + 1 synthesize


# ============================================================================
# Multi-block workflow scenarios
# ============================================================================


@pytest.mark.asyncio
async def test_complete_research_review_synthesis_workflow(mock_runner, workflow_souls):
    """Research -> parallel reviews -> synthesis runs as one multi-block workflow."""
    # Setup realistic mock responses
    mock_runner.execute.side_effect = [
        ExecutionResult(
            task_id="research-report-task",
            soul_id="researcher",
            output="Research: AI safety is critical. Key risks: alignment, capabilities.",
        ),
        ExecutionResult(
            task_id="review-feedback-task",
            soul_id="reviewer1",
            output="R1: Strong research, needs more on scalability",
        ),
        ExecutionResult(
            task_id="review-feedback-task",
            soul_id="reviewer2",
            output="R2: Good coverage, missing practical examples",
        ),
        ExecutionResult(
            task_id="review-feedback-task",
            soul_id="reviewer3",
            output="R3: Excellent analysis, suggest adding timelines",
        ),
        ExecutionResult(
            task_id="synthesis-report-task",
            soul_id="synthesizer",
            output="Synthesis: Research is strong. Add scalability, examples, timelines.",
        ),
    ]

    # Build workflow
    wf = Workflow("research_workflow")

    research_block = LinearBlock("research", workflow_souls["researcher"], mock_runner)
    review_block = DispatchBlock(
        "peer_reviews",
        _souls_to_branches(
            [workflow_souls["reviewer1"], workflow_souls["reviewer2"], workflow_souls["reviewer3"]]
        ),
        mock_runner,
    )
    synthesis_block = SynthesizeBlock(
        "final_report", ["research", "peer_reviews"], workflow_souls["synthesizer"], mock_runner
    )

    wf.add_block(research_block).add_block(review_block).add_block(synthesis_block)
    wf.add_transition("research", "peer_reviews")
    wf.add_transition("peer_reviews", "final_report")
    wf.add_transition("final_report", None)
    wf.set_entry("research")

    # Execute
    initial_state = WorkflowState(
        metadata={"workflow_type": "research_pipeline"},
    )
    final_state = await wf.run(initial_state)

    # Verify complete workflow execution (3 combined + 3 per-exit from Dispatch)
    assert "research" in final_state.results
    assert "peer_reviews" in final_state.results
    assert "final_report" in final_state.results

    # Verify metadata preserved
    assert final_state.metadata["workflow_type"] == "research_pipeline"

    # Verify messages accumulated (3 blocks = 3 messages)
    assert len(final_state.execution_log) == 3
    assert "[Block research]" in final_state.execution_log[0]["content"]
    assert "[Block peer_reviews]" in final_state.execution_log[1]["content"]
    assert "[Block final_report]" in final_state.execution_log[2]["content"]


@pytest.mark.asyncio
async def test_state_immutability_across_workflow_execution(mock_runner, workflow_souls):
    """Workflow execution preserves state immutability across blocks."""
    mock_runner.execute.side_effect = [
        ExecutionResult(task_id="research-task", soul_id="researcher", output="Output 1"),
        ExecutionResult(task_id="review-task", soul_id="reviewer1", output="Output 2"),
    ]

    # Build simple workflow
    wf = Workflow("immutability_workflow")
    immutable_research_block = LinearBlock(
        "immutable_research_step", workflow_souls["researcher"], mock_runner
    )
    immutable_review_block = LinearBlock(
        "immutable_review_step", workflow_souls["reviewer1"], mock_runner
    )
    wf.add_block(immutable_research_block).add_block(immutable_review_block)
    wf.add_transition("immutable_research_step", "immutable_review_step").add_transition(
        "immutable_review_step", None
    )
    wf.set_entry("immutable_research_step")

    # Execute and capture states
    initial_state = WorkflowState(
        results={"initial": BlockResult(output="value")},
    )

    # Store initial state ID
    initial_state_id = id(initial_state)
    initial_results_id = id(initial_state.results)

    final_state = await wf.run(initial_state)

    # Verify new state objects created (not mutated)
    assert id(final_state) != initial_state_id
    assert id(final_state.results) != initial_results_id

    # Verify original state unchanged
    assert initial_state.results == {"initial": BlockResult(output="value")}
    assert len(initial_state.execution_log) == 0

    # Verify final state has accumulated data
    assert "initial" in final_state.results
    assert "immutable_research_step" in final_state.results
    assert "immutable_review_step" in final_state.results
    assert len(final_state.execution_log) == 2


@pytest.mark.asyncio
async def test_error_propagation_through_workflow(mock_runner, workflow_souls):
    """Workflow execution stops and propagates block errors to the caller."""
    # First block succeeds, second raises exception
    mock_runner.execute.side_effect = [
        ExecutionResult(task_id="error-start-task", soul_id="researcher", output="Success"),
        Exception("Simulated execution failure"),
    ]

    wf = Workflow("error_propagation_workflow")
    error_start_block = LinearBlock("error_start_step", workflow_souls["researcher"], mock_runner)
    error_failure_block = LinearBlock(
        "error_failure_step", workflow_souls["reviewer1"], mock_runner
    )
    wf.add_block(error_start_block).add_block(error_failure_block)
    wf.add_transition("error_start_step", "error_failure_step").add_transition(
        "error_failure_step", None
    )
    wf.set_entry("error_start_step")

    initial_state = WorkflowState()

    # Verify exception propagates
    with pytest.raises(Exception, match="Simulated execution failure"):
        await wf.run(initial_state)
