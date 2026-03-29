from typing import List, Optional

from pydantic import BaseModel


class StepResponse(BaseModel):
    id: str
    name: str
    type: str
    path: str
    description: Optional[str] = None


class StepCreate(BaseModel):
    id: Optional[str] = None
    name: str
    type: str = "step"
    description: Optional[str] = None


class StepUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    description: Optional[str] = None


class StepListResponse(BaseModel):
    items: List[StepResponse]
    total: int
