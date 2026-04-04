"""Tests for ArtifactCleanupObserver fire-and-forget fix — RUN-318.

Verifies cleanup task reference is stored (not fire-and-forget)
and cleanup completes reliably.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from runsight_core.state import WorkflowState

from runsight_api.logic.observers.artifact_cleanup_observer import (
    ArtifactCleanupObserver,
)


class TestCleanupTaskStored:
    @pytest.mark.asyncio
    async def test_cleanup_task_reference_stored(self) -> None:
        store = MagicMock()
        store.cleanup = AsyncMock()
        obs = ArtifactCleanupObserver(artifact_store=store, root_workflow_name="wf")

        state = WorkflowState()
        obs.on_workflow_complete("wf", state, 1.0)

        assert obs._cleanup_task is not None
        assert isinstance(obs._cleanup_task, asyncio.Task)
        await obs._cleanup_task


class TestCleanupCompletes:
    @pytest.mark.asyncio
    async def test_cleanup_called_on_workflow_complete(self) -> None:
        store = MagicMock()
        store.cleanup = AsyncMock()
        obs = ArtifactCleanupObserver(artifact_store=store, root_workflow_name="wf")

        state = WorkflowState()
        obs.on_workflow_complete("wf", state, 1.0)
        await obs._cleanup_task

        store.cleanup.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_cleanup_called_on_workflow_error(self) -> None:
        store = MagicMock()
        store.cleanup = AsyncMock()
        obs = ArtifactCleanupObserver(artifact_store=store, root_workflow_name="wf")

        obs.on_workflow_error("wf", ValueError("boom"), 1.0)
        await obs._cleanup_task

        store.cleanup.assert_awaited_once()


class TestCleanupErrorHandling:
    @pytest.mark.asyncio
    async def test_cleanup_survives_store_failure(self) -> None:
        store = MagicMock()
        store.cleanup = AsyncMock(side_effect=RuntimeError("disk full"))
        obs = ArtifactCleanupObserver(artifact_store=store, root_workflow_name="wf")

        state = WorkflowState()
        obs.on_workflow_complete("wf", state, 1.0)
        await obs._cleanup_task  # should not raise
