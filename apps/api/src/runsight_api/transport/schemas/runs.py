from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field
from runsight_core.context_governance import ContextAuditEventV1

from ...domain.entities.run import RegressionIssueTypeLiteral
from .workflows import WarningItem


class WorkflowInputValidationFieldError(BaseModel):
    field: str
    code: str
    message: str
    input_path: List[str]
    expected_type: Optional[str]
    actual_type: Optional[str]


class WorkflowInputValidationErrorDetails(BaseModel):
    model_config = ConfigDict(extra="allow")

    kind: Literal["workflow_input_validation"]
    fields: List[WorkflowInputValidationFieldError]
    workflow_id: Optional[str] = None


class WorkflowInputValidationErrorResponse(BaseModel):
    error: str
    error_code: Literal["WORKFLOW_INPUT_VALIDATION_ERROR"]
    status_code: Literal[422]
    details: WorkflowInputValidationErrorDetails


class RunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workflow_id: str
    inputs: Dict[str, Any] = Field(default_factory=dict, json_schema_extra={"default": {}})
    source: Optional[str] = "manual"
    branch: Optional[str] = Field(default=None, min_length=1)


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
    error: Optional[str] = None
    started_at: Optional[float]
    completed_at: Optional[float]
    duration_seconds: Optional[float]
    total_cost_usd: float
    total_tokens: int
    created_at: float
    branch: str
    source: str = "manual"
    commit_sha: Optional[str] = None
    run_number: Optional[int] = None
    eval_pass_pct: Optional[float] = None
    eval_score_avg: Optional[float] = None
    regression_count: Optional[int] = 0
    regression_types: List[str] = Field(default_factory=list)
    warnings: List[WarningItem] = Field(default_factory=list, json_schema_extra={"default": []})
    node_summary: Optional[NodeSummary] = None
    parent_run_id: Optional[str] = None
    root_run_id: Optional[str] = None
    depth: int = 0
    workflow_inputs: Optional[Dict[str, Any]] = None
    workflow_input_schema: Optional[Dict[str, Any]] = None


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


class ContextAuditListResponse(BaseModel):
    items: List[ContextAuditEventV1]
    page_size: int
    has_next_page: bool
    end_cursor: Optional[str] = None


class RunRegressionIssue(BaseModel):
    node_id: str
    node_name: str
    type: RegressionIssueTypeLiteral
    delta: Dict[str, Any] = Field(default_factory=dict)


class RunRegressionsResponse(BaseModel):
    count: int
    issues: List[RunRegressionIssue] = Field(default_factory=list)
