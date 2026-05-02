"""Dashboard KPI calculations exclude simulation and non-main runs."""

import time
from unittest.mock import Mock

from fastapi.testclient import TestClient

from runsight_api.main import app
from runsight_api.transport.deps import get_eval_service, get_run_service
from tests.transport.run_filtering_helpers import (
    _make_mock_run,
    _mock_eval_svc,
)


class TestDashboardExcludesSimulations:
    """GET /api/dashboard must NOT count simulation runs in KPI calculations."""

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_dashboard_runs_today_excludes_simulation(self):
        """runs_today must not count simulation runs."""
        now = time.time()
        runs = [
            _make_mock_run(
                "manual-run", source="manual", total_cost_usd=1.0, created_at=now - 3600
            ),
            _make_mock_run(
                "simulation-run", source="simulation", total_cost_usd=2.0, created_at=now - 3600
            ),
            _make_mock_run(
                "webhook-run", source="webhook", total_cost_usd=0.5, created_at=now - 3600
            ),
        ]
        mock_service = Mock()
        mock_service.list_runs.return_value = runs
        mock_service.get_run_nodes.return_value = []
        app.dependency_overrides[get_run_service] = lambda: mock_service
        app.dependency_overrides[get_eval_service] = lambda: _mock_eval_svc()

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
                "manual-run", source="manual", total_cost_usd=1.0, created_at=now - 3600
            ),
            _make_mock_run(
                "simulation-run", source="simulation", total_cost_usd=2.0, created_at=now - 3600
            ),
            _make_mock_run(
                "webhook-run", source="webhook", total_cost_usd=0.5, created_at=now - 3600
            ),
        ]
        mock_service = Mock()
        mock_service.list_runs.return_value = runs
        mock_service.get_run_nodes.return_value = []
        app.dependency_overrides[get_run_service] = lambda: mock_service
        app.dependency_overrides[get_eval_service] = lambda: _mock_eval_svc()

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
                "simulation-dashboard-run-one",
                source="simulation",
                total_cost_usd=5.0,
                created_at=now - 3600,
            ),
            _make_mock_run(
                "simulation-dashboard-run-two",
                source="simulation",
                total_cost_usd=3.0,
                created_at=now - 7200,
            ),
        ]
        mock_service = Mock()
        mock_service.list_runs.return_value = runs
        mock_service.get_run_nodes.return_value = []
        app.dependency_overrides[get_run_service] = lambda: mock_service
        app.dependency_overrides[get_eval_service] = lambda: _mock_eval_svc()

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

    def test_dashboard_missing_branch_is_not_treated_as_main(self):
        """A run without branch must not be counted as production main."""
        now = time.time()
        run_main = _make_mock_run(
            "main-branch-run", source="manual", total_cost_usd=1.0, created_at=now - 3600
        )
        run_missing = _make_mock_run(
            "missing-branch-run", source="manual", total_cost_usd=2.0, created_at=now - 3600
        )
        delattr(run_missing, "branch")
        run_sim = _make_mock_run(
            "simulation-run", source="simulation", total_cost_usd=3.0, created_at=now - 3600
        )
        runs = [run_main, run_missing, run_sim]
        mock_service = Mock()
        mock_service.list_runs.return_value = runs
        mock_service.get_run_nodes.return_value = []
        app.dependency_overrides[get_run_service] = lambda: mock_service
        app.dependency_overrides[get_eval_service] = lambda: _mock_eval_svc()

        client = TestClient(app)
        response = client.get("/api/dashboard")
        assert response.status_code == 200
        data = response.json()
        assert data["runs_today"] == 1, (
            f"Expected only explicit main runs to count, got {data['runs_today']}"
        )
        assert data["cost_today_usd"] == 1.0, (
            f"Expected only main-branch cost to count, got {data['cost_today_usd']}"
        )


# ===========================================================================
# 9. Service layer: source and branch params accepted
# ===========================================================================
