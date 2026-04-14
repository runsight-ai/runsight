"""
Tests for WorkflowBlock execution, mapping, and state isolation.
"""

from unittest.mock import AsyncMock

import pytest
from runsight_core import WorkflowBlock
from runsight_core.state import BlockResult, WorkflowState


@pytest.fixture
def base_parent_state():
    """Create a parent state with pre-populated data."""
    return WorkflowState(
        shared_memory={"research_topic": "AI safety", "other": "data"},
        results={"existing_result": BlockResult(output="previous output")},
        current_task=None,
        metadata={"workflow_id": "test_wf"},
    )


@pytest.fixture
def mock_child_workflow():
    """Create a mock child workflow."""
    workflow = AsyncMock()
    workflow.name = "child_wf"
    workflow.run = AsyncMock()
    return workflow


@pytest.mark.asyncio
async def test_input_mapping_success(base_parent_state, mock_child_workflow):
    """Test successful input mapping from parent to child."""
    # Arrange
    child_final_state = WorkflowState(
        results={"final": BlockResult(output="child_output")},
        total_cost_usd=0.05,
        total_tokens=50,
    )
    mock_child_workflow.run = AsyncMock(return_value=child_final_state)

    block = WorkflowBlock(
        block_id="test_input",
        child_workflow=mock_child_workflow,
        inputs={"shared_memory.topic": "shared_memory.research_topic"},
        outputs={},
        max_depth=10,
    )

    # Act
    await block.execute(base_parent_state)

    # Assert - verify child received the mapped input
    call_args = mock_child_workflow.run.call_args
    child_state = call_args[0][0]
    assert child_state.shared_memory.get("topic") == "AI safety"


@pytest.mark.asyncio
async def test_input_mapping_missing_key_raises(base_parent_state, mock_child_workflow):
    """AC-8: Input mapping raises KeyError for missing parent key."""
    # Arrange
    block = WorkflowBlock(
        block_id="test_missing",
        child_workflow=mock_child_workflow,
        inputs={"topic": "shared_memory.nonexistent_key"},
        outputs={},
        max_depth=10,
    )

    # Act & Assert
    with pytest.raises(KeyError) as exc_info:
        await block.execute(base_parent_state)

    error_msg = str(exc_info.value)
    assert "nonexistent_key" in error_msg
    assert "shared_memory" in error_msg


@pytest.mark.asyncio
async def test_output_mapping_success(base_parent_state, mock_child_workflow):
    """AC-9: Output mapping writes child results to parent state."""
    # Arrange
    child_final_state = WorkflowState(
        results={"final": BlockResult(output="child_output_value")},
        total_cost_usd=0.05,
        total_tokens=50,
    )
    mock_child_workflow.run = AsyncMock(return_value=child_final_state)

    block = WorkflowBlock(
        block_id="test_output",
        child_workflow=mock_child_workflow,
        inputs={},
        outputs={"results.parent_out": "results.final"},
        max_depth=10,
    )

    # Act
    result = await block.execute(base_parent_state)

    # Assert - verify output was written to parent state
    assert result.results.get("parent_out") == BlockResult(output="child_output_value")


@pytest.mark.asyncio
async def test_child_state_isolation(base_parent_state, mock_child_workflow):
    """AC-10: Child receives clean isolated state (only mapped inputs)."""
    # Arrange
    child_final_state = WorkflowState(
        results={"child_result": BlockResult(output="output")},
        total_cost_usd=0.01,
        total_tokens=10,
    )
    mock_child_workflow.run = AsyncMock(return_value=child_final_state)

    block = WorkflowBlock(
        block_id="test_isolation",
        child_workflow=mock_child_workflow,
        inputs={},  # Empty inputs
        outputs={},  # Empty outputs
        max_depth=10,
    )

    # Act
    await block.execute(base_parent_state)

    # Assert - child should receive empty state
    call_args = mock_child_workflow.run.call_args
    child_state = call_args[0][0]
    assert child_state.results == {}  # No parent results
    assert child_state.shared_memory == {}  # No parent shared_memory
    assert child_state.metadata == {}  # No parent metadata


@pytest.mark.asyncio
async def test_cost_propagation(base_parent_state, mock_child_workflow):
    """AC-11: Cost and token counts propagate from child to parent."""
    # Arrange
    child_final_state = WorkflowState(
        results={"final": BlockResult(output="output")},
        total_cost_usd=0.05,
        total_tokens=100,
    )
    mock_child_workflow.run = AsyncMock(return_value=child_final_state)

    block = WorkflowBlock(
        block_id="test_cost",
        child_workflow=mock_child_workflow,
        inputs={},
        outputs={},
        max_depth=10,
    )

    parent_state = WorkflowState(
        total_cost_usd=0.10,
        total_tokens=200,
    )

    # Act
    result = await block.execute(parent_state)

    # Assert
    assert result.total_cost_usd == pytest.approx(0.15)  # 0.10 + 0.05
    assert result.total_tokens == 300  # 200 + 100


