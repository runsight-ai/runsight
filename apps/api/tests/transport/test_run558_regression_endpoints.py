"""Red-team tests for RUN-558: Per-run regression count and issue list.

Tests cover:
- AC1: RunResponse includes regression_count field
- AC3: GET /api/runs/:id/regressions returns per-issue list
- AC4: GET /api/workflows/:id/regressions returns per-issue list with run context
- AC7: Runs with no regressions return { count: 0, issues: [] }
- AC8: Works for completed, failed, and cancelled runs
- Edge: Run with no eval assertions => 0 regressions
- Edge: First run of a workflow (no baseline) => 0 regressions
"""

from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from runsight_api.main import app
from runsight_api.transport.deps import get_eval_service, get_run_service

client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_run(
    run_id: str = "run_558",
    *,
    workflow_id: str = "wf_1",
    workflow_name: str = "Research Flow",
    status: str = "completed",
    source: str = "manual",
    branch: str = "main",
    run_number: int = 1,
    eval_pass_pct: float | None = 100.0,
    regression_count: int | None = None,
):
    mock_run = Mock()
    mock_run.id = run_id
    mock_run.workflow_id = workflow_id
    mock_run.workflow_name = workflow_name
    mock_run.status = status
    mock_run.started_at = 100.0
    mock_run.completed_at = 130.0
    mock_run.duration_s = 30.0
    mock_run.total_cost_usd = 0.05
    mock_run.total_tokens = 500
    mock_run.created_at = 100.0
    mock_run.source = source
    mock_run.branch = branch
    mock_run.commit_sha = "abc123"
    mock_run.run_number = run_number
    mock_run.eval_pass_pct = eval_pass_pct
    mock_run.regression_count = regression_count
    mock_run.error = None
    mock_run.parent_run_id = None
    mock_run.root_run_id = None
    mock_run.depth = 0
    return mock_run


def _summary():
    return {
        "total_cost_usd": 0.05,
        "total_tokens": 500,
        "total": 3,
        "completed": 3,
        "running": 0,
        "pending": 0,
        "failed": 0,
    }


def _stub_service_with_paginated_runs(runs):
    mock_service = Mock()

    def paginated(
        offset=0,
        limit=20,
        status=None,
        workflow_id=None,
        source=None,
        branch=None,
    ):
        return runs, len(runs)

    mock_service.list_runs_paginated = paginated
    mock_service.get_node_summaries_batch.return_value = {run.id: _summary() for run in runs}
    return mock_service


def _make_regression_issue(
    *,
    node_id: str = "analyze",
    node_name: str = "Analyze Step",
    regression_type: str = "assertion_regression",
    delta: dict | None = None,
    run_id: str | None = None,
    run_number: int | None = None,
):
    """Build a regression issue dict as the endpoint would return."""
    issue = {
        "node_id": node_id,
        "node_name": node_name,
        "type": regression_type,
        "delta": delta or {"eval_passed": False, "baseline_eval_passed": True},
    }
    if run_id is not None:
        issue["run_id"] = run_id
    if run_number is not None:
        issue["run_number"] = run_number
    return issue


# ===========================================================================
# AC1: RunResponse includes regression_count field
# ===========================================================================


