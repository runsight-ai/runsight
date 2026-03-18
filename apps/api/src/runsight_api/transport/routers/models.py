"""Model catalog API endpoints (RUN-151)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ..deps import get_model_service
from ...logic.services.model_service import ModelService

router = APIRouter(tags=["models"])


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


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


class ProviderSummary(BaseModel):
    id: str
    name: str
    model_count: int
    is_configured: bool = False


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/models", response_model=list[ModelResponse])
def list_models(
    provider: str | None = Query(None),
    mode: str | None = Query(None),
    supports_vision: bool | None = Query(None),
    supports_function_calling: bool | None = Query(None),
    all: bool = Query(False),  # noqa: A002
    service: ModelService = Depends(get_model_service),
) -> list[ModelResponse]:
    models = service.get_available_models(
        provider=provider,
        mode=mode,
        supports_vision=supports_vision,
        supports_function_calling=supports_function_calling,
        all_providers=all,
    )
    result = []
    for m in models:
        max_tokens = m.max_tokens
        if max_tokens is not None and not isinstance(max_tokens, int):
            try:
                max_tokens = int(max_tokens)
            except (ValueError, TypeError):
                max_tokens = None
        result.append(
            ModelResponse(
                provider=m.provider,
                provider_name=m.provider.capitalize(),
                model_id=m.model_id,
                mode=m.mode,
                max_tokens=max_tokens,
                input_cost_per_token=m.input_cost_per_token,
                output_cost_per_token=m.output_cost_per_token,
                supports_vision=m.supports_vision,
                supports_function_calling=m.supports_function_calling,
            )
        )
    return result


@router.get("/models/providers", response_model=list[ProviderSummary])
def list_providers(
    service: ModelService = Depends(get_model_service),
) -> list[ProviderSummary]:
    summaries = service.get_provider_summary()
    return [ProviderSummary(**s) for s in summaries]
