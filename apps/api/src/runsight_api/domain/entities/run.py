import json
import time
from enum import Enum
from typing import Any, Dict, Iterable, List, Literal, Optional, TypeAlias

from pydantic import BaseModel, field_validator
from sqlmodel import JSON, Column, Field, SQLModel


class RunStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class NodeStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class RegressionIssueType(str, Enum):
    assertion_regression = "assertion_regression"
    cost_spike = "cost_spike"
    quality_drop = "quality_drop"


RegressionIssueTypeLiteral: TypeAlias = Literal[
    "assertion_regression",
    "cost_spike",
    "quality_drop",
]


# ---------------------------------------------------------------------------
# State transition guards
# ---------------------------------------------------------------------------

VALID_TRANSITIONS: Dict[str, set] = {
    RunStatus.pending: {RunStatus.running, RunStatus.cancelled, RunStatus.failed},
    RunStatus.running: {RunStatus.completed, RunStatus.failed, RunStatus.cancelled},
    RunStatus.completed: set(),  # terminal
    RunStatus.failed: set(),  # terminal
    RunStatus.cancelled: set(),  # terminal
}


class InvalidStateTransition(ValueError):
    """Raised when a run status transition is not allowed."""

    def __init__(self, current: RunStatus, target: RunStatus):
        self.current = current
        self.target = target
        super().__init__(f"Invalid state transition: {current.value} -> {target.value}")


MAX_SOURCE_METADATA_BYTES = 4096
_SENSITIVE_SOURCE_METADATA_KEYS = {
    "authorization",
    "auth",
    "authentication",
    "body",
    "cookie",
    "cookies",
    "headers",
    "idempotency",
    "idempotency_key",
    "input",
    "inputs",
    "password",
    "raw_body",
    "secret",
    "token",
    "workflow_inputs",
}


def _iter_source_metadata_keys(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for key, nested in value.items():
            if isinstance(key, str):
                yield key
            yield from _iter_source_metadata_keys(nested)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_source_metadata_keys(item)


def _is_sensitive_source_metadata_key(key: str) -> bool:
    normalized = key.lower()
    return normalized in _SENSITIVE_SOURCE_METADATA_KEYS or normalized.endswith("_token")


class _RunCreationValidator(BaseModel):
    branch: str
    source_metadata: Optional[Dict[str, Any]] = None

    @field_validator("source_metadata", mode="before")
    @classmethod
    def validate_source_metadata(cls, value: Any) -> Dict[str, Any]:
        return validate_source_metadata(value)


def validate_source_metadata(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("source_metadata must be an object")

    blocked_keys = sorted(
        {key for key in _iter_source_metadata_keys(value) if _is_sensitive_source_metadata_key(key)}
    )
    if blocked_keys:
        raise ValueError(f"source_metadata contains unsafe keys: {', '.join(blocked_keys)}")

    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise ValueError("source_metadata must be JSON serializable") from exc
    if len(encoded.encode("utf-8")) > MAX_SOURCE_METADATA_BYTES:
        raise ValueError("source_metadata is too large")

    return value


def validate_transition(current: RunStatus, target: RunStatus) -> None:
    """Raise InvalidStateTransition if *current* -> *target* is not allowed.

    Same-status transitions are treated as idempotent no-ops and are always
    allowed.
    """
    if current == target:
        return
    allowed = VALID_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise InvalidStateTransition(current, target)


class Run(SQLModel, table=True):
    def __init__(self, **data: Any):
        validated = _RunCreationValidator.model_validate(data)
        if "source_metadata" in data:
            data["source_metadata"] = validated.source_metadata
        super().__init__(**data)

    id: str = Field(primary_key=True)
    workflow_id: str
    workflow_name: str
    status: RunStatus = Field(default=RunStatus.pending)
    task_json: str
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    duration_s: Optional[float] = None
    total_cost_usd: float = Field(default=0.0)
    total_tokens: int = Field(default=0)
    results_json: Optional[str] = None
    error: Optional[str] = None
    error_traceback: Optional[str] = None
    cancelled_reason: Optional[str] = None
    branch: str
    source: str = Field(default="manual")
    commit_sha: Optional[str] = Field(default=None)
    source_correlation_id: Optional[str] = Field(default=None)
    source_metadata: Dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=True)
    )
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)

    # Budget-exceeded terminal state (RUN-717)
    fail_reason: Optional[str] = Field(default=None)
    fail_metadata: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    warnings_json: Optional[List[Dict[str, Any]]] = Field(default=None, sa_column=Column(JSON))
    workflow_inputs: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    workflow_input_schema: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))

    # Soft-delete tombstone (preserves audit history)
    deleted_at: Optional[float] = Field(default=None)

    # Nested-run linkage (RUN-607)
    parent_run_id: Optional[str] = Field(default=None)
    parent_node_id: Optional[str] = Field(default=None)
    root_run_id: Optional[str] = Field(default=None)
    depth: int = Field(default=0)


class RunNode(SQLModel, table=True):
    id: str = Field(primary_key=True)  # Composite: {run_id}:{node_id}
    run_id: str = Field(index=True)
    node_id: str
    block_type: str
    status: NodeStatus = Field(default=NodeStatus.pending)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    duration_s: Optional[float] = None
    cost_usd: float = Field(default=0.0)
    tokens: Dict[str, Any] = Field(
        default_factory=lambda: {"prompt": 0, "completion": 0, "total": 0}, sa_column=Column(JSON)
    )
    output: Optional[str] = None
    error: Optional[str] = None
    error_traceback: Optional[str] = None
    last_phase: Optional[str] = None
    soul_id: Optional[str] = None
    model_name: Optional[str] = None
    prompt_hash: Optional[str] = None
    soul_version: Optional[str] = None
    eval_score: Optional[float] = None
    eval_passed: Optional[bool] = None
    eval_results: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)

    # Nested-run linkage (RUN-607)
    child_run_id: Optional[str] = Field(default=None)
    exit_handle: Optional[str] = Field(default=None)


class BaselineStats(BaseModel):
    """Aggregated baseline statistics for a soul version."""

    avg_cost: float
    avg_tokens: float
    avg_score: Optional[float]
    run_count: int
