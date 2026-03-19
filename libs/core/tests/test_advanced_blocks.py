"""
Tests for advanced block implementations (RouterBlock, etc.).
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock

from runsight_core.state import WorkflowState
from runsight_core.primitives import Soul, Task
from runsight_core.blocks.implementations import (
    RouterBlock,
    TeamLeadBlock,
    EngineeringManagerBlock,
    MessageBusBlock,
)
from runsight_core.runner import ExecutionResult


# ===== Fixtures for RouterBlock Tests =====


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


# ===== RouterBlock Tests =====


@pytest.mark.asyncio
async def test_router_block_soul_evaluation(mock_runner, sample_soul):
    """
    AC-10: RouterBlock with Soul evaluator executes task, stores decision in results and metadata, appends message.
    """
    # Setup: Mock runner returns a decision
    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="decision_task", soul_id="test_soul", output="approved"
    )

    # Create RouterBlock with Soul evaluator
    block = RouterBlock("router1", sample_soul, mock_runner)
    task = Task(id="decision_task", instruction="Should we proceed with this plan?")
    state = WorkflowState(current_task=task)

    # Execute
    result_state = await block.execute(state)

    # Verify decision stored in results
    assert result_state.results["router1"] == "approved"

    # Verify decision stored in metadata
    assert result_state.metadata["router1_decision"] == "approved"

    # Verify message appended
    assert len(result_state.messages) == 1
    assert "[Block router1]" in result_state.messages[0]["content"]
    assert "RouterBlock decision: approved" in result_state.messages[0]["content"]

    # Verify runner called with task and soul
    mock_runner.execute_task.assert_called_once_with(task, sample_soul)


@pytest.mark.asyncio
async def test_router_block_callable_evaluation(mock_runner):
    """
    AC-11: RouterBlock with Callable evaluator calls function with state, stores decision in results and metadata.
    """

    # Define a callable evaluator
    def check_budget(state: WorkflowState) -> str:
        budget = state.shared_memory.get("remaining_budget", 0)
        return "approved" if budget > 1000 else "rejected"

    # Create RouterBlock with Callable evaluator (no runner needed)
    block = RouterBlock("router2", check_budget, runner=None)
    state = WorkflowState(shared_memory={"remaining_budget": 5000})

    # Execute
    result_state = await block.execute(state)

    # Verify decision stored in results
    assert result_state.results["router2"] == "approved"

    # Verify decision stored in metadata
    assert result_state.metadata["router2_decision"] == "approved"

    # Verify message appended
    assert len(result_state.messages) == 1
    assert "[Block router2]" in result_state.messages[0]["content"]
    assert "RouterBlock decision: approved" in result_state.messages[0]["content"]

    # Verify runner was not called (callable path)
    mock_runner.execute_task.assert_not_called()


@pytest.mark.asyncio
async def test_router_block_callable_evaluation_rejected(mock_runner):
    """
    RouterBlock with Callable evaluator returns 'rejected' when condition fails.
    """

    def check_budget(state: WorkflowState) -> str:
        budget = state.shared_memory.get("remaining_budget", 0)
        return "approved" if budget > 1000 else "rejected"

    block = RouterBlock("router3", check_budget, runner=None)
    state = WorkflowState(shared_memory={"remaining_budget": 500})

    result_state = await block.execute(state)

    assert result_state.results["router3"] == "rejected"
    assert result_state.metadata["router3_decision"] == "rejected"


@pytest.mark.asyncio
async def test_router_block_requires_runner_for_soul(sample_soul):
    """
    AC-12: ValueError raised in constructor if condition_evaluator is Soul but runner=None.
    """
    with pytest.raises(ValueError, match="runner is required when condition_evaluator is Soul"):
        RouterBlock("router_fail", sample_soul, runner=None)


@pytest.mark.asyncio
async def test_router_block_soul_requires_current_task(mock_runner, sample_soul):
    """
    AC: RouterBlock validates current_task not None when using Soul evaluator during execute().
    """
    block = RouterBlock("router4", sample_soul, mock_runner)
    state = WorkflowState(current_task=None)

    with pytest.raises(
        ValueError, match="state.current_task is None \\(required for Soul evaluator\\)"
    ):
        await block.execute(state)


@pytest.mark.asyncio
async def test_router_block_soul_strips_whitespace(mock_runner, sample_soul):
    """
    RouterBlock strips whitespace from Soul evaluator output.
    """
    # Mock runner returns decision with whitespace
    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="task", soul_id="test_soul", output="  approved  \n"
    )

    block = RouterBlock("router5", sample_soul, mock_runner)
    task = Task(id="task", instruction="Evaluate this")
    state = WorkflowState(current_task=task)

    result_state = await block.execute(state)

    # Decision should be stripped
    assert result_state.results["router5"] == "approved"
    assert result_state.metadata["router5_decision"] == "approved"


@pytest.mark.asyncio
async def test_router_block_callable_with_runner_allowed(mock_runner):
    """
    RouterBlock allows runner parameter even when using Callable evaluator (runner is optional).
    """

    def simple_check(state: WorkflowState) -> str:
        return "pass"

    # Should not raise error - runner is optional for Callable
    block = RouterBlock("router6", simple_check, runner=mock_runner)
    state = WorkflowState()

    result_state = await block.execute(state)

    assert result_state.results["router6"] == "pass"


@pytest.mark.asyncio
async def test_team_lead_block_analyzes_failure(mock_runner, sample_soul):
    """
    AC-1: TeamLeadBlock reads multiple failure_context_keys, produces recommendation
    in results and shared_memory['{block_id}_recommendation'].
    """
    # Setup: mock runner returns recommendation
    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="team_lead_analysis",
        soul_id="test_soul",
        output="Root cause: Network timeout. Recommendation: Increase timeout to 30s and add retry logic.",
    )

    # Create team lead block with 2 context keys
    block = TeamLeadBlock(
        block_id="team_lead1",
        failure_context_keys=["retry_errors", "execution_log"],
        team_lead_soul=sample_soul,
        runner=mock_runner,
    )

    # Populate shared_memory with mixed types (list and string)
    state = WorkflowState(
        shared_memory={
            "retry_errors": ["Attempt 1: Connection timeout", "Attempt 2: Connection refused"],
            "execution_log": "Started at 10:00, failed at 10:05",
        }
    )

    result_state = await block.execute(state)

    # Verify recommendation stored in both locations
    expected_recommendation = (
        "Root cause: Network timeout. Recommendation: Increase timeout to 30s and add retry logic."
    )
    assert result_state.results["team_lead1"] == expected_recommendation
    assert result_state.shared_memory["team_lead1_recommendation"] == expected_recommendation

    # Verify message logged
    assert len(result_state.messages) == 1
    assert "TeamLeadBlock analyzed 2 context(s)" in result_state.messages[0]["content"]

    # Verify task instruction includes both contexts
    call_args = mock_runner.execute_task.call_args
    task_arg = call_args[0][0]  # First positional arg is Task
    assert "retry_errors" in task_arg.instruction
    assert "execution_log" in task_arg.instruction
    # Verify list formatting with bullet points
    assert "  - Attempt 1: Connection timeout" in task_arg.instruction
    assert "  - Attempt 2: Connection refused" in task_arg.instruction
    # Verify string value included
    assert "Started at 10:00, failed at 10:05" in task_arg.instruction


@pytest.mark.asyncio
async def test_team_lead_block_missing_context_keys(mock_runner, sample_soul):
    """
    AC-2: TeamLeadBlock raises ValueError with missing keys listed and available keys shown
    if any key missing.
    """
    block = TeamLeadBlock(
        block_id="team_lead1",
        failure_context_keys=["retry_errors", "execution_log", "system_metrics"],
        team_lead_soul=sample_soul,
        runner=mock_runner,
    )

    # Only provide one of the three required keys
    state = WorkflowState(shared_memory={"retry_errors": ["Error 1"], "other_key": "value"})

    with pytest.raises(ValueError) as exc_info:
        await block.execute(state)

    error_msg = str(exc_info.value)
    # Verify missing keys are listed
    assert "execution_log" in error_msg
    assert "system_metrics" in error_msg
    # Verify available keys are shown
    assert "Available keys:" in error_msg
    assert "retry_errors" in error_msg
    assert "other_key" in error_msg


@pytest.mark.asyncio
async def test_team_lead_block_empty_failure_context_keys(mock_runner, sample_soul):
    """
    AC-3: TeamLeadBlock validates failure_context_keys is non-empty in constructor.
    """
    with pytest.raises(ValueError, match="failure_context_keys cannot be empty"):
        TeamLeadBlock(
            block_id="team_lead1",
            failure_context_keys=[],
            team_lead_soul=sample_soul,
            runner=mock_runner,
        )


@pytest.mark.asyncio
async def test_team_lead_block_handles_list_and_string_values(mock_runner, sample_soul):
    """
    AC-4: TeamLeadBlock handles both list and string values from shared_memory,
    formatting lists with bullet points.
    """
    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="team_lead_analysis", soul_id="test_soul", output="Analysis complete"
    )

    block = TeamLeadBlock(
        block_id="team_lead1",
        failure_context_keys=["errors_list", "status_string", "another_list"],
        team_lead_soul=sample_soul,
        runner=mock_runner,
    )

    state = WorkflowState(
        shared_memory={
            "errors_list": ["Error A", "Error B", "Error C"],
            "status_string": "System crashed",
            "another_list": ["Log 1", "Log 2"],
        }
    )

    result_state = await block.execute(state)

    # Verify execution succeeded
    assert result_state.results["team_lead1"] == "Analysis complete"

    # Verify task instruction format
    call_args = mock_runner.execute_task.call_args
    task_arg = call_args[0][0]
    instruction = task_arg.instruction

    # Check list formatting (bullet points)
    assert "  - Error A" in instruction
    assert "  - Error B" in instruction
    assert "  - Error C" in instruction
    assert "  - Log 1" in instruction
    assert "  - Log 2" in instruction

    # Check string formatting (no bullet points)
    assert "System crashed" in instruction
    # Ensure string is not formatted with bullet points
    assert "  - System crashed" not in instruction


@pytest.mark.asyncio
async def test_team_lead_block_preserves_existing_shared_memory(mock_runner, sample_soul):
    """TeamLeadBlock preserves existing shared_memory entries."""
    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="team_lead_analysis", soul_id="test_soul", output="Recommendation"
    )

    block = TeamLeadBlock(
        block_id="team_lead1",
        failure_context_keys=["error_log"],
        team_lead_soul=sample_soul,
        runner=mock_runner,
    )

    state = WorkflowState(
        shared_memory={
            "error_log": "Connection failed",
            "existing_key": "existing_value",
        }
    )

    result_state = await block.execute(state)

    # Verify existing shared_memory preserved
    assert result_state.shared_memory["existing_key"] == "existing_value"
    assert result_state.shared_memory["error_log"] == "Connection failed"
    # Verify new recommendation added
    assert result_state.shared_memory["team_lead1_recommendation"] == "Recommendation"


# ===== Additional Fixture for EngineeringManagerBlock =====


@pytest.fixture
def planner_soul():
    """Sample planning soul for EngineeringManagerBlock testing."""
    return Soul(
        id="engineering_manager",
        role="Engineering Manager",
        system_prompt="You create detailed execution plans.",
    )


# ===== EngineeringManagerBlock Tests =====
@pytest.mark.asyncio
async def test_engineering_manager_generates_new_steps(mock_runner, planner_soul):
    """
    AC1: pytest libs/core/tests/test_advanced_blocks.py::test_engineering_manager_generates_new_steps -v passes
    - Produces text plan in results[block_id]
    - JSON step list in metadata['{block_id}_new_steps']
    """
    # Mock LLM returns well-formatted plan with 3 steps
    well_formatted_plan = """1. requirements_analysis: Gather authentication requirements and security constraints
