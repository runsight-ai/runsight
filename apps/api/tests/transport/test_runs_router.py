from unittest.mock import AsyncMock, Mock

from fastapi.testclient import TestClient

from runsight_api.domain.entities.run import RunStatus
from runsight_api.main import app
from runsight_api.transport.deps import get_eval_service, get_execution_service, get_run_service

client = TestClient(app)


def _mock_eval_svc():
    """Return a mock EvalService that returns zero regressions."""
    mock_eval = Mock()
    mock_eval.get_run_regressions.return_value = {"count": 0, "issues": []}
    return mock_eval


def _make_mock_run(run_id="run_123"):
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
    mock_run.source = "manual"
    mock_run.branch = "main"
    mock_run.commit_sha = None
    mock_run.run_number = None
    mock_run.eval_pass_pct = None
    mock_run.regression_count = None
    mock_run.parent_run_id = None
    mock_run.root_run_id = None
    mock_run.depth = 0
    mock_run.warnings_json = None
    mock_run.error = None
    return mock_run


def test_runs_list():
    mock_service = Mock()
    mock_run = _make_mock_run()
    mock_run.warnings_json = [
        {
            "message": "Tool definition warning",
            "source": "tool_definitions",
            "context": "fetcher",
        }
    ]
    mock_service.list_runs_paginated.return_value = ([mock_run], 1)
    mock_service.get_node_summaries_batch.return_value = {
        mock_run.id: {
            "total_cost_usd": 0.0,
            "total_tokens": 0,
            "nodes_count": 0,
            "total": 0,
            "completed": 0,
            "running": 0,
            "pending": 0,
            "failed": 0,
        }
    }
    mock_service.get_node_summary.return_value = {
        "total_cost_usd": 0.0,
        "total_tokens": 0,
        "nodes_count": 0,
        "total": 0,
        "completed": 0,
        "running": 0,
        "pending": 0,
        "failed": 0,
    }
    app.dependency_overrides[get_run_service] = lambda: mock_service
    app.dependency_overrides[get_eval_service] = lambda: _mock_eval_svc()

    response = client.get("/api/runs")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == "run_123"
    assert data["items"][0]["warnings"] == mock_run.warnings_json
    app.dependency_overrides.clear()


def test_runs_get():
    mock_service = Mock()
    mock_run = _make_mock_run()
    mock_run.warnings_json = None
    mock_service.get_run.return_value = mock_run
    mock_service.get_node_summary.return_value = {
        "total_cost_usd": 0.0,
        "total_tokens": 0,
        "nodes_count": 0,
        "total": 0,
        "completed": 0,
        "running": 0,
        "pending": 0,
        "failed": 0,
    }
    app.dependency_overrides[get_run_service] = lambda: mock_service
    app.dependency_overrides[get_eval_service] = lambda: _mock_eval_svc()

    response = client.get("/api/runs/run_123")
    assert response.status_code == 200
    assert response.json()["id"] == "run_123"
    assert response.json()["warnings"] == []
    app.dependency_overrides.clear()


def test_runs_get_wires_non_empty_warnings():
    mock_service = Mock()
    mock_run = _make_mock_run("run_warned_detail")
    mock_run.warnings_json = [
        {
            "message": "Tool definition warning",
            "source": "tool_definitions",
            "context": "fetcher",
        }
    ]
    mock_service.get_run.return_value = mock_run
    mock_service.get_node_summary.return_value = {
        "total_cost_usd": 0.0,
        "total_tokens": 0,
        "nodes_count": 0,
        "total": 0,
        "completed": 0,
        "running": 0,
        "pending": 0,
        "failed": 0,
    }
    app.dependency_overrides[get_run_service] = lambda: mock_service
    app.dependency_overrides[get_eval_service] = lambda: _mock_eval_svc()

    response = client.get("/api/runs/run_warned_detail")
    assert response.status_code == 200
    assert response.json()["warnings"] == mock_run.warnings_json
    app.dependency_overrides.clear()


