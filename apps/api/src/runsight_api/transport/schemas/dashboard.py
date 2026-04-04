from typing import Literal

from pydantic import BaseModel


class DashboardKPIsResponse(BaseModel):
    runs_today: int
    cost_today_usd: float
    eval_pass_rate: float | None
    regressions: int | None
    runs_previous_period: int = 0
    cost_previous_period_usd: float = 0.0
    eval_pass_rate_previous_period: float | None = None
    regressions_previous_period: int | None = None
    period_hours: int = 24


class AttentionItem(BaseModel):
    type: Literal["assertion_regression", "cost_spike", "quality_drop", "new_baseline"]
    title: str
    description: str
    run_id: str
    workflow_id: str
    severity: Literal["warning", "info"]


class AttentionItemsResponse(BaseModel):
    items: list[AttentionItem]
