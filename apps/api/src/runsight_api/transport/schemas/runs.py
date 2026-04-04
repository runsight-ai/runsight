from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class RunCreate(BaseModel):
    workflow_id: str
    task_data: Dict[str, Any] = Field(default_factory=dict)
    source: Optional[str] = "manual"
    branch: str = "main"


class NodeSummary(BaseModel):
    total: int
    completed: int
    running: int
    pending: int
    failed: int


class RunResponse(BaseModel):
    id: str
    workflow_id: str
    workflow_name: str
    status: str
    started_at: Optional[float]
    completed_at: Optional[float]
    duration_seconds: Optional[float]
    total_cost_usd: float
    total_tokens: int
    created_at: float
    branch: str = "main"
    source: str = "manual"
    commit_sha: Optional[str] = None
    run_number: Optional[int] = None
    eval_pass_pct: Optional[float] = None
    regression_count: Optional[int] = None
    node_summary: Optional[NodeSummary] = None
    parent_run_id: Optional[str] = None
    root_run_id: Optional[str] = None
    depth: int = 0


class RunListResponse(BaseModel):
    items: List[RunResponse]
    total: int
    offset: int
    limit: int


class RunNodeResponse(BaseModel):
    id: str
    run_id: str
    node_id: str
    block_type: str
    status: str
    started_at: Optional[float]
    completed_at: Optional[float]
    duration_seconds: Optional[float]
    cost_usd: float
    tokens: Dict[str, Any]
    error: Optional[str]
    output: Optional[str] = None
    soul_id: Optional[str] = None
    model_name: Optional[str] = None
    eval_score: Optional[float] = None
    eval_passed: Optional[bool] = None
    eval_results: Optional[Dict[str, Any]] = None
    child_run_id: Optional[str] = None
    exit_handle: Optional[str] = None


class LogResponse(BaseModel):
    id: int
    run_id: str
    timestamp: float
    level: str
    node_id: Optional[str]
    message: str


class PaginatedLogsResponse(BaseModel):
    items: List[LogResponse]
    total: int
    offset: int
    limit: int
