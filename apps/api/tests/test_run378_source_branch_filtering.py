"""
RUN-378: Run list filtering by source and branch.

RED tests -- these must FAIL against the current codebase because:
  - GET /api/runs does not accept source or branch query params
  - list_runs_paginated (service + repo) does not filter by source or branch
  - _fetch_paginated_runs does not thread source/branch through
  - GET /api/dashboard does not exclude simulation runs from KPI calculations

AC covered:
  - GET /api/runs accepts source query param (list of strings)
  - GET /api/runs accepts branch query param (single string)
  - ?source=simulation returns only simulation runs
  - ?source=manual&source=webhook returns manual + webhook runs
  - ?branch=main returns only main branch runs
  - No params = all runs returned (no default exclusion)
  - Dashboard KPIs exclude simulation runs from calculations
  - All existing tests pass
"""

import time
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from runsight_api.domain.entities.run import RunStatus
from runsight_api.main import app
from runsight_api.transport.deps import get_run_service

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_run(
    run_id: str = "run_001",
    workflow_id: str = "wf_1",
    status: RunStatus = RunStatus.completed,
    source: str = "manual",
    branch: str = "main",
    total_cost_usd: float = 0.0,
    created_at: float | None = None,
) -> Mock:
    """Create a mock Run with source and branch attributes."""
    mock_run = Mock()
    mock_run.id = run_id
    mock_run.workflow_id = workflow_id
    mock_run.workflow_name = f"Workflow {workflow_id}"
    mock_run.status = status
    mock_run.started_at = (created_at or time.time()) - 10
    mock_run.completed_at = created_at or time.time()
    mock_run.duration_s = 10.0
    mock_run.total_cost_usd = total_cost_usd
    mock_run.total_tokens = 100
    mock_run.created_at = created_at or time.time()
    mock_run.source = source
    mock_run.branch = branch
    mock_run.commit_sha = None
    return mock_run


def _stub_service_with_runs(runs):
    """Wire up a mock RunService that filters by status, workflow_id, source, and branch."""
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
    mock_service.get_node_summaries_batch.return_value = {
        r.id: {
            "total_cost_usd": r.total_cost_usd,
            "total_tokens": r.total_tokens,
            "total": 1,
            "completed": 1,
            "running": 0,
            "pending": 0,
            "failed": 0,
        }
        for r in runs
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
    return mock_service


# ===========================================================================
# 1. Router accepts source param
# ===========================================================================


class TestRouterAcceptsSourceParam:
    """GET /api/runs must accept a source query parameter (list of strings)."""

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_source_param_accepted_single(self):
        """GET /api/runs?source=simulation must not return 422."""
        runs = [_make_mock_run("run_1", source="simulation")]
        mock_service = _stub_service_with_runs(runs)
        app.dependency_overrides[get_run_service] = lambda: mock_service

        client = TestClient(app)
        response = client.get("/api/runs?source=simulation")
        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: source param should be accepted"
        )

    def test_source_param_accepted_multiple(self):
        """GET /api/runs?source=manual&source=webhook must not return 422."""
        runs = [
            _make_mock_run("run_1", source="manual"),
            _make_mock_run("run_2", source="webhook"),
        ]
        mock_service = _stub_service_with_runs(runs)
        app.dependency_overrides[get_run_service] = lambda: mock_service

        client = TestClient(app)
        response = client.get("/api/runs?source=manual&source=webhook")
        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: multiple source params should be accepted"
        )


# ===========================================================================
# 2. Router accepts branch param
# ===========================================================================


class TestRouterAcceptsBranchParam:
    """GET /api/runs must accept a branch query parameter (single string)."""

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_branch_param_accepted(self):
        """GET /api/runs?branch=main must not return 422."""
        runs = [_make_mock_run("run_1", branch="main")]
        mock_service = _stub_service_with_runs(runs)
        app.dependency_overrides[get_run_service] = lambda: mock_service

        client = TestClient(app)
        response = client.get("/api/runs?branch=main")
        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: branch param should be accepted"
        )


