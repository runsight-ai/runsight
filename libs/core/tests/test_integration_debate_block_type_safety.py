"""
Integration tests for DebateBlock type safety and context formatting.

FOCUS: Tests the DebateBlock implementation to verify:
1. Type hints are correct (tests runtime behavior to catch 'any' vs 'Any' issue)
2. Task.context formatting with role names works as specified
3. Edge cases around debate rounds and context propagation
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from runsight_core.state import WorkflowState
from runsight_core.primitives import Soul, Task
from runsight_core.runner import ExecutionResult
from runsight_core.blocks.implementations import DebateBlock


@pytest.fixture
def mock_runner():
    """Mock RunsightTeamRunner with controlled outputs."""
    runner = MagicMock()
    runner.execute_task = AsyncMock()
    return runner


@pytest.fixture
def debate_souls():
    """Create souls for debate testing."""
    return {
        "proposer": Soul(id="proposer_id", role="Proposer", system_prompt="You propose solutions"),
        "critic": Soul(id="critic_id", role="Critic", system_prompt="You critique solutions"),
    }


@pytest.mark.asyncio
async def test_debate_block_context_formatting_first_round(mock_runner, debate_souls):
    """
    Test that soul_a gets None context in round 1, soul_b gets soul_a output with role name.

    This validates the Task.context field usage which was a review focus point.
    """
    mock_runner.execute_task.side_effect = [
        ExecutionResult(task_id="d_r1_a", soul_id="proposer_id", output="Proposal from round 1"),
        ExecutionResult(task_id="d_r1_b", soul_id="critic_id", output="Critique from round 1"),
    ]

    block = DebateBlock(
        "debate1",
        debate_souls["proposer"],
        debate_souls["critic"],
        iterations=1,
        runner=mock_runner,
    )
    task = Task(id="main", instruction="Should we use microservices?")
    state = WorkflowState(current_task=task)

    await block.execute(state)

    # Verify soul_a (first call) has None context
    first_call = mock_runner.execute_task.call_args_list[0]
    task_a = first_call[0][0]
    assert task_a.context is None, "Soul A should have None context in round 1"

    # Verify soul_b (second call) has context with soul_a role name
    second_call = mock_runner.execute_task.call_args_list[1]
    task_b = second_call[0][0]
    assert task_b.context is not None, "Soul B should have context"
    assert "Proposer" in task_b.context, "Soul B context should include soul_a role name"
    assert "Proposal from round 1" in task_b.context, "Soul B context should include soul_a output"


@pytest.mark.asyncio
async def test_debate_block_context_formatting_second_round(mock_runner, debate_souls):
    """
    Test that soul_a gets soul_b output with role name in round 2+.

    This validates the context propagation across multiple rounds.
    """
    mock_runner.execute_task.side_effect = [
        # Round 1
        ExecutionResult(task_id="d_r1_a", soul_id="proposer_id", output="Initial proposal"),
        ExecutionResult(task_id="d_r1_b", soul_id="critic_id", output="Initial critique"),
        # Round 2
        ExecutionResult(task_id="d_r2_a", soul_id="proposer_id", output="Revised proposal"),
        ExecutionResult(task_id="d_r2_b", soul_id="critic_id", output="Final critique"),
    ]

    block = DebateBlock(
        "debate1",
        debate_souls["proposer"],
        debate_souls["critic"],
        iterations=2,
        runner=mock_runner,
    )
    task = Task(id="main", instruction="Debate topic")
    state = WorkflowState(current_task=task)

    await block.execute(state)

    # Verify soul_a in round 2 has context with soul_b output and role name
    third_call = mock_runner.execute_task.call_args_list[2]  # Round 2, soul_a
    task_a_round2 = third_call[0][0]
    assert task_a_round2.context is not None, "Soul A should have context in round 2"
    assert "Critic" in task_a_round2.context, "Soul A context should include soul_b role name"
    assert "Initial critique" in task_a_round2.context, (
        "Soul A context should include previous soul_b output"
    )

    # Verify soul_b in round 2 still gets soul_a output with role name
    fourth_call = mock_runner.execute_task.call_args_list[3]  # Round 2, soul_b
    task_b_round2 = fourth_call[0][0]
    assert task_b_round2.context is not None
    assert "Proposer" in task_b_round2.context
    assert "Revised proposal" in task_b_round2.context


@pytest.mark.asyncio
async def test_debate_block_transcript_structure_validation(mock_runner, debate_souls):
    """
    Test that transcript is correctly structured as List[Dict[str, any]].

    This verifies the type hint matches actual runtime behavior.
    """
    mock_runner.execute_task.side_effect = [
        ExecutionResult(task_id="d1", soul_id="proposer_id", output="Prop 1"),
        ExecutionResult(task_id="d2", soul_id="critic_id", output="Crit 1"),
        ExecutionResult(task_id="d3", soul_id="proposer_id", output="Prop 2"),
        ExecutionResult(task_id="d4", soul_id="critic_id", output="Crit 2"),
    ]

    block = DebateBlock(
        "debate1",
        debate_souls["proposer"],
        debate_souls["critic"],
        iterations=2,
        runner=mock_runner,
    )
    task = Task(id="main", instruction="Test")
    state = WorkflowState(current_task=task)

    result_state = await block.execute(state)

    # Parse transcript
    transcript = json.loads(result_state.results["debate1"])

    # Verify structure matches List[Dict[str, any]]
    assert isinstance(transcript, list), "Transcript should be a list"
    assert len(transcript) == 2, "Should have 2 rounds"

    for round_entry in transcript:
        assert isinstance(round_entry, dict), "Each entry should be a dict"
        assert "round" in round_entry
        assert "soul_a" in round_entry
        assert "soul_b" in round_entry
        assert isinstance(round_entry["round"], int)
        assert isinstance(round_entry["soul_a"], str)
        assert isinstance(round_entry["soul_b"], str)


@pytest.mark.asyncio
async def test_debate_block_single_iteration_edge_case(mock_runner, debate_souls):
    """
    Test debate with iterations=1 (minimum valid value).

    Edge case: only 1 round, soul_a gets no previous context.
    """
    mock_runner.execute_task.side_effect = [
        ExecutionResult(task_id="d1_a", soul_id="proposer_id", output="Single proposal"),
        ExecutionResult(task_id="d1_b", soul_id="critic_id", output="Single critique"),
    ]

    block = DebateBlock(
        "debate1",
        debate_souls["proposer"],
        debate_souls["critic"],
        iterations=1,
        runner=mock_runner,
    )
    task = Task(id="main", instruction="Quick debate")
    state = WorkflowState(current_task=task)

    result_state = await block.execute(state)

    # Verify transcript has exactly 1 round
    transcript = json.loads(result_state.results["debate1"])
    assert len(transcript) == 1
    assert transcript[0]["round"] == 1

    # Verify conclusion is the only soul_b response
    assert result_state.shared_memory["debate1_conclusion"] == "Single critique"

    # Verify only 2 calls made
    assert mock_runner.execute_task.call_count == 2


@pytest.mark.asyncio
async def test_debate_block_preserves_state_fields(mock_runner, debate_souls):
    """
    Test that DebateBlock preserves existing state fields.

    Verifies state immutability and proper field preservation.
    """
    mock_runner.execute_task.side_effect = [
        ExecutionResult(task_id="d1", soul_id="proposer_id", output="Prop"),
        ExecutionResult(task_id="d2", soul_id="critic_id", output="Crit"),
    ]

    block = DebateBlock(
        "debate1",
        debate_souls["proposer"],
        debate_souls["critic"],
        iterations=1,
        runner=mock_runner,
    )
    task = Task(id="main", instruction="Test")

    # Create state with existing data
    initial_state = WorkflowState(
        current_task=task,
        results={"previous_block": "previous output"},
        shared_memory={"existing_key": "existing_value"},
        messages=[{"role": "system", "content": "Previous message"}],
        metadata={"workflow_id": "test123"},
    )

    result_state = await block.execute(initial_state)

    # Verify all existing fields preserved
    assert result_state.results["previous_block"] == "previous output"
    assert result_state.shared_memory["existing_key"] == "existing_value"
    assert len(result_state.messages) == 2  # Original + new
    assert result_state.messages[0]["content"] == "Previous message"
    assert result_state.metadata["workflow_id"] == "test123"

    # Verify new data added
    assert "debate1" in result_state.results
    assert "debate1_conclusion" in result_state.shared_memory


@pytest.mark.asyncio
async def test_debate_block_current_task_none_error(mock_runner, debate_souls):
    """
    Test that DebateBlock raises ValueError when current_task is None.

    This is an edge case that should be tested for all blocks.
    """
    block = DebateBlock(
        "debate1",
        debate_souls["proposer"],
        debate_souls["critic"],
        iterations=1,
        runner=mock_runner,
    )
    state = WorkflowState(current_task=None)

    with pytest.raises(ValueError, match="current_task is None"):
        await block.execute(state)


@pytest.mark.asyncio
async def test_debate_block_role_names_in_context(mock_runner, debate_souls):
    """
    Test that role names (not soul IDs) are used in context formatting.

    Critical: context should say "Previous response from Critic" not "critic_id".
    """
    mock_runner.execute_task.side_effect = [
        ExecutionResult(task_id="d1", soul_id="proposer_id", output="Proposal A"),
        ExecutionResult(task_id="d2", soul_id="critic_id", output="Critique A"),
        ExecutionResult(task_id="d3", soul_id="proposer_id", output="Proposal B"),
        ExecutionResult(task_id="d4", soul_id="critic_id", output="Critique B"),
    ]

    block = DebateBlock(
        "debate1",
        debate_souls["proposer"],
        debate_souls["critic"],
        iterations=2,
        runner=mock_runner,
    )
    task = Task(id="main", instruction="Debate")
    state = WorkflowState(current_task=task)

    await block.execute(state)

    # Verify role names used (not IDs)
    # Round 1, soul_b call
    call_1_b = mock_runner.execute_task.call_args_list[1]
    task_1_b = call_1_b[0][0]
    assert "Proposer" in task_1_b.context, "Should use role name 'Proposer', not 'proposer_id'"

    # Round 2, soul_a call
    call_2_a = mock_runner.execute_task.call_args_list[2]
    task_2_a = call_2_a[0][0]
    assert "Critic" in task_2_a.context, "Should use role name 'Critic', not 'critic_id'"

    # Round 2, soul_b call
    call_2_b = mock_runner.execute_task.call_args_list[3]
    task_2_b = call_2_b[0][0]
    assert "Proposer" in task_2_b.context, "Should use role name 'Proposer', not 'proposer_id'"


@pytest.mark.asyncio
async def test_debate_block_task_ids_are_unique(mock_runner, debate_souls):
    """
    Test that each debate round generates unique task IDs.

    Verifies task ID format: {block_id}_round{N}_{a|b}
    """
    mock_runner.execute_task.side_effect = [
        ExecutionResult(task_id="any", soul_id="proposer_id", output="P1"),
        ExecutionResult(task_id="any", soul_id="critic_id", output="C1"),
        ExecutionResult(task_id="any", soul_id="proposer_id", output="P2"),
        ExecutionResult(task_id="any", soul_id="critic_id", output="C2"),
    ]

    block = DebateBlock(
        "my_debate",
        debate_souls["proposer"],
        debate_souls["critic"],
        iterations=2,
        runner=mock_runner,
    )
    task = Task(id="main", instruction="Test")
    state = WorkflowState(current_task=task)

    await block.execute(state)

    # Extract task IDs from calls
    task_ids = [call[0][0].id for call in mock_runner.execute_task.call_args_list]

    # Verify format and uniqueness
    assert task_ids[0] == "my_debate_round1_a"
    assert task_ids[1] == "my_debate_round1_b"
    assert task_ids[2] == "my_debate_round2_a"
    assert task_ids[3] == "my_debate_round2_b"
    assert len(set(task_ids)) == 4, "All task IDs should be unique"
