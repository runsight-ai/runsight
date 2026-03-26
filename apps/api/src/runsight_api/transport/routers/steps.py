from fastapi import APIRouter, Depends
from typing import Optional

from ..schemas.steps import StepListResponse, StepResponse, StepCreate, StepUpdate
from ..deps import get_registry_service, get_step_repo
from ...logic.services.registry_service import RegistryService
from ...data.filesystem.step_repo import StepRepository
from ...domain.errors import StepNotFound

router = APIRouter(prefix="/steps", tags=["Steps"])


def _entity_to_response(entity: dict) -> StepResponse:
    return StepResponse(
        id=entity.get("id", ""),
        name=entity.get("name") or entity.get("id", "Unnamed"),
        type=entity.get("type", "step"),
        path=entity.get("path", ""),
        description=entity.get("description"),
    )


@router.get("", response_model=StepListResponse)
async def list_steps(
    q: Optional[str] = None,
    offset: int = 0,
    limit: int = 50,
    service: RegistryService = Depends(get_registry_service),
    repo: StepRepository = Depends(get_step_repo),
):
    # Merge registry (discovered) + repo (yaml files)
    seen = {}
    for s in service.discover_steps():
        seen[s["id"]] = s
    for entity in repo.list_all():
        d = entity.model_dump()
        d["path"] = d.get("path") or str(repo._get_path(entity.id))
        seen[entity.id] = d

    steps = list(seen.values())
    if q:
        steps = [
            s
            for s in steps
            if q.lower() in str(s.get("id", "")).lower()
            or q.lower() in str(s.get("name", "")).lower()
        ]

    items = steps[offset : offset + limit]
    response_items = [_entity_to_response(s) for s in items]
    return StepListResponse(items=response_items, total=len(steps))


@router.get("/{id}", response_model=StepResponse)
async def get_step(
    id: str,
    service: RegistryService = Depends(get_registry_service),
    repo: StepRepository = Depends(get_step_repo),
):
    # Try repo first (user-created)
    entity = repo.get_by_id(id)
    if entity:
        d = entity.model_dump()
        d["path"] = d.get("path") or str(repo._get_path(id))
        return _entity_to_response(d)

    # Fall back to registry
    steps = service.discover_steps()
    for s in steps:
        if s["id"] == id:
            return StepResponse(**s)

    raise StepNotFound(f"Step {id} not found")


@router.post("", response_model=StepResponse, status_code=201)
async def create_step(
    data: StepCreate,
    repo: StepRepository = Depends(get_step_repo),
):
    import re

    step_id = (
        data.id or re.sub(r"[^a-z0-9_-]", "-", data.name.lower()).strip("-") or f"step-{id(data)}"
    )
    payload = {
        "id": step_id,
        "name": data.name,
        "type": data.type,
        "description": data.description,
        "path": str(repo._get_path(step_id)),
    }
    entity = repo.create(payload)
    return _entity_to_response(entity.model_dump())


@router.put("/{id}", response_model=StepResponse)
async def update_step(
    id: str,
    data: StepUpdate,
    repo: StepRepository = Depends(get_step_repo),
):
    entity = repo.get_by_id(id)
    if not entity:
        raise StepNotFound(f"Step {id} not found")
    d = entity.model_dump()
    if data.name is not None:
        d["name"] = data.name
    if data.type is not None:
        d["type"] = data.type
    if data.description is not None:
        d["description"] = data.description
    updated = repo.update(id, d)
    d2 = updated.model_dump()
    d2["path"] = d2.get("path") or str(repo._get_path(id))
    return _entity_to_response(d2)


@router.delete("/{id}")
async def delete_step(
    id: str,
    repo: StepRepository = Depends(get_step_repo),
):
    ok = repo.delete(id)
    return {"id": id, "deleted": ok}