2. technology_selection: Choose between OAuth, SAML, or JWT-based auth
3. database_schema: Design user and session tables"""

    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="replanner1_planning", soul_id="planner", output=well_formatted_plan
    )

    block = EngineeringManagerBlock("replanner1", planner_soul, mock_runner)
    task = Task(id="main", instruction="Build authentication system")
    state = WorkflowState(current_task=task)

    result_state = await block.execute(state)

    # Verify text plan in results
    assert result_state.results["replanner1"] == well_formatted_plan

    # Verify JSON step list in metadata
    steps = result_state.metadata["replanner1_new_steps"]
    assert isinstance(steps, list)
    assert len(steps) == 3

    # Verify step structure with correct keys
    assert steps[0] == {
        "step_id": "requirements_analysis",
        "description": "Gather authentication requirements and security constraints",
    }
    assert steps[1] == {
        "step_id": "technology_selection",
        "description": "Choose between OAuth, SAML, or JWT-based auth",
    }
    assert steps[2] == {
        "step_id": "database_schema",
        "description": "Design user and session tables",
    }

    # Verify message appended
    assert len(result_state.messages) == 1
    assert "[Block replanner1]" in result_state.messages[0]["content"]
    assert "EngineeringManagerBlock generated 3 step(s)" in result_state.messages[0]["content"]


@pytest.mark.asyncio
async def test_engineering_manager_validates_current_task(mock_runner, planner_soul):
    """AC2: EngineeringManagerBlock validates current_task is not None during execute()."""
    block = EngineeringManagerBlock("replanner1", planner_soul, mock_runner)
    state = WorkflowState(current_task=None)

    with pytest.raises(
        ValueError, match="EngineeringManagerBlock replanner1: state.current_task is None"
    ):
        await block.execute(state)


@pytest.mark.asyncio
async def test_engineering_manager_regex_pattern_parsing(mock_runner, planner_soul):
    r"""AC3: Regex pattern '^\d+\.\s+([^:]+):\s+(.+)$' successfully parses format '1. step_id: description'."""
    # Test explicit regex pattern with various formats
    test_plan = """1. step_one: First step description
