"""Red tests for RUN-479 run list response fields."""

from unittest.mock import Mock

from fastapi.testclient import TestClient

from runsight_api.domain.entities.run import RunStatus
from runsight_api.main import app
from runsight_api.transport.deps import get_run_service

client = TestClient(app)


def _make_mock_run(
    run_id: str = "run_479",
    *,
    workflow_id: str = "wf_1",
    workflow_name: str = "Research Flow",
    source: str = "manual",
    branch: str = "main",
    run_number: int = 1,
    eval_pass_pct: float | None = 75.0,
):
    mock_run = Mock()
    mock_run.id = run_id
    mock_run.workflow_id = workflow_id
    mock_run.workflow_name = workflow_name
    mock_run.status = RunStatus.completed
    mock_run.started_at = 100.0
    mock_run.completed_at = 130.0
    mock_run.duration_s = 30.0
    mock_run.total_cost_usd = 0.0
    mock_run.total_tokens = 0
    mock_run.created_at = 100.0
    mock_run.source = source
    mock_run.branch = branch
    mock_run.commit_sha = "abc123"
    mock_run.run_number = run_number
    mock_run.eval_pass_pct = eval_pass_pct
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


def _stub_service_with_paginated_runs(runs):
    mock_service = Mock()
    captured = {}

    def paginated(
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
        return runs, len(runs)

    mock_service.list_runs_paginated = paginated
    mock_service.get_node_summaries_batch.return_value = {run.id: _summary() for run in runs}
    return mock_service, captured


def test_runs_list_includes_run_number_and_eval_pass_pct():
    run = _make_mock_run(run_number=7, eval_pass_pct=66.67)
    mock_service, _captured = _stub_service_with_paginated_runs([run])
    app.dependency_overrides[get_run_service] = lambda: mock_service

    try:
        response = client.get("/api/runs")
        assert response.status_code == 200
        item = response.json()["items"][0]
        assert item["run_number"] == 7
        assert item["eval_pass_pct"] == 66.67
    finally:
        app.dependency_overrides.clear()


def test_runs_list_keeps_source_and_branch_filters_unchanged_with_run479_fields():
    run = _make_mock_run(
        run_id="run_filtered",
        source="manual",
        branch="main",
        run_number=3,
        eval_pass_pct=None,
    )
    mock_service, captured = _stub_service_with_paginated_runs([run])
    app.dependency_overrides[get_run_service] = lambda: mock_service

    try:
        response = client.get("/api/runs?source=manual&branch=main")
        assert response.status_code == 200

        kwargs = captured["kwargs"]
        assert kwargs["source"] == ["manual"]
        assert kwargs["branch"] == "main"
        assert "include_simulations" not in kwargs

        item = response.json()["items"][0]
        assert item["run_number"] == 3
        assert item["eval_pass_pct"] is None
    finally:
        app.dependency_overrides.clear()
