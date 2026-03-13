from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlmodel import Session

from ..deps import get_provider_service, get_session
from ...logic.services.provider_service import ProviderService
from ...data.repositories.settings_repo import SettingsRepository
from ...domain.entities.settings import AppSettings as AppSettingsEntity

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
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ModelDefaultOut(BaseModel):
    id: str
    model_name: str
    provider_id: str
    provider_name: str
    fallback_chain: list[str] = []
    is_default: bool = False


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
    return ProviderOut(
        id=p.id,
        name=p.name,
        status=p.status,
        api_key_env="configured" if p.api_key_encrypted else "",
        base_url=p.base_url,
        models=p.models,
        created_at=str(p.created_at) if p.created_at else None,
        updated_at=str(p.updated_at) if p.updated_at else None,
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
        raise HTTPException(status_code=404, detail="Provider not found")
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
        raise HTTPException(status_code=404, detail="Provider not found")
    return _provider_to_out(provider)


@router.delete("/providers/{provider_id}")
async def delete_provider(
    provider_id: str,
    service: ProviderService = Depends(get_provider_service),
):
    deleted = service.delete_provider(provider_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Provider not found")
    return {"id": provider_id, "deleted": True}


@router.post("/providers/{provider_id}/test")
async def test_provider(
    provider_id: str,
    service: ProviderService = Depends(get_provider_service),
):
    return service.test_connection(provider_id)


@router.get("/models")
async def list_model_defaults():
    return {"items": [], "total": 0}


@router.put("/models/{model_id}")
async def update_model_default(model_id: str):
    return {"id": model_id}


@router.get("/budgets")
async def list_budgets():
    return {"items": [], "total": 0}


def _settings_to_out(repo: SettingsRepository) -> dict:
    result: dict = {}
    for setting in repo.list_settings():
        if setting.value in ("true", "false"):
            result[setting.key] = setting.value == "true"
        else:
            result[setting.key] = setting.value
    return result


@router.get("/app")
async def get_app_settings(session: Session = Depends(get_session)):
    repo = SettingsRepository(session)
    return _settings_to_out(repo)


@router.put("/app")
async def update_app_settings(
    data: AppSettingsOut,
    session: Session = Depends(get_session),
):
    import time

    repo = SettingsRepository(session)
    for key, value in data.model_dump(exclude_none=True).items():
        str_value = str(value).lower() if isinstance(value, bool) else str(value)
        repo.set_setting(AppSettingsEntity(key=key, value=str_value, updated_at=time.time()))
    return _settings_to_out(repo)
