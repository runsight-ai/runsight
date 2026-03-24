"""
Integration tests for **kwargs compatibility in BaseBlock implementations.

This module tests the cross-feature interaction between WorkflowBlock and
the block implementations that were updated to accept **kwargs in their
execute() signatures. This tests the conflict resolution from merging:
- TeamLeadBlock
- EngineeringManagerBlock

The **kwargs are required for WorkflowBlock to pass call_stack and
workflow_registry through the workflow execution chain without raising
TypeError.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from runsight_core.state import WorkflowState
from runsight_core import (
    TeamLeadBlock,
    EngineeringManagerBlock,
    WorkflowBlock,
)
from runsight_core.yaml.registry import WorkflowRegistry
from runsight_core.primitives import Soul


class TestTeamLeadBlockKwargsCompatibility:
    """Test TeamLeadBlock accepts and ignores **kwargs."""

    @pytest.mark.asyncio
    async def test_team_lead_block_execute_with_call_stack_kwarg(self):
        """Verify TeamLeadBlock.execute() accepts call_stack kwarg without error."""
        # Arrange
        block = TeamLeadBlock(
            block_id="team_lead_test",
            failure_context_keys=["error_key"],
            team_lead_soul=MagicMock(spec=Soul),
            runner=AsyncMock(),
        )

        state = WorkflowState()
        state = state.model_copy(update={"shared_memory": {"error_key": "error value"}})

        # Mock runner.execute_task
        mock_result = MagicMock()
        mock_result.output = "Test recommendation"
        mock_result.cost_usd = 0.01
        mock_result.total_tokens = 100
        block.runner.execute_task = AsyncMock(return_value=mock_result)

        # Act - Pass call_stack as kwarg (this would fail without **kwargs)
        result_state = await block.execute(
            state,
            call_stack=["parent_wf", "child_wf"],  # Should be accepted and ignored
        )

        # Assert
        assert result_state is not None
        assert "team_lead_test" in result_state.results

    @pytest.mark.asyncio
    async def test_team_lead_block_execute_with_workflow_registry_kwarg(self):
        """Verify TeamLeadBlock.execute() accepts workflow_registry kwarg without error."""
        # Arrange
        block = TeamLeadBlock(
            block_id="team_lead_test",
            failure_context_keys=["error_key"],
            team_lead_soul=MagicMock(spec=Soul),
            runner=AsyncMock(),
        )

        state = WorkflowState()
        state = state.model_copy(update={"shared_memory": {"error_key": "error value"}})

        # Mock runner.execute_task
        mock_result = MagicMock()
        mock_result.output = "Test recommendation"
        mock_result.cost_usd = 0.01
        mock_result.total_tokens = 100
        block.runner.execute_task = AsyncMock(return_value=mock_result)

        registry = WorkflowRegistry()

        # Act - Pass workflow_registry as kwarg
        result_state = await block.execute(
            state,
            workflow_registry=registry,  # Should be accepted and ignored
        )

        # Assert
        assert result_state is not None
        assert "team_lead_test" in result_state.results

    @pytest.mark.asyncio
    async def test_team_lead_block_execute_with_multiple_kwargs(self):
        """Verify TeamLeadBlock.execute() accepts multiple **kwargs."""
        # Arrange
        block = TeamLeadBlock(
            block_id="team_lead_test",
            failure_context_keys=["error_key"],
            team_lead_soul=MagicMock(spec=Soul),
            runner=AsyncMock(),
        )

        state = WorkflowState()
        state = state.model_copy(update={"shared_memory": {"error_key": "error value"}})

        # Mock runner.execute_task
        mock_result = MagicMock()
        mock_result.output = "Test recommendation"
        mock_result.cost_usd = 0.01
        mock_result.total_tokens = 100
        block.runner.execute_task = AsyncMock(return_value=mock_result)

        registry = WorkflowRegistry()

        # Act - Pass multiple kwargs
        result_state = await block.execute(
            state,
            call_stack=["parent_wf"],
            workflow_registry=registry,
            extra_arg="should_be_ignored",
        )

        # Assert
        assert result_state is not None
        assert "team_lead_test" in result_state.results


class TestEngineeringManagerBlockKwargsCompatibility:
    """Test EngineeringManagerBlock accepts and ignores **kwargs."""

    @pytest.mark.asyncio
    async def test_engineering_manager_block_execute_with_call_stack_kwarg(self):
        """Verify EngineeringManagerBlock.execute() accepts call_stack kwarg."""
        # Arrange
        block = EngineeringManagerBlock(
            block_id="eng_mgr_test",
            engineering_manager_soul=MagicMock(spec=Soul),
            runner=AsyncMock(),
        )

        state = WorkflowState()
        state = state.model_copy(update={"current_task": MagicMock(instruction="test task")})

        # Mock runner.execute_task
        mock_result = MagicMock()
        mock_result.output = "1. step_one: Description\n2. step_two: Description"
        mock_result.cost_usd = 0.01
        mock_result.total_tokens = 100
        block.runner.execute_task = AsyncMock(return_value=mock_result)

        # Act
        result_state = await block.execute(
            state,
            call_stack=["parent_wf"],  # Should be accepted and ignored
        )

        # Assert
        assert result_state is not None
        assert "eng_mgr_test" in result_state.results

    @pytest.mark.asyncio
    async def test_engineering_manager_block_execute_with_workflow_registry_kwarg(self):
        """Verify EngineeringManagerBlock.execute() accepts workflow_registry kwarg."""
        # Arrange
        block = EngineeringManagerBlock(
            block_id="eng_mgr_test",
            engineering_manager_soul=MagicMock(spec=Soul),
            runner=AsyncMock(),
        )

        state = WorkflowState()
        state = state.model_copy(update={"current_task": MagicMock(instruction="test task")})

        # Mock runner.execute_task
        mock_result = MagicMock()
        mock_result.output = "1. step_one: Description"
        mock_result.cost_usd = 0.01
        mock_result.total_tokens = 100
        block.runner.execute_task = AsyncMock(return_value=mock_result)

        registry = WorkflowRegistry()

        # Act
        result_state = await block.execute(
            state,
            workflow_registry=registry,  # Should be accepted and ignored
        )

        # Assert
        assert result_state is not None
        assert "eng_mgr_test" in result_state.results


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


class TestBackwardCompatibilityWithoutKwargs:
    """
    Test backward compatibility: blocks work without **kwargs params
    even when called without them.
    """

    @pytest.mark.asyncio
    async def test_team_lead_block_execute_without_kwargs(self):
        """Verify TeamLeadBlock.execute() works when called without kwargs."""
        # Arrange
        block = TeamLeadBlock(
            block_id="team_lead_test",
            failure_context_keys=["error_key"],
            team_lead_soul=MagicMock(spec=Soul),
            runner=AsyncMock(),
        )

        state = WorkflowState()
        state = state.model_copy(update={"shared_memory": {"error_key": "error value"}})

        # Mock runner.execute_task
        mock_result = MagicMock()
        mock_result.output = "Test recommendation"
        mock_result.cost_usd = 0.01
        mock_result.total_tokens = 100
        block.runner.execute_task = AsyncMock(return_value=mock_result)

        # Act - Call without any kwargs
        result_state = await block.execute(state)

        # Assert
        assert result_state is not None
        assert "team_lead_test" in result_state.results
