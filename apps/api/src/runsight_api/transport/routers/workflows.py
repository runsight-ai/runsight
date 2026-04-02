from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from ...logic.services.workflow_service import WorkflowService
from ..deps import get_workflow_service
from ..schemas.workflows import (
    WorkflowCommitCreate,
    WorkflowCommitResponse,
    WorkflowCreate,
    WorkflowDeleteResponse,
    WorkflowEnabledUpdate,
    WorkflowListResponse,
    WorkflowResponse,
    WorkflowSimulationCreate,
    WorkflowSimulationResponse,
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


@router.post("/{id}/commits", response_model=WorkflowCommitResponse)
async def commit_workflow(
    id: str,
    body: WorkflowCommitCreate,
    service: WorkflowService = Depends(get_workflow_service),
):
    data = body.model_dump(exclude={"message"}, exclude_unset=True)
    result = service.commit_workflow(id, data, body.message)
    return WorkflowCommitResponse(**result)


@router.post("/{id}/simulations", response_model=WorkflowSimulationResponse)
async def create_workflow_simulation(
    id: str,
    body: WorkflowSimulationCreate,
    service: WorkflowService = Depends(get_workflow_service),
):
    result = service.create_simulation(workflow_id=id, yaml=body.yaml)
    return WorkflowSimulationResponse(**result)


@router.patch("/{id}/enabled", response_model=WorkflowResponse)
async def patch_workflow_enabled(
    id: str,
    body: WorkflowEnabledUpdate,
    service: WorkflowService = Depends(get_workflow_service),
):
    from ...domain.errors import RunsightError

    try:
        w = service.set_enabled(id, body.enabled)
    except RunsightError as exc:
        return JSONResponse(status_code=exc.status_code, content=exc.to_dict())
    return WorkflowResponse(**w.model_dump())


@router.delete("/{id}", response_model=WorkflowDeleteResponse)
async def delete_workflow(
    id: str,
    force: bool = False,
    service: WorkflowService = Depends(get_workflow_service),
):
    return service.delete_workflow(id, force=force)
