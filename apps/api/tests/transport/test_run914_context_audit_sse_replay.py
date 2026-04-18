"""RED tests for RUN-914: normalized context audit SSE replay."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import Mock

from fastapi.testclient import TestClient

from runsight_api.domain.entities.run import RunStatus
from runsight_api.main import app
from runsight_api.transport.deps import get_execution_service, get_run_service

client = TestClient(app)


def _make_run(run_id: str = "run_sse_914"):
    run = Mock()
    run.id = run_id
    run.workflow_id = "wf_914"
    run.workflow_name = "context_audit_sse"
    run.status = RunStatus.running
    run.started_at = 100.0
    run.completed_at = None
    run.duration_s = None
    run.total_cost_usd = 0.0
    run.total_tokens = 0
    run.created_at = 100.0
    return run


def _parse_sse_events(raw: str) -> list[dict]:
    events = []
    current_event = None
    current_data = []

    for line in raw.split("\n"):
        if line.startswith("event:"):
            current_event = line[len("event:") :].strip()
        elif line.startswith("data:"):
            current_data.append(line[len("data:") :].strip())
        elif line == "" and current_event is not None:
            events.append(
                {
                    "event": current_event,
                    "data": json.loads("\n".join(current_data)),
                }
            )
            current_event = None
            current_data = []

    return events


def _audit_payload() -> dict:
    return {
        "schema_version": "context_audit.v1",
        "event": "context_resolution",
        "run_id": "run_sse_914",
        "workflow_name": "context_audit_sse",
        "node_id": "summarize",
        "block_type": "linear",
        "access": "declared",
        "mode": "strict",
        "sequence": 7,
        "records": [
            {
                "input_name": "summary",
                "from_ref": "draft.summary",
                "namespace": "results",
                "source": "draft",
                "field_path": "summary",
                "status": "resolved",
                "severity": "allow",
                "value_type": "str",
                "preview": "bounded preview",
                "reason": None,
                "internal": False,
            }
        ],
        "resolved_count": 1,
        "denied_count": 0,
        "warning_count": 0,
        "emitted_at": datetime.now(timezone.utc).isoformat(),
    }


def _log(message: dict, log_id: int):
    log = Mock()
    log.id = log_id
    log.run_id = "run_sse_914"
    log.node_id = message.get("node_id")
    log.level = "trace"
    log.message = json.dumps(message)
    log.timestamp = float(log_id)
    log.created_at = float(log_id)
    return log


def test_sse_replay_emits_context_resolution_for_audit_logs_and_keeps_generic_replay() -> None:
    """Audit rows replay as context_resolution; ordinary rows remain replay events."""
    mock_run_service = Mock()
    mock_run_service.get_run.return_value = _make_run()
    mock_run_service.get_run_logs.return_value = [
        _log({"event": "block_start", "block_id": "draft"}, 1),
        _log(_audit_payload(), 2),
    ]

    mock_exec_service = Mock()

    async def _fake_stream(run_id: str):
        yield {"event": "run_completed", "data": {"run_id": run_id}}

    mock_exec_service.subscribe_stream = _fake_stream
    app.dependency_overrides[get_run_service] = lambda: mock_run_service
    app.dependency_overrides[get_execution_service] = lambda: mock_exec_service

    try:
        with client.stream("GET", "/api/runs/run_sse_914/stream") as response:
            body = response.read().decode()
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    events = _parse_sse_events(body)
    assert [event["event"] for event in events] == [
        "replay",
        "context_resolution",
        "run_completed",
    ]
    assert events[0]["data"] == {"event": "block_start", "block_id": "draft"}
    assert events[1]["data"]["schema_version"] == "context_audit.v1"
    assert events[1]["data"]["event"] == "context_resolution"
    assert events[1]["data"]["node_id"] == "summarize"
