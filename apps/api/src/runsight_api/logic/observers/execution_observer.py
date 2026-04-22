"""ExecutionObserver: bridges core WorkflowObserver protocol to API persistence."""

import asyncio
import json
import logging
import time
import traceback
import uuid
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Optional

from runsight_core.budget_enforcement import BudgetKilledException
from runsight_core.context_governance import (
    ContextAuditEventV1,
    ContextAuditSeverity,
    redact_context_audit_event_preview,
)
from runsight_core.identity import EntityKind, EntityRef, validate_entity_id
from runsight_core.observer import compute_prompt_hash, compute_soul_version
from runsight_core.primitives import Soul
from runsight_core.redaction import redact_runtime_value_for_state, redact_text_for_state
from runsight_core.state import WorkflowState
from sqlmodel import Session

from runsight_api.core.context import (
    bind_block_context,
    bind_execution_context,
    clear_block_context,
    clear_execution_context,
)
from runsight_api.data.repositories.run_repo import RunRepository
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


@contextmanager
def _run_repo(engine):
    with Session(engine) as session:
        yield RunRepository(session)


def _is_workflow_block_type(block_type: str) -> bool:
    normalized = block_type.strip().lower()
    return normalized in {"workflow", "workflowblock"}


def _serialize_result_value(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, dict):
        return {key: _serialize_result_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_serialize_result_value(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _context_audit_level(event: ContextAuditEventV1) -> str:
    severities = {record.severity for record in event.records}
    if ContextAuditSeverity.ERROR.value in severities:
        return "error"
    if event.warning_count > 0 or ContextAuditSeverity.WARN.value in severities:
        return "warning"
    return "trace"


def _redact_for_state(value: Any, state: WorkflowState | None) -> Any:
    return redact_runtime_value_for_state(value, state)


def _redact_text(value: str, state: WorkflowState | None) -> str:
    return redact_text_for_state(value, state)


class DatabaseRunLifecycleWriter:
    """Owns Run lifecycle persistence for a single run."""

    def __init__(self, *, engine, run_id: str):
        self.engine = engine
        self.run_id = run_id

    def start(self) -> bool:
        with _run_repo(self.engine) as repo:
            run = repo.get_run(self.run_id)
            if run:
                try:
                    validate_transition(run.status, RunStatus.running)
                except InvalidStateTransition:
                    logger.warning(
                        "Skipping invalid state transition: %s -> running for run %s",
                        run.status.value,
                        self.run_id,
                    )
                    return False
                now = time.time()
                run.status = RunStatus.running
                run.started_at = now
                run.updated_at = now
                repo.update_run(run)
        return True

    def complete(self, state: WorkflowState, duration_s: float) -> bool:
        with _run_repo(self.engine) as repo:
            run = repo.get_run(self.run_id)
            if run:
                try:
                    validate_transition(run.status, RunStatus.completed)
                except InvalidStateTransition:
                    logger.warning(
                        "Skipping invalid state transition: %s -> completed for run %s",
                        run.status.value,
                        self.run_id,
                    )
                    return False
                now = time.time()
                run.status = RunStatus.completed
                run.completed_at = now
                run.duration_s = duration_s
                run.total_cost_usd = state.total_cost_usd
                run.total_tokens = state.total_tokens
                serialized_results = {
                    key: _serialize_result_value(value) for key, value in state.results.items()
                }
                run.results_json = json.dumps(_redact_for_state(serialized_results, state))
                run.updated_at = now
                repo.update_run(run)
        return True

    def error(
        self,
        error: Exception,
        duration_s: float,
        *,
        state: WorkflowState | None = None,
    ) -> bool:
        is_cancelled = isinstance(error, asyncio.CancelledError)
        status = RunStatus.cancelled if is_cancelled else RunStatus.failed
        tb_str = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        error_message = _redact_text(str(error), state)
        tb_str = _redact_text(tb_str, state)

        with _run_repo(self.engine) as repo:
            run = repo.get_run(self.run_id)
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
                    return False
                now = time.time()
                run.status = status
                run.completed_at = now
                run.duration_s = duration_s
                run.error = error_message
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

                run.updated_at = now
                repo.update_run(run)
        return True


class DatabaseNodeLifecycleWriter:
    """Owns RunNode persistence and child-run creation for a single run."""

    def __init__(self, *, engine, run_id: str):
        self.engine = engine
        self.run_id = run_id
        self._last_cumulative_cost: float = 0.0
        self._last_cost_delta: float = 0.0

    def get_child_run_id(self, block_id: str) -> Optional[str]:
        try:
            with _run_repo(self.engine) as repo:
                node = repo.get_node(f"{self.run_id}:{block_id}")
                return node.child_run_id if node else None
        except Exception:
            logger.warning(
                "ExecutionObserver.get_child_run_id_for_block failed for run %s block %s",
                self.run_id,
                block_id,
                exc_info=True,
            )
            return None

    def start(
        self,
        workflow_name: str,
        block_id: str,
        block_type: str,
        *,
        soul: Optional[Soul] = None,
        **kwargs: Any,
    ) -> None:
        del soul

        node = RunNode(
            id=f"{self.run_id}:{block_id}",
            run_id=self.run_id,
            node_id=block_id,
            block_type=block_type,
            status=NodeStatus.running,
            started_at=time.time(),
        )

        if _is_workflow_block_type(block_type):
            child_run_id = f"{self.run_id}:child:{block_id}:{uuid.uuid4().hex[:8]}"
            parent_run = self._get_run()
            parent_depth = parent_run.depth if parent_run else 0
            parent_root = parent_run.root_run_id if parent_run else None
            root_run_id = parent_root if parent_root is not None else self.run_id
            child_workflow_id = kwargs.get("child_workflow_id") or f"wf_child_{block_id}"
            child_workflow_name = kwargs.get("child_workflow_name") or workflow_name

            child_run = Run(
                id=child_run_id,
                workflow_id=child_workflow_id,
                workflow_name=child_workflow_name,
                status=RunStatus.running,
                task_json="{}",
                branch=parent_run.branch if parent_run else "main",
                warnings_json=None,
                source=parent_run.source if parent_run else "manual",
                commit_sha=parent_run.commit_sha if parent_run else None,
                parent_run_id=self.run_id,
                parent_node_id=f"{self.run_id}:{block_id}",
                root_run_id=root_run_id,
                depth=parent_depth + 1,
                started_at=time.time(),
            )
            node.child_run_id = child_run_id

            with _run_repo(self.engine) as repo:
                repo.create_node(node)
                repo.create_run(child_run)
            return

        with _run_repo(self.engine) as repo:
            repo.create_node(node)

    def heartbeat(self, block_id: str, phase: str) -> None:
        with _run_repo(self.engine) as repo:
            node = repo.get_node(f"{self.run_id}:{block_id}")
            if node:
                node.last_phase = phase
                node.updated_at = time.time()
                repo.update_node(node)

    def complete(
        self,
        block_id: str,
        duration_s: float,
        state: WorkflowState,
        *,
        soul: Optional[Soul] = None,
    ) -> float:
        cost_delta = state.total_cost_usd - self._last_cumulative_cost
        self._last_cumulative_cost = state.total_cost_usd
        self._last_cost_delta = cost_delta

        with _run_repo(self.engine) as repo:
            node = repo.get_node(f"{self.run_id}:{block_id}")
            if node:
                now = time.time()
                node.status = NodeStatus.completed
                node.duration_s = duration_s
                node.completed_at = now
                node.cost_usd = cost_delta
                node.tokens = {"total": state.total_tokens}
                result = state.results.get(block_id)
                node.output = _redact_text(result.output, state) if result else None
                if soul is not None:
                    node.prompt_hash = compute_prompt_hash(soul)
                    node.soul_version = compute_soul_version(soul)
                node.updated_at = now
                repo.update_node(node)

        return cost_delta

    def error(
        self,
        block_id: str,
        duration_s: float,
        error: Exception,
        *,
        state: WorkflowState | None = None,
    ) -> None:
        tb_str = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        error_message = _redact_text(str(error), state)
        tb_str = _redact_text(tb_str, state)

        with _run_repo(self.engine) as repo:
            node = repo.get_node(f"{self.run_id}:{block_id}")
            if node:
                now = time.time()
                node.status = NodeStatus.failed
                node.duration_s = duration_s
                node.completed_at = now
                node.error = error_message
                node.error_traceback = tb_str
                node.updated_at = now
                repo.update_node(node)
                if node.child_run_id:
                    child_run = repo.get_run(node.child_run_id)
                    if child_run:
                        try:
                            validate_transition(child_run.status, RunStatus.failed)
                        except InvalidStateTransition:
                            pass
                        else:
                            child_run.status = RunStatus.failed
                            child_run.completed_at = now
                            child_run.duration_s = duration_s
                            child_run.error = error_message
                            child_run.error_traceback = tb_str
                            child_run.updated_at = now
                            repo.update_run(child_run)

    def _get_run(self) -> Optional[Run]:
        try:
            with _run_repo(self.engine) as repo:
                return repo.get_run(self.run_id)
        except Exception:
            logger.warning("ExecutionObserver._get_run failed", exc_info=True)
            return None


class DatabaseEventLogSink:
    """Owns structured event-log writes for a single run."""

    def __init__(self, *, engine, run_id: str):
        self.engine = engine
        self.run_id = run_id

    def write(self, level: str, message: str, node_id: Optional[str] = None) -> None:
        entry = LogEntry(
            run_id=self.run_id,
            node_id=node_id,
            level=level,
            message=message,
        )
        with _run_repo(self.engine) as repo:
            repo.create_log(entry)


class DatabaseExecutionLogSink:
    """Owns incremental execution-log tail persistence for a single run."""

    def __init__(self, *, engine, run_id: str):
        self.engine = engine
        self.run_id = run_id
        self.high_water_mark = 0

    def persist(self, state: WorkflowState, node_id: Optional[str] = None) -> None:
        new_entries = state.execution_log[self.high_water_mark :]
        if not new_entries:
            return

        with _run_repo(self.engine) as repo:
            for entry in new_entries:
                log = LogEntry(
                    run_id=self.run_id,
                    node_id=node_id,
                    level="trace",
                    message=json.dumps(_redact_for_state(entry, state)),
                )
                repo.create_log(log)

        self.high_water_mark = len(state.execution_log)


class DefaultContextAuditSerializer:
    """Owns context-audit payload shaping before persistence."""

    def serialize(self, event: ContextAuditEventV1) -> str:
        return redact_context_audit_event_preview(event).model_dump_json()


class DatabaseContextAuditSink:
    """Owns persisted context-audit log writes for a single run."""

    def __init__(self, *, event_log_sink: DatabaseEventLogSink):
        self.event_log_sink = event_log_sink

    def write(self, event: ContextAuditEventV1, payload: str) -> None:
        self.event_log_sink.write(
            _context_audit_level(event),
            payload,
            node_id=event.node_id,
        )


class ExecutionObserver:
    """WorkflowObserver facade composed from lifecycle writers and log sinks."""

    def __init__(
        self,
        *,
        engine,
        run_id: str,
        run_lifecycle_writer: Optional[DatabaseRunLifecycleWriter] = None,
        node_lifecycle_writer: Optional[DatabaseNodeLifecycleWriter] = None,
        event_log_sink: Optional[DatabaseEventLogSink] = None,
        execution_log_sink: Optional[DatabaseExecutionLogSink] = None,
        context_audit_serializer: Optional[DefaultContextAuditSerializer] = None,
        context_audit_sink: Optional[DatabaseContextAuditSink] = None,
    ):
        self.engine = engine
        self.run_id = run_id
        self.run_lifecycle_writer = run_lifecycle_writer or DatabaseRunLifecycleWriter(
            engine=engine,
            run_id=run_id,
        )
        self.node_lifecycle_writer = node_lifecycle_writer or DatabaseNodeLifecycleWriter(
            engine=engine,
            run_id=run_id,
        )
        self.event_log_sink = event_log_sink or DatabaseEventLogSink(
            engine=engine,
            run_id=run_id,
        )
        self.execution_log_sink = execution_log_sink or DatabaseExecutionLogSink(
            engine=engine,
            run_id=run_id,
        )
        self.context_audit_serializer = context_audit_serializer or DefaultContextAuditSerializer()
        self.context_audit_sink = context_audit_sink or DatabaseContextAuditSink(
            event_log_sink=self.event_log_sink
        )

    @property
    def _log_hwm(self) -> int:
        return getattr(self.execution_log_sink, "high_water_mark", 0)

    @_log_hwm.setter
    def _log_hwm(self, value: int) -> None:
        if hasattr(self.execution_log_sink, "high_water_mark"):
            self.execution_log_sink.high_water_mark = value

    def get_child_run_id_for_block(self, block_id: str) -> Optional[str]:
        return self.node_lifecycle_writer.get_child_run_id(block_id)

    def clone_for_child_run(self, *, child_run_id: str) -> "ExecutionObserver":
        return ExecutionObserver(
            engine=self.engine,
            run_id=child_run_id,
            context_audit_serializer=self.context_audit_serializer,
        )

    def record_workflow_input_snapshot(
        self,
        input_schema: Any,
        inputs: Any,
        *,
        redactor: Any = None,
    ) -> None:
        try:
            from runsight_api.logic.services.execution_service import (
                _workflow_input_schema_snapshot,
                _workflow_input_values_snapshot,
            )

            with _run_repo(self.engine) as repo:
                run = repo.get_run(self.run_id)
                if run:
                    run.workflow_inputs = _workflow_input_values_snapshot(
                        input_schema or {},
                        inputs,
                        redactor=redactor,
                    )
                    run.workflow_input_schema = _workflow_input_schema_snapshot(input_schema or {})
                    run.updated_at = time.time()
                    repo.update_run(run)
        except Exception:
            logger.warning(
                "ExecutionObserver.record_workflow_input_snapshot failed for run %s",
                self.run_id,
                exc_info=True,
            )

    def on_workflow_start(self, workflow_name: str, state: WorkflowState) -> None:
        del state
        try:
            bind_execution_context(run_id=self.run_id, workflow_name=workflow_name)
            workflow_ref = self._workflow_ref(workflow_name)

            should_log = True
            try:
                should_log = self.run_lifecycle_writer.start()
            except Exception:
                logger.warning("ExecutionObserver.on_workflow_start failed", exc_info=True)

            if should_log:
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
            try:
                self.node_lifecycle_writer.start(
                    workflow_name,
                    block_id,
                    block_type,
                    soul=soul,
                    **kwargs,
                )
            except Exception:
                logger.warning("ExecutionObserver.on_block_start failed", exc_info=True)

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

    def on_block_heartbeat(
        self,
        workflow_name: str,
        block_id: str,
        phase: str,
        detail: str,
        timestamp: datetime,
    ) -> None:
        del workflow_name, detail, timestamp
        try:
            self.node_lifecycle_writer.heartbeat(block_id, phase)
        except Exception:
            logger.warning("ExecutionObserver.on_block_heartbeat failed", exc_info=True)

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
        del workflow_name
        cost_delta = state.total_cost_usd
        try:
            try:
                cost_delta = self.node_lifecycle_writer.complete(
                    block_id,
                    duration_s,
                    state,
                    soul=soul,
                )
            except Exception:
                logger.warning("ExecutionObserver.on_block_complete failed", exc_info=True)

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

            self._persist_execution_log(state, node_id=block_id)
        finally:
            try:
                clear_block_context()
            except Exception:
                logger.warning("ExecutionObserver.on_block_complete failed", exc_info=True)

    def on_block_error(
        self,
        workflow_name: str,
        block_id: str,
        block_type: str,
        duration_s: float,
        error: Exception,
        *,
        state: WorkflowState | None = None,
    ) -> None:
        del workflow_name
        try:
            try:
                self.node_lifecycle_writer.error(
                    block_id,
                    duration_s,
                    error,
                    state=state,
                )
            except Exception:
                logger.warning("ExecutionObserver.on_block_error failed", exc_info=True)

            self._insert_log(
                "error",
                json.dumps(
                    _redact_for_state(
                        {
                            "event": "block_error",
                            "block_id": block_id,
                            "block_type": block_type,
                            "duration_s": duration_s,
                            "error_type": type(error).__name__,
                            "error": str(error),
                        },
                        state,
                    )
                ),
            )
        finally:
            try:
                clear_block_context()
            except Exception:
                logger.warning("ExecutionObserver.on_block_error failed", exc_info=True)

    def on_workflow_complete(
        self,
        workflow_name: str,
        state: WorkflowState,
        duration_s: float,
    ) -> None:
        try:
            should_continue = True
            try:
                should_continue = self.run_lifecycle_writer.complete(state, duration_s)
            except Exception:
                logger.warning("ExecutionObserver.on_workflow_complete failed", exc_info=True)

            if not should_continue:
                return

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
        finally:
            try:
                clear_execution_context()
            except Exception:
                logger.warning("ExecutionObserver.on_workflow_complete failed", exc_info=True)

    def on_workflow_error(
        self,
        workflow_name: str,
        error: Exception,
        duration_s: float,
        *,
        state: WorkflowState | None = None,
    ) -> None:
        try:
            should_continue = True
            try:
                should_continue = self.run_lifecycle_writer.error(
                    error,
                    duration_s,
                    state=state,
                )
            except Exception:
                logger.warning("ExecutionObserver.on_workflow_error failed", exc_info=True)

            if not should_continue:
                return

            level = "warning" if isinstance(error, asyncio.CancelledError) else "error"
            self._insert_log(
                level,
                json.dumps(
                    _redact_for_state(
                        {
                            "event": "workflow_error",
                            "workflow_name": workflow_name,
                            "duration_s": duration_s,
                            "error_type": type(error).__name__,
                            "error": str(error),
                        },
                        state,
                    )
                ),
            )
        finally:
            try:
                clear_execution_context()
            except Exception:
                logger.warning("ExecutionObserver.on_workflow_error failed", exc_info=True)

    def on_context_resolution(self, event: ContextAuditEventV1) -> None:
        try:
            payload = self.context_audit_serializer.serialize(event)
            self.context_audit_sink.write(event, payload)
        except Exception:
            logger.warning("ExecutionObserver.on_context_resolution failed", exc_info=True)

    def _persist_execution_log(self, state: WorkflowState, node_id: Optional[str] = None) -> None:
        try:
            self.execution_log_sink.persist(state, node_id=node_id)
        except Exception:
            logger.warning("ExecutionObserver._persist_execution_log failed", exc_info=True)

    def _insert_log(self, level: str, message: str, node_id: Optional[str] = None) -> None:
        try:
            self.event_log_sink.write(level, message, node_id=node_id)
        except Exception:
            logger.warning("ExecutionObserver._insert_log failed", exc_info=True)

    @staticmethod
    def _workflow_ref(workflow_name: str) -> str:
        try:
            validate_entity_id(workflow_name, EntityKind.WORKFLOW)
            return str(EntityRef(EntityKind.WORKFLOW, workflow_name))
        except ValueError:
            return workflow_name
