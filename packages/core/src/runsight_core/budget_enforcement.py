"""Budget enforcement primitives for the RUN-708 epic.

Provides:
- BudgetKilledException: raised when a block or workflow exceeds a budget limit.
- BudgetWarningEvent: emitted when usage approaches a budget cap.
- BudgetKillEvent: emitted when a budget cap is breached and execution is killed.
- BudgetSession: mutable accumulator with parent propagation for hierarchical enforcement.
- _active_budget: ContextVar tracking the active budget scope per-task.
"""

from __future__ import annotations

import re
import time
from contextvars import ContextVar
from typing import TYPE_CHECKING, Literal, Optional

from pydantic import BaseModel

if TYPE_CHECKING:
    from runsight_core.yaml.schema import BlockLimitsDef, WorkflowLimitsDef


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
        target = f"block '{block_id}'" if scope == "block" else "workflow"
        super().__init__(
            f"Budget limit exceeded on {target}: "
            f"{limit_kind}={actual_value:.4f} > cap={limit_value:.4f}"
        )


_BUDGET_KILLED_MESSAGE_RE = re.compile(
    r"^Budget limit exceeded on (?:(workflow)|block '([^']+)'): "
    r"(cost_usd|token_cap|timeout)=([0-9.]+) > cap=([0-9.]+)$"
)


def budget_killed_exception_to_payload(exc: BudgetKilledException) -> dict[str, object]:
    """Serialize a BudgetKilledException for IPC error frames."""
    return {
        "error_type": "BudgetKilledException",
        "scope": exc.scope,
        "block_id": exc.block_id,
        "limit_kind": exc.limit_kind,
        "limit_value": exc.limit_value,
        "actual_value": exc.actual_value,
    }


def budget_killed_exception_from_payload(payload: object) -> BudgetKilledException | None:
    """Reconstruct a BudgetKilledException from a structured IPC payload."""
    if not isinstance(payload, dict):
        return None
    if payload.get("error_type") != "BudgetKilledException":
        return None

    scope = payload.get("scope")
    limit_kind = payload.get("limit_kind")
    if scope not in {"block", "workflow"}:
        return None
    if limit_kind not in {"cost_usd", "token_cap", "timeout"}:
        return None

    try:
        limit_value = float(payload.get("limit_value"))
        actual_value = float(payload.get("actual_value"))
    except (TypeError, ValueError):
        return None

    block_id_raw = payload.get("block_id")
    block_id = str(block_id_raw) if block_id_raw is not None else None
    return BudgetKilledException(
        scope=scope,  # type: ignore[arg-type]
        block_id=block_id,
        limit_kind=limit_kind,  # type: ignore[arg-type]
        limit_value=limit_value,
        actual_value=actual_value,
    )


