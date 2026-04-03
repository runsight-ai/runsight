from typing import List

from pydantic import BaseModel


class ProviderResponse(BaseModel):
    id: str
    name: str
    is_configured: bool


class FallbackTargetResponse(BaseModel):
    provider_id: str
    provider_name: str
    fallback_provider_id: str | None = None
    fallback_model_id: str | None = None


class SettingsResponse(BaseModel):
    providers: List[ProviderResponse]
    fallback_targets: List[FallbackTargetResponse]
    budget_limit_usd: float
