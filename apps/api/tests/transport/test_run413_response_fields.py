from unittest.mock import Mock

from fastapi.testclient import TestClient

from runsight_api.domain.entities.run import RunStatus
from runsight_api.main import app
from runsight_api.transport.deps import get_eval_service, get_run_service

client = TestClient(app)


def _make_mock_run(
    run_id: str = "run_413",
    *,
    branch: str = "feat/run-413",
    source: str = "webhook",
    commit_sha: str | None = "abc123def456",
    workflow_commit_sha: str | None = None,
):
    mock_run = Mock()
    mock_run.id = run_id
    mock_run.workflow_id = "wf_1"
    mock_run.workflow_name = "wf_1"
    mock_run.status = RunStatus.pending
    mock_run.started_at = 123.0
    mock_run.completed_at = None
    mock_run.duration_s = None
    mock_run.total_cost_usd = 0.0
    mock_run.total_tokens = 0
    mock_run.created_at = 123.0
    mock_run.branch = branch
    mock_run.source = source
    mock_run.commit_sha = commit_sha
    mock_run.workflow_commit_sha = workflow_commit_sha
    mock_run.run_number = None
    mock_run.eval_pass_pct = None
    mock_run.regression_count = None
    mock_run.error = None
    mock_run.parent_run_id = None
    mock_run.root_run_id = None
    mock_run.depth = 0
    return mock_run


def _summary():
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


def _mock_eval_svc():
    """Return a mock EvalService that returns zero regressions."""
    mock_eval = Mock()
    mock_eval.get_run_regressions.return_value = {"count": 0, "issues": []}
    return mock_eval


def _stub_run_service(run):
    mock_service = Mock()
    mock_service.get_run.return_value = run
    mock_service.get_node_summary.return_value = _summary()
    mock_service.get_node_summaries_batch.return_value = {run.id: _summary()}
    mock_service.list_runs.return_value = [run]

    def paginated(offset=0, limit=20, status=None, workflow_id=None, source=None, branch=None):
        return [run], 1

    mock_service.list_runs_paginated = paginated
    return mock_service


def test_runs_list_includes_branch_source_and_commit_sha():
    mock_run = _make_mock_run()
    mock_service = _stub_run_service(mock_run)
    app.dependency_overrides[get_run_service] = lambda: mock_service
    app.dependency_overrides[get_eval_service] = lambda: _mock_eval_svc()

    try:
        response = client.get("/api/runs")
        assert response.status_code == 200
        item = response.json()["items"][0]
        assert item["branch"] == "feat/run-413"
        assert item["source"] == "webhook"
        assert item["commit_sha"] == "abc123def456"
    finally:
        app.dependency_overrides.clear()


def test_runs_get_includes_branch_source_and_commit_sha():
    mock_run = _make_mock_run(run_id="run_413_get")
    mock_service = _stub_run_service(mock_run)
    app.dependency_overrides[get_run_service] = lambda: mock_service
    app.dependency_overrides[get_eval_service] = lambda: _mock_eval_svc()

    try:
        response = client.get("/api/runs/run_413_get")
        assert response.status_code == 200
        body = response.json()
        assert body["branch"] == "feat/run-413"
        assert body["source"] == "webhook"
        assert body["commit_sha"] == "abc123def456"
    finally:
        app.dependency_overrides.clear()


def test_runs_get_serializes_commit_sha_as_null_when_unset():
    mock_run = _make_mock_run(
        run_id="run_413_null",
        branch="main",
        source="manual",
        commit_sha=None,
    )
    mock_service = _stub_run_service(mock_run)
    app.dependency_overrides[get_run_service] = lambda: mock_service
    app.dependency_overrides[get_eval_service] = lambda: _mock_eval_svc()

    try:
        response = client.get("/api/runs/run_413_null")
        assert response.status_code == 200
        body = response.json()
        assert body["branch"] == "main"
        assert body["source"] == "manual"
        assert body["commit_sha"] is None
    finally:
        app.dependency_overrides.clear()


def test_runs_get_does_not_use_legacy_workflow_commit_sha_for_old_records():
    mock_run = _make_mock_run(
        run_id="run_413_legacy",
        branch="main",
        source="manual",
        commit_sha=None,
        workflow_commit_sha="legacysha413",
    )
    mock_service = _stub_run_service(mock_run)
    app.dependency_overrides[get_run_service] = lambda: mock_service
    app.dependency_overrides[get_eval_service] = lambda: _mock_eval_svc()

    try:
        response = client.get("/api/runs/run_413_legacy")
        assert response.status_code == 200
        body = response.json()
        assert body["commit_sha"] is None
        assert "workflow_commit_sha" not in body
    finally:
        app.dependency_overrides.clear()
