from typing import List, Optional

from pydantic import BaseModel, Field


class NodeTokens(BaseModel):
    """Token usage for a node."""

    prompt: int = 0
    completion: int = 0
    total: int = 0


class NodeSummary(BaseModel):
    """Summary of node statuses."""

    total: int = 0
    completed: int = 0
    running: int = 0
    pending: int = 0
    failed: int = 0


class CostSummary(BaseModel):
    """Summary of costs."""

    total_cost_usd: float = 0.0


class WorkflowEntity(BaseModel):
    id: str
    name: Optional[str] = None
    yaml: Optional[str] = None
    valid: bool = True
    enabled: bool = False
    validation_error: Optional[str] = None
    filename: Optional[str] = None
    model_config = {"extra": "allow"}


class SoulEntity(BaseModel):
    id: str
    role: Optional[str] = None
    system_prompt: Optional[str] = None
    tools: Optional[List[str]] = None
    max_tool_iterations: int = Field(default=5)
    model_name: Optional[str] = None
    provider: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    avatar_color: Optional[str] = None
    workflow_count: int = Field(default=0)
    modified_at: Optional[float] = None
    model_config = {"extra": "allow"}


class TaskEntity(BaseModel):
    id: str
    name: Optional[str] = None
    model_config = {"extra": "ignore"}


class StepEntity(BaseModel):
    id: str
    name: Optional[str] = None
    model_config = {"extra": "ignore"}


class ProviderEntity(BaseModel):
    id: str
    name: Optional[str] = None
    type: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    is_active: bool = True
    status: Optional[str] = None
    models: list = []
    model_config = {"extra": "allow"}
