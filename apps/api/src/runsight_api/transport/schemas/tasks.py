from pydantic import BaseModel
from typing import List, Optional


class TaskResponse(BaseModel):
    id: str
    name: str
    type: str
    path: str
    description: Optional[str] = None


class TaskCreate(BaseModel):
    id: Optional[str] = None
    name: str
    type: str = "task"
    description: Optional[str] = None


class TaskUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    description: Optional[str] = None


class TaskListResponse(BaseModel):
    items: List[TaskResponse]
    total: int
