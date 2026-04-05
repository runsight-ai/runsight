import inspect as _inspect
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, Query

from ...logic.services.eval_service import EvalService
from ...logic.services.execution_service import ExecutionService
from ...logic.services.run_service import RunService
from ..deps import get_eval_service, get_execution_service, get_run_service
from ..schemas.runs import (
    NodeSummary,
    PaginatedLogsResponse,
    RunCreate,
    RunListResponse,
    RunNodeResponse,
    RunResponse,
)

logger = logging.getLogger(__name__)
inspect = _inspect

router = APIRouter(prefix="/runs", tags=["Runs"])


def _run_response_field(run, field: str, default):
    """Read a response field from a run-like object with a safe default."""
    value = getattr(run, field, default)
    if field in {"branch", "source"}:
        return value if isinstance(value, str) else default
    if field == "commit_sha":
        return value if value is None or isinstance(value, str) else None
    return value


def _run_metric_field(run, field: str):
    """Read optional list metrics while rejecting mock/default placeholder values."""
    value = getattr(run, field, None)
    if field == "run_number":
        return value if isinstance(value, int) else None
    if field == "eval_pass_pct":
        return float(value) if isinstance(value, int | float) else None
    if field == "eval_score_avg":
        return float(value) if isinstance(value, int | float) else None
    if field == "regression_count":
        return value if isinstance(value, int) else None
    return None


def _regression_types(result) -> list[str]:
    if not isinstance(result, dict):
        return []

    issues = result.get("issues")
    if not isinstance(issues, list):
        return []

    types: list[str] = []
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        regression_type = issue.get("type")
        if isinstance(regression_type, str) and regression_type not in types:
            types.append(regression_type)
    return types


@router.post("", response_model=RunResponse)
async def create_run(
    body: RunCreate,
    run_service: RunService = Depends(get_run_service),
    execution_service: Optional[ExecutionService] = Depends(get_execution_service),
):
    source = body.source or "manual"
    branch = body.branch or "main"
    run = run_service.create_run(
        body.workflow_id,
        body.task_data,
        source=source,
        branch=branch,
    )
    if execution_service is not None:
        try:
            await execution_service.launch_execution(
                run.id,
                run.workflow_id,
                body.task_data,
                branch=branch,
            )
        except Exception:
            logger.exception("Failed to launch execution for run %s", run.id)
    return RunResponse(
        id=run.id,
        workflow_id=run.workflow_id,
        workflow_name=run.workflow_name,
        status=run.status,
        error=getattr(run, "error", None),
        started_at=run.started_at,
        completed_at=run.completed_at,
        duration_seconds=run.duration_s,
        total_cost_usd=run.total_cost_usd,
        total_tokens=run.total_tokens,
        created_at=run.created_at,
        branch=_run_response_field(run, "branch", "main"),
        source=_run_response_field(run, "source", "manual"),
        commit_sha=_run_response_field(run, "commit_sha", None),
        run_number=_run_metric_field(run, "run_number"),
        eval_pass_pct=_run_metric_field(run, "eval_pass_pct"),
        eval_score_avg=_run_metric_field(run, "eval_score_avg"),
        regression_count=_run_metric_field(run, "regression_count"),
        regression_types=[],
        node_summary=NodeSummary(total=0, completed=0, running=0, pending=0, failed=0),
    )


def _fetch_paginated_runs(
    run_service: RunService,
    offset: int,
    limit: int,
    status: Optional[List[str]] = None,
    workflow_id: Optional[str] = None,
    source: Optional[List[str]] = None,
    branch: Optional[str] = None,
):
    """Fetch runs with the canonical paginated contract."""
    result = run_service.list_runs_paginated(
        offset=offset,
        limit=limit,
        status=status,
        workflow_id=workflow_id,
        source=source,
        branch=branch,
    )
    if not isinstance(result, tuple) or len(result) != 2:
        raise TypeError("run_service.list_runs_paginated must return (items, total)")
    return result


def _resolve_summaries(run_service: RunService, run_ids: list, raw_batch):
    """Resolve summaries from the canonical batch result."""
    if isinstance(raw_batch, dict):
        return raw_batch
    raise TypeError("run_service.get_node_summaries_batch must return dict")