2. step_two: Second step description with more detail
3. step_three: Third step"""

    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="replanner1_planning", soul_id="planner", output=test_plan
    )

    block = EngineeringManagerBlock("replanner1", planner_soul, mock_runner)
    task = Task(id="test", instruction="Test task")
    state = WorkflowState(current_task=task)

    result_state = await block.execute(state)

    steps = result_state.metadata["replanner1_new_steps"]
    assert len(steps) == 3
    assert steps[0]["step_id"] == "step_one"
    assert steps[0]["description"] == "First step description"
    assert steps[1]["step_id"] == "step_two"
    assert steps[1]["description"] == "Second step description with more detail"
    assert steps[2]["step_id"] == "step_three"
    assert steps[2]["description"] == "Third step"


@pytest.mark.asyncio
async def test_engineering_manager_fallback_creates_generic_step(mock_runner, planner_soul):
    """AC4: Fallback creates single generic step if regex finds no matches."""
    # Mock LLM returns unformatted text (doesn't match pattern)
    unformatted_plan = """Here's my plan for this project:
- First we need to do some research
- Then we should design the system
- Finally implement and test"""

    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="replanner1_planning", soul_id="planner", output=unformatted_plan
    )

    block = EngineeringManagerBlock("replanner1", planner_soul, mock_runner)
    task = Task(id="test", instruction="Test task")
    state = WorkflowState(current_task=task)

    result_state = await block.execute(state)

    # Verify single generic step created
    steps = result_state.metadata["replanner1_new_steps"]
    assert len(steps) == 1
    assert steps[0]["step_id"] == "replanned_execution"
    assert steps[0]["description"] == unformatted_plan  # Full text since < 200 chars


@pytest.mark.asyncio
async def test_engineering_manager_fallback_truncates_at_200_chars(mock_runner, planner_soul):
    """Verify fallback truncates description at 200 chars."""
    # Create unformatted plan longer than 200 chars
    long_unformatted_plan = "A" * 250 + " some more text"

    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="replanner1_planning", soul_id="planner", output=long_unformatted_plan
    )

    block = EngineeringManagerBlock("replanner1", planner_soul, mock_runner)
    task = Task(id="test", instruction="Test task")
    state = WorkflowState(current_task=task)

    result_state = await block.execute(state)

    steps = result_state.metadata["replanner1_new_steps"]
    assert len(steps) == 1
    assert steps[0]["step_id"] == "replanned_execution"
    # Verify truncation at 200 chars with "..."
    assert steps[0]["description"] == long_unformatted_plan[:200] + "..."
    assert len(steps[0]["description"]) == 203  # 200 + "..."


@pytest.mark.asyncio
async def test_engineering_manager_regex_with_whitespace_variations(mock_runner, planner_soul):
    """Test regex handles various whitespace around step_id and description."""
    # Test with extra spaces
    plan_with_spaces = """1.   step_with_spaces  :   Description with spaces
