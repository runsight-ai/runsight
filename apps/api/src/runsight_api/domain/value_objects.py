from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator
from runsight_core.identity import EntityKind, validate_entity_id


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
    kind: Literal["workflow"]
    id: str
    name: Optional[str] = None
    yaml: Optional[str] = None
    valid: bool = True
    enabled: bool = False
    validation_error: Optional[str] = None
    filename: Optional[str] = None
    warnings: List[Dict[str, Optional[str]]] = Field(default_factory=list)
    model_config = ConfigDict(extra="allow")


class SoulEntity(BaseModel):
    kind: Literal["soul"]
    name: str
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
    model_config = ConfigDict(extra="forbid")

    @field_validator("id")
    @classmethod
    def _validate_identity(cls, value: str) -> str:
        validate_entity_id(value, EntityKind.SOUL)
        return value


class StepEntity(BaseModel):
    id: str
    name: Optional[str] = None
    type: str = "step"
    path: Optional[str] = None
    description: Optional[str] = None
    model_config = ConfigDict(extra="forbid")


class ProviderEntity(BaseModel):
    kind: Literal["provider"]
    id: str
    name: Optional[str] = None
    type: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    is_active: bool = True
    status: Optional[str] = None
    models: list[str] = Field(default_factory=list)
    created_at: Optional[float] = None
    updated_at: Optional[float] = None
    last_status_check: Optional[float] = None
    model_config = ConfigDict(extra="forbid")

    @field_validator("id")
    @classmethod
    def _validate_identity(cls, value: str) -> str:
        validate_entity_id(value, EntityKind.PROVIDER)
        return value
