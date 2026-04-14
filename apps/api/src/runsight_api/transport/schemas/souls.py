from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, field_validator
from runsight_core.identity import EntityKind, validate_entity_id


class SoulResponse(BaseModel):
    kind: Literal["soul"]
    name: str
    id: str
    role: Optional[str] = None
    system_prompt: Optional[str] = None
    tools: Optional[List[str]] = None
    max_tool_iterations: int = 5
    model_name: Optional[str] = None
    provider: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    avatar_color: Optional[str] = None
    workflow_count: int = 0
    modified_at: Optional[float] = None


class SoulListResponse(BaseModel):
    items: List[SoulResponse]
    total: int


class SoulCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kind: Literal["soul"]
    name: str
    role: str
    system_prompt: str
    tools: Optional[List[str]] = None
    max_tool_iterations: int = 5
    model_name: Optional[str] = None
    provider: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    avatar_color: Optional[str] = None

    @field_validator("id")
    @classmethod
    def _validate_identity(cls, value: str) -> str:
        validate_entity_id(value, EntityKind.SOUL)
        return value


class SoulUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Optional[str] = None
    system_prompt: Optional[str] = None
    tools: Optional[List[str]] = None
    max_tool_iterations: Optional[int] = None
    model_name: Optional[str] = None
    provider: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    avatar_color: Optional[str] = None
    copy_on_edit: bool = False


class SoulUsageEntry(BaseModel):
    workflow_id: str
    workflow_name: str


class SoulUsageResponse(BaseModel):
    soul_id: str
    usages: List[SoulUsageEntry]
    total: int