2. normal_step: Normal description
3.step_no_space:No space after number"""

    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="replanner1_planning", soul_id="planner", output=plan_with_spaces
    )

    block = EngineeringManagerBlock("replanner1", planner_soul, mock_runner)
    task = Task(id="test", instruction="Test task")
    state = WorkflowState(current_task=task)

    result_state = await block.execute(state)

    steps = result_state.metadata["replanner1_new_steps"]
    # First line matches because ^\d+\. requires space after period
    # Third line doesn't match because no space after period
    assert len(steps) == 2
    # Verify trimming works
    assert steps[0]["step_id"] == "step_with_spaces"
    assert steps[0]["description"] == "Description with spaces"
    assert steps[1]["step_id"] == "normal_step"
    assert steps[1]["description"] == "Normal description"


@pytest.mark.asyncio
async def test_engineering_manager_preserves_existing_results_and_metadata(
    mock_runner, planner_soul
):
    """EngineeringManagerBlock preserves existing results and metadata."""
    plan = "1. step1: Description 1"

    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="replanner1_planning", soul_id="planner", output=plan
    )

    block = EngineeringManagerBlock("replanner1", planner_soul, mock_runner)
    task = Task(id="test", instruction="Test task")
    state = WorkflowState(
        current_task=task,
        results={"previous_block": "Previous result"},
        metadata={"existing_key": "existing_value"},
    )

    result_state = await block.execute(state)

    # Verify existing data preserved
    assert result_state.results["previous_block"] == "Previous result"
    assert result_state.metadata["existing_key"] == "existing_value"

    # Verify new data added
    assert result_state.results["replanner1"] == plan
    assert "replanner1_new_steps" in result_state.metadata


@pytest.mark.asyncio
async def test_engineering_manager_reads_previous_errors_from_shared_memory(
    mock_runner, planner_soul
):
    """EngineeringManagerBlock includes previous errors from shared_memory in planning context."""
    plan = "1. retry_step: Try again with fix"

    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="replanner1_planning", soul_id="planner", output=plan
    )

    block = EngineeringManagerBlock("replanner1", planner_soul, mock_runner)
    task = Task(id="test", instruction="Build feature")
    state = WorkflowState(
        current_task=task,
        shared_memory={"replanner1_previous_errors": "Error: Connection timeout"},
    )

    await block.execute(state)

    # Verify the task was called with error context
    call_args = mock_runner.execute_task.call_args
    planning_task = call_args[0][0]
    assert "Original Goal: Build feature" in planning_task.instruction
    assert "Previous Errors:" in planning_task.instruction
    assert "Error: Connection timeout" in planning_task.instruction


@pytest.mark.asyncio
async def test_engineering_manager_multiline_descriptions(mock_runner, planner_soul):
    """Test that regex correctly handles single-line format (multiline descriptions should not match)."""
    # Each step must be on single line - multiline descriptions shouldn't match
    plan_single_line = """1. step1: This is a single line description
