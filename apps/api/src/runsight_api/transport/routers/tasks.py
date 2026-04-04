from typing import Optional

from fastapi import APIRouter, Depends

from ...data.filesystem.task_repo import TaskRepository
from ...domain.errors import TaskNotFound
from ...logic.services.registry_service import RegistryService
from ..deps import get_registry_service, get_task_repo
from ..schemas.tasks import TaskCreate, TaskListResponse, TaskResponse, TaskUpdate

router = APIRouter(prefix="/tasks", tags=["Tasks"])


def _entity_to_response(entity: dict) -> TaskResponse:
    return TaskResponse(
        id=entity.get("id", ""),
        name=entity.get("name") or entity.get("id", "Unnamed"),
        type=entity.get("type", "task"),
        path=entity.get("path", ""),
        description=entity.get("description"),
    )


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    q: Optional[str] = None,
    offset: int = 0,
    limit: int = 50,
    service: RegistryService = Depends(get_registry_service),
    repo: TaskRepository = Depends(get_task_repo),
):
    # Merge registry (discovered) + repo (yaml files)
    seen = {}
    for t in service.discover_tasks():
        seen[t["id"]] = t
    for entity in repo.list_all():
        d = entity.model_dump()
        d["path"] = d.get("path") or str(repo._get_path(entity.id))
        seen[entity.id] = d

    tasks = list(seen.values())
    if q:
        tasks = [
            t
            for t in tasks
            if q.lower() in str(t.get("id", "")).lower()
            or q.lower() in str(t.get("name", "")).lower()
        ]

    items = tasks[offset : offset + limit]
    response_items = [_entity_to_response(t) for t in items]
    return TaskListResponse(items=response_items, total=len(tasks))


@router.get("/{id}", response_model=TaskResponse)
async def get_task(
    id: str,
    service: RegistryService = Depends(get_registry_service),
    repo: TaskRepository = Depends(get_task_repo),
):
    # Try repo first (user-created)
    entity = repo.get_by_id(id)
    if entity:
        d = entity.model_dump()
        d["path"] = d.get("path") or str(repo._get_path(id))
        return _entity_to_response(d)

    # Fall back to registry
    tasks = service.discover_tasks()
    for t in tasks:
        if t["id"] == id:
            return TaskResponse(**t)

    raise TaskNotFound(f"Task {id} not found")


@router.post("", response_model=TaskResponse, status_code=201)
async def create_task(
    data: TaskCreate,
    repo: TaskRepository = Depends(get_task_repo),
):
    import re

    task_id = (
        data.id or re.sub(r"[^a-z0-9_-]", "-", data.name.lower()).strip("-") or f"task-{id(data)}"
    )
    payload = {
        "id": task_id,
        "name": data.name,
        "type": data.type,
        "description": data.description,
        "path": str(repo._get_path(task_id)),
    }
    entity = repo.create(payload)
    return _entity_to_response(entity.model_dump())


@router.put("/{id}", response_model=TaskResponse)
async def update_task(
    id: str,
    data: TaskUpdate,
    repo: TaskRepository = Depends(get_task_repo),
):
    entity = repo.get_by_id(id)
    if not entity:
        raise TaskNotFound(f"Task {id} not found")
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
async def delete_task(
    id: str,
    repo: TaskRepository = Depends(get_task_repo),
):
    ok = repo.delete(id)
    return {"id": id, "deleted": ok}
