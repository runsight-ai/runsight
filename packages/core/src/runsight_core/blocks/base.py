"""
BaseBlock abstract interface for workflow blocks.
"""

import asyncio
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from runsight_core.block_io import BlockContext, BlockOutput
    from runsight_core.state import WorkflowState


class NodeKilledException(Exception):
    """Raised when a block is killed during execution."""

    def __init__(self, block_id: str):
        super().__init__(f"Node '{block_id}' was killed")
        self.block_id = block_id


class BaseBlock(ABC):
    """
    Abstract base for workflow blocks. All concrete blocks must implement execute().

    Constructor contract: All subclasses MUST accept block_id as first parameter.
    """

    def __init__(self, block_id: str, *, retry_config=None):
        """
        Args:
            block_id: Unique identifier for this block instance within a blueprint.
                     Used as the key in state.results.
            retry_config: Optional RetryConfig for retry execution in workflow runner.

        Raises:
            ValueError: If block_id is empty string.
        """
        if not block_id:
            raise ValueError("block_id cannot be empty")
        self.block_id = block_id
        self.assertions = None
        self.exit_conditions = None
        self.retry_config = retry_config
        self.stateful = False
        self._pause_event: asyncio.Event = asyncio.Event()
        self._pause_event.set()  # not paused by default
        self._kill_flag: bool = False

    async def _check_pause(self) -> None:
        """
        Check pause/kill status. Blocks if paused; raises NodeKilledException if killed.

        Call at LLM boundaries to enable cooperative pause/kill.

        Raises:
            NodeKilledException: If the kill flag is set after the pause event is signaled.
        """
        await self._pause_event.wait()
        if self._kill_flag:
            raise NodeKilledException(self.block_id)

    async def write_artifact(
        self, state: WorkflowState, key: str, content: str, metadata: dict | None = None
    ) -> str:
        """Write an artifact via the state's artifact store.

        Args:
            state: Current workflow state (must have an artifact_store attached).
            key: Artifact key/name.
            content: String content to persist.
            metadata: Optional metadata dict to attach to the artifact.

        Returns:
            The ref string produced by the store.

        Raises:
            RuntimeError: If state.artifact_store is None.
        """
        if state.artifact_store is None:
            raise RuntimeError(
                "No ArtifactStore attached to WorkflowState. "
                "Provide an artifact_store when constructing the state."
            )
        return await state.artifact_store.write(key, content, metadata=metadata)

    async def read_artifact(self, state: WorkflowState, ref: str) -> str:
        """Read an artifact by ref via the state's artifact store.

        Args:
            state: Current workflow state (must have an artifact_store attached).
            ref: The artifact reference string returned by a previous write.

        Returns:
            The artifact content string.

        Raises:
            RuntimeError: If state.artifact_store is None.
        """
        if state.artifact_store is None:
            raise RuntimeError(
                "No ArtifactStore attached to WorkflowState. "
                "Provide an artifact_store when constructing the state."
            )
        return await state.artifact_store.read(ref)

    @abstractmethod
    async def execute(self, ctx: "BlockContext") -> "BlockOutput":
        """
        Execute this block's logic.

        Args:
            ctx: BlockContext containing instruction, inputs, soul, model, etc.

        Returns:
            BlockOutput with output, exit_handle, cost, tokens, and optional updates.

        Raises:
            ValueError: If required inputs are missing.
            Exception: If execution fails (propagates to Workflow.run() caller).
        """
        pass
