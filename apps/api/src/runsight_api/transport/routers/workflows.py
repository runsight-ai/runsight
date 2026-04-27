from typing import Optional

from fastapi import APIRouter, Depends, Request
from runsight_core.identity import EntityKind, EntityRef

from ...logic.services.eval_service import EvalService
from ...logic.services.api_run_service import ApiRunService
from ...logic.services.workflow_service import WorkflowService
from ..deps import get_api_run_service, get_eval_service, get_workflow_service
from ..schemas.runs import (
    DirectApiRunCreate,
    ErrorResponse,
    NodeSummary,
    RunResponse,
    WorkflowInputValidationErrorResponse,
)
from .runs import _build_run_response, _run_metric_field
from ..schemas.workflows import (
    WorkflowCommitCreate,
    WorkflowCommitResponse,
    WorkflowCreate,
    WorkflowDeleteResponse,
    WorkflowEnabledUpdate,
    WorkflowRegressionsResponse,
    WorkflowListResponse,
    WorkflowResponse,
    WorkflowSimulationCreate,
    WorkflowSimulationResponse,
    WorkflowUpdate,
)

router = APIRouter(prefix="/workflows", tags=["Workflows"])


def _workflow_ref(workflow_id: str) -> str:
    return str(EntityRef(EntityKind.WORKFLOW, workflow_id))


def _direct_api_source_correlation_id(request: Request) -> str | None:
    return request.headers.get("x-request-id") or request.headers.get("x-correlation-id")


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
    from ...domain.errors import WorkflowNotFound

    w = service.get_workflow_detail(id)
    if not w:
        raise WorkflowNotFound(f"Workflow {_workflow_ref(id)} not found")
    return WorkflowResponse(**w.model_dump())


@router.post("", response_model=WorkflowResponse)
async def create_workflow(
    body: WorkflowCreate, service: WorkflowService = Depends(get_workflow_service)
):
    data = body.model_dump(exclude={"commit"})
    w = service.create_workflow(data, commit=body.commit)
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


@router.post(
    "/{id}/simulations",
    response_model=WorkflowSimulationResponse,
    responses={422: {"model": WorkflowInputValidationErrorResponse}},
)
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
    w = service.set_enabled(id, body.enabled)
    return WorkflowResponse(**w.model_dump())


@router.post(
    "/{workflow_id}/runs",
    response_model=RunResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Workflow not found"},
        422: {"model": WorkflowInputValidationErrorResponse},
        429: {
            "model": ErrorResponse,
            "description": "External invocation admission is saturated",
        },
        503: {"model": ErrorResponse, "description": "Execution runtime is unavailable"},
        413: {"model": ErrorResponse, "description": "Request body too large"},
    },
)
async def create_direct_api_run(
    workflow_id: str,
    body: DirectApiRunCreate,
    request: Request,
    service: ApiRunService = Depends(get_api_run_service),
):
    run = await service.create_direct_api_run(
        workflow_id=workflow_id,
        inputs=body.inputs,
        source_correlation_id=_direct_api_source_correlation_id(request),
        source_metadata={
            "entry_path": "direct_api",
            "request_path": request.url.path,
        },
    )
    return _build_run_response(
        run,
        total_cost_usd=run.total_cost_usd,
        total_tokens=run.total_tokens,
        node_summary=NodeSummary(total=0, completed=0, running=0, pending=0, failed=0),
        eval_score_avg=_run_metric_field(run, "eval_score_avg"),
        regression_count=_run_metric_field(run, "regression_count"),
        regression_types=[],
    )


@router.get("/{id}/regressions", response_model=WorkflowRegressionsResponse)
async def get_workflow_regressions(
    id: str,
    eval_service: EvalService = Depends(get_eval_service),
):
    result = eval_service.get_workflow_regressions(id)
    return WorkflowRegressionsResponse.model_validate(result)


@router.delete("/{id}", response_model=WorkflowDeleteResponse)
async def delete_workflow(
    id: str,
    force: bool = False,
    service: WorkflowService = Depends(get_workflow_service),
):
    return service.delete_workflow(id, force=force)