# ===========================================================================
# 3. Source filtering -- single value
# ===========================================================================


class TestSourceFilteringSingle:
    """?source=simulation returns only simulation runs."""

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_source_simulation_returns_only_simulation_runs(self):
        """GET /api/runs?source=simulation must return only runs with source=simulation."""
        runs = [
            _make_mock_run("run_sim", source="simulation"),
            _make_mock_run("run_manual", source="manual"),
            _make_mock_run("run_webhook", source="webhook"),
        ]
        mock_service = _stub_service_with_runs(runs)
        app.dependency_overrides[get_run_service] = lambda: mock_service

        client = TestClient(app)
        response = client.get("/api/runs?source=simulation")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1, f"Expected 1 simulation run, got {len(data['items'])}"
        assert data["items"][0]["id"] == "run_sim"
        assert data["items"][0]["source"] == "simulation"

    def test_source_manual_returns_only_manual_runs(self):
        """GET /api/runs?source=manual must return only runs with source=manual."""
        runs = [
            _make_mock_run("run_sim", source="simulation"),
            _make_mock_run("run_manual", source="manual"),
            _make_mock_run("run_schedule", source="schedule"),
        ]
        mock_service = _stub_service_with_runs(runs)
        app.dependency_overrides[get_run_service] = lambda: mock_service

        client = TestClient(app)
        response = client.get("/api/runs?source=manual")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1, f"Expected 1 manual run, got {len(data['items'])}"
        assert data["items"][0]["id"] == "run_manual"
        assert data["items"][0]["source"] == "manual"

    def test_source_filter_empty_result(self):
        """GET /api/runs?source=schedule returns empty when no schedule runs exist."""
        runs = [
            _make_mock_run("run_1", source="manual"),
            _make_mock_run("run_2", source="simulation"),
        ]
        mock_service = _stub_service_with_runs(runs)
        app.dependency_overrides[get_run_service] = lambda: mock_service

        client = TestClient(app)
        response = client.get("/api/runs?source=schedule")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 0
        assert data["total"] == 0


# ===========================================================================
# 4. Source filtering -- multiple values
# ===========================================================================


class TestSourceFilteringMultiple:
    """?source=manual&source=webhook returns manual + webhook runs."""

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_multiple_sources_returns_union(self):
        """GET /api/runs?source=manual&source=webhook returns manual + webhook runs."""
        runs = [
            _make_mock_run("run_manual", source="manual"),
            _make_mock_run("run_webhook", source="webhook"),
            _make_mock_run("run_sim", source="simulation"),
            _make_mock_run("run_schedule", source="schedule"),
        ]
        mock_service = _stub_service_with_runs(runs)
        app.dependency_overrides[get_run_service] = lambda: mock_service

        client = TestClient(app)
        response = client.get("/api/runs?source=manual&source=webhook")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2, (
            f"Expected 2 runs (manual + webhook), got {len(data['items'])}"
        )
        sources = {item["source"] for item in data["items"]}
        assert sources == {"manual", "webhook"}

    def test_three_sources_returns_union(self):
        """GET /api/runs?source=manual&source=webhook&source=schedule returns all three."""
        runs = [
            _make_mock_run("run_manual", source="manual"),
            _make_mock_run("run_webhook", source="webhook"),
            _make_mock_run("run_sim", source="simulation"),
            _make_mock_run("run_schedule", source="schedule"),
        ]
        mock_service = _stub_service_with_runs(runs)
        app.dependency_overrides[get_run_service] = lambda: mock_service

        client = TestClient(app)
        response = client.get("/api/runs?source=manual&source=webhook&source=schedule")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 3, f"Expected 3 runs, got {len(data['items'])}"
        sources = {item["source"] for item in data["items"]}
        assert sources == {"manual", "webhook", "schedule"}


# ===========================================================================
# 5. Branch filtering
# ===========================================================================


