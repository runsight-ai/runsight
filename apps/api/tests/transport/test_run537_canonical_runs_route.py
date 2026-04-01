"""Red tests for RUN-537 canonical /api/runs route behavior."""

from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from runsight_api.domain.entities.run import RunStatus
from runsight_api.main import app
from runsight_api.transport.deps import get_run_service
from runsight_api.transport.routers import runs as runs_router


def _make_mock_run(run_id: str = "run_537"):
    mock_run = Mock()
    mock_run.id = run_id
    mock_run.workflow_id = "wf_1"
    mock_run.workflow_name = "Workflow wf_1"
    mock_run.status = RunStatus.completed
    mock_run.started_at = 100.0
    mock_run.completed_at = 120.0
    mock_run.duration_s = 20.0
    mock_run.total_cost_usd = 0.0
    mock_run.total_tokens = 0
    mock_run.created_at = 100.0
    mock_run.source = "manual"
    mock_run.branch = "main"
    mock_run.commit_sha = None
    mock_run.run_number = None
    mock_run.eval_pass_pct = None
    return mock_run


def _canonical_summary():
    return {
        "total_cost_usd": 0.0,
        "total_tokens": 0,
        "nodes_count": 0,
        "total": 0,
        "completed": 0,
        "running": 0,
        "pending": 0,
        "failed": 0,
    }


def _canonical_service(run):
    mock_service = Mock()
    captured = {}

    def list_runs_paginated(
        offset=0,
        limit=20,
        status=None,
        workflow_id=None,
        source=None,
        branch=None,
    ):
        captured["kwargs"] = {
            "offset": offset,
            "limit": limit,
            "status": status,
            "workflow_id": workflow_id,
            "source": source,
            "branch": branch,
        }
        return [run], 1

    mock_service.list_runs_paginated = list_runs_paginated
    mock_service.get_node_summaries_batch.return_value = {run.id: _canonical_summary()}
    mock_service.get_node_summary.return_value = _canonical_summary()
    return mock_service, captured


def test_runs_route_uses_canonical_service_signature_without_runtime_introspection(monkeypatch):
    """GET /api/runs should succeed without calling inspect.signature at runtime."""
    run = _make_mock_run()
    mock_service, captured = _canonical_service(run)
    app.dependency_overrides[get_run_service] = lambda: mock_service

    def forbid_signature_lookup(*_args, **_kwargs):
        raise AssertionError("inspect.signature should not be called for /api/runs")

    monkeypatch.setattr(runs_router.inspect, "signature", forbid_signature_lookup)
    client = TestClient(app, raise_server_exceptions=False)

    try:
        response = client.get("/api/runs?workflow_id=wf_1&source=manual&branch=main")

        assert response.status_code == 200
        assert captured["kwargs"] == {
            "offset": 0,
            "limit": 20,
            "status": None,
            "workflow_id": "wf_1",
            "source": ["manual"],
            "branch": "main",
        }
    finally:
        app.dependency_overrides.clear()


def test_resolve_summaries_rejects_invalid_batch_shape_without_per_run_fallback():
    """Non-dict batch summaries should fail explicitly instead of degrading to per-run reads."""
    mock_service = Mock()
    mock_service.get_node_summary.side_effect = AssertionError(
        "must not fall back to per-run summary reads"
    )

    with pytest.raises(TypeError):
        runs_router._resolve_summaries(mock_service, ["run_537"], raw_batch=[])

    mock_service.get_node_summary.assert_not_called()


def test_runs_route_does_not_fall_back_to_per_run_summaries_when_batch_shape_is_invalid():
    """GET /api/runs should fail explicitly without calling get_node_summary on invalid batch data."""
    run = _make_mock_run()
    mock_service, _captured = _canonical_service(run)
    mock_service.get_node_summaries_batch.return_value = []
    mock_service.get_node_summary.side_effect = AssertionError(
        "must not fall back to per-run summary reads"
    )
    app.dependency_overrides[get_run_service] = lambda: mock_service
    client = TestClient(app, raise_server_exceptions=False)

    try:
        response = client.get("/api/runs")

        assert response.status_code == 500
        mock_service.get_node_summary.assert_not_called()
    finally:
        app.dependency_overrides.clear()
