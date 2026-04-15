"""Response schemas for the model catalog API (RUN-859)."""

from __future__ import annotations

from pydantic import BaseModel


class ModelResponse(BaseModel):
    provider: str
    provider_name: str
    model_id: str
    mode: str
    max_tokens: int | None = None
    input_cost_per_token: float | None = None
    output_cost_per_token: float | None = None
    supports_vision: bool = False
    supports_function_calling: bool = False


class ModelListResponse(BaseModel):
    items: list[ModelResponse]
    total: int


class ProviderSummary(BaseModel):
    id: str
    name: str
    model_count: int
    is_configured: bool = False
