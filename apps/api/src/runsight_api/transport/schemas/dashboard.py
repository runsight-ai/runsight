from pydantic import BaseModel


class DashboardKPIsResponse(BaseModel):
    runs_today: int
    cost_today_usd: float
    eval_pass_rate: float | None
    regressions: int | None
    period_hours: int = 24
