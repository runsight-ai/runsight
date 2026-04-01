from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class CanvasViewport(BaseModel):
    x: float = 0.0
    y: float = 0.0
    zoom: float = 1.0


class WorkflowCanvasState(BaseModel):
    nodes: List[Dict[str, Any]] = Field(default_factory=list)
    edges: List[Dict[str, Any]] = Field(default_factory=list)
    viewport: CanvasViewport = Field(default_factory=CanvasViewport)
    selected_node_id: Optional[str] = None
    canvas_mode: Literal["dag", "state-machine"] = "dag"


class WorkflowHealthMetrics(BaseModel):
    run_count: int = 0
    eval_pass_pct: float | None = None
    eval_health: Literal["success", "warning", "danger"] | None = None
    total_cost_usd: float = 0.0
    regression_count: int = 0


class WorkflowResponse(BaseModel):
    id: str
    name: Optional[str] = None
    description: Optional[str] = None
    yaml: Optional[str] = None
    canvas_state: Optional[WorkflowCanvasState] = None
    valid: bool = True
    validation_error: Optional[str] = None
    block_count: int = 0
    modified_at: float | None = None
    enabled: bool = False
    commit_sha: str | None = None
    health: WorkflowHealthMetrics = Field(default_factory=WorkflowHealthMetrics)


class WorkflowListResponse(BaseModel):
    items: List[WorkflowResponse]
    total: int


class WorkflowCreate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    yaml: str
    canvas_state: Optional[WorkflowCanvasState] = None


class WorkflowUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    yaml: str
    canvas_state: Optional[WorkflowCanvasState] = None


class WorkflowCommitCreate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    yaml: str
    canvas_state: Optional[WorkflowCanvasState] = None
    message: str = Field(min_length=1)


class WorkflowCommitResponse(BaseModel):
    hash: str
    message: str


class WorkflowSimulationCreate(BaseModel):
    yaml: str


class WorkflowSimulationResponse(BaseModel):
    branch: str
    commit_sha: str


class WorkflowDeleteResponse(BaseModel):
    id: str
    deleted: bool
    runs_deleted: int