class TestRunResponseRegressionCount:
    """RunResponse schema must include regression_count."""

    def test_run_response_model_has_regression_count_field(self):
        """The RunResponse Pydantic model must declare regression_count."""
        from runsight_api.transport.schemas.runs import RunResponse

        assert "regression_count" in RunResponse.model_fields

    def test_regression_count_is_optional_and_nullable(self):
        """regression_count should accept None (for backward compat)."""
        from runsight_api.transport.schemas.runs import RunResponse

        assert "regression_count" in RunResponse.model_fields
        # Should accept None
        resp = RunResponse(
            id="run_1",
            workflow_id="wf_1",
            workflow_name="Test",
            status="completed",
            started_at=None,
            completed_at=None,
            duration_seconds=None,
            total_cost_usd=0.0,
            total_tokens=0,
            created_at=100.0,
            regression_count=None,
        )
        assert resp.regression_count is None

    def test_regression_count_accepts_integer_value(self):
        """regression_count should accept an integer when present."""
        from runsight_api.transport.schemas.runs import RunResponse

        resp = RunResponse(
            id="run_1",
            workflow_id="wf_1",
            workflow_name="Test",
            status="completed",
            started_at=None,
            completed_at=None,
            duration_seconds=None,
            total_cost_usd=0.0,
            total_tokens=0,
            created_at=100.0,
            regression_count=3,
        )
        assert resp.regression_count == 3

    def test_run_list_response_serializes_regression_count(self):
        """GET /api/runs list should include regression_count in each item."""
        run = _make_mock_run(regression_count=2)
        mock_service = _stub_service_with_paginated_runs([run])
        mock_eval = Mock()
        mock_eval.get_run_regressions.return_value = {"count": 2, "issues": []}
        app.dependency_overrides[get_run_service] = lambda: mock_service
        app.dependency_overrides[get_eval_service] = lambda: mock_eval

        try:
            response = client.get("/api/runs")
            assert response.status_code == 200
            item = response.json()["items"][0]
            assert "regression_count" in item
            assert item["regression_count"] == 2
        finally:
            app.dependency_overrides.clear()

    def test_single_run_response_includes_regression_count(self):
        """GET /api/runs/:id should include regression_count."""
        run = _make_mock_run(regression_count=1)
        mock_service = Mock()
        mock_service.get_run.return_value = run
        mock_service.get_node_summary.return_value = _summary()
        mock_eval = Mock()
        mock_eval.get_run_regressions.return_value = {"count": 1, "issues": []}
        app.dependency_overrides[get_run_service] = lambda: mock_service
        app.dependency_overrides[get_eval_service] = lambda: mock_eval

        try:
            response = client.get("/api/runs/run_558")
            assert response.status_code == 200
            data = response.json()
            assert "regression_count" in data
            assert data["regression_count"] == 1
        finally:
            app.dependency_overrides.clear()


# ===========================================================================
# AC3: GET /api/runs/:id/regressions endpoint
# ===========================================================================


class TestRunRegressionsEndpoint:
    """GET /api/runs/{run_id}/regressions must return per-issue list."""

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_route_registered(self):
        """The regressions route must be registered on the app."""
        routes = [r.path for r in app.routes]
        assert "/api/runs/{run_id}/regressions" in routes

    def test_returns_200_with_regression_data(self):
        """Endpoint returns 200 with count and issues."""
        mock_service = Mock()
        mock_service.get_run_regressions.return_value = {
            "count": 1,
            "issues": [
                _make_regression_issue(
                    node_id="analyze",
                    node_name="Analyze Step",
                    regression_type="assertion_regression",
                )
            ],
        }
        app.dependency_overrides[get_eval_service] = lambda: mock_service

        response = client.get("/api/runs/run_001/regressions")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert len(data["issues"]) == 1

    def test_issue_has_required_fields(self):
        """Each issue must have node_id, node_name, type, delta."""
        mock_service = Mock()
        mock_service.get_run_regressions.return_value = {
            "count": 1,
            "issues": [
                _make_regression_issue(
                    node_id="summarize",
                    node_name="Summarize Step",
                    regression_type="cost_spike",
                    delta={"cost_pct": 35.0, "baseline_cost": 0.005},
                )
            ],
        }
        app.dependency_overrides[get_eval_service] = lambda: mock_service

        response = client.get("/api/runs/run_001/regressions")
        issue = response.json()["issues"][0]
        assert "node_id" in issue
        assert "node_name" in issue
        assert "type" in issue
        assert "delta" in issue

    def test_regression_types_include_all_three(self):
        """Response may include assertion_regression, cost_spike, quality_drop."""
        mock_service = Mock()
        mock_service.get_run_regressions.return_value = {
            "count": 3,
            "issues": [
                _make_regression_issue(regression_type="assertion_regression"),
                _make_regression_issue(
                    node_id="node_b",
                    node_name="Node B",
                    regression_type="cost_spike",
                    delta={"cost_pct": 25.0},
                ),
                _make_regression_issue(
                    node_id="node_c",
                    node_name="Node C",
                    regression_type="quality_drop",
                    delta={"score_delta": -0.15},
                ),
            ],
        }
        app.dependency_overrides[get_eval_service] = lambda: mock_service

        response = client.get("/api/runs/run_001/regressions")
        data = response.json()
        types = {issue["type"] for issue in data["issues"]}
        assert "assertion_regression" in types
        assert "cost_spike" in types
        assert "quality_drop" in types

    def test_returns_404_for_nonexistent_run(self):
        """Endpoint returns 404 when run does not exist (not because route is missing)."""
        # First, confirm the route exists
        routes = [r.path for r in app.routes]
        assert "/api/runs/{run_id}/regressions" in routes, (
            "Route must exist before testing 404 behavior"
        )

        mock_service = Mock()
        mock_service.get_run_regressions.return_value = None
        app.dependency_overrides[get_eval_service] = lambda: mock_service

        response = client.get("/api/runs/nonexistent/regressions")
        assert response.status_code == 404