2. step2: Another single line
3. step3: Final step"""

    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="replanner1_planning", soul_id="planner", output=plan_single_line
    )

    block = EngineeringManagerBlock("replanner1", planner_soul, mock_runner)
    task = Task(id="test", instruction="Test")
    state = WorkflowState(current_task=task)

    result_state = await block.execute(state)

    steps = result_state.metadata["replanner1_new_steps"]
    assert len(steps) == 3


# ===== Additional Fixture for MessageBusBlock =====


@pytest.fixture
def sample_souls():
    """Sample souls for MessageBusBlock testing."""
    return [
        Soul(id="agent1", role="Researcher", system_prompt="You research."),
        Soul(id="agent2", role="Engineer", system_prompt="You engineer."),
        Soul(id="agent3", role="Ethicist", system_prompt="You analyze ethics."),
        Soul(id="agent4", role="Critic", system_prompt="You critique."),
    ]


# ===== MessageBusBlock Tests =====
@pytest.mark.asyncio
async def test_messagebus_n_agents(mock_runner, sample_souls):
    """AC-1: 4 agents × 3 iterations produces JSON transcript with 3 rounds of 4 contributions each."""
    # Create a counter-based mock that returns unique outputs per call
    call_count = [0]

    def create_result(*args, **kwargs):
        call_count[0] += 1
        task = args[0]
        soul = args[1]
        return ExecutionResult(
            task_id=task.id,
            soul_id=soul.id,
            output=f"Output from {soul.id} - call {call_count[0]}",
        )

    mock_runner.execute_task.side_effect = create_result

    # Create MessageBusBlock with 4 agents and 3 iterations
    block = MessageBusBlock("messagebus1", sample_souls, iterations=3, runner=mock_runner)
    task = Task(id="brainstorm", instruction="Generate ideas for AI safety")
    state = WorkflowState(current_task=task)

    # Execute
    result_state = await block.execute(state)

    # Verify transcript format
    transcript_json = result_state.results["messagebus1"]
    transcript = json.loads(transcript_json)

    # Should have 3 rounds
    assert len(transcript) == 3

    # Each round should have 4 contributions
    for round_idx, round_data in enumerate(transcript):
        assert round_data["round"] == round_idx + 1
        assert len(round_data["contributions"]) == 4

        # Verify each contribution has soul_id and output
        for contrib_idx, contrib in enumerate(round_data["contributions"]):
            assert "soul_id" in contrib
            assert "output" in contrib
            assert contrib["soul_id"] == sample_souls[contrib_idx].id

    # Verify consensus stored in shared_memory (last contribution from last round)
    expected_consensus = transcript[-1]["contributions"][-1]["output"]
    assert result_state.shared_memory["messagebus1_consensus"] == expected_consensus

    # Verify message appended
    assert len(result_state.messages) == 1
    assert "[Block messagebus1]" in result_state.messages[0]["content"]
    assert "4 agents × 3 rounds" in result_state.messages[0]["content"]

    # Verify total calls (4 agents × 3 rounds = 12)
    assert mock_runner.execute_task.call_count == 12


@pytest.mark.asyncio
async def test_messagebus_validation(mock_runner, sample_souls):
    """AC-2: ValueError for empty souls list, iterations < 1, or current_task=None."""
    # Test empty souls list
    with pytest.raises(ValueError, match="souls list cannot be empty"):
        MessageBusBlock("messagebus1", [], iterations=3, runner=mock_runner)

    # Test iterations < 1
    with pytest.raises(ValueError, match="iterations must be >= 1, got 0"):
        MessageBusBlock("messagebus1", sample_souls, iterations=0, runner=mock_runner)

    # Test current_task=None
    block = MessageBusBlock("messagebus1", sample_souls, iterations=3, runner=mock_runner)
    state = WorkflowState(current_task=None)

    with pytest.raises(ValueError, match="state.current_task is None"):
        await block.execute(state)


@pytest.mark.asyncio
async def test_messagebus_context_passing(mock_runner, sample_souls):
    """Verify context passing: each agent sees formatted contributions from earlier agents in same round."""
    # Track all task objects passed to execute_task
    task_contexts = []

    def capture_task(*args, **kwargs):
        task = args[0]
        soul = args[1]
        task_contexts.append({"task": task, "soul_id": soul.id})
        return ExecutionResult(task_id=task.id, soul_id=soul.id, output=f"Output from {soul.id}")

    mock_runner.execute_task.side_effect = capture_task

    # Use 3 agents, 2 iterations
    souls = sample_souls[:3]
    block = MessageBusBlock("messagebus1", souls, iterations=2, runner=mock_runner)
    task = Task(id="discussion", instruction="Discuss the topic")
    state = WorkflowState(current_task=task)

    await block.execute(state)

    # Total calls: 3 agents × 2 rounds = 6
    assert len(task_contexts) == 6

    # Round 1:
    # Agent 1 (index 0): should have no context
    assert task_contexts[0]["task"].context is None

    # Agent 2 (index 1): should see agent 1's contribution
    agent2_round1_context = task_contexts[1]["task"].context
    assert agent2_round1_context is not None
    assert "[agent1]:" in agent2_round1_context
    assert "Output from agent1" in agent2_round1_context

    # Agent 3 (index 2): should see agent 1 and agent 2's contributions
    agent3_round1_context = task_contexts[2]["task"].context
    assert agent3_round1_context is not None
    assert "[agent1]:" in agent3_round1_context
    assert "[agent2]:" in agent3_round1_context
    assert "Output from agent1" in agent3_round1_context
    assert "Output from agent2" in agent3_round1_context

    # Round 2:
    # Agent 1 (index 3): should have no context (fresh round)
    assert task_contexts[3]["task"].context is None

    # Agent 2 (index 4): should see only agent 1's contribution from round 2
    agent2_round2_context = task_contexts[4]["task"].context
    assert agent2_round2_context is not None
    assert "[agent1]:" in agent2_round2_context
    assert "Output from agent1" in agent2_round2_context


@pytest.mark.asyncio
async def test_messagebus_transcript_format(mock_runner, sample_souls):
    """AC-4: Transcript format verification with proper JSON structure."""
    mock_runner.execute_task.return_value = ExecutionResult(
        task_id="t1", soul_id="agent1", output="Sample output"
    )

    # Single iteration with 2 agents to simplify
    souls = sample_souls[:2]
    block = MessageBusBlock("messagebus1", souls, iterations=1, runner=mock_runner)
    task = Task(id="task1", instruction="Test instruction")
    state = WorkflowState(current_task=task)

    result_state = await block.execute(state)

    # Parse transcript
    transcript = json.loads(result_state.results["messagebus1"])

    # Verify structure
    assert isinstance(transcript, list)
    assert len(transcript) == 1

    round_data = transcript[0]
    assert "round" in round_data
    assert "contributions" in round_data
    assert round_data["round"] == 1

    contributions = round_data["contributions"]
    assert isinstance(contributions, list)
    assert len(contributions) == 2

    for contrib in contributions:
        assert "soul_id" in contrib
        assert "output" in contrib
        assert isinstance(contrib["soul_id"], str)
        assert isinstance(contrib["output"], str)
