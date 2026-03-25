from enum import Enum
from pydantic import BaseModel
from sqlmodel import SQLModel, Field, JSON, Column
from typing import Optional, Dict, Any
import time


class RunStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


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
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


class RunNode(SQLModel, table=True):
    id: str = Field(primary_key=True)  # Composite: {run_id}:{node_id}
    run_id: str = Field(index=True)
    node_id: str
    block_type: str
    status: str = Field(default="pending")
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