def budget_killed_exception_from_message(message: str) -> BudgetKilledException | None:
    """Best-effort reconstruction from the stable BudgetKilledException message."""
    match = _BUDGET_KILLED_MESSAGE_RE.match(message)
    if match is None:
        return None

    workflow_marker, block_id, limit_kind, actual_value, limit_value = match.groups()
    scope = "workflow" if workflow_marker else "block"
    return BudgetKilledException(
        scope=scope,  # type: ignore[arg-type]
        block_id=None if scope == "workflow" else block_id,
        limit_kind=limit_kind,  # type: ignore[arg-type]
        limit_value=float(limit_value),
        actual_value=float(actual_value),
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


class BudgetSession:
    """Mutable accumulator tracking cost/tokens/time with parent-chain propagation."""

    def __init__(
        self,
        *,
        scope_name: str,
        cost_cap_usd: Optional[float] = None,
        token_cap: Optional[int] = None,
        max_duration_seconds: Optional[int] = None,
        on_exceed: Literal["fail", "warn"] = "fail",
        warn_at_pct: float = 0.8,
        parent: Optional[BudgetSession] = None,
    ) -> None:
        self.scope_name = scope_name
        self.cost_cap_usd = cost_cap_usd
        self.token_cap = token_cap
        self.max_duration_seconds = max_duration_seconds
        self.on_exceed = on_exceed
        self.warn_at_pct = warn_at_pct
        self.parent = parent
        self.cost_usd: float = 0.0
        self.tokens: int = 0
        self._started_at: float = time.monotonic()

    @property
    def elapsed_s(self) -> float:
        """Wall-clock seconds since session creation."""
        return time.monotonic() - self._started_at

    def accrue(self, *, cost_usd: float, tokens: int) -> None:
        """Add cost and tokens to this session and propagate to parent."""
        self.cost_usd += cost_usd
        self.tokens += tokens
        if self.parent is not None:
            self.parent.accrue(cost_usd=cost_usd, tokens=tokens)

    def _check_self(self, block_id: Optional[str] = None) -> None:
        """Check this session's caps and raise/skip based on on_exceed."""
        scope: Literal["block", "workflow"] = (
            "block" if self.scope_name.startswith("block") else "workflow"
        )
        if self.cost_cap_usd is not None and self.cost_usd > self.cost_cap_usd:
            if self.on_exceed == "fail":
                raise BudgetKilledException(
                    scope=scope,
                    block_id=block_id,
                    limit_kind="cost_usd",
                    limit_value=self.cost_cap_usd,
                    actual_value=self.cost_usd,
                )
        if self.token_cap is not None and self.tokens > self.token_cap:
            if self.on_exceed == "fail":
                raise BudgetKilledException(
                    scope=scope,
                    block_id=block_id,
                    limit_kind="token_cap",
                    limit_value=self.token_cap,
                    actual_value=self.tokens,
                )
        if self.max_duration_seconds is not None and self.elapsed_s > self.max_duration_seconds:
            if self.on_exceed == "fail":
                raise BudgetKilledException(
                    scope=scope,
                    block_id=block_id,
                    limit_kind="timeout",
                    limit_value=self.max_duration_seconds,
                    actual_value=self.elapsed_s,
                )

    def check_or_raise(self, block_id: Optional[str] = None) -> None:
        """Check this session's caps, then walk the parent chain recursively."""
        self._check_self(block_id=block_id)
        if self.parent is not None:
            self.parent.check_or_raise(block_id=block_id)

    def create_isolated_child(self, branch_id: str) -> BudgetSession:
        """Create an isolated child for parallel branches (parent=None)."""
        return BudgetSession(
            scope_name=f"{self.scope_name}:{branch_id}",
            cost_cap_usd=self.cost_cap_usd,
            token_cap=self.token_cap,
            max_duration_seconds=self.max_duration_seconds,
            on_exceed=self.on_exceed,
            warn_at_pct=self.warn_at_pct,
            parent=None,
        )

    def reconcile_child(self, child: BudgetSession) -> None:
        """Merge an isolated child's totals into this session."""
        self.cost_usd += child.cost_usd
        self.tokens += child.tokens

    @classmethod
    def from_workflow_limits(cls, limits: WorkflowLimitsDef, workflow_name: str) -> BudgetSession:
        """Construct a BudgetSession from a WorkflowLimitsDef."""
        return cls(
            scope_name=f"workflow:{workflow_name}",
            cost_cap_usd=limits.cost_cap_usd,
            token_cap=limits.token_cap,
            max_duration_seconds=limits.max_duration_seconds,
            on_exceed=limits.on_exceed,
            warn_at_pct=limits.warn_at_pct,
        )

    @classmethod
    def from_block_limits(
        cls,
        limits: BlockLimitsDef,
        block_id: str,
        parent: Optional[BudgetSession] = None,
    ) -> BudgetSession:
        """Construct a BudgetSession from a BlockLimitsDef."""
        return cls(
            scope_name=f"block:{block_id}",
            cost_cap_usd=limits.cost_cap_usd,
            token_cap=limits.token_cap,
            max_duration_seconds=limits.max_duration_seconds,
            on_exceed=limits.on_exceed,
            parent=parent,
        )