@router.get("", response_model=RunListResponse)
async def list_runs(
    status: Optional[List[str]] = Query(None),
    workflow_id: Optional[str] = Query(None),
    source: Optional[List[str]] = Query(None),
    branch: Optional[str] = Query(None),
    offset: int = 0,
    limit: int = 20,
    run_service: RunService = Depends(get_run_service),
    eval_service: EvalService = Depends(get_eval_service),
):
    limit = min(limit, 100)
    runs, total = _fetch_paginated_runs(
        run_service,
        offset,
        limit,
        status=status,
        workflow_id=workflow_id,
        source=source,
        branch=branch,
    )

    run_ids = [run.id for run in runs]
    summaries_map = _resolve_summaries(
        run_service, run_ids, run_service.get_node_summaries_batch(run_ids=run_ids)
    )

    # Enrich each run with its regression count
    regression_counts: dict[str, int] = {}
    for run in runs:
        result = eval_service.get_run_regressions(run.id)
        regression_counts[run.id] = result["count"] if result else 0
        run.__dict__["regression_types"] = _regression_types(result)

    response_items = []
    for run in runs:
        summaries = summaries_map.get(run.id, {})
        response_items.append(
            RunResponse(
                id=run.id,
                workflow_id=run.workflow_id,
                workflow_name=run.workflow_name,
                status=run.status,
                error=getattr(run, "error", None),
                started_at=run.started_at,
                completed_at=run.completed_at,
                duration_seconds=run.duration_s,
                total_cost_usd=summaries.get("total_cost_usd", 0.0),
                total_tokens=summaries.get("total_tokens", 0),
                created_at=run.created_at,
                branch=_run_response_field(run, "branch", "main"),
                source=_run_response_field(run, "source", "manual"),
                commit_sha=_run_response_field(run, "commit_sha", None),
                run_number=_run_metric_field(run, "run_number"),
                eval_pass_pct=_run_metric_field(run, "eval_pass_pct"),
                eval_score_avg=summaries.get("eval_score_avg"),
                regression_count=regression_counts.get(run.id, 0),
                regression_types=_run_response_field(run, "regression_types", []),
                node_summary=NodeSummary(
                    total=summaries.get("total", 0),
                    completed=summaries.get("completed", 0),
                    running=summaries.get("running", 0),
                    pending=summaries.get("pending", 0),
                    failed=summaries.get("failed", 0),
                ),
            )
        )

    return RunListResponse(items=response_items, total=total, offset=offset, limit=limit)


@router.get("/{run_id}", response_model=RunResponse)
async def get_run(
    run_id: str,
    run_service: RunService = Depends(get_run_service),
    eval_service: EvalService = Depends(get_eval_service),
):
    run = run_service.get_run(run_id)
    if not run:
        from ...domain.errors import RunNotFound

        raise RunNotFound(f"Run {run_id} not found")
    summaries = run_service.get_node_summary(run.id)
    reg_result = eval_service.get_run_regressions(run_id)
    return RunResponse(
        id=run.id,
        workflow_id=run.workflow_id,
        workflow_name=run.workflow_name,
        status=run.status,
        error=getattr(run, "error", None),
        started_at=run.started_at,
        completed_at=run.completed_at,
        duration_seconds=run.duration_s,
        total_cost_usd=summaries["total_cost_usd"],
        total_tokens=summaries["total_tokens"],
        created_at=run.created_at,
        branch=_run_response_field(run, "branch", "main"),
        source=_run_response_field(run, "source", "manual"),
        commit_sha=_run_response_field(run, "commit_sha", None),
        run_number=_run_metric_field(run, "run_number"),
        eval_pass_pct=_run_metric_field(run, "eval_pass_pct"),
        eval_score_avg=summaries.get("eval_score_avg"),
        regression_count=reg_result["count"] if reg_result else 0,
        regression_types=_regression_types(reg_result),
        node_summary=NodeSummary(
            total=summaries["total"],
            completed=summaries["completed"],
            running=summaries["running"],
            pending=summaries["pending"],
            failed=summaries["failed"],
        ),
        parent_run_id=getattr(run, "parent_run_id", None),
        root_run_id=getattr(run, "root_run_id", None),
        depth=getattr(run, "depth", 0),
    )


