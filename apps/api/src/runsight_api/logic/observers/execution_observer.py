"""ExecutionObserver: bridges core WorkflowObserver protocol to API DB persistence."""

import asyncio
import json
import logging
import time
import traceback
import uuid
from datetime import datetime
from typing import Any, Optional

from runsight_core.identity import EntityKind, EntityRef, validate_entity_id
from runsight_core.observer import compute_prompt_hash, compute_soul_version
from runsight_core.primitives import Soul
from runsight_core.state import WorkflowState
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
    NodeStatus,
    Run,
    RunNode,
    RunStatus,
    validate_transition,
)

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

    @staticmethod
    def _is_workflow_block_type(block_type: str) -> bool:
        normalized = block_type.strip().lower()
        return normalized in {"workflow", "workflowblock"}

    @classmethod
    def _serialize_result_value(cls, value: Any) -> Any:
        if hasattr(value, "model_dump"):
            return value.model_dump()
        if isinstance(value, dict):
            return {key: cls._serialize_result_value(item) for key, item in value.items()}
        if isinstance(value, list):
            return [cls._serialize_result_value(item) for item in value]
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        return str(value)

    def get_child_run_id_for_block(self, block_id: str) -> Optional[str]:
        try:
            with Session(self.engine) as session:
                node = session.get(RunNode, f"{self.run_id}:{block_id}")
                return node.child_run_id if node else None
        except Exception:
            logger.warning(
                "ExecutionObserver.get_child_run_id_for_block failed for run %s block %s",
                self.run_id,
                block_id,
                exc_info=True,
            )
            return None

    def clone_for_child_run(self, *, child_run_id: str) -> "ExecutionObserver":
        return ExecutionObserver(engine=self.engine, run_id=child_run_id)

    # ------------------------------------------------------------------
    # on_workflow_start
    # ------------------------------------------------------------------

    def on_workflow_start(self, workflow_name: str, state: WorkflowState) -> None:
        try:
            bind_execution_context(run_id=self.run_id, workflow_name=workflow_name)
            try:
                validate_entity_id(workflow_name, EntityKind.WORKFLOW)
                workflow_ref = str(EntityRef(EntityKind.WORKFLOW, workflow_name))
            except ValueError:
                workflow_ref = workflow_name
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
                        "workflow_ref": workflow_ref,
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
        self,
        workflow_name: str,
        block_id: str,
        block_type: str,
        *,
        soul: Optional[Soul] = None,
        **kwargs: Any,
    ) -> None:
        try:
            bind_block_context(block_id)
            node = RunNode(
                id=f"{self.run_id}:{block_id}",
                run_id=self.run_id,
                node_id=block_id,
                block_type=block_type,
                status=NodeStatus.running,
                started_at=time.time(),
            )

            # If the block is a workflow call, create a child Run record
            if self._is_workflow_block_type(block_type):
                child_run_id = f"{self.run_id}:child:{block_id}:{uuid.uuid4().hex[:8]}"
                parent_run = self._get_run()
                parent_depth = parent_run.depth if parent_run else 0
                parent_root = parent_run.root_run_id if parent_run else None
                # Root run has root_run_id=None; children point to the outermost ancestor
                root_run_id = parent_root if parent_root is not None else self.run_id
                child_workflow_id = kwargs.get("child_workflow_id") or f"wf_child_{block_id}"
                child_workflow_name = kwargs.get("child_workflow_name") or workflow_name

                child_run = Run(
                    id=child_run_id,
                    workflow_id=child_workflow_id,
                    workflow_name=child_workflow_name,
                    status=RunStatus.running,
                    task_json="{}",
                    warnings_json=None,
                    parent_run_id=self.run_id,
                    parent_node_id=f"{self.run_id}:{block_id}",
                    root_run_id=root_run_id,
                    depth=parent_depth + 1,
                    started_at=time.time(),
                )
                node.child_run_id = child_run_id

                with Session(self.engine) as session:
                    session.add(node)
                    session.add(child_run)
                    session.commit()
            else:
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
    # on_block_heartbeat
    # ------------------------------------------------------------------

    def on_block_heartbeat(
        self,
        workflow_name: str,
        block_id: str,
        phase: str,
        detail: str,
        timestamp: datetime,
    ) -> None:
        try:
            with Session(self.engine) as session:
                node = session.get(RunNode, f"{self.run_id}:{block_id}")
                if node:
                    node.last_phase = phase
                    node.updated_at = time.time()
                    session.add(node)
                session.commit()
        except Exception:
            logger.warning("ExecutionObserver.on_block_heartbeat failed", exc_info=True)

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
                    node.status = NodeStatus.completed
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
                    node.status = NodeStatus.failed
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
                        {
                            key: self._serialize_result_value(value)
                            for key, value in state.results.items()
                        }
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
            from runsight_core.budget_enforcement import BudgetKilledException

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

                    if isinstance(error, BudgetKilledException):
                        run.fail_reason = "budget_exceeded"
                        run.fail_metadata = {
                            "scope": error.scope,
                            "block_id": error.block_id,
                            "limit_kind": error.limit_kind,
                            "limit_value": error.limit_value,
                            "actual_value": error.actual_value,
                        }

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

    def _get_run(self) -> Optional[Run]:
        """Load the Run record for this observer's run_id."""
        try:
            with Session(self.engine) as session:
                return session.get(Run, self.run_id)
        except Exception:
            logger.warning("ExecutionObserver._get_run failed", exc_info=True)
            return None

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
