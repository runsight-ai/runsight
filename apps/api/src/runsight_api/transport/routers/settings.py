from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ...data.filesystem.settings_repo import FileSystemSettingsRepo
from ...domain.errors import ProviderNotFound
from ...logic.services.provider_service import ProviderService
from ...logic.services.settings_service import SettingsService
from ..deps import get_provider_service, get_settings_repo, get_settings_service

router = APIRouter(prefix="/settings", tags=["Settings"])


class ProviderCreate(BaseModel):
    name: str
    api_key_env: Optional[str] = None  # Frontend sends the raw API key in this field
    base_url: Optional[str] = None


class ProviderUpdate(BaseModel):
    name: Optional[str] = None
    api_key_env: Optional[str] = None  # Frontend sends the raw API key in this field
    base_url: Optional[str] = None


class ProviderOut(BaseModel):
    id: str
    name: str
    status: str
    api_key_env: Optional[str] = None  # Return "configured" or "" - never the real key
    base_url: Optional[str] = None
    models: list[str] = []
    model_count: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ModelDefaultOut(BaseModel):
    id: str
    model_name: str
    provider_id: str
    provider_name: str
    fallback_chain: list[str] = []
    is_default: bool = False


class ModelDefaultUpdate(BaseModel):
    model_name: str | None = None
    is_default: bool | None = None
    fallback_chain: list[str] | None = None


class BudgetOut(BaseModel):
    id: str
    name: str
    limit_usd: float
    spent_usd: float
    period: str
    reset_at: Optional[str] = None


class AppSettingsOut(BaseModel):
    base_path: Optional[str] = None
    default_provider: Optional[str] = None
    auto_save: Optional[bool] = None
    onboarding_completed: Optional[bool] = None


def _provider_to_out(p) -> ProviderOut:
    models = p.models if p.models else []
    return ProviderOut(
        id=p.id,
        name=p.name,
        status=p.status or "unknown",
        api_key_env="configured" if p.api_key else "",
        base_url=p.base_url,
        models=models,
        model_count=len(models),
        created_at=str(p.created_at) if hasattr(p, "created_at") and p.created_at else None,
        updated_at=str(p.updated_at) if hasattr(p, "updated_at") and p.updated_at else None,
    )


@router.get("/providers")
async def list_providers(
    service: ProviderService = Depends(get_provider_service),
):
    providers = service.list_providers()
    items = [_provider_to_out(p) for p in providers]
    return {"items": items, "total": len(items)}


@router.get("/providers/{provider_id}")
async def get_provider(
    provider_id: str,
    service: ProviderService = Depends(get_provider_service),
):
    provider = service.get_provider(provider_id)
    if not provider:
        raise ProviderNotFound(f"Provider {provider_id} not found")
    return _provider_to_out(provider)


@router.post("/providers")
async def create_provider(
    data: ProviderCreate,
    service: ProviderService = Depends(get_provider_service),
):
    provider = service.create_provider(
        name=data.name,
        api_key=data.api_key_env,
        base_url=data.base_url,
    )
    return _provider_to_out(provider)


@router.put("/providers/{provider_id}")
async def update_provider(
    provider_id: str,
    data: ProviderUpdate,
    service: ProviderService = Depends(get_provider_service),
):
    provider = service.update_provider(
        provider_id=provider_id,
        name=data.name,
        api_key=data.api_key_env,
        base_url=data.base_url,
    )
    if not provider:
        raise ProviderNotFound(f"Provider {provider_id} not found")
    return _provider_to_out(provider)


@router.delete("/providers/{provider_id}")
async def delete_provider(
    provider_id: str,
    service: ProviderService = Depends(get_provider_service),
):
    deleted = service.delete_provider(provider_id)
    if not deleted:
        raise ProviderNotFound(f"Provider {provider_id} not found")
    return {"id": provider_id, "deleted": True}


@router.post("/providers/{provider_id}/test")
async def test_provider(
    provider_id: str,
    service: ProviderService = Depends(get_provider_service),
):
    return await service.test_connection(provider_id)


@router.get("/models")
async def list_model_defaults(
    service: SettingsService = Depends(get_settings_service),
):
    items = service.get_model_defaults()
    return {"items": items, "total": len(items)}


@router.put("/models/{model_id}")
async def update_model_default(
    model_id: str,
    data: ModelDefaultUpdate,
    service: SettingsService = Depends(get_settings_service),
):
    return service.update_model_default(
        provider_id=model_id,
        model_name=data.model_name,
        is_default=data.is_default,
        fallback_chain=data.fallback_chain,
    )


@router.get("/budgets")
async def list_budgets():
    return {"items": [], "total": 0}


@router.get("/app")
async def get_app_settings(
    repo: FileSystemSettingsRepo = Depends(get_settings_repo),
):
    settings_config = repo.get_settings()
    return settings_config.model_dump(exclude_none=True)


@router.put("/app")
async def update_app_settings(
    data: AppSettingsOut,
    repo: FileSystemSettingsRepo = Depends(get_settings_repo),
):
    updates = data.model_dump(exclude_none=True)
    settings_config = repo.update_settings(updates)
    return settings_config.model_dump(exclude_none=True)
