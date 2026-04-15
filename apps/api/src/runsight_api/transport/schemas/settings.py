"""Response and request schemas for the settings API (RUN-859)."""

from typing import Optional

from pydantic import BaseModel, ConfigDict, StrictBool


class ProviderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    api_key_env: Optional[str] = None  # Frontend sends the raw API key in this field
    base_url: Optional[str] = None


class ProviderUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = None
    api_key_env: Optional[str] = None  # Frontend sends the raw API key in this field
    base_url: Optional[str] = None
    is_active: Optional[bool] = None


class ProviderTestIn(BaseModel):
    provider_id: Optional[str] = None
    provider_type: Optional[str] = None
    name: Optional[str] = None
    api_key_env: Optional[str] = None
    base_url: Optional[str] = None


class ProviderTestOut(BaseModel):
    success: bool
    message: str
    models: list[str] = []
    model_count: int = 0
    latency_ms: float = 0.0


class SettingsProviderResponse(BaseModel):
    id: str
    name: str
    type: Optional[str] = None
    status: str
    is_active: bool = True
    api_key_env: Optional[str] = None
    api_key_preview: Optional[str] = None
    base_url: Optional[str] = None
    models: list[str] = []
    model_count: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class SettingsProviderListResponse(BaseModel):
    items: list["SettingsProviderResponse"]
    total: int


class SettingsFallbackResponse(BaseModel):
    id: str
    provider_id: str
    provider_name: str
    fallback_provider_id: str | None = None
    fallback_model_id: str | None = None


class SettingsFallbackListResponse(BaseModel):
    items: list["SettingsFallbackResponse"]
    total: int


class FallbackUpdate(BaseModel):
    fallback_provider_id: str | None = None
    fallback_model_id: str | None = None


# Non-Optional StrictBool with a None default keeps fields optional in OpenAPI
# while explicit null still fails validation.
class AppSettingsOut(BaseModel):
    base_path: Optional[str] = None
    onboarding_completed: StrictBool = None
    fallback_enabled: StrictBool = None


class AppSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    onboarding_completed: StrictBool = None
    fallback_enabled: StrictBool = None
