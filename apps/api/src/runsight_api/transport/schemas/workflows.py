from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal
import uuid


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


class WorkflowResponse(BaseModel):
    id: str
    name: Optional[str] = None
    description: Optional[str] = None
    blocks: Dict[str, Any] = Field(default_factory=dict)
    edges: List[Dict[str, Any]] = Field(default_factory=list)
    canvas_state: Optional[WorkflowCanvasState] = None


class WorkflowListResponse(BaseModel):
    items: List[WorkflowResponse]
    total: int


class WorkflowCreate(BaseModel):
    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    name: Optional[str] = None
    description: Optional[str] = None
    blocks: Dict[str, Any] = Field(default_factory=dict)
    edges: List[Dict[str, Any]] = Field(default_factory=list)
    canvas_state: Optional[WorkflowCanvasState] = None


class WorkflowUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    blocks: Optional[Dict[str, Any]] = None
    edges: Optional[List[Dict[str, Any]]] = None
    canvas_state: Optional[WorkflowCanvasState] = None
