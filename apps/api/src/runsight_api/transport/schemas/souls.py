from typing import List, Optional

from pydantic import BaseModel


class SoulResponse(BaseModel):
    id: str
    name: Optional[str] = None
    system_prompt: Optional[str] = None
    models: Optional[List[str]] = None


class SoulListResponse(BaseModel):
    items: List[SoulResponse]
    total: int


class SoulCreate(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    system_prompt: Optional[str] = None
    models: Optional[List[str]] = None


class SoulUpdate(BaseModel):
    name: Optional[str] = None
    system_prompt: Optional[str] = None
    models: Optional[List[str]] = None
    copy_on_edit: bool = False
