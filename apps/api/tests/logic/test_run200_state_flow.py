"""Tests for RUN-200: execution_service state flow — pass WorkflowState to Workflow.run().

Updated for RUN-866: Task/current_task removed. Workflow.run() now receives
inputs as a keyword argument, which seeds state.results["workflow"].
"""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest
from runsight_core.state import WorkflowState

from runsight_api.logic.services.execution_service import ExecutionService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_service(**overrides):
    """Create an ExecutionService with mocked repos."""
    return ExecutionService(
        run_repo=overrides.get("run_repo", Mock()),
        workflow_repo=overrides.get("workflow_repo", Mock()),
        provider_repo=overrides.get("provider_repo", Mock()),
        engine=overrides.get("engine", None),
    )


# ---------------------------------------------------------------------------
# 1. wf.run() receives WorkflowState, not a string
# ---------------------------------------------------------------------------


class TestRunReceivesWorkflowState:
    """Verify that _run_workflow passes WorkflowState to wf.run()."""

    @pytest.mark.asyncio
    async def test_wf_run_called_with_workflow_state_instance(self):
        """wf.run() first positional arg must be a WorkflowState, not a string."""
        svc = _make_service()

        mock_wf = Mock()
        mock_wf.run = AsyncMock(return_value=WorkflowState())

        inputs = {"topic": "Summarize the document"}

        await svc._run_workflow("run_1", mock_wf, inputs)

        mock_wf.run.assert_called_once()
        first_arg = mock_wf.run.call_args[0][0]
        assert isinstance(first_arg, WorkflowState), (
            f"Expected WorkflowState, got {type(first_arg).__name__}"
        )

    @pytest.mark.asyncio
    async def test_wf_run_not_called_with_string(self):
        """wf.run() must NOT receive the raw instruction string as first arg."""
        svc = _make_service()

        mock_wf = Mock()
        mock_wf.run = AsyncMock(return_value=WorkflowState())

        inputs = {"topic": "Analyze this data"}

        await svc._run_workflow("run_2", mock_wf, inputs)

        mock_wf.run.assert_called_once()
        first_arg = mock_wf.run.call_args[0][0]
        assert not isinstance(first_arg, str), "wf.run() received a string instead of WorkflowState"


# ---------------------------------------------------------------------------
# 2. inputs passed to wf.run() as keyword argument
# ---------------------------------------------------------------------------


class TestInputsPassedToWorkflowRun:
    """Verify that inputs dict is forwarded to wf.run(inputs=...)."""

    @pytest.mark.asyncio
    async def test_inputs_passed_as_keyword(self):
        """wf.run() must receive inputs as a keyword argument."""
        svc = _make_service()

        mock_wf = Mock()
        mock_wf.run = AsyncMock(return_value=WorkflowState())

        inputs = {"customer_id": "123", "reason": "defective"}

        await svc._run_workflow("run_3", mock_wf, inputs)

        mock_wf.run.assert_called_once()
        call_kwargs = mock_wf.run.call_args[1]
        assert "inputs" in call_kwargs, "wf.run() must receive inputs= keyword arg"
        assert call_kwargs["inputs"] == inputs

    @pytest.mark.asyncio
    async def test_empty_inputs_forwarded(self):
        """Empty inputs dict is still forwarded to wf.run()."""
        svc = _make_service()

        mock_wf = Mock()
        mock_wf.run = AsyncMock(return_value=WorkflowState())

        await svc._run_workflow("run_4", mock_wf, {})

        call_kwargs = mock_wf.run.call_args[1]
        assert call_kwargs["inputs"] == {}


# ---------------------------------------------------------------------------
# 3. observer passed to wf.run()
# ---------------------------------------------------------------------------


class TestObserverReceivesRealState:
    """Verify that wf.run() receives the observer."""

    @pytest.mark.asyncio
    async def test_observer_passed_to_wf_run(self):
        """wf.run() must receive the observer keyword arg."""
        svc = _make_service()

        mock_wf = Mock()
        mock_wf.run = AsyncMock(return_value=WorkflowState())

        inputs = {"data": "Process data"}

        with patch(
            "runsight_api.logic.services.execution_service.CompositeObserver"
        ) as MockComposite:
            mock_observer = Mock()
            MockComposite.return_value = mock_observer

            await svc._run_workflow("run_5", mock_wf, inputs)

        mock_wf.run.assert_called_once()
        first_arg = mock_wf.run.call_args[0][0]
        assert isinstance(first_arg, WorkflowState)

        assert mock_wf.run.call_args[1].get("observer") is mock_observer, (
            "observer must be passed to wf.run() so Workflow.run() can fire events"
        )


# ---------------------------------------------------------------------------
# 4. Integration: full launch_execution path passes WorkflowState + inputs
# ---------------------------------------------------------------------------


class TestLaunchExecutionStateFlow:
    """End-to-end test through launch_execution to verify the state flow."""

    @pytest.mark.asyncio
    async def test_launch_execution_passes_workflow_state_and_inputs(self):
        """Full path: launch_execution -> _run_workflow -> wf.run(WorkflowState, inputs=...)."""
        workflow_repo = Mock()
        provider_repo = Mock()

        mock_entity = Mock()
        mock_entity.yaml = (
            "workflow:\n  name: test\n  entry: b1\n  transitions: []\n"
            "blocks:\n  b1:\n    type: linear\n    soul_ref: test\n"
            "souls: {}\nconfig: {}"
        )
        workflow_repo.get_by_id.return_value = mock_entity
        provider_repo.get_by_type.return_value = None

        svc = _make_service(
            workflow_repo=workflow_repo,
            provider_repo=provider_repo,
        )

        inputs = {"topic": "Run the full workflow"}

        with patch(
            "runsight_api.logic.services.execution_service.parse_workflow_yaml"
        ) as mock_parse:
            mock_wf = Mock()
            mock_wf.run = AsyncMock(return_value=WorkflowState())
            mock_parse.return_value = mock_wf

            await svc.launch_execution("run_e2e", "wf_1", inputs)

            # Wait for background task to complete
            await asyncio.sleep(0.1)

            mock_wf.run.assert_called_once()
            first_arg = mock_wf.run.call_args[0][0]
            assert isinstance(first_arg, WorkflowState), (
                f"Expected WorkflowState, got {type(first_arg).__name__}"
            )
            call_kwargs = mock_wf.run.call_args[1]
            assert call_kwargs["inputs"] == inputs
