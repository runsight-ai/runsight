from fastapi import APIRouter, Depends
from typing import Optional
from ..schemas.souls import SoulResponse, SoulListResponse, SoulCreate, SoulUpdate
from ..deps import get_soul_service
from ...logic.services.soul_service import SoulService

router = APIRouter(prefix="/souls", tags=["Souls"])


@router.get("", response_model=SoulListResponse)
async def list_souls(
    q: Optional[str] = None,
    offset: int = 0,
    limit: int = 50,
    service: SoulService = Depends(get_soul_service),
):
    souls = service.list_souls(query=q)
    items = souls[offset : offset + limit]
    response_items = [SoulResponse(**s.model_dump()) for s in items]
    return SoulListResponse(items=response_items, total=len(souls))


@router.get("/{id}", response_model=SoulResponse)
async def get_soul(id: str, service: SoulService = Depends(get_soul_service)):
    s = service.get_soul(id)
    if not s:
        from ...domain.errors import SoulNotFound

        raise SoulNotFound(f"Soul {id} not found")
    return SoulResponse(**s.model_dump())


@router.post("", response_model=SoulResponse)
async def create_soul(body: SoulCreate, service: SoulService = Depends(get_soul_service)):
    s = service.create_soul(body.model_dump(exclude_unset=True))
    return SoulResponse(**s.model_dump())


@router.put("/{id}", response_model=SoulResponse)
async def update_soul(id: str, body: SoulUpdate, service: SoulService = Depends(get_soul_service)):
    data = body.model_dump(exclude_unset=True, exclude={"copy_on_edit"})
    s = service.update_soul(id, data, copy_on_edit=body.copy_on_edit)
    return SoulResponse(**s.model_dump())


@router.delete("/{id}")
async def delete_soul(id: str, service: SoulService = Depends(get_soul_service)):
    service.delete_soul(id)
    return {"id": id, "deleted": True}
