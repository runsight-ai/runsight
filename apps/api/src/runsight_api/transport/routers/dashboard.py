import time

from fastapi import APIRouter, Depends

from ...logic.services.eval_service import EvalService
from ...logic.services.run_service import RunService
from ..deps import get_eval_service, get_run_service
from ..schemas.dashboard import AttentionItemsResponse, DashboardKPIsResponse

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

PERIOD_HOURS = 24


@router.get("", response_model=DashboardKPIsResponse)
async def get_dashboard(run_service: RunService = Depends(get_run_service)):
    runs = run_service.list_runs()
    cutoff = time.time() - PERIOD_HOURS * 3600

    recent_runs = [r for r in runs if r.created_at > cutoff]
    # Exclude simulation runs from production KPIs
    recent_runs = [r for r in recent_runs if r.source != "simulation"]

    runs_today = len(recent_runs)
    cost_today_usd = sum(r.total_cost_usd for r in recent_runs if r.total_cost_usd)

    # Collect all RunNodes from recent runs that have eval data
    eval_nodes = []
    for r in recent_runs:
        try:
            for node in run_service.get_run_nodes(r.id):
                if node.eval_passed is not None:
                    eval_nodes.append(node)
        except TypeError:
            pass

    eval_pass_rate: float | None = None
    regressions: int | None = None

    if eval_nodes:
        eval_pass_rate = sum(1 for n in eval_nodes if n.eval_passed) / len(eval_nodes)
        regressions = sum(1 for n in eval_nodes if not n.eval_passed and n.soul_id is not None)

    return DashboardKPIsResponse(
        runs_today=runs_today,
        cost_today_usd=cost_today_usd,
        eval_pass_rate=eval_pass_rate,
        regressions=regressions,
        period_hours=PERIOD_HOURS,
    )


@router.get("/attention", response_model=AttentionItemsResponse)
async def get_attention_items(
    limit: int = 5,
    eval_service: EvalService = Depends(get_eval_service),
) -> AttentionItemsResponse:
    items = eval_service.get_attention_items()
    return AttentionItemsResponse(items=items[:limit])
