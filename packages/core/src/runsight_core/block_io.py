"""
BlockContext and BlockOutput models, and apply_block_output for RUN-883.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from runsight_core.artifacts import ArtifactStore
from runsight_core.primitives import Soul
from runsight_core.state import BlockResult, WorkflowState


class BlockContext(BaseModel):
    """Input context passed to a block during execution."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    block_id: str
    instruction: str
    context: Optional[str] = None
    inputs: Dict[str, Any] = Field(default_factory=dict)
    conversation_history: List[Dict] = Field(default_factory=list)
    soul: Optional[Soul] = None
    model_name: Optional[str] = None
    artifact_store: Optional[ArtifactStore] = None
    state_snapshot: Optional[WorkflowState] = None

    @field_validator("conversation_history", mode="before")
    @classmethod
    def copy_conversation_history(cls, v: Any) -> Any:
        if isinstance(v, list):
            return list(v)
        return v


class BlockOutput(BaseModel):
    """Output produced by a block after execution."""

    output: str
    exit_handle: Optional[str] = None
    artifact_ref: Optional[str] = None
    artifact_type: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    cost_usd: float = 0.0
    total_tokens: int = 0
    log_entries: List[Dict[str, str]] = Field(default_factory=list)
    conversation_updates: Optional[Dict[str, List[Dict]]] = None
    shared_memory_updates: Optional[Dict[str, Any]] = None
    extra_results: Optional[Dict[str, Any]] = None


def apply_block_output(state: WorkflowState, block_id: str, output: BlockOutput) -> WorkflowState:
    """Apply a BlockOutput to a WorkflowState, returning a new WorkflowState.

    Creates a new WorkflowState with the block result stored, cost/tokens accumulated,
    execution log extended, and optional shared_memory, conversation_histories, and
    extra_results merged in.
    """
    new_result = BlockResult(
        output=output.output,
        exit_handle=output.exit_handle,
        artifact_ref=output.artifact_ref,
        artifact_type=output.artifact_type,
        metadata=output.metadata if output.metadata else None,
    )

    new_results = {**state.results, block_id: new_result}
    if output.extra_results:
        new_results.update(output.extra_results)

    new_shared_memory = dict(state.shared_memory)
    if output.shared_memory_updates is not None:
        new_shared_memory.update(output.shared_memory_updates)

    new_execution_log = list(state.execution_log) + list(output.log_entries)

    new_conversation_histories = dict(state.conversation_histories)
    if output.conversation_updates is not None:
        for key, messages in output.conversation_updates.items():
            existing = list(new_conversation_histories.get(key, []))
            existing.extend(messages)
            new_conversation_histories[key] = existing

    return state.model_copy(
        update={
            "results": new_results,
            "total_cost_usd": state.total_cost_usd + output.cost_usd,
            "total_tokens": state.total_tokens + output.total_tokens,
            "execution_log": new_execution_log,
            "shared_memory": new_shared_memory,
            "conversation_histories": new_conversation_histories,
        }
    )
