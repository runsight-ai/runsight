from pydantic import BaseModel


class DashboardResponse(BaseModel):
    active_runs: int
    completed_runs: int
    total_cost_usd: float
    recent_errors: int
    system_status: str
