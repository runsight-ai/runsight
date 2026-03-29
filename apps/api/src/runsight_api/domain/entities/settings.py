from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Pydantic models for filesystem-backed settings (RUN-233)
# ---------------------------------------------------------------------------


class AppSettingsConfig(BaseModel):
    """Flat app settings stored in .runsight/settings.yaml."""

    default_provider: str | None = None
    auto_save: bool | None = None
    onboarding_completed: bool = False


class FallbackChainEntry(BaseModel):
    """Single entry in the fallback chain list."""

    provider_id: str
    model_id: str


class ModelDefaultEntry(BaseModel):
    """Single model-default entry, keyed by (provider_id, model_id)."""

    provider_id: str
    model_id: str
    is_default: bool = False