def test_runs_get_coerces_non_list_warning_payloads_to_empty_list():
    """Guardrail: route coercion must ignore mock placeholders and non-list warnings_json."""
    mock_service = Mock()
    mock_run = Mock()
    mock_run.id = "run_mock_warn_trap"
    mock_run.workflow_id = "wf_1"
    mock_run.workflow_name = "wf_1"
    mock_run.status = RunStatus.pending
    mock_run.started_at = 123.0
    mock_run.completed_at = None
    mock_run.duration_s = None
    mock_run.created_at = 123.0
    mock_run.branch = "main"
    mock_run.source = "manual"
    mock_run.commit_sha = None
    mock_run.run_number = None
    mock_run.eval_pass_pct = None
    mock_run.parent_run_id = None
    mock_run.root_run_id = None
    mock_run.depth = 0
    mock_run.error = None
    # Intentionally omit warnings_json to exercise Mock getattr() trap.
    mock_service.get_run.return_value = mock_run
    mock_service.get_node_summary.return_value = {
        "total_cost_usd": 0.0,
        "total_tokens": 0,
        "nodes_count": 0,
        "total": 0,
        "completed": 0,
        "running": 0,
        "pending": 0,
        "failed": 0,
    }
    app.dependency_overrides[get_run_service] = lambda: mock_service
    app.dependency_overrides[get_eval_service] = lambda: _mock_eval_svc()

    response = client.get("/api/runs/run_mock_warn_trap")
    assert response.status_code == 200
    assert response.json()["warnings"] == []
    app.dependency_overrides.clear()


def test_runs_get_404():
    mock_service = Mock()
    mock_service.get_run.return_value = None
    app.dependency_overrides[get_run_service] = lambda: mock_service

    response = client.get("/api/runs/missing")
    assert response.status_code == 404
    app.dependency_overrides.clear()


def test_runs_post():
    mock_service = Mock()
    mock_run = _make_mock_run("run_new")
    mock_run.warnings_json = [
        {
            "message": "Tool definition warning",
            "source": "tool_definitions",
            "context": "fetcher",
        }
    ]
    mock_service.create_run.return_value = mock_run
    mock_exec_service = Mock()
    mock_exec_service.launch_execution = AsyncMock()
    app.dependency_overrides[get_run_service] = lambda: mock_service
    app.dependency_overrides[get_execution_service] = lambda: mock_exec_service

    response = client.post("/api/runs", json={"workflow_id": "wf_1", "task_data": {}})
    assert response.status_code == 200
    assert response.json()["id"] == "run_new"
    assert response.json()["warnings"] == mock_run.warnings_json
    app.dependency_overrides.clear()


def test_runs_post_passes_source_and_branch_to_services():
    """POST /api/runs should pass branch and source to both service calls."""
    mock_service = Mock()
    mock_run = _make_mock_run("run_branch_source")
    mock_run.branch = "sim/wf_1/20260330/abc12"
    mock_run.source = "simulation"
    mock_service.create_run.return_value = mock_run
    mock_exec_service = Mock()
    mock_exec_service.launch_execution = AsyncMock()
    app.dependency_overrides[get_run_service] = lambda: mock_service
    app.dependency_overrides[get_execution_service] = lambda: mock_exec_service

    payload = {
        "workflow_id": "wf_1",
        "task_data": {"instruction": "go"},
        "branch": "sim/wf_1/20260330/abc12",
        "source": "simulation",
    }
    response = client.post("/api/runs", json=payload)

    assert response.status_code == 200
    assert response.json()["id"] == "run_branch_source"
    assert response.json()["branch"] == "sim/wf_1/20260330/abc12"
    assert response.json()["source"] == "simulation"
    mock_service.create_run.assert_called_once_with(
        "wf_1",
        {"instruction": "go"},
        source="simulation",
        branch="sim/wf_1/20260330/abc12",
    )
    mock_exec_service.launch_execution.assert_called_once_with(
        "run_branch_source",
        "wf_1",
        {"instruction": "go"},
        branch="sim/wf_1/20260330/abc12",
    )
    app.dependency_overrides.clear()


