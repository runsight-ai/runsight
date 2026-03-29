"""
Integration tests for blocks + workflow interactions.

PRIORITY 1: Tests conflict resolution area (implementations.py merge)
PRIORITY 2: Tests cross-feature interactions (Workflow orchestrating blocks)
PRIORITY 3: Tests multi-block workflow scenarios
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from runsight_core import (
    FanOutBlock,
    LinearBlock,
    SynthesizeBlock,
)
from runsight_core.blocks.fanout import FanOutBranch
from runsight_core.primitives import Soul, Task
from runsight_core.runner import ExecutionResult
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.workflow import Workflow


def _souls_to_branches(souls):
    """Convert a list of Soul objects to FanOutBranch objects for backwards compat."""
    return [
        FanOutBranch(exit_id=s.id, label=s.role, soul=s, task_instruction="Execute task")
        for s in souls
    ]


@pytest.fixture
def mock_runner():
    """Mock RunsightTeamRunner with controlled outputs."""
    runner = MagicMock()
    runner.model_name = "gpt-4o"
    runner.execute_task = AsyncMock()
    return runner


@pytest.fixture
def sample_souls():
    """Create sample souls for testing."""
    return {
        "researcher": Soul(id="researcher", role="Researcher", system_prompt="Research topics"),
        "coder": Soul(id="coder", role="Coder", system_prompt="Write code"),
        "reviewer1": Soul(id="reviewer1", role="Reviewer 1", system_prompt="Review code"),
        "reviewer2": Soul(id="reviewer2", role="Reviewer 2", system_prompt="Review code"),
        "reviewer3": Soul(id="reviewer3", role="Reviewer 3", system_prompt="Review code"),
        "synthesizer": Soul(id="synthesizer", role="Synthesizer", system_prompt="Combine feedback"),
    }


# ============================================================================
# PRIORITY 1: CONFLICT RESOLUTION AREA TESTS
# Test that all 4 blocks work together in implementations.py after merge
# ============================================================================


@pytest.mark.asyncio
async def test_all_three_blocks_import_and_instantiate(mock_runner, sample_souls):
    """
    CONFLICT RESOLUTION TEST: Verify all 3 blocks can be imported and instantiated.

    This tests the merge conflict resolution where HEAD had all blocks and the
    correct import statements (Dict, List from typing and Task from primitives).
    """
    # Verify all blocks can be instantiated without errors
    linear = LinearBlock("linear1", sample_souls["researcher"], mock_runner)
    assert linear.block_id == "linear1"

    fanout = FanOutBlock(
        "fanout1",
        _souls_to_branches([sample_souls["reviewer1"], sample_souls["reviewer2"]]),
        mock_runner,
    )
    assert fanout.block_id == "fanout1"

    synthesize = SynthesizeBlock(
        "synth1", ["block_a", "block_b"], sample_souls["synthesizer"], mock_runner
    )
    assert synthesize.block_id == "synth1"


@pytest.mark.asyncio
async def test_blocks_share_state_correctly(mock_runner, sample_souls):
    """
    CONFLICT RESOLUTION TEST: Verify blocks properly share WorkflowState.

    Tests that the Task import and Dict typing work correctly across all blocks.
    """
    # Setup mock responses
    mock_runner.execute_task.side_effect = [
        ExecutionResult(task_id="t1", soul_id="researcher", output="Research complete"),
        ExecutionResult(task_id="t2", soul_id="reviewer1", output="Review A"),
        ExecutionResult(task_id="t2", soul_id="reviewer2", output="Review B"),
    ]

    # Create initial state
    task = Task(id="t1", instruction="Research AI safety")
    state = WorkflowState(current_task=task)

    # Execute LinearBlock
    linear = LinearBlock("research", sample_souls["researcher"], mock_runner)
    state = await linear.execute(state)
    assert "research" in state.results
    assert state.results["research"].output == "Research complete"

    # Update task and execute FanOutBlock
    state = state.model_copy(update={"current_task": Task(id="t2", instruction="Review research")})
    fanout = FanOutBlock(
        "reviews",
        _souls_to_branches([sample_souls["reviewer1"], sample_souls["reviewer2"]]),
        mock_runner,
    )
    state = await fanout.execute(state)

    # Verify state accumulation
    assert "research" in state.results  # Previous result preserved
    assert "reviews" in state.results  # New result added
    reviews_data = json.loads(state.results["reviews"].output)
    assert len(reviews_data) == 2


# ============================================================================
# PRIORITY 2: CROSS-FEATURE INTERACTION TESTS
# Test Workflow orchestrating different block types
# ============================================================================


@pytest.mark.asyncio
async def test_workflow_linear_to_fanout_workflow(mock_runner, sample_souls):
    """
    CROSS-FEATURE TEST: Workflow orchestrates Linear → FanOut.

    Tests interaction between Workflow state machine and block execution,
    verifying state propagation across block types.
    """
    # Setup mock responses
    mock_runner.execute_task.side_effect = [
        ExecutionResult(task_id="task1", soul_id="researcher", output="Research findings"),
        ExecutionResult(task_id="task2", soul_id="reviewer1", output="Critique from R1"),
        ExecutionResult(task_id="task2", soul_id="reviewer2", output="Critique from R2"),
        ExecutionResult(task_id="task2", soul_id="reviewer3", output="Critique from R3"),
    ]

    # Build workflow
    wf = Workflow("research_review_pipeline")

    linear = LinearBlock("research", sample_souls["researcher"], mock_runner)
    fanout = FanOutBlock(
        "reviews",
        _souls_to_branches(
            [sample_souls["reviewer1"], sample_souls["reviewer2"], sample_souls["reviewer3"]]
        ),
        mock_runner,
    )

    wf.add_block(linear).add_block(fanout)
    wf.add_transition("research", "reviews").add_transition("reviews", None)
    wf.set_entry("research")

    # Validate workflow
    errors = wf.validate()
    assert errors == [], f"Workflow validation failed: {errors}"

    # Execute
    initial_state = WorkflowState(current_task=Task(id="task1", instruction="Research AI"))
    final_state = await wf.run(initial_state)

    # Verify both blocks executed
    assert "research" in final_state.results
    assert "reviews" in final_state.results

    # Verify FanOut produced JSON with 3 reviews
    reviews = json.loads(final_state.results["reviews"].output)
    assert len(reviews) == 3
    assert reviews[0]["exit_id"] == "reviewer1"
    assert reviews[1]["exit_id"] == "reviewer2"
    assert reviews[2]["exit_id"] == "reviewer3"


@pytest.mark.asyncio
async def test_workflow_fanout_to_synthesize_workflow(mock_runner, sample_souls):
    """
    CROSS-FEATURE TEST: Workflow orchestrates FanOut → Synthesize.

    Tests that SynthesizeBlock can read FanOut's JSON output from state.results
    and combine multiple inputs correctly.
    """
    # Setup mock responses
    mock_runner.execute_task.side_effect = [
        # FanOut responses
        ExecutionResult(task_id="t1", soul_id="reviewer1", output="Positive review"),
        ExecutionResult(task_id="t1", soul_id="reviewer2", output="Critical review"),
        # Synthesize response
        ExecutionResult(
            task_id="synth_task", soul_id="synthesizer", output="Combined: Mixed feedback overall"
        ),
    ]

    # Build workflow
    wf = Workflow("review_synthesis_pipeline")

    fanout = FanOutBlock(
        "fanout",
        _souls_to_branches([sample_souls["reviewer1"], sample_souls["reviewer2"]]),
        mock_runner,
    )
    synthesize = SynthesizeBlock("synthesis", ["fanout"], sample_souls["synthesizer"], mock_runner)

    wf.add_block(fanout).add_block(synthesize)
    wf.add_transition("fanout", "synthesis").add_transition("synthesis", None)
    wf.set_entry("fanout")

    # Execute
    initial_state = WorkflowState(current_task=Task(id="t1", instruction="Review proposal"))
    final_state = await wf.run(initial_state)

    # Verify SynthesizeBlock received FanOut output
    assert "fanout" in final_state.results
    assert "synthesis" in final_state.results
    assert "Combined" in final_state.results["synthesis"].output

    # Verify synthesizer task included fanout JSON output (variable data is in context)
    synth_call = mock_runner.execute_task.call_args_list[2]  # 3rd call
    task_arg = synth_call[0][0]
    assert "fanout" in task_arg.context
    assert "Positive review" in task_arg.context or "Critical review" in task_arg.context


# ============================================================================
# PRIORITY 3: MULTI-BLOCK WORKFLOW SCENARIOS
# End-to-end workflow tests
# ============================================================================


@pytest.mark.asyncio
async def test_complete_research_review_synthesis_workflow(mock_runner, sample_souls):
    """
    END-TO-END TEST: Research → FanOut Reviews → Synthesize.

    Simulates a real workflow: research a topic, get parallel reviews, synthesize.
    """
    # Setup realistic mock responses
    mock_runner.execute_task.side_effect = [
        ExecutionResult(
            task_id="research_task",
            soul_id="researcher",
            output="Research: AI safety is critical. Key risks: alignment, capabilities.",
        ),
        ExecutionResult(
            task_id="review_task",
            soul_id="reviewer1",
            output="R1: Strong research, needs more on scalability",
        ),
        ExecutionResult(
            task_id="review_task",
            soul_id="reviewer2",
            output="R2: Good coverage, missing practical examples",
        ),
        ExecutionResult(
            task_id="review_task",
            soul_id="reviewer3",
            output="R3: Excellent analysis, suggest adding timelines",
        ),
        ExecutionResult(
            task_id="synth_task",
            soul_id="synthesizer",
            output="Synthesis: Research is strong. Add scalability, examples, timelines.",
        ),
    ]

    # Build workflow
    wf = Workflow("research_workflow")

    research_block = LinearBlock("research", sample_souls["researcher"], mock_runner)
    review_block = FanOutBlock(
        "peer_reviews",
        _souls_to_branches(
            [sample_souls["reviewer1"], sample_souls["reviewer2"], sample_souls["reviewer3"]]
        ),
        mock_runner,
    )
    synthesis_block = SynthesizeBlock(
        "final_report", ["research", "peer_reviews"], sample_souls["synthesizer"], mock_runner
    )

    wf.add_block(research_block).add_block(review_block).add_block(synthesis_block)
    wf.add_transition("research", "peer_reviews")
    wf.add_transition("peer_reviews", "final_report")
    wf.add_transition("final_report", None)
    wf.set_entry("research")

    # Execute
    initial_state = WorkflowState(
        current_task=Task(
            id="main_task", instruction="Research AI safety and compile comprehensive report"
        ),
        metadata={"workflow_type": "research_pipeline"},
    )
    final_state = await wf.run(initial_state)

    # Verify complete workflow execution (3 combined + 3 per-exit from FanOut)
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
async def test_state_immutability_across_workflow_execution(mock_runner, sample_souls):
    """
    STATE IMMUTABILITY TEST: Verify blocks don't mutate state in-place.

    Tests that each block returns a new state via model_copy, preserving
    immutability contract across the workflow.
    """
    mock_runner.execute_task.side_effect = [
        ExecutionResult(task_id="t1", soul_id="researcher", output="Output 1"),
        ExecutionResult(task_id="t2", soul_id="reviewer1", output="Output 2"),
    ]

    # Build simple workflow
    wf = Workflow("immutability_test")
    block1 = LinearBlock("b1", sample_souls["researcher"], mock_runner)
    block2 = LinearBlock("b2", sample_souls["reviewer1"], mock_runner)
    wf.add_block(block1).add_block(block2)
    wf.add_transition("b1", "b2").add_transition("b2", None)
    wf.set_entry("b1")

    # Execute and capture states
    initial_state = WorkflowState(
        current_task=Task(id="t1", instruction="Test"),
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
    assert "b1" in final_state.results
    assert "b2" in final_state.results
    assert len(final_state.execution_log) == 2


@pytest.mark.asyncio
async def test_error_propagation_through_workflow(mock_runner, sample_souls):
    """
    ERROR HANDLING TEST: Verify exceptions propagate through workflow.

    Tests that if a block raises an exception, the workflow execution stops
    and the error propagates to the caller.
    """
    # First block succeeds, second raises exception
    mock_runner.execute_task.side_effect = [
        ExecutionResult(task_id="t1", soul_id="researcher", output="Success"),
        Exception("Simulated execution failure"),
    ]

    wf = Workflow("error_test")
    block1 = LinearBlock("b1", sample_souls["researcher"], mock_runner)
    block2 = LinearBlock("b2", sample_souls["reviewer1"], mock_runner)
    wf.add_block(block1).add_block(block2)
    wf.add_transition("b1", "b2").add_transition("b2", None)
    wf.set_entry("b1")

    initial_state = WorkflowState(current_task=Task(id="t1", instruction="Test"))

    # Verify exception propagates
    with pytest.raises(Exception, match="Simulated execution failure"):
        await wf.run(initial_state)
