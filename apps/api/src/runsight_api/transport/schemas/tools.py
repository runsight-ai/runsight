from pydantic import BaseModel


class ToolListItemResponse(BaseModel):
    slug: str
    name: str
    description: str
    type: str