class TestBranchFiltering:
    """?branch=main returns only main-branch runs."""

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_branch_main_returns_only_main_runs(self):
        """GET /api/runs?branch=main must return only runs on the main branch."""
        runs = [
            _make_mock_run("run_main", branch="main"),
            _make_mock_run("run_feat", branch="feat/experiment"),
            _make_mock_run("run_sim", branch="sim/test/20260330/abc123"),
        ]
        mock_service = _stub_service_with_runs(runs)
        app.dependency_overrides[get_run_service] = lambda: mock_service

        client = TestClient(app)
        response = client.get("/api/runs?branch=main")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1, f"Expected 1 main-branch run, got {len(data['items'])}"
        assert data["items"][0]["id"] == "run_main"
        assert data["items"][0]["branch"] == "main"

    def test_branch_feature_returns_only_feature_runs(self):
        """GET /api/runs?branch=feat/experiment must return only that branch."""
        runs = [
            _make_mock_run("run_main", branch="main"),
            _make_mock_run("run_feat", branch="feat/experiment"),
        ]
        mock_service = _stub_service_with_runs(runs)
        app.dependency_overrides[get_run_service] = lambda: mock_service

        client = TestClient(app)
        response = client.get("/api/runs?branch=feat/experiment")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1, (
            f"Expected 1 run for feat/experiment, got {len(data['items'])}"
        )
        assert data["items"][0]["id"] == "run_feat"

    def test_branch_filter_empty_result(self):
        """GET /api/runs?branch=nonexistent returns empty list."""
        runs = [
            _make_mock_run("run_1", branch="main"),
            _make_mock_run("run_2", branch="develop"),
        ]
        mock_service = _stub_service_with_runs(runs)
        app.dependency_overrides[get_run_service] = lambda: mock_service

        client = TestClient(app)
        response = client.get("/api/runs?branch=nonexistent")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 0
        assert data["total"] == 0


# ===========================================================================
# 6. Combined filters: source + branch + status
# ===========================================================================


class TestCombinedFilters:
    """source, branch, and status filters work together."""

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_source_and_branch_combined(self):
        """GET /api/runs?source=manual&branch=main returns only manual runs on main."""
        runs = [
            _make_mock_run("run_1", source="manual", branch="main"),
            _make_mock_run("run_2", source="simulation", branch="main"),
            _make_mock_run("run_3", source="manual", branch="feat/x"),
            _make_mock_run("run_4", source="simulation", branch="feat/x"),
        ]
        mock_service = _stub_service_with_runs(runs)
        app.dependency_overrides[get_run_service] = lambda: mock_service

        client = TestClient(app)
        response = client.get("/api/runs?source=manual&branch=main")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1, f"Expected 1 manual+main run, got {len(data['items'])}"
        assert data["items"][0]["id"] == "run_1"
        assert data["items"][0]["source"] == "manual"
        assert data["items"][0]["branch"] == "main"

    def test_source_and_status_combined(self):
        """GET /api/runs?source=manual&status=completed returns only completed manual runs."""
        runs = [
            _make_mock_run("run_1", source="manual", status=RunStatus.completed),
            _make_mock_run("run_2", source="manual", status=RunStatus.running),
            _make_mock_run("run_3", source="simulation", status=RunStatus.completed),
        ]
        mock_service = _stub_service_with_runs(runs)
        app.dependency_overrides[get_run_service] = lambda: mock_service

        client = TestClient(app)
        response = client.get("/api/runs?source=manual&status=completed")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1, f"Expected 1 completed manual run, got {len(data['items'])}"
        assert data["items"][0]["id"] == "run_1"

    def test_source_branch_and_status_combined(self):
        """All three filters applied simultaneously."""
        runs = [
            _make_mock_run("run_hit", source="manual", branch="main", status=RunStatus.completed),
            _make_mock_run(
                "run_miss_src", source="simulation", branch="main", status=RunStatus.completed
            ),
            _make_mock_run(
                "run_miss_br", source="manual", branch="feat/x", status=RunStatus.completed
            ),
            _make_mock_run("run_miss_st", source="manual", branch="main", status=RunStatus.running),
        ]
        mock_service = _stub_service_with_runs(runs)
        app.dependency_overrides[get_run_service] = lambda: mock_service

        client = TestClient(app)
        response = client.get("/api/runs?source=manual&branch=main&status=completed")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1, (
            f"Expected exactly 1 run matching all filters, got {len(data['items'])}"
        )
        assert data["items"][0]["id"] == "run_hit"


