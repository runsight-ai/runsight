"""Model catalog API endpoints (RUN-151)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ...logic.services.model_service import ModelService
from ..deps import get_model_service
from ..schemas.models import ModelListResponse, ModelResponse, ProviderSummary

router = APIRouter(prefix="/models", tags=["Models"])


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=ModelListResponse)
async def list_models(
    provider: str | None = Query(None),
    mode: str | None = Query(None),
    supports_vision: bool | None = Query(None),
    supports_function_calling: bool | None = Query(None),
    all: bool = Query(False),  # noqa: A002
    service: ModelService = Depends(get_model_service),
) -> ModelListResponse:
    models = service.get_available_models(
        provider=provider,
        mode=mode,
        supports_vision=supports_vision,
        supports_function_calling=supports_function_calling,
        all_providers=all,
    )
    items = []
    for m in models:
        max_tokens = m.max_tokens
        if max_tokens is not None and not isinstance(max_tokens, int):
            try:
                max_tokens = int(max_tokens)
            except (ValueError, TypeError):
                max_tokens = None
        items.append(
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
    return ModelListResponse(items=items, total=len(items))


@router.get("/providers", response_model=list[ProviderSummary])
async def list_providers(
    service: ModelService = Depends(get_model_service),
) -> list[ProviderSummary]:
    summaries = service.get_provider_summary()
    return [ProviderSummary(**s) for s in summaries]
