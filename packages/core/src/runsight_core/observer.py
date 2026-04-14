"""
Workflow observability: protocol and built-in observers.

Usage:
    from runsight_core.observer import LoggingObserver, FileObserver

    # Logging (prints to stderr via Python logging)
    observer = LoggingObserver(level=logging.INFO)
    await workflow.run(state, observer=observer)

    # File-based (JSON lines, tail -f friendly)
    observer = FileObserver("pipeline.log")
    await workflow.run(state, observer=observer)
"""

import hashlib
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Protocol, runtime_checkable

from runsight_core.identity import EntityKind, EntityRef, validate_entity_id
from runsight_core.primitives import Soul
from runsight_core.state import WorkflowState


def compute_prompt_hash(soul: Optional[Soul]) -> Optional[str]:
    """Return SHA-256 hex digest of soul.system_prompt, or None if soul is None."""
    if soul is None:
        return None
    return hashlib.sha256(soul.system_prompt.encode()).hexdigest()


def compute_soul_version(soul: Optional[Soul]) -> Optional[str]:
    """Return SHA-256 hex digest of soul.model_dump_json(), or None if soul is None."""
    if soul is None:
        return None
    return hashlib.sha256(soul.model_dump_json().encode()).hexdigest()


@runtime_checkable
class WorkflowObserver(Protocol):
    """Protocol for workflow execution observers. All methods are optional no-ops by default."""

    def on_workflow_start(self, workflow_name: str, state: WorkflowState) -> None: ...

    def on_block_start(
        self,
        workflow_name: str,
        block_id: str,
        block_type: str,
        *,
        soul: Optional[Soul] = None,
        **kwargs: Any,
    ) -> None: ...

    def on_block_complete(
        self,
        workflow_name: str,
        block_id: str,
        block_type: str,
        duration_s: float,
        state: WorkflowState,
        *,
        soul: Optional[Soul] = None,
    ) -> None: ...

    def on_block_error(
        self,
        workflow_name: str,
        block_id: str,
        block_type: str,
        duration_s: float,
        error: Exception,
    ) -> None: ...

    def on_workflow_complete(
        self, workflow_name: str, state: WorkflowState, duration_s: float
    ) -> None: ...

    def on_block_heartbeat(
        self,
        workflow_name: str,
        block_id: str,
        phase: str,
        detail: str,
        timestamp: datetime,
    ) -> None: ...

    def on_workflow_error(
        self, workflow_name: str, error: Exception, duration_s: float
    ) -> None: ...


class LoggingObserver:
    """Observer that logs workflow events via Python's logging module."""

    def __init__(self, logger_name: str = "runsight.workflow", level: int = logging.INFO):
        self.logger = logging.getLogger(logger_name)
        self.level = level

    def on_workflow_start(self, workflow_name: str, state: WorkflowState) -> None:
        try:
            validate_entity_id(workflow_name, EntityKind.WORKFLOW)
            workflow_ref = str(EntityRef(EntityKind.WORKFLOW, workflow_name))
        except ValueError:
            workflow_ref = workflow_name
        self.logger.log(self.level, "[%s] Workflow started", workflow_ref)

    def on_block_start(
        self,
        workflow_name: str,
        block_id: str,
        block_type: str,
        *,
        soul: Optional[Soul] = None,
        **kwargs: Any,
    ) -> None:
        self.logger.log(
            self.level, "[%s] Block started: %s (type: %s)", workflow_name, block_id, block_type
        )

    def on_block_complete(
        self,
        workflow_name: str,
        block_id: str,
        block_type: str,
        duration_s: float,
        state: WorkflowState,
        *,
        soul: Optional[Soul] = None,
    ) -> None:
        self.logger.log(
            self.level,
            "[%s] Block complete: %s (%.1fs, cost: $%.4f, tokens: %d)",
            workflow_name,
            block_id,
            duration_s,
            state.total_cost_usd,
            state.total_tokens,
        )

    def on_block_error(
        self,
        workflow_name: str,
        block_id: str,
        block_type: str,
        duration_s: float,
        error: Exception,
    ) -> None:
        self.logger.error(
            "[%s] Block error: %s (%.1fs) — %s: %s",
            workflow_name,
            block_id,
            duration_s,
            type(error).__name__,
            error,
        )

    def on_workflow_complete(
        self, workflow_name: str, state: WorkflowState, duration_s: float
    ) -> None:
        self.logger.log(
            self.level,
            "[%s] Workflow complete (%.1fs, total cost: $%.4f, total tokens: %d)",
            workflow_name,
            duration_s,
            state.total_cost_usd,
            state.total_tokens,
        )

    def on_block_heartbeat(
        self,
        workflow_name: str,
        block_id: str,
        phase: str,
        detail: str,
        timestamp: datetime,
    ) -> None:
        self.logger.log(
            self.level,
            "[%s] Heartbeat: block=%s phase=%s detail=%s",
            workflow_name,
            block_id,
            phase,
            detail,
        )

    def on_workflow_error(self, workflow_name: str, error: Exception, duration_s: float) -> None:
        self.logger.error(
            "[%s] Workflow failed (%.1fs) — %s: %s",
            workflow_name,
            duration_s,
            type(error).__name__,
            error,
        )


