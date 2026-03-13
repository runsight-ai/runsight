from sqlmodel import SQLModel, Field
import time


class AppSettings(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value: str
    updated_at: float = Field(default_factory=time.time)


class FallbackChain(SQLModel, table=True):
    position: int = Field(primary_key=True)
    provider_id: str
    model_id: str


class ModelDefault(SQLModel, table=True):
    provider_id: str = Field(primary_key=True)
    model_id: str = Field(primary_key=True)
    is_default: bool = Field(default=False)
