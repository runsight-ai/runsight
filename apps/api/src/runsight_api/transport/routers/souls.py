from typing import Optional

from fastapi import APIRouter, Depends
from runsight_core.identity import EntityKind, EntityRef

from ...logic.services.soul_service import SoulService
from ..deps import get_soul_service, get_workflow_repo
from ..schemas.souls import (
    SoulCreate,
    SoulListResponse,
    SoulResponse,
    SoulUpdate,
    SoulUsageResponse,
)

router = APIRouter(prefix="/souls", tags=["Souls"])


def _soul_ref(soul_id: str) -> str:
    return str(EntityRef(EntityKind.SOUL, soul_id))


@router.get("", response_model=SoulListResponse)
async def list_souls(
    q: Optional[str] = None,
    offset: int = 0,
    limit: int = 50,
    service: SoulService = Depends(get_soul_service),
):
    souls = service.list_souls(query=q)
    items = souls[offset : offset + limit]
    response_items = [
        SoulResponse(kind="soul", name=s.name, **s.model_dump(exclude={"kind", "name"}))
        for s in items
    ]
    return SoulListResponse(items=response_items, total=len(souls))


@router.get("/{id}/usages", response_model=SoulUsageResponse)
async def get_soul_usages(
    id: str,
    service: SoulService = Depends(get_soul_service),
):
    usages = service.get_soul_usages(id)
    return SoulUsageResponse(soul_id=id, usages=usages, total=len(usages))


@router.get("/{id}", response_model=SoulResponse)
async def get_soul(id: str, service: SoulService = Depends(get_soul_service)):
    s = service.get_soul(id)
    if not s:
        from ...domain.errors import SoulNotFound

        raise SoulNotFound(f"Soul {_soul_ref(id)} not found")
    return SoulResponse(kind="soul", name=s.name, **s.model_dump(exclude={"kind", "name"}))


@router.post("", response_model=SoulResponse)
async def create_soul(body: SoulCreate, service: SoulService = Depends(get_soul_service)):
    s = service.create_soul(body.model_dump(exclude_unset=True))
    return SoulResponse(kind="soul", name=s.name, **s.model_dump(exclude={"kind", "name"}))


@router.put("/{id}", response_model=SoulResponse)
async def update_soul(id: str, body: SoulUpdate, service: SoulService = Depends(get_soul_service)):
    data = body.model_dump(exclude_unset=True, exclude={"copy_on_edit"})
    s = service.update_soul(id, data, copy_on_edit=body.copy_on_edit)
    return SoulResponse(kind="soul", name=s.name, **s.model_dump(exclude={"kind", "name"}))


@router.delete("/{id}")
async def delete_soul(
    id: str,
    force: bool = False,
    service: SoulService = Depends(get_soul_service),
    workflow_repo=Depends(get_workflow_repo),
):
    service.delete_soul(id, force=force, workflow_repo=workflow_repo)
    return {"id": id, "deleted": True}
