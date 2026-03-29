"""
WorkflowState data model for workflow execution context.
"""

from typing import Annotated, Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, SkipValidation

from runsight_core.artifacts import ArtifactStore
from runsight_core.primitives import Task


class BlockResult(BaseModel):
    """Structured result from a block execution."""

    output: str
    exit_handle: Optional[str] = None
    artifact_ref: Optional[str] = None
    artifact_type: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    @classmethod
    def from_string(cls, s: str) -> "BlockResult":
        return cls(output=s)

    def __str__(self) -> str:
        return self.output

    def __iter__(self):
        raise TypeError(f"'{type(self).__name__}' object is not iterable")


class WorkflowState(BaseModel):
    """
    Workflow execution context. Blocks receive state, return updated state.

    Best Practice: Use model_copy(update={...}) to create new state instances
    rather than mutating fields directly.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    execution_log: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Execution audit log. Format: [{'role': 'system', 'content': '...'}]",
    )
    shared_memory: Dict[str, Any] = Field(
        default_factory=dict,
        description="Cross-block shared data. Keys: arbitrary strings. Values: JSON-serializable.",
    )
    current_task: Optional[Task] = Field(
        default=None,
        description="Active task being processed. Blocks read this to determine their work.",
    )
    results: Dict[str, BlockResult] = Field(
        default_factory=dict,
        description="Block outputs keyed by block_id. Values are BlockResult instances.",
    )

    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Workflow-level tracking: execution_start_time, blueprint_name, etc.",
    )
    total_cost_usd: float = Field(
        default=0.0,
        description="Cumulative cost in USD for all LLM calls in the workflow.",
    )
    total_tokens: int = Field(
        default=0,
        description="Cumulative token count for all LLM calls in the workflow.",
    )
    conversation_histories: Dict[str, List[Dict[str, Any]]] = Field(
        default_factory=dict,
        description="Per-block-soul conversation histories. Keys: '{block_id}_{soul_id}'. Values: list of message dicts.",
    )
    artifact_store: Optional[Annotated[ArtifactStore, SkipValidation]] = Field(
        default=None, exclude=True
    )
