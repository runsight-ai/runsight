"""
BaseBlock abstract interface for workflow blocks.
"""

import asyncio
from abc import ABC, abstractmethod
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
        self.retry_config = retry_config
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

    @abstractmethod
    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        """
        Execute this block's logic using the provided state.

        Args:
            state: Current workflow state. MUST NOT be mutated directly.

        Returns:
            New WorkflowState with updated results, messages, or shared_memory.
            MUST include this block's output in state.results[self.block_id].

        Raises:
            ValueError: If required inputs are missing from state.
            Exception: If execution fails (propagates to Workflow.run() caller).
        """
        pass
