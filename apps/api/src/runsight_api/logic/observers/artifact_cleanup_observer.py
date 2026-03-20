"""ArtifactCleanupObserver: triggers artifact cleanup when the root workflow finishes."""

import asyncio
import logging

from runsight_core.artifacts import ArtifactStore
from runsight_core.state import WorkflowState

logger = logging.getLogger(__name__)


class ArtifactCleanupObserver:
    """Implements WorkflowObserver protocol. Cleans up artifacts when the root workflow
    completes or errors. Child workflow events are ignored."""

    def __init__(self, artifact_store: ArtifactStore, root_workflow_name: str) -> None:
        self.artifact_store = artifact_store
        self.root_workflow_name = root_workflow_name

    # ------------------------------------------------------------------
    # Cleanup helper
    # ------------------------------------------------------------------

    def _schedule_cleanup(self) -> None:
        """Fire-and-forget async cleanup, swallowing any errors."""

        async def _do_cleanup() -> None:
            try:
                await self.artifact_store.cleanup()
            except Exception:
                logger.warning("ArtifactCleanupObserver: cleanup failed", exc_info=True)

        asyncio.ensure_future(_do_cleanup())

    # ------------------------------------------------------------------
    # WorkflowObserver protocol methods
    # ------------------------------------------------------------------

    def on_workflow_start(self, workflow_name: str, state: WorkflowState) -> None:
        pass

    def on_block_start(self, workflow_name: str, block_id: str, block_type: str) -> None:
        pass

    def on_block_complete(
        self,
        workflow_name: str,
        block_id: str,
        block_type: str,
        duration_s: float,
        state: WorkflowState,
    ) -> None:
        pass

    def on_block_error(
        self,
        workflow_name: str,
        block_id: str,
        block_type: str,
        duration_s: float,
        error: Exception,
    ) -> None:
        pass

    def on_workflow_complete(
        self, workflow_name: str, state: WorkflowState, duration_s: float
    ) -> None:
        if workflow_name == self.root_workflow_name:
            self._schedule_cleanup()

    def on_workflow_error(self, workflow_name: str, error: Exception, duration_s: float) -> None:
        if workflow_name == self.root_workflow_name:
            self._schedule_cleanup()
