from sqlmodel import SQLModel, Field
from typing import Optional
import time


class RuntimeAudit(SQLModel, table=True):
    id: str = Field(primary_key=True)
    run_id: str = Field(index=True)
    node_id: str
    action_type: str
    details_json: Optional[str] = None
    timestamp: float = Field(default_factory=time.time)
    user_id: str = Field(default="local")
    created_at: float = Field(default_factory=time.time)