def test_runs_post_defaults_branch_to_main_for_existing_callers():
    """POST /api/runs without branch should still pass branch='main' and source='manual'."""
    mock_service = Mock()
    mock_run = _make_mock_run("run_main_default")
    mock_run.source = "manual"
    mock_service.create_run.return_value = mock_run
    mock_exec_service = Mock()
    mock_exec_service.launch_execution = AsyncMock()
    app.dependency_overrides[get_run_service] = lambda: mock_service
    app.dependency_overrides[get_execution_service] = lambda: mock_exec_service

    response = client.post(
        "/api/runs",
        json={"workflow_id": "wf_1", "task_data": {"instruction": "go"}},
    )

    assert response.status_code == 200
    assert response.json()["id"] == "run_main_default"
    mock_service.create_run.assert_called_once_with(
        "wf_1",
        {"instruction": "go"},
        source="manual",
        branch="main",
    )
    mock_exec_service.launch_execution.assert_called_once_with(
        "run_main_default",
        "wf_1",
        {"instruction": "go"},
        branch="main",
    )
    app.dependency_overrides.clear()


def test_runs_post_422():
    mock_exec_service = Mock()
    mock_exec_service.launch_execution = AsyncMock()
    app.dependency_overrides[get_execution_service] = lambda: mock_exec_service
    response = client.post("/api/runs", json={"workflow_id": 123})  # must be str
    assert response.status_code == 422
    app.dependency_overrides.clear()


def test_runs_cancel():
    mock_service = Mock()
    mock_run = _make_mock_run()
    mock_run.status = RunStatus.cancelled
    mock_service.cancel_run.return_value = mock_run
    app.dependency_overrides[get_run_service] = lambda: mock_service

    response = client.post("/api/runs/run_123/cancel")
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    app.dependency_overrides.clear()


def test_runs_logs():
    mock_service = Mock()
    mock_service.get_run_logs.return_value = []
    app.dependency_overrides[get_run_service] = lambda: mock_service

    response = client.get("/api/runs/run_123/logs")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    app.dependency_overrides.clear()


def test_runs_nodes():
    mock_service = Mock()
    mock_service.get_run_nodes.return_value = []
    app.dependency_overrides[get_run_service] = lambda: mock_service

    response = client.get("/api/runs/run_123/nodes")
    assert response.status_code == 200
    assert response.json() == []
    app.dependency_overrides.clear()


def test_runs_post_propagates_branch_and_source_to_service_and_execution():
    mock_service = Mock()
    mock_run = _make_mock_run("run_sim")
    mock_run.branch = "sim/test-flow/20260330/abc12"
    mock_run.source = "simulation"
    mock_service.create_run.return_value = mock_run

    mock_exec_service = Mock()
    mock_exec_service.launch_execution = AsyncMock()

    app.dependency_overrides[get_run_service] = lambda: mock_service
    app.dependency_overrides[get_execution_service] = lambda: mock_exec_service

    payload = {
        "workflow_id": "wf_1",
        "task_data": {"instruction": "go"},
        "source": "simulation",
        "branch": "sim/test-flow/20260330/abc12",
    }

    response = client.post("/api/runs", json=payload)
    assert response.status_code == 200
    mock_service.create_run.assert_called_once_with(
        "wf_1",
        {"instruction": "go"},
        branch="sim/test-flow/20260330/abc12",
        source="simulation",
    )
    mock_exec_service.launch_execution.assert_awaited_once_with(
        "run_sim",
        "wf_1",
        {"instruction": "go"},
        branch="sim/test-flow/20260330/abc12",
    )
    app.dependency_overrides.clear()


# ===========================================================================
# RUN-339: Status filter on GET /api/runs
# ===========================================================================


def _make_mock_run_with_status(run_id: str, status: RunStatus):
    """Create a mock run with a specific status."""
    mock_run = _make_mock_run(run_id)
    mock_run.status = status
    return mock_run


