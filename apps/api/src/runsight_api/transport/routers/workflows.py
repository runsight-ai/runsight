from typing import Optional

from fastapi import APIRouter, Depends

from ...logic.services.workflow_service import WorkflowService
from ..deps import get_workflow_service
from ..schemas.workflows import (
    WorkflowCreate,
    WorkflowListResponse,
    WorkflowResponse,
    WorkflowUpdate,
)

router = APIRouter(prefix="/workflows", tags=["Workflows"])


@router.get("", response_model=WorkflowListResponse)
async def list_workflows(
    q: Optional[str] = None,
    offset: int = 0,
    limit: int = 50,
    service: WorkflowService = Depends(get_workflow_service),
):
    all_workflows = service.list_workflows(query=q)
    items = all_workflows[offset : offset + limit]
    response_items = [WorkflowResponse(**w.model_dump()) for w in items]
    return WorkflowListResponse(items=response_items, total=len(all_workflows))


@router.get("/{id}", response_model=WorkflowResponse)
async def get_workflow(id: str, service: WorkflowService = Depends(get_workflow_service)):
    w = service.get_workflow(id)
    if not w:
        from ...domain.errors import WorkflowNotFound

        raise WorkflowNotFound(f"Workflow {id} not found")
    return WorkflowResponse(**w.model_dump())


@router.post("", response_model=WorkflowResponse)
async def create_workflow(
    body: WorkflowCreate, service: WorkflowService = Depends(get_workflow_service)
):
    w = service.create_workflow(body.model_dump())
    return WorkflowResponse(**w.model_dump())


@router.put("/{id}", response_model=WorkflowResponse)
async def update_workflow(
    id: str, body: WorkflowUpdate, service: WorkflowService = Depends(get_workflow_service)
):
    data = body.model_dump(exclude_unset=True)
    w = service.update_workflow(id, data)
    return WorkflowResponse(**w.model_dump())


@router.delete("/{id}")
async def delete_workflow(id: str, service: WorkflowService = Depends(get_workflow_service)):
    success = service.delete_workflow(id)
    return {"id": id, "deleted": success}
