from pydantic import ConfigDict
from pydantic import BaseModel
from pydantic import StrictBool

# ---------------------------------------------------------------------------
# Pydantic models for filesystem-backed settings (RUN-233)
# ---------------------------------------------------------------------------


class AppSettingsConfig(BaseModel):
    """Flat app settings stored in .runsight/settings.yaml."""

    onboarding_completed: StrictBool = False
    fallback_enabled: StrictBool = False


class FallbackTargetEntry(BaseModel):
    """Single per-provider fallback target."""

    model_config = ConfigDict(extra="forbid")

    provider_id: str
    fallback_provider_id: str
    fallback_model_id: str
