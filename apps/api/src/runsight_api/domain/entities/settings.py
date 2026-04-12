from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Pydantic models for filesystem-backed settings (RUN-233)
# ---------------------------------------------------------------------------


class AppSettingsConfig(BaseModel):
    """Flat app settings stored in .runsight/settings.yaml."""

    onboarding_completed: bool = False
    fallback_enabled: bool = False


class FallbackTargetEntry(BaseModel):
    """Single per-provider fallback target."""

    provider_id: str
    fallback_provider_id: str
    fallback_model_id: str
