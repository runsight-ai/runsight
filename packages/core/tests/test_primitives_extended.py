"""
Tests for extended primitives: Step.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from runsight_core import LinearBlock
from runsight_core.primitives import Soul, Step
from runsight_core.runner import ExecutionResult
from runsight_core.state import WorkflowState


@pytest.fixture
def mock_runner():
    """Mock RunsightTeamRunner with controlled outputs."""
    runner = MagicMock()
    runner.execute = AsyncMock()
    return runner


@pytest.fixture
def sample_soul():
    """Sample soul for testing."""
    return Soul(id="test_soul", role="Tester", system_prompt="You test things.")


@pytest.mark.asyncio
async def test_step_executes_hooks(mock_runner, sample_soul):
    """
    AC-1: pytest packages/core/tests/test_primitives_extended.py::test_step_executes_hooks -v passes
    - pre_hook runs, then block, then post_hook
    - state flows through all three phases
    """
    # Setup mock runner to return a result
    mock_runner.execute.return_value = ExecutionResult(
        task_id="t1", soul_id="test_soul", output="Block output"
    )

    # Create a LinearBlock as the wrapped block
    block = LinearBlock("linear1", sample_soul, mock_runner)
    initial_state = WorkflowState()

    # Define hooks that track execution order by mutating state.metadata
    def pre_hook(state: WorkflowState) -> WorkflowState:
        return state.model_copy(
            update={
                "metadata": {
                    **state.metadata,
                    "pre_hook_ran": True,
                    "execution_order": ["pre_hook"],
                }
            }
        )

    def post_hook(state: WorkflowState) -> WorkflowState:
        execution_order = state.metadata.get("execution_order", [])
        execution_order.append("post_hook")
        return state.model_copy(
            update={
                "metadata": {
                    **state.metadata,
                    "post_hook_ran": True,
                    "execution_order": execution_order,
                }
            }
        )

    # Create Step with both hooks
    step = Step(block, pre_hook=pre_hook, post_hook=post_hook)

    # Execute
    result_state = await step.execute(initial_state)

    # Verify execution order: pre_hook → block → post_hook
    assert result_state.metadata["pre_hook_ran"] is True
    assert result_state.metadata["post_hook_ran"] is True
    assert result_state.metadata["execution_order"] == ["pre_hook", "post_hook"]

    # Verify block executed successfully
    assert result_state.results["linear1"].output == "Block output"
    assert len(result_state.execution_log) == 1
    assert "[Block linear1]" in result_state.execution_log[0]["content"]


@pytest.mark.asyncio
async def test_step_no_hooks(mock_runner, sample_soul):
    """
    AC-4: Hooks can be None, in which case that phase is skipped.
    Test with both hooks as None - verify block executes normally.
    """
    # Setup mock runner
    mock_runner.execute.return_value = ExecutionResult(
        task_id="t1", soul_id="test_soul", output="Block output"
    )

    # Create block and state
    block = LinearBlock("linear1", sample_soul, mock_runner)
    initial_state = WorkflowState()

    # Create Step with no hooks
    step = Step(block, pre_hook=None, post_hook=None)

    # Execute
    result_state = await step.execute(initial_state)

    # Verify block executed normally
    assert result_state.results["linear1"].output == "Block output"
    assert len(result_state.execution_log) == 1
    assert "[Block linear1]" in result_state.execution_log[0]["content"]


@pytest.mark.asyncio
async def test_step_only_pre_hook(mock_runner, sample_soul):
    """
    AC-4: Test with only pre_hook present, post_hook=None.
    """
    # Setup mock runner
    mock_runner.execute.return_value = ExecutionResult(
        task_id="t1", soul_id="test_soul", output="Block output"
    )

    # Create block and state
    block = LinearBlock("linear1", sample_soul, mock_runner)
    initial_state = WorkflowState()

    # Define only pre_hook
    def pre_hook(state: WorkflowState) -> WorkflowState:
        return state.model_copy(update={"metadata": {**state.metadata, "pre_hook_ran": True}})

    # Create Step with only pre_hook
    step = Step(block, pre_hook=pre_hook, post_hook=None)

    # Execute
    result_state = await step.execute(initial_state)

    # Verify pre_hook ran
    assert result_state.metadata["pre_hook_ran"] is True

    # Verify block executed
    assert result_state.results["linear1"].output == "Block output"


@pytest.mark.asyncio
async def test_step_only_post_hook(mock_runner, sample_soul):
    """
    AC-4: Test with only post_hook present, pre_hook=None.
    """
    # Setup mock runner
    mock_runner.execute.return_value = ExecutionResult(
        task_id="t1", soul_id="test_soul", output="Block output"
    )

    # Create block and state
    block = LinearBlock("linear1", sample_soul, mock_runner)
    initial_state = WorkflowState()

    # Define only post_hook
    def post_hook(state: WorkflowState) -> WorkflowState:
        return state.model_copy(update={"metadata": {**state.metadata, "post_hook_ran": True}})

    # Create Step with only post_hook
    step = Step(block, pre_hook=None, post_hook=post_hook)

    # Execute
    result_state = await step.execute(initial_state)

    # Verify post_hook ran
    assert result_state.metadata["post_hook_ran"] is True

    # Verify block executed
    assert result_state.results["linear1"].output == "Block output"


@pytest.mark.asyncio
async def test_step_state_flows_through_phases(mock_runner, sample_soul):
    """
    Verify that state flows correctly through all three phases:
    - pre_hook modifies state
    - block sees modified state and updates it
    - post_hook sees block's output and can further modify
    """
    # Setup mock runner
    mock_runner.execute.return_value = ExecutionResult(
        task_id="t1", soul_id="test_soul", output="Block output"
    )

    # Create block and state
    block = LinearBlock("linear1", sample_soul, mock_runner)
    initial_state = WorkflowState()

    # Define hooks that add to shared_memory to track state flow
    def pre_hook(state: WorkflowState) -> WorkflowState:
        return state.model_copy(
            update={"shared_memory": {**state.shared_memory, "pre_value": "from_pre"}}
        )

    def post_hook(state: WorkflowState) -> WorkflowState:
        # Post hook can see both pre_hook's addition and block's result
        assert state.shared_memory["pre_value"] == "from_pre"
        assert state.results["linear1"].output == "Block output"
        return state.model_copy(
            update={"shared_memory": {**state.shared_memory, "post_value": "from_post"}}
        )

    # Create Step
    step = Step(block, pre_hook=pre_hook, post_hook=post_hook)

    # Execute
    result_state = await step.execute(initial_state)

    # Verify all state modifications are present in final state
    assert result_state.shared_memory["pre_value"] == "from_pre"
    assert result_state.shared_memory["post_value"] == "from_post"
    assert result_state.results["linear1"].output == "Block output"
