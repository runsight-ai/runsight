import time
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel
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
    branch: str = Field(default="main")
    source: str = Field(default="manual")
    commit_sha: Optional[str] = Field(default=None)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


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


class BaselineStats(BaseModel):
    """Aggregated baseline statistics for a soul version."""

    avg_cost: float
    avg_tokens: float
    avg_score: Optional[float]
    run_count: int
