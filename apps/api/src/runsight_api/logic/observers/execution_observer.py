"""ExecutionObserver: bridges core WorkflowObserver protocol to API DB persistence."""

import asyncio
import json
import logging
import time
import traceback
from typing import Optional

from sqlmodel import Session

from runsight_api.core.context import (
    bind_block_context,
    bind_execution_context,
    clear_block_context,
    clear_execution_context,
)
from runsight_api.domain.entities.log import LogEntry
from runsight_api.domain.entities.run import (
    InvalidStateTransition,
    Run,
    RunNode,
    RunStatus,
    validate_transition,
)
from runsight_core.observer import compute_prompt_hash, compute_soul_version
from runsight_core.primitives import Soul
from runsight_core.state import WorkflowState

logger = logging.getLogger(__name__)


class ExecutionObserver:
    """Implements WorkflowObserver protocol, persisting events to the API database.

    Each method creates its own Session (session-per-write pattern).
    All methods are defensively wrapped — DB errors are logged, never raised.
    """

    def __init__(self, *, engine, run_id: str):
        self.engine = engine
        self.run_id = run_id
        self._last_cumulative_cost: float = 0.0
        self._log_hwm: int = 0

    # ------------------------------------------------------------------
    # on_workflow_start
    # ------------------------------------------------------------------

    def on_workflow_start(self, workflow_name: str, state: WorkflowState) -> None:
        try:
            bind_execution_context(run_id=self.run_id, workflow_name=workflow_name)
            with Session(self.engine) as session:
                run = session.get(Run, self.run_id)
                if run:
                    try:
                        validate_transition(run.status, RunStatus.running)
                    except InvalidStateTransition:
                        logger.warning(
                            "Skipping invalid state transition: %s -> running for run %s",
                            run.status.value,
                            self.run_id,
                        )
                        return
                    run.status = RunStatus.running
                    run.started_at = time.time()
                    run.updated_at = time.time()
                    session.add(run)
                session.commit()

            self._insert_log(
                "info",
                json.dumps(
                    {
                        "event": "workflow_start",
                        "workflow_name": workflow_name,
                    }
                ),
            )
        except Exception:
            logger.warning("ExecutionObserver.on_workflow_start failed", exc_info=True)

    # ------------------------------------------------------------------
    # on_block_start
    # ------------------------------------------------------------------

    def on_block_start(
        self, workflow_name: str, block_id: str, block_type: str, *, soul: Optional[Soul] = None
    ) -> None:
        try:
            bind_block_context(block_id)
            node = RunNode(
                id=f"{self.run_id}:{block_id}",
                run_id=self.run_id,
                node_id=block_id,
                block_type=block_type,
                status="running",
                started_at=time.time(),
            )
            with Session(self.engine) as session:
                session.add(node)
                session.commit()

            self._insert_log(
                "info",
                json.dumps(
                    {
                        "event": "block_start",
                        "block_id": block_id,
                        "block_type": block_type,
                    }
                ),
            )
        except Exception:
            logger.warning("ExecutionObserver.on_block_start failed", exc_info=True)

    # ------------------------------------------------------------------
    # on_block_complete
    # ------------------------------------------------------------------

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
        try:
            cost_delta = state.total_cost_usd - self._last_cumulative_cost
            self._last_cumulative_cost = state.total_cost_usd

            with Session(self.engine) as session:
                node = session.get(RunNode, f"{self.run_id}:{block_id}")
                if node:
                    node.status = "completed"
                    node.duration_s = duration_s
                    node.completed_at = time.time()
                    node.cost_usd = cost_delta
                    node.tokens = {"total": state.total_tokens}
                    result = state.results.get(block_id)
                    node.output = result.output if result else None
                    if soul is not None:
                        node.prompt_hash = compute_prompt_hash(soul)
                        node.soul_version = compute_soul_version(soul)
                    node.updated_at = time.time()
                    session.add(node)
                session.commit()

            self._insert_log(
                "info",
                json.dumps(
                    {
                        "event": "block_complete",
                        "block_id": block_id,
                        "block_type": block_type,
                        "duration_s": duration_s,
                        "cost_delta": cost_delta,
                    }
                ),
            )

            clear_block_context()
            self._persist_execution_log(state, node_id=block_id)
        except Exception:
            logger.warning("ExecutionObserver.on_block_complete failed", exc_info=True)

    # ------------------------------------------------------------------
    # on_block_error
    # ------------------------------------------------------------------

    def on_block_error(
        self,
        workflow_name: str,
        block_id: str,
        block_type: str,
        duration_s: float,
        error: Exception,
    ) -> None:
        try:
            tb_str = "".join(traceback.format_exception(type(error), error, error.__traceback__))

            with Session(self.engine) as session:
                node = session.get(RunNode, f"{self.run_id}:{block_id}")
                if node:
                    node.status = "failed"
                    node.duration_s = duration_s
                    node.completed_at = time.time()
                    node.error = str(error)
                    node.error_traceback = tb_str
                    node.updated_at = time.time()
                    session.add(node)
                session.commit()

            self._insert_log(
                "error",
                json.dumps(
                    {
                        "event": "block_error",
                        "block_id": block_id,
                        "block_type": block_type,
                        "duration_s": duration_s,
                        "error_type": type(error).__name__,
                        "error": str(error),
                    }
                ),
            )

            clear_block_context()
        except Exception:
            logger.warning("ExecutionObserver.on_block_error failed", exc_info=True)

    # ------------------------------------------------------------------
    # on_workflow_complete
    # ------------------------------------------------------------------

    def on_workflow_complete(
        self, workflow_name: str, state: WorkflowState, duration_s: float
    ) -> None:
        try:
            with Session(self.engine) as session:
                run = session.get(Run, self.run_id)
                if run:
                    try:
                        validate_transition(run.status, RunStatus.completed)
                    except InvalidStateTransition:
                        logger.warning(
                            "Skipping invalid state transition: %s -> completed for run %s",
                            run.status.value,
                            self.run_id,
                        )
                        return
                    run.status = RunStatus.completed
                    run.completed_at = time.time()
                    run.duration_s = duration_s
                    run.total_cost_usd = state.total_cost_usd
                    run.total_tokens = state.total_tokens
                    run.results_json = json.dumps(
                        {k: v.model_dump() for k, v in state.results.items()}
                    )
                    run.updated_at = time.time()
                    session.add(run)
                session.commit()

            self._insert_log(
                "info",
                json.dumps(
                    {
                        "event": "workflow_complete",
                        "workflow_name": workflow_name,
                        "duration_s": duration_s,
                    }
                ),
            )

            self._persist_execution_log(state)
            clear_execution_context()
        except Exception:
            logger.warning("ExecutionObserver.on_workflow_complete failed", exc_info=True)

    # ------------------------------------------------------------------
    # on_workflow_error
    # ------------------------------------------------------------------

    def on_workflow_error(self, workflow_name: str, error: Exception, duration_s: float) -> None:
        try:
            is_cancelled = isinstance(error, asyncio.CancelledError)
            status = RunStatus.cancelled if is_cancelled else RunStatus.failed
            level = "warning" if is_cancelled else "error"

            tb_str = "".join(traceback.format_exception(type(error), error, error.__traceback__))

            with Session(self.engine) as session:
                run = session.get(Run, self.run_id)
                if run:
                    try:
                        validate_transition(run.status, status)
                    except InvalidStateTransition:
                        logger.warning(
                            "Skipping invalid state transition: %s -> %s for run %s",
                            run.status.value,
                            status.value,
                            self.run_id,
                        )
                        return
                    run.status = status
                    run.completed_at = time.time()
                    run.duration_s = duration_s
                    run.error = str(error)
                    run.error_traceback = tb_str
                    run.updated_at = time.time()
                    session.add(run)
                session.commit()

            self._insert_log(
                level,
                json.dumps(
                    {
                        "event": "workflow_error",
                        "workflow_name": workflow_name,
                        "duration_s": duration_s,
                        "error_type": type(error).__name__,
                        "error": str(error),
                    }
                ),
            )

            clear_execution_context()
        except Exception:
            logger.warning("ExecutionObserver.on_workflow_error failed", exc_info=True)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _persist_execution_log(self, state: WorkflowState, node_id: Optional[str] = None) -> None:
        """Persist new execution_log entries since the last high-water mark."""
        try:
            new_entries = state.execution_log[self._log_hwm :]
            if not new_entries:
                return
            with Session(self.engine) as session:
                for entry in new_entries:
                    log = LogEntry(
                        run_id=self.run_id,
                        node_id=node_id,
                        level="trace",
                        message=json.dumps(entry),
                    )
                    session.add(log)
                session.commit()
            self._log_hwm = len(state.execution_log)
        except Exception:
            logger.warning("ExecutionObserver._persist_execution_log failed", exc_info=True)

    def _insert_log(self, level: str, message: str, node_id: Optional[str] = None) -> None:
        try:
            entry = LogEntry(
                run_id=self.run_id,
                node_id=node_id,
                level=level,
                message=message,
            )
            with Session(self.engine) as session:
                session.add(entry)
                session.commit()
        except Exception:
            logger.warning("ExecutionObserver._insert_log failed", exc_info=True)
