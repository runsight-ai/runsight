"""Fixture builders for SSE stream transport tests."""

from __future__ import annotations

import json
from unittest.mock import Mock

from runsight_api.domain.entities.run import RunStatus


def make_mock_run(run_id: str = "run_sse_1", status: RunStatus = RunStatus.running) -> Mock:
    mock_run = Mock()
    mock_run.id = run_id
    mock_run.workflow_id = "wf_sse_stream"
    mock_run.workflow_name = "wf_sse_stream"
    mock_run.status = status
    mock_run.started_at = 100.0
    mock_run.completed_at = None
    mock_run.duration_s = None
    mock_run.total_cost_usd = 0.0
    mock_run.total_tokens = 0
    mock_run.created_at = 100.0
    return mock_run


def parse_sse_events(raw: str) -> list[dict]:
    """Parse SSE text into a list of {event, data} dicts."""
    events = []
    current_event = None
    current_data = []

    for line in raw.split("\n"):
        if line.startswith("event:"):
            current_event = line[len("event:") :].strip()
        elif line.startswith("data:"):
            current_data.append(line[len("data:") :].strip())
        elif line == "" and current_event is not None:
            data_str = "\n".join(current_data)
            try:
                data = json.loads(data_str)
            except json.JSONDecodeError:
                data = data_str
            events.append({"event": current_event, "data": data})
            current_event = None
            current_data = []

    return events


def make_log(*, id: int, message: str | dict, level: str = "info", timestamp: float) -> Mock:
    log = Mock()
    log.id = id
    log.message = json.dumps(message) if isinstance(message, dict) else message
    log.level = level
    log.timestamp = timestamp
    return log


def context_audit_message(run_id: str) -> dict:
    return {
        "schema_version": "context_audit.v1",
        "event": "context_resolution",
        "run_id": run_id,
        "workflow_name": "child_workflow",
        "node_id": "resolve_context",
        "block_type": "linear",
        "access": "declared",
        "mode": "strict",
        "records": [
            {
                "input_name": "query",
                "from_ref": "results.query",
                "namespace": "results",
                "source": "query",
                "field_path": "query",
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
        "emitted_at": "2026-04-23T00:00:00+00:00",
    }


def make_run_service(*, run: Mock | None = None, logs: list[Mock] | None = None) -> Mock:
    service = Mock()
    service.get_run.return_value = make_mock_run() if run is None else run
    if logs is not None:
        service.get_run_logs.return_value = logs
    return service


def make_execution_service_with_stream(stream) -> Mock:
    service = Mock()
    service.subscribe_stream = stream
    return service