@router.get("/{run_id}/children", response_model=List[RunResponse])
async def get_run_children(
    run_id: str,
    run_service: RunService = Depends(get_run_service),
    eval_service: EvalService = Depends(get_eval_service),
):
    children = run_service.list_children(run_id)
    summaries_map = run_service.get_node_summaries_batch(run_ids=[c.id for c in children])
    response_items = []
    for child in children:
        summaries = summaries_map.get(child.id, {})
        reg_result = eval_service.get_run_regressions(child.id)
        response_items.append(
            RunResponse(
                id=child.id,
                workflow_id=child.workflow_id,
                workflow_name=child.workflow_name,
                status=child.status,
                error=getattr(child, "error", None),
                started_at=child.started_at,
                completed_at=child.completed_at,
                duration_seconds=child.duration_s,
                total_cost_usd=summaries.get("total_cost_usd", 0.0),
                total_tokens=summaries.get("total_tokens", 0),
                created_at=child.created_at,
                branch=_run_response_field(child, "branch", "main"),
                source=_run_response_field(child, "source", "manual"),
                commit_sha=_run_response_field(child, "commit_sha", None),
                run_number=_run_metric_field(child, "run_number"),
                eval_pass_pct=_run_metric_field(child, "eval_pass_pct"),
                eval_score_avg=summaries.get("eval_score_avg"),
                regression_count=reg_result["count"] if reg_result else 0,
                regression_types=_regression_types(reg_result),
                node_summary=NodeSummary(
                    total=summaries.get("total", 0),
                    completed=summaries.get("completed", 0),
                    running=summaries.get("running", 0),
                    pending=summaries.get("pending", 0),
                    failed=summaries.get("failed", 0),
                ),
                parent_run_id=getattr(child, "parent_run_id", None),
                root_run_id=getattr(child, "root_run_id", None),
                depth=getattr(child, "depth", 0),
            )
        )
    return response_items


@router.post("/{run_id}/cancel")
async def cancel_run(
    run_id: str,
    run_service: RunService = Depends(get_run_service),
    execution_service: Optional[ExecutionService] = Depends(get_execution_service),
):
    if execution_service is not None:
        execution_service.cancel_execution(run_id)
    run = run_service.cancel_run(run_id)
    return {"id": run.id, "status": run.status}


@router.get("/{run_id}/logs", response_model=PaginatedLogsResponse)
async def get_run_logs(
    run_id: str,
    offset: int = 0,
    limit: int = 50,
    run_service: RunService = Depends(get_run_service),
):
    logs = run_service.get_run_logs(run_id)
    items = logs[offset : offset + limit]
    return PaginatedLogsResponse(items=items, total=len(logs), offset=offset, limit=limit)


@router.get("/{run_id}/regressions")
async def get_run_regressions(
    run_id: str,
    eval_service: EvalService = Depends(get_eval_service),
):
    result = eval_service.get_run_regressions(run_id)
    if result is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return result


@router.get("/{run_id}/nodes", response_model=List[RunNodeResponse])
async def get_run_nodes(run_id: str, run_service: RunService = Depends(get_run_service)):
    nodes = run_service.get_run_nodes(run_id)
    return [
        RunNodeResponse(
            id=n.id,
            run_id=n.run_id,
            node_id=n.node_id,
            block_type=n.block_type,
            status=n.status,
            started_at=n.started_at,
            completed_at=n.completed_at,
            duration_seconds=n.duration_s,
            cost_usd=n.cost_usd,
            tokens=n.tokens,
            error=n.error,
            output=n.output,
            soul_id=n.soul_id,
            model_name=n.model_name,
            eval_score=n.eval_score,
            eval_passed=n.eval_passed,
            eval_results=n.eval_results,
            child_run_id=getattr(n, "child_run_id", None),
            exit_handle=getattr(n, "exit_handle", None),
        )
        for n in nodes
    ]
