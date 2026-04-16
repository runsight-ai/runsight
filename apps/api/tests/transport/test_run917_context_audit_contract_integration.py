"""Purple integration tests for RUN-917 context audit API/SSE contracts."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import Mock

from fastapi.testclient import TestClient
from runsight_core.context_governance import ContextAuditEventV1, ContextAuditRecordV1
from sqlmodel import SQLModel, Session, create_engine, select

from runsight_api.domain.entities.log import LogEntry
from runsight_api.domain.entities.run import Run, RunStatus
from runsight_api.logic.observers.execution_observer import ExecutionObserver
from runsight_api.logic.observers.streaming_observer import StreamingObserver
from runsight_api.main import app
from runsight_api.transport.deps import get_run_service

client = TestClient(app)


def _engine():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine


def _seed_run(engine, run_id: str = "run_917") -> None:
    with Session(engine) as session:
        session.add(
            Run(
                id=run_id,
                workflow_id="wf_917",
                workflow_name="context_governance_integration",
                status=RunStatus.running,
                task_json="{}",
            )
        )
        session.commit()


def _event(run_id: str = "run_917") -> ContextAuditEventV1:
    return ContextAuditEventV1(
        run_id=run_id,
        workflow_name="context_governance_integration",
        node_id="review",
        block_type="linear",
        access="declared",
        mode="strict",
        sequence=17,
        records=[
            ContextAuditRecordV1(
                input_name="summary",
                from_ref="draft.summary",
                namespace="results",
                source="draft",
                field_path="summary",
                status="resolved",
                severity="allow",
                value_type="str",
                preview="safe draft",
                reason=None,
                internal=False,
            )
        ],
        resolved_count=1,
        denied_count=0,
        warning_count=0,
        emitted_at=datetime.now(timezone.utc),
    )


def _mock_run(run_id: str = "run_917"):
    run = Mock()
    run.id = run_id
    run.workflow_id = "wf_917"
    run.workflow_name = "context_governance_integration"
    run.status = RunStatus.running
    run.started_at = 100.0
    run.completed_at = None
    run.duration_s = None
    run.total_cost_usd = 0.0
    run.total_tokens = 0
    run.created_at = 100.0
    return run


def _malformed_log():
    log = Mock()
    log.id = "malformed"
    log.run_id = "run_917"
    log.node_id = "broken"
    log.level = "trace"
    log.message = json.dumps(
        {
            "schema_version": "context_audit.v1",
            "event": "context_resolution",
            "node_id": "missing_required_fields",
        }
    )
    log.timestamp = 1.0
    log.created_at = 1.0
    return log


def _logs(engine) -> list[LogEntry]:
    with Session(engine) as session:
        return list(session.exec(select(LogEntry)).all())


def _normalized(payload: object) -> dict:
    return ContextAuditEventV1.model_validate(payload).model_dump(mode="json")


def test_execution_streaming_history_and_gui_contract_payloads_match() -> None:
    """One ContextAuditEventV1 payload must survive DB logs, history, and SSE unchanged."""
    engine = _engine()
    _seed_run(engine)
    event = _event()
    execution_observer = ExecutionObserver(engine=engine, run_id="run_917")
    streaming_observer = StreamingObserver(run_id="run_917")

    execution_observer.on_context_resolution(event)
    streaming_observer.on_context_resolution(event)

    service = Mock()
    service.get_run.return_value = _mock_run()
    service.get_run_logs.return_value = [_malformed_log(), *_logs(engine)]
    app.dependency_overrides[get_run_service] = lambda: service
    try:
        response = client.get("/api/runs/run_917/context-audit")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    queued = streaming_observer.queue.get_nowait()
    assert queued["event"] == "context_resolution"
    assert _normalized(body["items"][0]) == _normalized(queued["data"])
    assert _normalized(body["items"][0]) == event.model_dump(mode="json")
    assert "missing_required_fields" not in json.dumps(body)