# ===========================================================================
# 7. No params = all runs returned (no default exclusion)
# ===========================================================================


class TestNoParamsReturnsAll:
    """Default behavior: no source/branch params returns all runs."""

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_no_params_returns_all_sources(self):
        """GET /api/runs without source param returns runs of all sources."""
        runs = [
            _make_mock_run("run_manual", source="manual"),
            _make_mock_run("run_sim", source="simulation"),
            _make_mock_run("run_webhook", source="webhook"),
            _make_mock_run("run_schedule", source="schedule"),
        ]
        mock_service = _stub_service_with_runs(runs)
        app.dependency_overrides[get_run_service] = lambda: mock_service

        client = TestClient(app)
        response = client.get("/api/runs")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 4, (
            f"Expected all 4 runs (no default exclusion), got {len(data['items'])}"
        )

    def test_no_params_returns_all_branches(self):
        """GET /api/runs without branch param returns runs from all branches."""
        runs = [
            _make_mock_run("run_main", branch="main"),
            _make_mock_run("run_feat", branch="feat/experiment"),
            _make_mock_run("run_sim_branch", branch="sim/test/20260330/abc123"),
        ]
        mock_service = _stub_service_with_runs(runs)
        app.dependency_overrides[get_run_service] = lambda: mock_service

        client = TestClient(app)
        response = client.get("/api/runs")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 3, (
            f"Expected all 3 runs (all branches), got {len(data['items'])}"
        )


# ===========================================================================
# 8. Dashboard excludes simulation runs from KPIs
# ===========================================================================


class TestDashboardExcludesSimulations:
    """GET /api/dashboard must NOT count simulation runs in KPI calculations."""

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_dashboard_runs_today_excludes_simulation(self):
        """runs_today must not count simulation runs."""
        now = time.time()
        runs = [
            _make_mock_run(
                "run_manual", source="manual", total_cost_usd=1.0, created_at=now - 3600
            ),
            _make_mock_run(
                "run_sim", source="simulation", total_cost_usd=2.0, created_at=now - 3600
            ),
            _make_mock_run(
                "run_webhook", source="webhook", total_cost_usd=0.5, created_at=now - 3600
            ),
        ]
        mock_service = Mock()
        mock_service.list_runs.return_value = runs
        mock_service.get_run_nodes.return_value = []
        app.dependency_overrides[get_run_service] = lambda: mock_service

        client = TestClient(app)
        response = client.get("/api/dashboard")
        assert response.status_code == 200
        data = response.json()
        assert data["runs_today"] == 2, (
            f"Expected 2 runs (excluding simulation), got {data['runs_today']}"
        )

    def test_dashboard_cost_excludes_simulation(self):
        """cost_today_usd must not include cost from simulation runs."""
        now = time.time()
        runs = [
            _make_mock_run(
                "run_manual", source="manual", total_cost_usd=1.0, created_at=now - 3600
            ),
            _make_mock_run(
                "run_sim", source="simulation", total_cost_usd=2.0, created_at=now - 3600
            ),
            _make_mock_run(
                "run_webhook", source="webhook", total_cost_usd=0.5, created_at=now - 3600
            ),
        ]
        mock_service = Mock()
        mock_service.list_runs.return_value = runs
        mock_service.get_run_nodes.return_value = []
        app.dependency_overrides[get_run_service] = lambda: mock_service

        client = TestClient(app)
        response = client.get("/api/dashboard")
        assert response.status_code == 200
        data = response.json()
        assert data["cost_today_usd"] == 1.5, (
            f"Expected $1.50 (manual + webhook, excluding simulation), got {data['cost_today_usd']}"
        )

    def test_dashboard_all_simulation_runs_gives_zero(self):
        """If ALL recent runs are simulation, runs_today and cost must be 0."""
        now = time.time()
        runs = [
            _make_mock_run(
                "run_sim1", source="simulation", total_cost_usd=5.0, created_at=now - 3600
            ),
            _make_mock_run(
                "run_sim2", source="simulation", total_cost_usd=3.0, created_at=now - 7200
            ),
        ]
        mock_service = Mock()
        mock_service.list_runs.return_value = runs
        mock_service.get_run_nodes.return_value = []
        app.dependency_overrides[get_run_service] = lambda: mock_service

        client = TestClient(app)
        response = client.get("/api/dashboard")
        assert response.status_code == 200
        data = response.json()
        assert data["runs_today"] == 0, (
            f"Expected 0 runs (all simulations), got {data['runs_today']}"
        )
        assert data["cost_today_usd"] == 0.0, (
            f"Expected $0.00 (all simulations), got {data['cost_today_usd']}"
        )


