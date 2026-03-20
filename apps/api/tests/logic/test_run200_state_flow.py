"""Red tests for RUN-200: Fix execution_service state flow — pass WorkflowState to Workflow.run().

Bug: execution_service.py:134 passes a raw string to wf.run() instead of a WorkflowState.
These tests verify that _run_workflow constructs a proper WorkflowState with current_task
and passes it to Workflow.run().
"""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from runsight_api.logic.services.execution_service import ExecutionService
from runsight_core.primitives import Task
from runsight_core.state import WorkflowState


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

        task_data = {"instruction": "Summarize the document"}

        await svc._run_workflow("run_1", mock_wf, task_data)

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

        task_data = {"instruction": "Analyze this data"}

        await svc._run_workflow("run_2", mock_wf, task_data)

        mock_wf.run.assert_called_once()
        first_arg = mock_wf.run.call_args[0][0]
        assert not isinstance(first_arg, str), "wf.run() received a string instead of WorkflowState"


# ---------------------------------------------------------------------------
# 2. WorkflowState has current_task set from task_data
# ---------------------------------------------------------------------------


class TestCurrentTaskFromTaskData:
    """Verify that the WorkflowState passed to wf.run() has current_task populated."""

    @pytest.mark.asyncio
    async def test_state_has_current_task_set(self):
        """The WorkflowState passed to wf.run() must have current_task != None."""
        svc = _make_service()

        mock_wf = Mock()
        mock_wf.run = AsyncMock(return_value=WorkflowState())

        task_data = {"instruction": "Write a report"}

        await svc._run_workflow("run_3", mock_wf, task_data)

        first_arg = mock_wf.run.call_args[0][0]
        assert first_arg.current_task is not None, (
            "WorkflowState.current_task must be set, got None"
        )

    @pytest.mark.asyncio
    async def test_current_task_is_task_instance(self):
        """current_task must be a Task primitive instance."""
        svc = _make_service()

        mock_wf = Mock()
        mock_wf.run = AsyncMock(return_value=WorkflowState())

        task_data = {"instruction": "Do something"}

        await svc._run_workflow("run_4", mock_wf, task_data)

        first_arg = mock_wf.run.call_args[0][0]
        assert isinstance(first_arg.current_task, Task), (
            f"Expected Task, got {type(first_arg.current_task).__name__}"
        )

    @pytest.mark.asyncio
    async def test_current_task_has_id(self):
        """current_task.id must be set (non-empty string)."""
        svc = _make_service()

        mock_wf = Mock()
        mock_wf.run = AsyncMock(return_value=WorkflowState())

        task_data = {"instruction": "Test instruction"}

        await svc._run_workflow("run_5", mock_wf, task_data)

        first_arg = mock_wf.run.call_args[0][0]
        assert first_arg.current_task.id, "current_task.id must be a non-empty string"


# ---------------------------------------------------------------------------
# 3. current_task.instruction matches task_data["instruction"]
# ---------------------------------------------------------------------------


class TestInstructionMatches:
    """Verify that the instruction flows through correctly."""

    @pytest.mark.asyncio
    async def test_instruction_matches_task_data(self):
        """current_task.instruction must equal task_data['instruction']."""
        svc = _make_service()

        mock_wf = Mock()
        mock_wf.run = AsyncMock(return_value=WorkflowState())

        instruction = "Analyze the quarterly earnings report"
        task_data = {"instruction": instruction}

        await svc._run_workflow("run_6", mock_wf, task_data)

        first_arg = mock_wf.run.call_args[0][0]
        assert first_arg.current_task.instruction == instruction

    @pytest.mark.asyncio
    async def test_instruction_preserved_with_special_characters(self):
        """Instructions with special characters are passed through unchanged."""
        svc = _make_service()

        mock_wf = Mock()
        mock_wf.run = AsyncMock(return_value=WorkflowState())

        instruction = "What's the cost? $100 for <item> & 'stuff'\nnew line"
        task_data = {"instruction": instruction}

        await svc._run_workflow("run_7", mock_wf, task_data)

        first_arg = mock_wf.run.call_args[0][0]
        assert first_arg.current_task.instruction == instruction


# ---------------------------------------------------------------------------
# 4. observer.on_workflow_start receives real initial state
# ---------------------------------------------------------------------------


class TestObserverReceivesRealState:
    """Verify that on_workflow_start gets the state with current_task, not an empty one."""

    @pytest.mark.asyncio
    async def test_observer_on_workflow_start_gets_state_with_current_task(self):
        """on_workflow_start must receive a state where current_task is set."""
        svc = _make_service()

        mock_wf = Mock()
        mock_wf.run = AsyncMock(return_value=WorkflowState())

        task_data = {"instruction": "Process data"}

        captured_state = None

        with patch(
            "runsight_api.logic.services.execution_service.CompositeObserver"
        ) as MockComposite:
            mock_observer = Mock()
            MockComposite.return_value = mock_observer

            # Capture the state passed to on_workflow_start
            def capture_start(name, state):
                nonlocal captured_state
                captured_state = state

            mock_observer.on_workflow_start.side_effect = capture_start

            await svc._run_workflow("run_8", mock_wf, task_data)

        assert captured_state is not None, "on_workflow_start was not called"
        assert captured_state.current_task is not None, (
            "on_workflow_start received a state with current_task=None"
        )
        assert captured_state.current_task.instruction == "Process data"


# ---------------------------------------------------------------------------
# 5. Integration: full launch_execution path passes WorkflowState
# ---------------------------------------------------------------------------


class TestLaunchExecutionStateFlow:
    """End-to-end test through launch_execution to verify the state flow."""

    @pytest.mark.asyncio
    async def test_launch_execution_passes_workflow_state_to_run(self):
        """Full path: launch_execution -> _run_workflow -> wf.run(WorkflowState)."""
        workflow_repo = Mock()
        provider_repo = Mock()

        mock_entity = Mock()
        mock_entity.yaml = (
            "workflow:\n  name: test\n  entry: b1\n  transitions: []\n"
            "blocks:\n  b1:\n    type: placeholder\n    description: t\n"
            "souls: {}\nconfig: {}"
        )
        workflow_repo.get_by_id.return_value = mock_entity
        provider_repo.get_by_type.return_value = None

        svc = _make_service(
            workflow_repo=workflow_repo,
            provider_repo=provider_repo,
        )

        instruction = "Run the full workflow"

        with (
            patch(
                "runsight_api.logic.services.execution_service.parse_workflow_yaml"
            ) as mock_parse,
        ):
            mock_wf = Mock()
            mock_wf.run = AsyncMock(return_value=WorkflowState())
            mock_parse.return_value = mock_wf

            await svc.launch_execution("run_e2e", "wf_1", {"instruction": instruction})

            # Wait for background task to complete
            await asyncio.sleep(0.1)

            mock_wf.run.assert_called_once()
            first_arg = mock_wf.run.call_args[0][0]
            assert isinstance(first_arg, WorkflowState), (
                f"Expected WorkflowState, got {type(first_arg).__name__}"
            )
            assert first_arg.current_task is not None
            assert first_arg.current_task.instruction == instruction
