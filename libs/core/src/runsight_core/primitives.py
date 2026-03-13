"""
Core primitives for Runsight Agent OS.
"""

from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from runsight_core.blocks.base import BaseBlock
    from runsight_core.state import WorkflowState


class Soul(BaseModel):
    """
    Represents an agent's persona, capabilities, and expected output schema.
    """

    id: str = Field(..., description="Unique identifier for the soul (e.g., 'researcher_v1')")
    role: str = Field(..., description="The role of the agent (e.g., 'Senior Researcher')")
    system_prompt: str = Field(
        ..., description="The system instructions defining the agent's behavior and constraints"
    )
    tools: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="Optional list of tools the agent can use"
    )
    model_name: Optional[str] = Field(
        default=None, description="Optional model override (uses runner default if None)"
    )


class Task(BaseModel):
    """
    Represents an isolated instruction for an agent to execute.
    """

    id: str = Field(..., description="Unique identifier for the task")
    instruction: str = Field(..., description="The main instruction or prompt for the task")
    context: Optional[str] = Field(
        default=None, description="Additional context or background information for the task"
    )


class Step:
    """
    Wrapper for BaseBlock with pre/post hook execution.

    Use Case: Add logging, validation, or state transformation around blocks.
    Example: pre_hook = log start time, post_hook = log end time + duration.

    Note: Hooks must be synchronous. For async operations, use a block instead.
    """

    def __init__(
        self,
        block: "BaseBlock",
        pre_hook: Optional[Callable[["WorkflowState"], "WorkflowState"]] = None,
        post_hook: Optional[Callable[["WorkflowState"], "WorkflowState"]] = None,
    ) -> None:
        """
        Args:
            block: The block to wrap.
            pre_hook: Optional function to run before block execution.
                     Receives state, returns modified state (or same state).
                     MUST be synchronous (not async).
            post_hook: Optional function to run after block execution.
                      Receives state (output from block), returns modified state.
                      MUST be synchronous (not async).
        """
        self.block = block
        self.pre_hook = pre_hook
        self.post_hook = post_hook

    async def execute(self, state: "WorkflowState") -> "WorkflowState":
        """
        Execute pre_hook → block → post_hook in sequence.

        Args:
            state: Initial workflow state.

        Returns:
            Final state after all three phases (or fewer if hooks are None).

        Raises:
            Exception: Propagates any exception from hooks or block.
        """
        # Import at runtime to avoid circular import

        # Phase 1: Pre-hook (optional)
        if self.pre_hook is not None:
            state = self.pre_hook(state)

        # Phase 2: Block execution (required)
        state = await self.block.execute(state)

        # Phase 3: Post-hook (optional)
        if self.post_hook is not None:
            state = self.post_hook(state)

        return state
