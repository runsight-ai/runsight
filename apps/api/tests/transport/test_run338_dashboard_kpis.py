"""
RED-TEAM tests for RUN-338: A2 — KPI Runs Today + Cost Today — end-to-end.

These tests verify the redesigned GET /api/dashboard endpoint:

  1. New response model: runs_today, cost_today_usd, eval_pass_rate, regressions, period_hours
  2. Time-scoping: only counts runs from the last 24h
  3. Eval fields return None when no eval data
  4. Old fields (active_runs, completed_runs, total_cost_usd, recent_errors, system_status) are GONE

Expected: ALL tests fail against the current implementation which returns the
old DashboardResponse shape with all-time, unscoped counts.
"""

import time
from unittest.mock import Mock

from fastapi.testclient import TestClient

from runsight_api.domain.entities.run import RunStatus
from runsight_api.main import app
from runsight_api.transport.deps import get_run_service

client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_run(
    run_id: str = "run_001",
    status: RunStatus = RunStatus.completed,
    total_cost_usd: float = 0.0,
    created_at: float | None = None,
) -> Mock:
    """Create a mock Run with the given attributes."""
    mock_run = Mock()
    mock_run.id = run_id
    mock_run.workflow_id = "wf_1"
    mock_run.workflow_name = "Test Workflow"
    mock_run.status = status
    mock_run.started_at = (created_at or time.time()) - 10
    mock_run.completed_at = created_at or time.time()
    mock_run.duration_s = 10.0
    mock_run.total_cost_usd = total_cost_usd
    mock_run.total_tokens = 100
    mock_run.created_at = created_at or time.time()
    mock_run.updated_at = created_at or time.time()
    return mock_run


# ---------------------------------------------------------------------------
# 1. New response model shape
# ---------------------------------------------------------------------------


class TestDashboardKPIsResponseShape:
    """GET /api/dashboard must return the new DashboardKPIsResponse shape."""

    def setup_method(self):
        self.mock_service = Mock()
        self.mock_service.list_runs.return_value = []
        app.dependency_overrides[get_run_service] = lambda: self.mock_service

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_response_contains_runs_today(self):
        response = client.get("/api/dashboard")
        assert response.status_code == 200
        data = response.json()
        assert "runs_today" in data

    def test_response_contains_cost_today_usd(self):
        response = client.get("/api/dashboard")
        assert response.status_code == 200
        data = response.json()
        assert "cost_today_usd" in data

    def test_response_contains_eval_pass_rate(self):
        response = client.get("/api/dashboard")
        assert response.status_code == 200
        data = response.json()
        assert "eval_pass_rate" in data

    def test_response_contains_regressions(self):
        response = client.get("/api/dashboard")
        assert response.status_code == 200
        data = response.json()
        assert "regressions" in data

    def test_response_contains_period_hours(self):
        response = client.get("/api/dashboard")
        assert response.status_code == 200
        data = response.json()
        assert "period_hours" in data

    def test_period_hours_defaults_to_24(self):
        response = client.get("/api/dashboard")
        data = response.json()
        assert data["period_hours"] == 24


# ---------------------------------------------------------------------------
# 2. Old fields are gone
# ---------------------------------------------------------------------------


class TestOldFieldsRemoved:
    """Old DashboardResponse fields must NOT appear in the new response."""

    def setup_method(self):
        self.mock_service = Mock()
        self.mock_service.list_runs.return_value = []
        app.dependency_overrides[get_run_service] = lambda: self.mock_service

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_no_active_runs_field(self):
        data = client.get("/api/dashboard").json()
        assert "active_runs" not in data

    def test_no_completed_runs_field(self):
        data = client.get("/api/dashboard").json()
        assert "completed_runs" not in data

    def test_no_total_cost_usd_field(self):
        """total_cost_usd (all-time) replaced by cost_today_usd (24h scoped)."""
        data = client.get("/api/dashboard").json()
        assert "total_cost_usd" not in data

    def test_no_recent_errors_field(self):
        data = client.get("/api/dashboard").json()
        assert "recent_errors" not in data

    def test_no_system_status_field(self):
        data = client.get("/api/dashboard").json()
        assert "system_status" not in data


# ---------------------------------------------------------------------------
# 3. Time-scoping: only last 24h
# ---------------------------------------------------------------------------


