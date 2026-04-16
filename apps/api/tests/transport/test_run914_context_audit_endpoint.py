"""RED tests for RUN-914: historical context audit endpoint."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import Mock

from fastapi.testclient import TestClient

from runsight_api.domain.entities.run import RunStatus
from runsight_api.main import app
from runsight_api.transport.deps import get_run_service

client = TestClient(app)


def _make_run(run_id: str = "run_914"):
    run = Mock()
    run.id = run_id
    run.workflow_id = "wf_914"
    run.workflow_name = "context_audit_endpoint"
    run.status = RunStatus.running
    run.started_at = 100.0
    run.completed_at = None
    run.duration_s = None
    run.total_cost_usd = 0.0
    run.total_tokens = 0
    run.created_at = 100.0
    return run


def _audit_payload(
    *,
    node_id: str,
    sequence: int | None,
    input_name: str = "summary",
    from_ref: str = "draft.summary",
) -> dict:
    return {
        "schema_version": "context_audit.v1",
        "event": "context_resolution",
        "run_id": "run_914",
        "workflow_name": "context_audit_endpoint",
        "node_id": node_id,
        "block_type": "linear",
        "access": "declared",
        "mode": "strict",
        "sequence": sequence,
        "records": [
            {
                "input_name": input_name,
                "from_ref": from_ref,
                "namespace": "results",
                "source": from_ref.split(".")[0],
                "field_path": ".".join(from_ref.split(".")[1:]) or None,
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


def _log(
    message: str | dict,
    *,
    log_id: int,
    node_id: str | None = None,
    created_at: float | None = None,
):
    log = Mock()
    log.id = log_id
    log.run_id = "run_914"
    log.node_id = node_id
    log.level = "trace"
    log.message = json.dumps(message) if isinstance(message, dict) else message
    log.timestamp = float(log_id)
    log.created_at = created_at if created_at is not None else float(log_id)
    return log


def _mock_service(*, run_exists: bool = True, logs: list | None = None):
    service = Mock()
    service.get_run.return_value = _make_run() if run_exists else None
    service.get_run_logs.return_value = logs or []
    return service


def test_context_audit_endpoint_returns_paginated_valid_audit_events_only() -> None:
    """Endpoint parses valid audit log rows, skips malformed/non-audit rows, and paginates."""
    valid_first = _audit_payload(node_id="draft", sequence=1)
    valid_second = _audit_payload(node_id="review", sequence=2)
    malformed_audit = {
        "schema_version": "context_audit.v1",
        "event": "context_resolution",
        "node_id": "broken",
    }
    service = _mock_service(
        logs=[
            _log({"event": "block_start", "block_id": "draft"}, log_id=1),
            _log("not json", log_id=2),
            _log(valid_second, log_id=3),
            _log(malformed_audit, log_id=4),
            _log(valid_first, log_id=5),
        ]
    )
    app.dependency_overrides[get_run_service] = lambda: service

    try:
        response = client.get("/api/runs/run_914/context-audit?page_size=1")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    data = response.json()
    assert data["page_size"] == 1
    assert data["has_next_page"] is True
    assert data["end_cursor"] is not None
    assert len(data["items"]) == 1
    assert data["items"][0]["schema_version"] == "context_audit.v1"
    assert data["items"][0]["event"] == "context_resolution"
    assert data["items"][0]["node_id"] == "draft"
    assert "broken" not in json.dumps(data)
    assert "block_start" not in json.dumps(data)


def test_context_audit_endpoint_filters_by_node_id() -> None:
    service = _mock_service(
        logs=[
            _log(_audit_payload(node_id="draft", sequence=1), log_id=1),
            _log(_audit_payload(node_id="review", sequence=2), log_id=2),
        ]
    )
    app.dependency_overrides[get_run_service] = lambda: service

    try:
        response = client.get("/api/runs/run_914/context-audit?node_id=review")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    data = response.json()
    assert [item["node_id"] for item in data["items"]] == ["review"]
    assert data["has_next_page"] is False


def test_context_audit_endpoint_returns_404_for_missing_run_using_run_route_model() -> None:
    service = _mock_service(run_exists=False)
    app.dependency_overrides[get_run_service] = lambda: service

    try:
        response = client.get("/api/runs/missing/context-audit")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    service.get_run.assert_called_once_with("missing")
    service.get_run_logs.assert_not_called()


def test_context_audit_endpoint_rejects_invalid_page_size() -> None:
    service = _mock_service()
    app.dependency_overrides[get_run_service] = lambda: service

    try:
        too_small = client.get("/api/runs/run_914/context-audit?page_size=0")
        too_large = client.get("/api/runs/run_914/context-audit?page_size=501")
    finally:
        app.dependency_overrides.clear()

    assert too_small.status_code == 422
    assert too_large.status_code == 422


def test_context_audit_endpoint_safe_error_does_not_expose_stack_trace() -> None:
    service = _mock_service()
    service.get_run_logs.side_effect = RuntimeError("database password stack trace")
    app.dependency_overrides[get_run_service] = lambda: service

    try:
        response = client.get("/api/runs/run_914/context-audit")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 500
    body = response.text.lower()
    assert "traceback" not in body
    assert "database password stack trace" not in body
