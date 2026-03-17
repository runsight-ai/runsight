from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal


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
    yaml: Optional[str] = None
    canvas_state: Optional[WorkflowCanvasState] = None
    valid: bool = True
    validation_error: Optional[str] = None


class WorkflowListResponse(BaseModel):
    items: List[WorkflowResponse]
    total: int


class WorkflowCreate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    yaml: Optional[str] = None
    canvas_state: Optional[WorkflowCanvasState] = None


class WorkflowUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    yaml: Optional[str] = None
    canvas_state: Optional[WorkflowCanvasState] = None
