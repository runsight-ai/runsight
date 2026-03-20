"""
WorkflowState data model for workflow execution context.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator
from runsight_core.artifacts import ArtifactStore
from runsight_core.primitives import Task


class BlockResult(BaseModel):
    """Structured result from a block execution."""

    output: str
    artifact_ref: Optional[str] = None
    artifact_type: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    @classmethod
    def from_string(cls, s: str) -> "BlockResult":
        return cls(output=s)

    def __str__(self) -> str:
        return self.output

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            return self.output == other
        return super().__eq__(other)

    def __hash__(self) -> int:
        return hash(self.output)

    # --- String-protocol methods for backward compatibility ---
    # These allow BlockResult to be used transparently where code expects
    # a plain string (len, 'in' operator, iteration, indexing, etc.)

    def __len__(self) -> int:
        return len(self.output)

    def __contains__(self, item: object) -> bool:
        return item in self.output

    def __getitem__(self, key: Any) -> str:
        return self.output[key]

    def __iter__(self):
        return iter(self.output)

    def __format__(self, format_spec: str) -> str:
        return self.output.__format__(format_spec)

    def startswith(self, *args, **kwargs):
        return self.output.startswith(*args, **kwargs)

    def endswith(self, *args, **kwargs):
        return self.output.endswith(*args, **kwargs)

    def strip(self, *args, **kwargs):
        return self.output.strip(*args, **kwargs)

    def split(self, *args, **kwargs):
        return self.output.split(*args, **kwargs)

    def upper(self):
        return self.output.upper()

    def lower(self):
        return self.output.lower()

    def replace(self, *args, **kwargs):
        return self.output.replace(*args, **kwargs)

    def encode(self, *args, **kwargs):
        return self.output.encode(*args, **kwargs)


# ---------------------------------------------------------------------------
# Backward-compatibility shim: allow json.loads(BlockResult(...)) to work
# transparently.  json.loads performs an isinstance(s, str) check that
# BlockResult (a BaseModel, not a str subclass) cannot pass.  We patch
# json.loads once at import time to unwrap BlockResult before delegating
# to the original implementation.
# ---------------------------------------------------------------------------
import json as _json  # noqa: E402

_original_json_loads = _json.loads


def _json_loads_with_block_result(s, **kwargs):
    if isinstance(s, BlockResult):
        s = s.output
    return _original_json_loads(s, **kwargs)


_json.loads = _json_loads_with_block_result


class WorkflowState(BaseModel):
    """
    Workflow execution context. Blocks receive state, return updated state.

    Best Practice: Use model_copy(update={...}) to create new state instances
    rather than mutating fields directly.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    messages: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Conversation history. Format: [{'role': 'system', 'content': '...'}]",
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
    artifact_store: Optional[ArtifactStore] = Field(default=None, exclude=True)

    @field_validator("results", mode="before")
    @classmethod
    def _coerce_str_to_block_result(cls, v: Any) -> Any:
        if isinstance(v, dict):
            return {
                k: BlockResult(output=val) if isinstance(val, str) else val for k, val in v.items()
            }
        return v
