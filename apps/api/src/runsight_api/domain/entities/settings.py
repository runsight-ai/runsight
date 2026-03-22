from sqlmodel import SQLModel, Field
import time

from pydantic import BaseModel


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


# ---------------------------------------------------------------------------
# Pydantic models for filesystem-backed settings (RUN-233)
# ---------------------------------------------------------------------------


class AppSettingsConfig(BaseModel):
    """Flat app settings stored in .runsight/settings.yaml."""

    default_provider: str | None = None
    auto_save: bool | None = None
    onboarding_completed: bool | None = None


class FallbackChainEntry(BaseModel):
    """Single entry in the fallback chain list."""

    provider_id: str
    model_id: str


class ModelDefaultEntry(BaseModel):
    """Single model-default entry, keyed by (provider_id, model_id)."""

    provider_id: str
    model_id: str
    is_default: bool = False
