from pydantic import BaseModel
from typing import List


class ProviderResponse(BaseModel):
    id: str
    name: str
    is_configured: bool


class ModelDefaultResponse(BaseModel):
    role: str
    model: str
    provider: str


class SettingsResponse(BaseModel):
    providers: List[ProviderResponse]
    model_defaults: List[ModelDefaultResponse]
    budget_limit_usd: float
