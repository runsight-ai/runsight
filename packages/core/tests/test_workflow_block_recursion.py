"""
Tests for WorkflowBlock cycle detection and depth limit enforcement.
"""

from unittest.mock import AsyncMock

import pytest
from runsight_core import WorkflowBlock
from runsight_core.state import WorkflowState


@pytest.fixture
def mock_child_workflow():
    """Create a mock child workflow."""
    workflow = AsyncMock()
    workflow.name = "cycle_child_workflow"
    workflow.run = AsyncMock()
    return workflow


async def _run_block_with_call_stack(block, state: WorkflowState, call_stack=None) -> WorkflowState:
    """Helper: build BlockContext with optional call_stack, run block, apply output."""
    from runsight_core.block_io import BlockContext, BlockOutput, apply_block_output

    ctx = BlockContext(
        block_id=block.block_id,
        instruction="",
        inputs={"call_stack": call_stack or []},
        state_snapshot=state,
    )
    output = await block.execute(ctx)
    if isinstance(output, WorkflowState):
        return output
    if isinstance(output, BlockOutput):
        return apply_block_output(state, block.block_id, output)
    return state


@pytest.mark.asyncio
async def test_cycle_detection_direct(mock_child_workflow):
    """Direct cycle detection (A→A)."""
    # Arrange
    block = WorkflowBlock(
        block_id="self_reference_workflow_block",
        child_workflow=mock_child_workflow,
        inputs={},
        outputs={},
        max_depth=10,
    )
    parent_state = WorkflowState()

    # Act & Assert
    with pytest.raises(RecursionError) as exc_info:
        await _run_block_with_call_stack(block, parent_state, call_stack=["cycle_child_workflow"])

    error_msg = str(exc_info.value)
    assert "cycle detected" in error_msg.lower()
    assert "cycle_child_workflow" in error_msg
    assert "call stack" in error_msg.lower()


@pytest.mark.asyncio
async def test_cycle_detection_indirect(mock_child_workflow):
    """Indirect cycle detection (A→B→A)."""
    # Arrange
    block = WorkflowBlock(
        block_id="invoke_child",
        child_workflow=mock_child_workflow,
        inputs={},
        outputs={},
        max_depth=10,
    )
    parent_state = WorkflowState()

    # Act & Assert
    with pytest.raises(RecursionError) as exc_info:
        await _run_block_with_call_stack(
            block,
            parent_state,
            call_stack=["root_cycle_workflow", "cycle_child_workflow"],
        )

    error_msg = str(exc_info.value)
    assert "cycle detected" in error_msg.lower()
    assert "cycle_child_workflow" in error_msg


@pytest.mark.asyncio
async def test_depth_limit(mock_child_workflow):
    """Depth limit enforcement."""
    # Arrange
    block = WorkflowBlock(
        block_id="depth_limit_workflow_block",
        child_workflow=mock_child_workflow,
        inputs={},
        outputs={},
        max_depth=3,
    )
    parent_state = WorkflowState()

    # Act & Assert - call_stack length equals max_depth
    with pytest.raises(RecursionError) as exc_info:
        await _run_block_with_call_stack(block, parent_state, call_stack=["a", "b", "c"])

    error_msg = str(exc_info.value)
    assert "maximum depth" in error_msg.lower() or "max_depth" in error_msg
    assert "3" in error_msg


@pytest.mark.asyncio
async def test_depth_within_limit(mock_child_workflow):
    """Test that execution proceeds when depth is within limit."""
    # Arrange
    mock_child_workflow.run = AsyncMock(return_value=WorkflowState())
    block = WorkflowBlock(
        block_id="depth_within_limit_workflow_block",
        child_workflow=mock_child_workflow,
        inputs={},
        outputs={},
        max_depth=5,
    )
    parent_state = WorkflowState()

    # Act - call_stack length < max_depth
    result = await _run_block_with_call_stack(block, parent_state, call_stack=["a", "b"])

    # Assert - should not raise RecursionError
    assert isinstance(result, WorkflowState)
    assert mock_child_workflow.run.called


@pytest.mark.asyncio
async def test_empty_call_stack_executes(mock_child_workflow):
    """Test that execution with empty call_stack works."""
    # Arrange
    mock_child_workflow.run = AsyncMock(return_value=WorkflowState())
    block = WorkflowBlock(
        block_id="no_stack",
        child_workflow=mock_child_workflow,
        inputs={},
        outputs={},
        max_depth=10,
    )
    parent_state = WorkflowState()

    # Act - default empty call_stack
    result = await _run_block_with_call_stack(block, parent_state)

    # Assert
    assert isinstance(result, WorkflowState)
    assert mock_child_workflow.run.called