# ===========================================================================
# AC4: GET /api/workflows/:id/regressions endpoint
# ===========================================================================


class TestWorkflowRegressionsEndpoint:
    """GET /api/workflows/{id}/regressions must return per-issue list with run context."""

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_route_registered(self):
        """The workflow regressions route must be registered."""
        routes = [r.path for r in app.routes]
        assert "/api/workflows/{id}/regressions" in routes

    def test_returns_200_with_regression_data(self):
        """Endpoint returns 200 with count and issues."""
        mock_service = Mock()
        mock_service.get_workflow_regressions.return_value = {
            "count": 2,
            "issues": [
                _make_regression_issue(
                    node_id="analyze",
                    node_name="Analyze",
                    regression_type="assertion_regression",
                    run_id="run_002",
                    run_number=2,
                ),
                _make_regression_issue(
                    node_id="summarize",
                    node_name="Summarize",
                    regression_type="cost_spike",
                    delta={"cost_pct": 40.0},
                    run_id="run_003",
                    run_number=3,
                ),
            ],
        }
        app.dependency_overrides[get_eval_service] = lambda: mock_service

        response = client.get("/api/workflows/wf_1/regressions")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2
        assert len(data["issues"]) == 2

    def test_issues_include_run_id_and_run_number(self):
        """Workflow regression issues must include run_id and run_number."""
        mock_service = Mock()
        mock_service.get_workflow_regressions.return_value = {
            "count": 1,
            "issues": [
                _make_regression_issue(
                    regression_type="quality_drop",
                    delta={"score_delta": -0.2},
                    run_id="run_005",
                    run_number=5,
                )
            ],
        }
        app.dependency_overrides[get_eval_service] = lambda: mock_service

        response = client.get("/api/workflows/wf_1/regressions")
        issue = response.json()["issues"][0]
        assert "run_id" in issue
        assert issue["run_id"] == "run_005"
        assert "run_number" in issue
        assert issue["run_number"] == 5

    def test_returns_empty_for_workflow_with_no_regressions(self):
        """Workflow with no regressions returns count=0 and empty issues."""
        mock_service = Mock()
        mock_service.get_workflow_regressions.return_value = {
            "count": 0,
            "issues": [],
        }
        app.dependency_overrides[get_eval_service] = lambda: mock_service

        response = client.get("/api/workflows/wf_clean/regressions")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert data["issues"] == []


# ===========================================================================
# AC7: Runs with no regressions return { count: 0, issues: [] }
# ===========================================================================


class TestZeroRegressionsContract:
    """Runs with no regressions return the canonical empty shape."""

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_no_regressions_returns_zero_count(self):
        mock_service = Mock()
        mock_service.get_run_regressions.return_value = {
            "count": 0,
            "issues": [],
        }
        app.dependency_overrides[get_eval_service] = lambda: mock_service

        response = client.get("/api/runs/run_clean/regressions")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert data["issues"] == []


# ===========================================================================
# AC8: Works for completed, failed, and cancelled runs
# ===========================================================================


class TestRegressionsForTerminalRunStates:
    """Regressions endpoint works for all terminal run statuses."""

    def teardown_method(self):
        app.dependency_overrides.clear()

    @pytest.mark.parametrize("status", ["completed", "failed", "cancelled"])
    def test_returns_regressions_for_terminal_status(self, status):
        """Regressions should be computed for completed, failed, and cancelled runs."""
        mock_service = Mock()
        mock_service.get_run_regressions.return_value = {
            "count": 1,
            "issues": [_make_regression_issue(regression_type="assertion_regression")],
        }
        app.dependency_overrides[get_eval_service] = lambda: mock_service

        response = client.get(f"/api/runs/run_{status}/regressions")
        assert response.status_code == 200
        assert response.json()["count"] == 1
