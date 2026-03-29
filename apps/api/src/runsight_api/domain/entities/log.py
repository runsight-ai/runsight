import time
from typing import Optional

from sqlmodel import Field, SQLModel


class LogEntry(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: str = Field(index=True)
    node_id: Optional[str] = None
    level: str = Field(default="info")
    message: str
    timestamp: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)
