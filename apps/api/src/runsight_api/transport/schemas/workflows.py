from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uuid


class WorkflowResponse(BaseModel):
    id: str
    name: Optional[str] = None
    description: Optional[str] = None
    blocks: Dict[str, Any] = Field(default_factory=dict)
    edges: List[Dict[str, Any]] = Field(default_factory=list)


class WorkflowListResponse(BaseModel):
    items: List[WorkflowResponse]
    total: int


class WorkflowCreate(BaseModel):
    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    name: Optional[str] = None
    description: Optional[str] = None
    blocks: Dict[str, Any] = Field(default_factory=dict)
    edges: List[Dict[str, Any]] = Field(default_factory=list)


class WorkflowUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    blocks: Optional[Dict[str, Any]] = None
    edges: Optional[List[Dict[str, Any]]] = None
