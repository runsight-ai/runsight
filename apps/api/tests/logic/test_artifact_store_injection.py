"""
Failing tests for RUN-184: ArtifactStore injection at ExecutionService._run_workflow.

Tests cover:
- ExecutionService._run_workflow creates InMemoryArtifactStore(run_id=run_id)
- The artifact_store is injected into the WorkflowState passed to workflow.run()
- After execution, the state has artifact_store set
"""

from unittest.mock import Mock

import pytest


def _import_execution_service():
    """Deferred import."""
    from runsight_api.logic.services.execution_service import ExecutionService

    return ExecutionService


# ==============================================================================
# ExecutionService injects InMemoryArtifactStore
# ==============================================================================


class TestArtifactStoreInjection:
    """ExecutionService._run_workflow should inject InMemoryArtifactStore into state."""

    @pytest.mark.asyncio
    async def test_run_workflow_injects_artifact_store(self):
        """_run_workflow creates InMemoryArtifactStore(run_id=run_id) and passes it in state."""
        ExecutionService = _import_execution_service()

        captured_states = []

        async def capture_run(state, **kwargs):
            captured_states.append(state)
            return state

        mock_wf = Mock()
        mock_wf.run = capture_run

        svc = ExecutionService(
            run_repo=Mock(),
            workflow_repo=Mock(),
            provider_repo=Mock(),
            engine=None,
        )

        await svc._run_workflow("run-42", mock_wf, {"instruction": "do something"})

        assert len(captured_states) == 1
        state = captured_states[0]
        assert state.artifact_store is not None

    @pytest.mark.asyncio
    async def test_injected_store_is_in_memory_artifact_store(self):
        """The injected artifact_store should be an InMemoryArtifactStore instance."""
        from runsight_core.artifacts import InMemoryArtifactStore

        ExecutionService = _import_execution_service()

        captured_states = []

        async def capture_run(state, **kwargs):
            captured_states.append(state)
            return state

        mock_wf = Mock()
        mock_wf.run = capture_run

        svc = ExecutionService(
            run_repo=Mock(),
            workflow_repo=Mock(),
            provider_repo=Mock(),
            engine=None,
        )

        await svc._run_workflow("run-42", mock_wf, {"instruction": "do something"})

        state = captured_states[0]
        assert isinstance(state.artifact_store, InMemoryArtifactStore)

    @pytest.mark.asyncio
    async def test_injected_store_has_correct_run_id(self):
        """The InMemoryArtifactStore should be created with run_id matching the execution run_id."""
        ExecutionService = _import_execution_service()

        captured_states = []

        async def capture_run(state, **kwargs):
            captured_states.append(state)
            return state

        mock_wf = Mock()
        mock_wf.run = capture_run

        svc = ExecutionService(
            run_repo=Mock(),
            workflow_repo=Mock(),
            provider_repo=Mock(),
            engine=None,
        )

        await svc._run_workflow("run-42", mock_wf, {"instruction": "do something"})

        state = captured_states[0]
        assert state.artifact_store.run_id == "run-42"

    @pytest.mark.asyncio
    async def test_different_runs_get_different_stores(self):
        """Each _run_workflow call should create a fresh InMemoryArtifactStore."""
        ExecutionService = _import_execution_service()

        captured_states = []

        async def capture_run(state, **kwargs):
            captured_states.append(state)
            return state

        mock_wf = Mock()
        mock_wf.run = capture_run

        svc = ExecutionService(
            run_repo=Mock(),
            workflow_repo=Mock(),
            provider_repo=Mock(),
            engine=None,
        )

        await svc._run_workflow("run-1", mock_wf, {"instruction": "first"})
        await svc._run_workflow("run-2", mock_wf, {"instruction": "second"})

        assert len(captured_states) == 2
        assert captured_states[0].artifact_store is not captured_states[1].artifact_store
        assert captured_states[0].artifact_store.run_id == "run-1"
        assert captured_states[1].artifact_store.run_id == "run-2"