class FileObserver:
    """
    Observer that writes JSON-lines to a file. Designed for real-time tailing.
    Each line is a self-contained JSON object with event type and data.
    """

    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Truncate on init (new run = new log)
        self.path.write_text("", encoding="utf-8")

    def _write(self, event: str, data: Dict[str, Any]) -> None:
        entry = {"ts": time.time(), "event": event, **data}
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
            f.flush()

    def on_workflow_start(self, workflow_name: str, state: WorkflowState) -> None:
        self._write("workflow_start", {"workflow": workflow_name})

    def on_block_start(
        self,
        workflow_name: str,
        block_id: str,
        block_type: str,
        *,
        soul: Optional[Soul] = None,
        **kwargs: Any,
    ) -> None:
        self._write(
            "block_start",
            {"workflow": workflow_name, "block_id": block_id, "block_type": block_type},
        )

    def on_block_complete(
        self,
        workflow_name: str,
        block_id: str,
        block_type: str,
        duration_s: float,
        state: WorkflowState,
        *,
        soul: Optional[Soul] = None,
    ) -> None:
        self._write(
            "block_complete",
            {
                "workflow": workflow_name,
                "block_id": block_id,
                "block_type": block_type,
                "duration_s": round(duration_s, 2),
                "cost_usd": round(state.total_cost_usd, 6),
                "tokens": state.total_tokens,
            },
        )

    def on_block_error(
        self,
        workflow_name: str,
        block_id: str,
        block_type: str,
        duration_s: float,
        error: Exception,
    ) -> None:
        self._write(
            "block_error",
            {
                "workflow": workflow_name,
                "block_id": block_id,
                "block_type": block_type,
                "duration_s": round(duration_s, 2),
                "error": f"{type(error).__name__}: {error}",
            },
        )

    def on_workflow_complete(
        self, workflow_name: str, state: WorkflowState, duration_s: float
    ) -> None:
        self._write(
            "workflow_complete",
            {
                "workflow": workflow_name,
                "duration_s": round(duration_s, 2),
                "cost_usd": round(state.total_cost_usd, 6),
                "tokens": state.total_tokens,
            },
        )

    def on_block_heartbeat(
        self,
        workflow_name: str,
        block_id: str,
        phase: str,
        detail: str,
        timestamp: datetime,
    ) -> None:
        self._write(
            "block_heartbeat",
            {
                "workflow": workflow_name,
                "block_id": block_id,
                "phase": phase,
                "detail": detail,
            },
        )

    def on_workflow_error(self, workflow_name: str, error: Exception, duration_s: float) -> None:
        self._write(
            "workflow_error",
            {
                "workflow": workflow_name,
                "duration_s": round(duration_s, 2),
                "error": f"{type(error).__name__}: {error}",
            },
        )


_composite_logger = logging.getLogger("runsight.observer.composite")


class ChildObserverWrapper:
    """Wraps a parent observer, forwarding non-terminal events and intercepting terminal ones.

    When a child workflow runs inside a WorkflowBlock, its completion/error
    events are local to the child — they must NOT propagate to the parent's
    observer (e.g. StreamingObserver) because the parent workflow is still
    running.  Block-level events (start, complete, error, heartbeat) are
    forwarded normally so the parent observer can track child block progress.
    """

    def __init__(self, parent_observer: WorkflowObserver, child_run_id: Optional[str] = None):
        self._parent = parent_observer
        self.child_run_id = child_run_id

    # -- Forwarded events (block-level) ------------------------------------

    def on_block_start(
        self,
        workflow_name: str,
        block_id: str,
        block_type: str,
        *,
        soul: Optional[Soul] = None,
        **kwargs: Any,
    ) -> None:
        self._parent.on_block_start(workflow_name, block_id, block_type, soul=soul, **kwargs)

    def on_block_complete(
        self,
        workflow_name: str,
        block_id: str,
        block_type: str,
        duration_s: float,
        state: WorkflowState,
        *,
        soul: Optional[Soul] = None,
    ) -> None:
        self._parent.on_block_complete(
            workflow_name, block_id, block_type, duration_s, state, soul=soul
        )

    def on_block_error(
        self,
        workflow_name: str,
        block_id: str,
        block_type: str,
        duration_s: float,
        error: Exception,
    ) -> None:
        self._parent.on_block_error(workflow_name, block_id, block_type, duration_s, error)

    def on_block_heartbeat(
        self,
        workflow_name: str,
        block_id: str,
        phase: str,
        detail: str,
        timestamp: datetime,
    ) -> None:
        self._parent.on_block_heartbeat(workflow_name, block_id, phase, detail, timestamp)

    # -- Intercepted events (workflow-level terminal) -----------------------

    def on_workflow_start(self, workflow_name: str, state: WorkflowState) -> None:
        pass  # child start is not a parent event

    def on_workflow_complete(
        self, workflow_name: str, state: WorkflowState, duration_s: float
    ) -> None:
        pass  # child completion is NOT terminal for parent

    def on_workflow_error(self, workflow_name: str, error: Exception, duration_s: float) -> None:
        pass  # child error is NOT terminal for parent


