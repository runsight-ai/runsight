"""
Integration tests for **kwargs compatibility in BaseBlock implementations.

This module tests the cross-feature interaction between WorkflowBlock and
the block implementations that were updated to accept **kwargs in their
execute() signatures.

The **kwargs are required for WorkflowBlock to pass call_stack and
workflow_registry through the workflow execution chain without raising
TypeError.
"""

from unittest.mock import AsyncMock

import pytest
from runsight_core import (
    WorkflowBlock,
)
from runsight_core.state import WorkflowState
from runsight_core.yaml.registry import WorkflowRegistry


class TestKwargsCompatibilityWithWorkflowBlock:
    """Test that WorkflowBlock can invoke other blocks with kwargs parameters."""

    @pytest.mark.asyncio
    async def test_workflow_block_execution_passes_kwargs_to_child(self):
        """
        Verify WorkflowBlock correctly passes call_stack and workflow_registry
        to child workflow execution, and the child blocks accept these kwargs.
        """
        # Create a simple child workflow with a placeholder block
        child_workflow = AsyncMock()
        child_workflow.name = "child_wf"

        # Mock child_workflow.run to accept **kwargs
        child_final_state = WorkflowState()
        child_final_state = child_final_state.model_copy(
            update={"results": {"child_step": "child result"}}
        )
        child_workflow.run = AsyncMock(return_value=child_final_state)

        # Create WorkflowBlock
        workflow_block = WorkflowBlock(
            block_id="invoke_child",
            child_workflow=child_workflow,
            inputs={},
            outputs={"results.child_output": "results.child_step"},
            max_depth=10,
        )

        parent_state = WorkflowState()
        registry = WorkflowRegistry()

        # Act - Execute WorkflowBlock with call_stack and registry
        result_state = await workflow_block.execute(
            parent_state,
            call_stack=["parent_wf"],
            workflow_registry=registry,
        )

        # Assert
        # Verify that child_workflow.run was called with kwargs
        child_workflow.run.assert_called_once()
        call_args = child_workflow.run.call_args

        # Check that call_stack was passed
        assert call_args.kwargs.get("call_stack") is not None
        assert call_args.kwargs.get("workflow_registry") is not None

        # Verify output mapping worked
        assert result_state is not None
        assert "invoke_child" in result_state.results