def _stub_service_with_runs(runs):
    """Wire up a mock RunService that returns the given runs list."""
    mock_service = Mock()

    def paginated(offset=0, limit=20, status=None, workflow_id=None, source=None, branch=None):
        filtered = runs
        if status:
            filtered = [r for r in filtered if r.status in status]
        if workflow_id:
            filtered = [r for r in filtered if r.workflow_id == workflow_id]
        if source:
            filtered = [r for r in filtered if r.source in source]
        if branch:
            filtered = [r for r in filtered if r.branch == branch]
        page = filtered[offset : offset + limit]
        return page, len(filtered)

    mock_service.list_runs_paginated = paginated
    mock_service.list_runs.return_value = runs
    mock_service.get_node_summaries_batch.return_value = {}
    mock_service.get_node_summary.return_value = {
        "total_cost_usd": 0.0,
        "total_tokens": 0,
        "nodes_count": 0,
        "total": 0,
        "completed": 0,
        "running": 0,
        "pending": 0,
        "failed": 0,
    }
    return mock_service


def test_runs_list_status_filter_running():
    """GET /api/runs?status=running returns only running runs."""
    runs = [
        _make_mock_run_with_status("run_1", RunStatus.running),
        _make_mock_run_with_status("run_2", RunStatus.pending),
        _make_mock_run_with_status("run_3", RunStatus.completed),
    ]
    mock_service = _stub_service_with_runs(runs)
    app.dependency_overrides[get_run_service] = lambda: mock_service
    app.dependency_overrides[get_eval_service] = lambda: _mock_eval_svc()

    response = client.get("/api/runs?status=running")
    assert response.status_code == 200
    data = response.json()
    assert all(item["status"] == "running" for item in data["items"])
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == "run_1"
    app.dependency_overrides.clear()


def test_runs_list_status_filter_multiple():
    """GET /api/runs?status=running&status=pending returns running + pending runs."""
    runs = [
        _make_mock_run_with_status("run_1", RunStatus.running),
        _make_mock_run_with_status("run_2", RunStatus.pending),
        _make_mock_run_with_status("run_3", RunStatus.completed),
        _make_mock_run_with_status("run_4", RunStatus.failed),
    ]
    mock_service = _stub_service_with_runs(runs)
    app.dependency_overrides[get_run_service] = lambda: mock_service
    app.dependency_overrides[get_eval_service] = lambda: _mock_eval_svc()

    response = client.get("/api/runs?status=running&status=pending")
    assert response.status_code == 200
    data = response.json()
    statuses = {item["status"] for item in data["items"]}
    assert statuses == {"running", "pending"}
    assert len(data["items"]) == 2
    app.dependency_overrides.clear()


def test_runs_list_no_status_filter_returns_all():
    """GET /api/runs without status param returns all runs (backwards compatible)."""
    runs = [
        _make_mock_run_with_status("run_1", RunStatus.running),
        _make_mock_run_with_status("run_2", RunStatus.pending),
        _make_mock_run_with_status("run_3", RunStatus.completed),
    ]
    mock_service = _stub_service_with_runs(runs)
    app.dependency_overrides[get_run_service] = lambda: mock_service
    app.dependency_overrides[get_eval_service] = lambda: _mock_eval_svc()

    response = client.get("/api/runs")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 3
    app.dependency_overrides.clear()


def test_runs_list_status_filter_empty_result():
    """GET /api/runs?status=running returns empty list when no runs match."""
    runs = [
        _make_mock_run_with_status("run_1", RunStatus.completed),
        _make_mock_run_with_status("run_2", RunStatus.failed),
    ]
    mock_service = _stub_service_with_runs(runs)
    app.dependency_overrides[get_run_service] = lambda: mock_service
    app.dependency_overrides[get_eval_service] = lambda: _mock_eval_svc()

    response = client.get("/api/runs?status=running")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 0
    assert data["total"] == 0
    app.dependency_overrides.clear()