class TestTimeScoping:
    """Dashboard endpoint must only count runs created in the last 24 hours."""

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_runs_today_counts_only_recent_runs(self):
        """A run from 2 hours ago counts; a run from 48 hours ago does not."""
        now = time.time()
        recent_run = _make_mock_run("run_recent", RunStatus.completed, 1.50, now - 3600)
        old_run = _make_mock_run("run_old", RunStatus.completed, 2.00, now - 48 * 3600)

        mock_service = Mock()
        mock_service.list_runs.return_value = [recent_run, old_run]
        app.dependency_overrides[get_run_service] = lambda: mock_service

        data = client.get("/api/dashboard").json()
        assert data["runs_today"] == 1  # only the recent run

    def test_cost_today_sums_only_recent_runs(self):
        """Cost from a 2h-ago run is included; cost from a 48h-ago run is excluded."""
        now = time.time()
        recent_run = _make_mock_run("run_recent", RunStatus.completed, 1.50, now - 3600)
        old_run = _make_mock_run("run_old", RunStatus.completed, 2.00, now - 48 * 3600)

        mock_service = Mock()
        mock_service.list_runs.return_value = [recent_run, old_run]
        app.dependency_overrides[get_run_service] = lambda: mock_service

        data = client.get("/api/dashboard").json()
        assert data["cost_today_usd"] == 1.50  # only recent_run's cost

    def test_runs_today_zero_when_all_runs_older_than_24h(self):
        now = time.time()
        old_run = _make_mock_run("run_old", RunStatus.completed, 5.00, now - 48 * 3600)

        mock_service = Mock()
        mock_service.list_runs.return_value = [old_run]
        app.dependency_overrides[get_run_service] = lambda: mock_service

        data = client.get("/api/dashboard").json()
        assert data["runs_today"] == 0

    def test_cost_today_zero_when_all_runs_older_than_24h(self):
        now = time.time()
        old_run = _make_mock_run("run_old", RunStatus.completed, 5.00, now - 48 * 3600)

        mock_service = Mock()
        mock_service.list_runs.return_value = [old_run]
        app.dependency_overrides[get_run_service] = lambda: mock_service

        data = client.get("/api/dashboard").json()
        assert data["cost_today_usd"] == 0.0

    def test_runs_today_includes_all_statuses_within_24h(self):
        """Pending, running, completed, failed — all count if within 24h."""
        now = time.time()
        runs = [
            _make_mock_run("run_p", RunStatus.pending, 0.0, now - 100),
            _make_mock_run("run_r", RunStatus.running, 0.0, now - 200),
            _make_mock_run("run_c", RunStatus.completed, 0.0, now - 300),
            _make_mock_run("run_f", RunStatus.failed, 0.0, now - 400),
        ]

        mock_service = Mock()
        mock_service.list_runs.return_value = runs
        app.dependency_overrides[get_run_service] = lambda: mock_service

        data = client.get("/api/dashboard").json()
        assert data["runs_today"] == 4


# ---------------------------------------------------------------------------
# 4. Eval fields return None (no eval engine yet)
# ---------------------------------------------------------------------------


class TestEvalFieldsNull:
    """eval_pass_rate and regressions must be None until eval engine is wired."""

    def setup_method(self):
        self.mock_service = Mock()
        self.mock_service.list_runs.return_value = []
        app.dependency_overrides[get_run_service] = lambda: self.mock_service

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_eval_pass_rate_is_null(self):
        data = client.get("/api/dashboard").json()
        assert data["eval_pass_rate"] is None

    def test_regressions_is_null(self):
        data = client.get("/api/dashboard").json()
        assert data["regressions"] is None

    def test_eval_fields_null_even_with_runs(self):
        """Even when runs exist, eval fields stay None (no eval engine)."""
        now = time.time()
        run = _make_mock_run("run_1", RunStatus.completed, 1.0, now - 3600)
        self.mock_service.list_runs.return_value = [run]

        data = client.get("/api/dashboard").json()
        assert data["eval_pass_rate"] is None
        assert data["regressions"] is None


# ---------------------------------------------------------------------------
# 5. Pydantic response model exists with correct fields
# ---------------------------------------------------------------------------


class TestDashboardKPIsResponseModel:
    """The new Pydantic model must exist with the correct field types."""

    def test_dashboard_kpis_response_importable(self):
        from runsight_api.transport.schemas.dashboard import DashboardKPIsResponse  # noqa: F811

        assert DashboardKPIsResponse is not None

    def test_model_has_runs_today_int(self):
        from runsight_api.transport.schemas.dashboard import DashboardKPIsResponse

        fields = DashboardKPIsResponse.model_fields
        assert "runs_today" in fields
        assert fields["runs_today"].annotation is int

    def test_model_has_cost_today_usd_float(self):
        from runsight_api.transport.schemas.dashboard import DashboardKPIsResponse

        fields = DashboardKPIsResponse.model_fields
        assert "cost_today_usd" in fields
        assert fields["cost_today_usd"].annotation is float

    def test_model_has_eval_pass_rate_optional_float(self):
        from runsight_api.transport.schemas.dashboard import DashboardKPIsResponse

        fields = DashboardKPIsResponse.model_fields
        assert "eval_pass_rate" in fields
        # Should accept None
        instance = DashboardKPIsResponse(
            runs_today=0, cost_today_usd=0.0, eval_pass_rate=None, regressions=None
        )
        assert instance.eval_pass_rate is None

    def test_model_has_regressions_optional_int(self):
        from runsight_api.transport.schemas.dashboard import DashboardKPIsResponse

        fields = DashboardKPIsResponse.model_fields
        assert "regressions" in fields
        instance = DashboardKPIsResponse(
            runs_today=0, cost_today_usd=0.0, eval_pass_rate=None, regressions=None
        )
        assert instance.regressions is None

    def test_model_has_period_hours_default_24(self):
        from runsight_api.transport.schemas.dashboard import DashboardKPIsResponse

        instance = DashboardKPIsResponse(
            runs_today=0, cost_today_usd=0.0, eval_pass_rate=None, regressions=None
        )
        assert instance.period_hours == 24
