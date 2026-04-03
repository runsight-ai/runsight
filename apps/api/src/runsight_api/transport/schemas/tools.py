from typing import Literal

from pydantic import BaseModel


class ToolListItemResponse(BaseModel):
    id: str
    name: str
    description: str
    origin: Literal["builtin", "custom"]
    executor: Literal["native", "python", "request"]
