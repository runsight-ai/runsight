"""
RED tests for RUN-913 API observers: context audit persistence and streaming.

Core emits ContextAuditEventV1; API observers must persist/stream that event as
bounded JSON without exposing raw secret values.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from runsight_core.context_governance import (
    ContextAuditEventV1,
    ContextAuditRecordV1,
)
from sqlmodel import SQLModel, Session, create_engine, select

from runsight_api.domain.entities.log import LogEntry
from runsight_api.domain.entities.run import Run, RunStatus
from runsight_api.logic.observers.execution_observer import ExecutionObserver
from runsight_api.logic.observers.streaming_observer import StreamingObserver


def _db_engine():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine


def _seed_run(engine, run_id: str = "run_913") -> None:
    with Session(engine) as session:
        session.add(
            Run(
                id=run_id,
                workflow_id="wf_913",
                workflow_name="context_audit_observer",
                status=RunStatus.running,
                task_json="{}",
            )
        )
        session.commit()


def _event(
    *,
    node_id: str = "summarize",
    severity: str = "allow",
    status: str = "resolved",
    warning_count: int = 0,
    denied_count: int = 0,
) -> ContextAuditEventV1:
    return ContextAuditEventV1(
        run_id="run_913",
        workflow_name="context_audit_observer",
        node_id=node_id,
        block_type="linear",
        access="declared",
        mode="strict",
        records=[
            ContextAuditRecordV1(
                input_name="api_key",
                from_ref="metadata.credentials.api_key",
                namespace="metadata",
                source="credentials",
                field_path="api_key",
                status=status,
                severity=severity,
                value_type="str",
                preview="super-secret-api-key",
                reason=None if status == "resolved" else "missing credential",
            )
        ],
        resolved_count=1 if status == "resolved" else 0,
        denied_count=denied_count,
        warning_count=warning_count,
        emitted_at=datetime.now(timezone.utc),
    )


def _logged_context_events(engine, run_id: str = "run_913") -> list[LogEntry]:
    with Session(engine) as session:
        return list(
            session.exec(
                select(LogEntry)
                .where(LogEntry.run_id == run_id)
                .where(LogEntry.node_id == "summarize")
            ).all()
        )


def _validate_stream_payload(payload: object) -> ContextAuditEventV1:
    if isinstance(payload, str):
        return ContextAuditEventV1.model_validate_json(payload)
    return ContextAuditEventV1.model_validate(payload)


def test_execution_observer_persists_context_audit_event_as_valid_json() -> None:
    """ExecutionObserver writes one LogEntry with ContextAuditEventV1 JSON."""
    engine = _db_engine()
    _seed_run(engine)
    observer = ExecutionObserver(engine=engine, run_id="run_913")

    observer.on_context_resolution(_event())

    logs = _logged_context_events(engine)
    assert len(logs) == 1
    log = logs[0]
    assert log.node_id == "summarize"
    assert log.level == "trace"
    parsed = ContextAuditEventV1.model_validate_json(log.message)
    assert parsed.event == "context_resolution"
    assert parsed.node_id == "summarize"
    assert parsed.records[0].input_name == "api_key"
    assert "super-secret-api-key" not in log.message


def test_execution_observer_maps_warning_audit_severity_to_warning_log_level() -> None:
    """Warning/error audit severities must not be flattened to info logs."""
    engine = _db_engine()
    _seed_run(engine)
    observer = ExecutionObserver(engine=engine, run_id="run_913")

    observer.on_context_resolution(_event(severity="warn", status="missing", warning_count=1))

    logs = _logged_context_events(engine)
    assert len(logs) == 1
    assert logs[0].level == "warning"
    parsed = ContextAuditEventV1.model_validate_json(logs[0].message)
    assert parsed.warning_count == 1


def test_streaming_observer_queues_context_resolution_sse_event() -> None:
    """StreamingObserver emits the dedicated context_resolution SSE event name."""
    observer = StreamingObserver(run_id="run_913")

    observer.on_context_resolution(_event())

    queued = observer.queue.get_nowait()
    assert queued["event"] == "context_resolution"
    parsed = _validate_stream_payload(queued["data"])
    assert parsed.event == "context_resolution"
    assert parsed.node_id == "summarize"
    assert "super-secret-api-key" not in json.dumps(queued, default=str)
