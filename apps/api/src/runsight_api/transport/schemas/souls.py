from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class SoulResponse(BaseModel):
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


class SoulListResponse(BaseModel):
    items: List[SoulResponse]
    total: int


class SoulCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: Optional[str] = None
    role: str
    system_prompt: str
    tools: Optional[List[str]] = None
    max_tool_iterations: int = 5
    model_name: Optional[str] = None
    provider: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    avatar_color: Optional[str] = None


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
