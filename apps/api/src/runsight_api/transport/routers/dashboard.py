import time

from fastapi import APIRouter, Depends

from ..schemas.dashboard import AttentionItemsResponse, DashboardKPIsResponse
from ..deps import get_eval_service, get_run_service
from ...logic.services.eval_service import EvalService
from ...logic.services.run_service import RunService

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

PERIOD_HOURS = 24


@router.get("", response_model=DashboardKPIsResponse)
async def get_dashboard(run_service: RunService = Depends(get_run_service)):
    runs = run_service.list_runs()
    cutoff = time.time() - PERIOD_HOURS * 3600

    recent_runs = [r for r in runs if r.created_at > cutoff]

    runs_today = len(recent_runs)
    cost_today_usd = sum(r.total_cost_usd for r in recent_runs if r.total_cost_usd)

    return DashboardKPIsResponse(
        runs_today=runs_today,
        cost_today_usd=cost_today_usd,
        eval_pass_rate=None,
        regressions=None,
        period_hours=PERIOD_HOURS,
    )


@router.get("/attention", response_model=AttentionItemsResponse)
async def get_attention_items(
    limit: int = 5,
    eval_service: EvalService = Depends(get_eval_service),
) -> AttentionItemsResponse:
    items = eval_service.get_attention_items()
    return AttentionItemsResponse(items=items[:limit])