# ===========================================================================
# 9. Service layer: source and branch params accepted
# ===========================================================================


class TestServiceAcceptsSourceAndBranch:
    """RunService.list_runs_paginated must accept source and branch kwargs."""

    @pytest.fixture
    def run_repo(self):
        return Mock()

    @pytest.fixture
    def workflow_repo(self):
        return Mock()

    @pytest.fixture
    def run_service(self, run_repo, workflow_repo):
        from runsight_api.logic.services.run_service import RunService

        return RunService(run_repo, workflow_repo)

    def test_service_accepts_source_param(self, run_service, run_repo):
        """list_runs_paginated(source=['simulation']) must not raise TypeError."""
        run_repo.list_runs_paginated.return_value = ([], 0)

        # This call will raise TypeError today because the method has no source param
        run_service.list_runs_paginated(offset=0, limit=20, source=["simulation"])

    def test_service_accepts_branch_param(self, run_service, run_repo):
        """list_runs_paginated(branch='main') must not raise TypeError."""
        run_repo.list_runs_paginated.return_value = ([], 0)

        # This call will raise TypeError today because the method has no branch param
        run_service.list_runs_paginated(offset=0, limit=20, branch="main")

    def test_service_forwards_source_to_repo(self, run_service, run_repo):
        """Service must forward source to repo layer for SQL filtering."""
        run_repo.list_runs_paginated.return_value = ([], 0)

        run_service.list_runs_paginated(offset=0, limit=20, source=["manual", "webhook"])

        run_repo.list_runs_paginated.assert_called_once()
        _, kwargs = run_repo.list_runs_paginated.call_args
        assert kwargs.get("source") == ["manual", "webhook"], (
            "run_repo.list_runs_paginated must receive source=['manual', 'webhook']"
        )

    def test_service_forwards_branch_to_repo(self, run_service, run_repo):
        """Service must forward branch to repo layer for SQL filtering."""
        run_repo.list_runs_paginated.return_value = ([], 0)

        run_service.list_runs_paginated(offset=0, limit=20, branch="main")

        run_repo.list_runs_paginated.assert_called_once()
        _, kwargs = run_repo.list_runs_paginated.call_args
        assert kwargs.get("branch") == "main", (
            "run_repo.list_runs_paginated must receive branch='main'"
        )

    def test_service_source_and_branch_with_existing_params(self, run_service, run_repo):
        """source + branch work alongside existing status + workflow_id params."""
        run_repo.list_runs_paginated.return_value = ([], 0)

        run_service.list_runs_paginated(
            offset=0,
            limit=20,
            status=["completed"],
            workflow_id="wf_1",
            source=["manual"],
            branch="main",
        )

        run_repo.list_runs_paginated.assert_called_once()
        _, kwargs = run_repo.list_runs_paginated.call_args
        assert kwargs.get("status") == ["completed"]
        assert kwargs.get("workflow_id") == "wf_1"
        assert kwargs.get("source") == ["manual"]
        assert kwargs.get("branch") == "main"
