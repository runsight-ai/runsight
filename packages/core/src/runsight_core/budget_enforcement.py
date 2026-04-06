"""Budget enforcement primitives for the RUN-708 epic.

Provides:
- BudgetKilledException: raised when a block or workflow exceeds a budget limit.
- BudgetWarningEvent: emitted when usage approaches a budget cap.
- BudgetKillEvent: emitted when a budget cap is breached and execution is killed.
- _active_budget: ContextVar tracking the active budget scope per-task.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Literal, Optional

from pydantic import BaseModel


class BudgetKilledException(Exception):
    """Raised when a block or workflow exceeds its budget limit."""

    def __init__(
        self,
        *,
        scope: Literal["block", "workflow"],
        block_id: Optional[str],
        limit_kind: Literal["timeout", "cost_usd", "token_cap"],
        limit_value: float,
        actual_value: float,
    ) -> None:
        self.scope = scope
        self.block_id = block_id
        self.limit_kind = limit_kind
        self.limit_value = limit_value
        self.actual_value = actual_value
        target = f"block '{block_id}'" if block_id else "workflow"
        super().__init__(
            f"Budget limit exceeded on {target}: "
            f"{limit_kind}={actual_value:.4f} > cap={limit_value:.4f}"
        )


class BudgetWarningEvent(BaseModel):
    """Emitted when usage approaches a budget cap."""

    scope: Literal["block", "workflow"]
    block_id: Optional[str] = None
    limit_kind: Literal["timeout", "cost_usd", "token_cap"]
    pct_used: float
    current_value: float
    cap_value: float
    workflow_name: str


class BudgetKillEvent(BaseModel):
    """Emitted when a budget cap is breached and execution is killed."""

    scope: Literal["block", "workflow"]
    block_id: Optional[str] = None
    limit_kind: Literal["timeout", "cost_usd", "token_cap"]
    current_value: float
    cap_value: float
    workflow_name: str


_active_budget: ContextVar[Optional[object]] = ContextVar("_active_budget", default=None)
