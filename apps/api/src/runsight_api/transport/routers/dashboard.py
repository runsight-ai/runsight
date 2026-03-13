from fastapi import APIRouter, Depends
from ..schemas.dashboard import DashboardResponse
from ..deps import get_run_service
from ...logic.services.run_service import RunService
from ...domain.entities.run import RunStatus

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("", response_model=DashboardResponse)
async def get_dashboard(run_service: RunService = Depends(get_run_service)):
    runs = run_service.list_runs()
    active_runs = sum(1 for r in runs if r.status in [RunStatus.running, RunStatus.pending])
    completed_runs = sum(1 for r in runs if r.status == RunStatus.completed)
    recent_errors = sum(1 for r in runs if r.status == RunStatus.failed)

    total_cost_usd = 0.0
    for r in runs:
        if r.total_cost_usd:
            total_cost_usd += r.total_cost_usd

    return DashboardResponse(
        active_runs=active_runs,
        completed_runs=completed_runs,
        total_cost_usd=total_cost_usd,
        recent_errors=recent_errors,
        system_status="online",
    )
