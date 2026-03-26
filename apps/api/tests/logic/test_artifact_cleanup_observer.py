"""Red tests for RUN-185: ArtifactCleanupObserver.

Observer that cleans up artifacts when a workflow completes or errors.
Holds a direct reference to the ArtifactStore (injected via __init__),
and discriminates root vs child workflow completions using root_workflow_name.

Target module:
  apps/api/src/runsight_api/logic/observers/artifact_cleanup_observer.py

All tests should FAIL until the implementation exists.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from runsight_core.observer import WorkflowObserver
from runsight_core.state import WorkflowState


# ---------------------------------------------------------------------------
# Deferred import helper (module does not exist yet)
# ---------------------------------------------------------------------------


def _import_cleanup_observer():
    from runsight_api.logic.observers.artifact_cleanup_observer import (
        ArtifactCleanupObserver,
    )

    return ArtifactCleanupObserver


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_store():
    """Create a mock ArtifactStore with async cleanup method."""
    store = MagicMock()
    store.cleanup = AsyncMock()
    return store


@pytest.fixture
def observer(mock_store):
    """Create an ArtifactCleanupObserver for root workflow 'root_wf'."""
    ArtifactCleanupObserver = _import_cleanup_observer()
    return ArtifactCleanupObserver(artifact_store=mock_store, root_workflow_name="root_wf")


@pytest.fixture
def state():
    """Minimal WorkflowState for observer method calls."""
    return WorkflowState()


# ---------------------------------------------------------------------------
# 1. Class existence and protocol conformance
# ---------------------------------------------------------------------------


class TestArtifactCleanupObserverExists:
    def test_implements_workflow_observer_protocol(self):
        """ArtifactCleanupObserver satisfies the WorkflowObserver runtime_checkable protocol."""
        ArtifactCleanupObserver = _import_cleanup_observer()
        store = MagicMock()
        store.cleanup = AsyncMock()
        obs = ArtifactCleanupObserver(artifact_store=store, root_workflow_name="wf")
        assert isinstance(obs, WorkflowObserver)

    def test_constructor_accepts_artifact_store_and_root_workflow_name(self):
        """Constructor accepts artifact_store and root_workflow_name."""
        ArtifactCleanupObserver = _import_cleanup_observer()
        store = MagicMock()
        store.cleanup = AsyncMock()
        obs = ArtifactCleanupObserver(artifact_store=store, root_workflow_name="my_wf")
        assert obs is not None


# ---------------------------------------------------------------------------
# 2. on_workflow_complete — root workflow triggers cleanup
# ---------------------------------------------------------------------------


class TestOnWorkflowCompleteRootCleanup:
    """on_workflow_complete for the root workflow must call artifact_store.cleanup()."""

    @pytest.mark.asyncio
    async def test_cleanup_called_on_root_workflow_complete(self, mock_store, observer, state):
        """When workflow_name matches root_workflow_name, cleanup is called."""
        observer.on_workflow_complete("root_wf", state, 5.0)

        # cleanup() is async — give the event loop a tick to process
        await asyncio.sleep(0)

        mock_store.cleanup.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_cleanup_called_exactly_once(self, mock_store, observer, state):
        """Cleanup is called exactly once, not multiple times."""
        observer.on_workflow_complete("root_wf", state, 5.0)
        await asyncio.sleep(0)

        assert mock_store.cleanup.await_count == 1


# ---------------------------------------------------------------------------
# 3. on_workflow_complete — child workflow does NOT trigger cleanup
# ---------------------------------------------------------------------------


class TestOnWorkflowCompleteChildIgnored:
    """on_workflow_complete for a child workflow must NOT call cleanup."""

    @pytest.mark.asyncio
    async def test_child_workflow_complete_does_not_trigger_cleanup(
        self, mock_store, observer, state
    ):
        """When workflow_name does NOT match root_workflow_name, cleanup is skipped."""
        observer.on_workflow_complete("child_wf", state, 1.0)
        await asyncio.sleep(0)

        mock_store.cleanup.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_nested_child_workflow_does_not_trigger_cleanup(
        self, mock_store, observer, state
    ):
        """Deeply nested child workflows also do not trigger cleanup."""
        observer.on_workflow_complete("child_wf_level_2", state, 0.5)
        observer.on_workflow_complete("another_child", state, 0.8)
        await asyncio.sleep(0)

        mock_store.cleanup.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_child_complete_then_root_complete(self, mock_store, observer, state):
        """Child completions followed by root completion triggers cleanup exactly once."""
        observer.on_workflow_complete("child_wf", state, 0.5)
        observer.on_workflow_complete("another_child", state, 0.8)
        await asyncio.sleep(0)
        mock_store.cleanup.assert_not_awaited()

        observer.on_workflow_complete("root_wf", state, 5.0)
        await asyncio.sleep(0)
        mock_store.cleanup.assert_awaited_once()


# ---------------------------------------------------------------------------
# 4. on_workflow_error — root workflow triggers cleanup
# ---------------------------------------------------------------------------


class TestOnWorkflowErrorRootCleanup:
    """on_workflow_error for the root workflow must call artifact_store.cleanup()."""

    @pytest.mark.asyncio
    async def test_cleanup_called_on_root_workflow_error(self, mock_store, observer):
        """When workflow_name matches root_workflow_name on error, cleanup is called."""
        observer.on_workflow_error("root_wf", RuntimeError("boom"), 3.0)
        await asyncio.sleep(0)

        mock_store.cleanup.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_child_workflow_error_does_not_trigger_cleanup(self, mock_store, observer):
        """When workflow_name does NOT match root_workflow_name on error, cleanup is skipped."""
        observer.on_workflow_error("child_wf", RuntimeError("child failed"), 1.0)
        await asyncio.sleep(0)

        mock_store.cleanup.assert_not_awaited()


# ---------------------------------------------------------------------------
# 5. Cancellation (asyncio.CancelledError) triggers cleanup
# ---------------------------------------------------------------------------


class TestCancellationTriggersCleanup:
    """asyncio.CancelledError flows through on_workflow_error and triggers cleanup."""

    @pytest.mark.asyncio
    async def test_cancelled_error_triggers_cleanup(self, mock_store, observer):
        """CancelledError on the root workflow triggers cleanup."""
        observer.on_workflow_error("root_wf", asyncio.CancelledError(), 1.0)
        await asyncio.sleep(0)

        mock_store.cleanup.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_cancelled_error_on_child_does_not_trigger_cleanup(self, mock_store, observer):
        """CancelledError on a child workflow does NOT trigger cleanup."""
        observer.on_workflow_error("child_wf", asyncio.CancelledError(), 0.5)
        await asyncio.sleep(0)

        mock_store.cleanup.assert_not_awaited()


# ---------------------------------------------------------------------------
# 6. Edge case: cleanup failure is swallowed (don't mask original error)
# ---------------------------------------------------------------------------


class TestCleanupFailureSwallowed:
    """If artifact_store.cleanup() raises, the observer must log a warning
    and NOT re-raise — this avoids masking the original workflow error."""

    @pytest.mark.asyncio
    async def test_cleanup_exception_does_not_propagate_on_complete(self, state):
        """cleanup() raising on workflow complete does not propagate."""
        store = MagicMock()
        store.cleanup = AsyncMock(side_effect=OSError("disk full"))

        ArtifactCleanupObserver = _import_cleanup_observer()
        obs = ArtifactCleanupObserver(artifact_store=store, root_workflow_name="root_wf")

        # Must not raise
        obs.on_workflow_complete("root_wf", state, 5.0)
        await asyncio.sleep(0)

        store.cleanup.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_cleanup_exception_does_not_propagate_on_error(self):
        """cleanup() raising on workflow error does not propagate."""
        store = MagicMock()
        store.cleanup = AsyncMock(side_effect=RuntimeError("cleanup crashed"))

        ArtifactCleanupObserver = _import_cleanup_observer()
        obs = ArtifactCleanupObserver(artifact_store=store, root_workflow_name="root_wf")

        # Must not raise — don't mask the original workflow error
        obs.on_workflow_error("root_wf", ValueError("original error"), 2.0)
        await asyncio.sleep(0)

        store.cleanup.assert_awaited_once()


# ---------------------------------------------------------------------------
# 7. Idempotent cleanup (no error when store already cleaned)
# ---------------------------------------------------------------------------


class TestIdempotentCleanup:
    """Calling cleanup multiple times (store already cleaned) must be safe."""

    @pytest.mark.asyncio
    async def test_double_complete_calls_cleanup_twice_without_error(self, mock_store, state):
        """If on_workflow_complete fires twice for root, cleanup is called each time — no error."""
        ArtifactCleanupObserver = _import_cleanup_observer()
        obs = ArtifactCleanupObserver(artifact_store=mock_store, root_workflow_name="root_wf")

        obs.on_workflow_complete("root_wf", state, 5.0)
        await asyncio.sleep(0)
        obs.on_workflow_complete("root_wf", state, 5.0)
        await asyncio.sleep(0)

        assert mock_store.cleanup.await_count == 2


# ---------------------------------------------------------------------------
# 8. No-op methods do not trigger cleanup
# ---------------------------------------------------------------------------


class TestNoOpMethods:
    """Other observer methods (on_workflow_start, on_block_*) must NOT trigger cleanup."""

    @pytest.mark.asyncio
    async def test_on_workflow_start_does_not_trigger_cleanup(self, mock_store, observer):
        """on_workflow_start must not call cleanup."""
        observer.on_workflow_start("root_wf", WorkflowState())
        await asyncio.sleep(0)

        mock_store.cleanup.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_on_block_start_does_not_trigger_cleanup(self, mock_store, observer):
        """on_block_start must not call cleanup."""
        observer.on_block_start("root_wf", "block_a", "LinearBlock")
        await asyncio.sleep(0)

        mock_store.cleanup.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_on_block_complete_does_not_trigger_cleanup(self, mock_store, observer):
        """on_block_complete must not call cleanup."""
        observer.on_block_complete("root_wf", "block_a", "LinearBlock", 1.0, WorkflowState())
        await asyncio.sleep(0)

        mock_store.cleanup.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_on_block_error_does_not_trigger_cleanup(self, mock_store, observer):
        """on_block_error must not call cleanup."""
        observer.on_block_error("root_wf", "block_a", "LinearBlock", 1.0, RuntimeError("x"))
        await asyncio.sleep(0)

        mock_store.cleanup.assert_not_awaited()
