from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class RunCreate(BaseModel):
    workflow_id: str
    task_data: Dict[str, Any] = Field(default_factory=dict)


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
    node_summary: Optional[NodeSummary] = None


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
