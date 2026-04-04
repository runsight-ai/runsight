import time

from fastapi import APIRouter, Depends

from ...logic.services.eval_service import EvalService
from ...logic.services.run_service import RunService
from ..deps import get_eval_service, get_run_service
from ..schemas.dashboard import AttentionItemsResponse, DashboardKPIsResponse

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

PERIOD_HOURS = 24
PRODUCTION_SOURCES = {"manual", "webhook", "schedule"}


def _is_production_main_run(run) -> bool:
    branch = getattr(run, "branch", "main")
    source = getattr(run, "source", "manual")
    branch_value = branch if isinstance(branch, str) else "main"
    source_value = source if isinstance(source, str) else "manual"
    return branch_value == "main" and source_value in PRODUCTION_SOURCES


def _window_metrics(
    run_service: RunService,
    production_runs: list,
    target_run_ids: set[str],
) -> tuple[float | None, int | None]:
    eval_total = 0
    eval_passed = 0
    regressions = 0
    previous_by_key: dict[tuple[str, str, str], object] = {}

    for run in production_runs:
        try:
            run_nodes = sorted(run_service.get_run_nodes(run.id), key=lambda node: node.created_at)
        except TypeError:
            run_nodes = []

        for node in run_nodes:
            previous_node = None
            if node.soul_version is not None:
                key = (run.workflow_id, node.node_id, node.soul_version)
                previous_node = previous_by_key.get(key)
                previous_by_key[key] = node

            if run.id not in target_run_ids or node.eval_passed is None:
                continue

            eval_total += 1
            if node.eval_passed:
                eval_passed += 1

            if (
                node.soul_version is not None
                and node.eval_passed is False
                and previous_node is not None
            ):
                if previous_node.eval_passed is True:
                    regressions += 1

    if eval_total == 0:
        return None, None

    return eval_passed / eval_total, regressions


@router.get("", response_model=DashboardKPIsResponse)
async def get_dashboard(run_service: RunService = Depends(get_run_service)):
    runs = run_service.list_runs()
    now = time.time()
    cutoff = now - PERIOD_HOURS * 3600
    previous_cutoff = cutoff - PERIOD_HOURS * 3600

    production_runs = sorted(
        (r for r in runs if _is_production_main_run(r)), key=lambda run: run.created_at
    )
    recent_run_ids = {run.id for run in production_runs if cutoff < run.created_at <= now}
    previous_run_ids = {
        run.id for run in production_runs if previous_cutoff < run.created_at <= cutoff
    }
    recent_runs = [run for run in production_runs if run.id in recent_run_ids]
    previous_runs = [run for run in production_runs if run.id in previous_run_ids]

    runs_today = len(recent_runs)
    runs_previous_period = len(previous_runs)
    cost_today_usd = sum(r.total_cost_usd for r in recent_runs if r.total_cost_usd)
    cost_previous_period_usd = sum(r.total_cost_usd for r in previous_runs if r.total_cost_usd)
    eval_pass_rate, regressions_value = _window_metrics(
        run_service, production_runs, recent_run_ids
    )
    eval_pass_rate_previous_period, regressions_previous_period = _window_metrics(
        run_service,
        production_runs,
        previous_run_ids,
    )

    return DashboardKPIsResponse(
        runs_today=runs_today,
        cost_today_usd=cost_today_usd,
        eval_pass_rate=eval_pass_rate,
        regressions=regressions_value,
        runs_previous_period=runs_previous_period,
        cost_previous_period_usd=cost_previous_period_usd,
        eval_pass_rate_previous_period=eval_pass_rate_previous_period,
        regressions_previous_period=regressions_previous_period,
        period_hours=PERIOD_HOURS,
    )


@router.get("/attention", response_model=AttentionItemsResponse)
async def get_attention_items(
    limit: int = 5,
    eval_service: EvalService = Depends(get_eval_service),
) -> AttentionItemsResponse:
    items = eval_service.get_attention_items()
    return AttentionItemsResponse(items=items[:limit])