def build_child_observer(
    parent_observer: WorkflowObserver,
    *,
    block_id: str,
) -> tuple[WorkflowObserver, Optional[str]]:
    """Derive a child observer when the parent can expose child-run context.

    For simple observers, fall back to ChildObserverWrapper so child terminal
    events do not bubble up to the parent observer. When the parent observer
    chain can provide a concrete child run id and child-specific clones, return
    those instead so nested runs get their own persisted lifecycle.
    """

    getter = getattr(parent_observer, "get_child_run_id_for_block", None)
    child_run_id = getter(block_id) if callable(getter) else None

    cloner = getattr(parent_observer, "clone_for_child_run", None)
    if child_run_id and callable(cloner):
        return cloner(child_run_id=child_run_id), child_run_id

    return ChildObserverWrapper(parent_observer), child_run_id


class CompositeObserver:
    """Composite observer that delegates to multiple observers.

    Each observer call is isolated with try/except so that one failing
    observer never prevents the remaining observers from firing.
    """

    def __init__(self, *observers: WorkflowObserver):
        self.observers = list(observers)

    def get_child_run_id_for_block(self, block_id: str) -> Optional[str]:
        for obs in self.observers:
            getter = getattr(obs, "get_child_run_id_for_block", None)
            if not callable(getter):
                continue
            child_run_id = getter(block_id)
            if child_run_id:
                return child_run_id
        return None

    def clone_for_child_run(self, *, child_run_id: str) -> "CompositeObserver":
        child_observers: list[WorkflowObserver] = []
        for obs in self.observers:
            cloner = getattr(obs, "clone_for_child_run", None)
            if callable(cloner):
                child_observers.append(cloner(child_run_id=child_run_id))
            else:
                child_observers.append(ChildObserverWrapper(obs))
        return CompositeObserver(*child_observers)

    def _safe_call(
        self, obs: WorkflowObserver, method_name: str, *args: Any, **kwargs: Any
    ) -> None:
        """Call a method on an observer, catching and logging any exception."""
        try:
            getattr(obs, method_name)(*args, **kwargs)
        except Exception:
            _composite_logger.warning(
                "Observer %s.%s failed", type(obs).__name__, method_name, exc_info=True
            )

    def on_workflow_start(self, workflow_name: str, state: WorkflowState) -> None:
        for obs in self.observers:
            self._safe_call(obs, "on_workflow_start", workflow_name, state)

    def on_block_start(
        self,
        workflow_name: str,
        block_id: str,
        block_type: str,
        *,
        soul: Optional[Soul] = None,
        **kwargs: Any,
    ) -> None:
        kwargs = dict(kwargs)
        if soul is not None:
            kwargs["soul"] = soul
        for obs in self.observers:
            self._safe_call(obs, "on_block_start", workflow_name, block_id, block_type, **kwargs)

    def on_block_complete(
        self,
        workflow_name: str,
        block_id: str,
        block_type: str,
        duration_s: float,
        state: WorkflowState,
        *,
        soul: Optional[Soul] = None,
    ) -> None:
        kwargs: Dict[str, Any] = {}
        if soul is not None:
            kwargs["soul"] = soul
        for obs in self.observers:
            self._safe_call(
                obs,
                "on_block_complete",
                workflow_name,
                block_id,
                block_type,
                duration_s,
                state,
                **kwargs,
            )

    def on_block_error(
        self,
        workflow_name: str,
        block_id: str,
        block_type: str,
        duration_s: float,
        error: Exception,
    ) -> None:
        for obs in self.observers:
            self._safe_call(
                obs, "on_block_error", workflow_name, block_id, block_type, duration_s, error
            )

    def on_workflow_complete(
        self, workflow_name: str, state: WorkflowState, duration_s: float
    ) -> None:
        for obs in self.observers:
            self._safe_call(obs, "on_workflow_complete", workflow_name, state, duration_s)

    def on_block_heartbeat(
        self,
        workflow_name: str,
        block_id: str,
        phase: str,
        detail: str,
        timestamp: datetime,
    ) -> None:
        for obs in self.observers:
            self._safe_call(
                obs,
                "on_block_heartbeat",
                workflow_name,
                block_id,
                phase,
                detail,
                timestamp,
            )

    def on_workflow_error(self, workflow_name: str, error: Exception, duration_s: float) -> None:
        for obs in self.observers:
            self._safe_call(obs, "on_workflow_error", workflow_name, error, duration_s)