@pytest.mark.asyncio
async def test_system_message_appended(base_parent_state, mock_child_workflow):
    """Test that system message is appended to messages."""
    # Arrange
    child_final_state = WorkflowState(
        results={"final": BlockResult(output="output")},
        total_cost_usd=0.05,
        total_tokens=50,
    )
    mock_child_workflow.run = AsyncMock(return_value=child_final_state)

    block = WorkflowBlock(
        block_id="test_msg",
        child_workflow=mock_child_workflow,
        inputs={},
        outputs={},
        max_depth=10,
    )

    # Act
    result = await block.execute(base_parent_state)

    # Assert - check for system message
    system_messages = [m for m in result.execution_log if m.get("role") == "system"]
    assert len(system_messages) > 0
    assert "test_msg" in system_messages[0]["content"]
    assert "child_wf" in system_messages[0]["content"]


@pytest.mark.asyncio
async def test_invalid_path_prefix_raises(base_parent_state, mock_child_workflow):
    """Test that invalid path prefix raises ValueError."""
    # Arrange
    block = WorkflowBlock(
        block_id="test_bad_prefix",
        child_workflow=mock_child_workflow,
        inputs={"x": "invalid_prefix.key"},
        outputs={},
        max_depth=10,
    )

    # Act & Assert
    with pytest.raises(ValueError) as exc_info:
        await block.execute(base_parent_state)

    error_msg = str(exc_info.value)
    assert "invalid" in error_msg.lower() or "unknown" in error_msg.lower()


@pytest.mark.asyncio
async def test_resolve_dotted_current_task(base_parent_state):
    """Test _resolve_dotted raises for deprecated current_task path (RUN-877)."""
    # Arrange
    from runsight_core.primitives import Task

    task = Task(id="task_1", instruction="Do something")
    state = WorkflowState(current_task=task)
    block = WorkflowBlock(
        block_id="test_resolve",
        child_workflow=AsyncMock(),
        inputs={},
        outputs={},
    )

    # Act & Assert — current_task is deprecated, must raise ValueError
    with pytest.raises(ValueError, match=r"(?i)deprecat|use results\.\*|use shared_memory\.\*"):
        block._resolve_dotted(state, "current_task")


@pytest.mark.asyncio
async def test_resolve_dotted_results(base_parent_state):
    """Test _resolve_dotted with results path."""
    # Arrange
    state = WorkflowState(results={"block_a": BlockResult(output="output_a")})
    block = WorkflowBlock(
        block_id="test_resolve",
        child_workflow=AsyncMock(),
        inputs={},
        outputs={},
    )

    # Act
    value = block._resolve_dotted(state, "results.block_a")

    # Assert
    assert value == BlockResult(output="output_a")


@pytest.mark.asyncio
async def test_resolve_dotted_shared_memory(base_parent_state):
    """Test _resolve_dotted with shared_memory path."""
    # Arrange
    state = WorkflowState(shared_memory={"topic": "AI safety"})
    block = WorkflowBlock(
        block_id="test_resolve",
        child_workflow=AsyncMock(),
        inputs={},
        outputs={},
    )

    # Act
    value = block._resolve_dotted(state, "shared_memory.topic")

    # Assert
    assert value == "AI safety"


@pytest.mark.asyncio
async def test_resolve_dotted_metadata(base_parent_state):
    """Test _resolve_dotted with metadata path."""
    # Arrange
    state = WorkflowState(metadata={"workflow_id": "wf_123"})
    block = WorkflowBlock(
        block_id="test_resolve",
        child_workflow=AsyncMock(),
        inputs={},
        outputs={},
    )

    # Act
    value = block._resolve_dotted(state, "metadata.workflow_id")

    # Assert
    assert value == "wf_123"


@pytest.mark.asyncio
async def test_write_dotted_results(base_parent_state):
    """Test _write_dotted with results path."""
    # Arrange
    state = WorkflowState(results={"existing": BlockResult(output="value")})
    block = WorkflowBlock(
        block_id="test_write",
        child_workflow=AsyncMock(),
        inputs={},
        outputs={},
    )

    # Act
    new_state = block._write_dotted(state, "results.new_key", "new_value")

    # Assert
    assert new_state.results["new_key"] == "new_value"
    assert new_state.results["existing"] == BlockResult(output="value")  # Original preserved


@pytest.mark.asyncio
async def test_write_dotted_shared_memory(base_parent_state):
    """Test _write_dotted with shared_memory path."""
    # Arrange
    state = WorkflowState(shared_memory={"existing": "value"})
    block = WorkflowBlock(
        block_id="test_write",
        child_workflow=AsyncMock(),
        inputs={},
        outputs={},
    )

    # Act
    new_state = block._write_dotted(state, "shared_memory.new_key", "new_value")

    # Assert
    assert new_state.shared_memory["new_key"] == "new_value"
    assert new_state.shared_memory["existing"] == "value"
