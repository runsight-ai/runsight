from pydantic import BaseModel
from typing import Optional


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
    killed: int = 0


class CostSummary(BaseModel):
    """Summary of costs."""

    total_cost_usd: float = 0.0


class WorkflowEntity(BaseModel):
    id: str
    name: Optional[str] = None
    model_config = {"extra": "allow"}


class SoulEntity(BaseModel):
    id: str
    name: Optional[str] = None
    model_config = {"extra": "allow"}


class TaskEntity(BaseModel):
    id: str
    name: Optional[str] = None
    model_config = {"extra": "allow"}


class StepEntity(BaseModel):
    id: str
    name: Optional[str] = None
    model_config = {"extra": "allow"}
