"""GET /api/runs source and branch filtering contracts."""

from fastapi.testclient import TestClient

from runsight_api.domain.entities.run import RunStatus
from runsight_api.main import app
from runsight_api.transport.deps import get_eval_service, get_run_service
from tests.transport.run_filtering_helpers import (
    _make_mock_run,
    _mock_eval_svc,
    _stub_service_with_runs,
)


class TestRouterAcceptsSourceParam:
    """GET /api/runs must accept a source query parameter (list of strings)."""

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_source_param_accepted_single(self):
        """GET /api/runs?source=simulation must not return 422."""
        runs = [_make_mock_run("simulation-source-param-run", source="simulation")]
        mock_service = _stub_service_with_runs(runs)
        app.dependency_overrides[get_run_service] = lambda: mock_service
        app.dependency_overrides[get_eval_service] = lambda: _mock_eval_svc()

        client = TestClient(app)
        response = client.get("/api/runs?source=simulation")
        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: source param should be accepted"
        )

    def test_source_param_accepted_multiple(self):
        """GET /api/runs?source=manual&source=webhook must not return 422."""
        runs = [
            _make_mock_run("manual-source-param-run", source="manual"),
            _make_mock_run("webhook-source-param-run", source="webhook"),
        ]
        mock_service = _stub_service_with_runs(runs)
        app.dependency_overrides[get_run_service] = lambda: mock_service
        app.dependency_overrides[get_eval_service] = lambda: _mock_eval_svc()

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
        runs = [_make_mock_run("main-branch-param-run", branch="main")]
        mock_service = _stub_service_with_runs(runs)
        app.dependency_overrides[get_run_service] = lambda: mock_service
        app.dependency_overrides[get_eval_service] = lambda: _mock_eval_svc()

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
            _make_mock_run("simulation-run", source="simulation"),
            _make_mock_run("manual-run", source="manual"),
            _make_mock_run("webhook-run", source="webhook"),
        ]
        mock_service = _stub_service_with_runs(runs)
        app.dependency_overrides[get_run_service] = lambda: mock_service
        app.dependency_overrides[get_eval_service] = lambda: _mock_eval_svc()

        client = TestClient(app)
        response = client.get("/api/runs?source=simulation")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1, f"Expected 1 simulation run, got {len(data['items'])}"
        assert data["items"][0]["id"] == "simulation-run"
        assert data["items"][0]["source"] == "simulation"

    def test_source_manual_returns_only_manual_runs(self):
        """GET /api/runs?source=manual must return only runs with source=manual."""
        runs = [
            _make_mock_run("simulation-run", source="simulation"),
            _make_mock_run("manual-run", source="manual"),
            _make_mock_run("schedule-run", source="schedule"),
        ]
        mock_service = _stub_service_with_runs(runs)
        app.dependency_overrides[get_run_service] = lambda: mock_service
        app.dependency_overrides[get_eval_service] = lambda: _mock_eval_svc()

        client = TestClient(app)
        response = client.get("/api/runs?source=manual")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1, f"Expected 1 manual run, got {len(data['items'])}"
        assert data["items"][0]["id"] == "manual-run"
        assert data["items"][0]["source"] == "manual"

    def test_source_filter_empty_result(self):
        """GET /api/runs?source=schedule returns empty when no schedule runs exist."""
        runs = [
            _make_mock_run("manual-nonmatching-source-run", source="manual"),
            _make_mock_run("simulation-nonmatching-source-run", source="simulation"),
        ]
        mock_service = _stub_service_with_runs(runs)
        app.dependency_overrides[get_run_service] = lambda: mock_service
        app.dependency_overrides[get_eval_service] = lambda: _mock_eval_svc()

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
            _make_mock_run("manual-run", source="manual"),
            _make_mock_run("webhook-run", source="webhook"),
            _make_mock_run("simulation-run", source="simulation"),
            _make_mock_run("schedule-run", source="schedule"),
        ]
        mock_service = _stub_service_with_runs(runs)
        app.dependency_overrides[get_run_service] = lambda: mock_service
        app.dependency_overrides[get_eval_service] = lambda: _mock_eval_svc()

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
            _make_mock_run("manual-run", source="manual"),
            _make_mock_run("webhook-run", source="webhook"),
            _make_mock_run("simulation-run", source="simulation"),
            _make_mock_run("schedule-run", source="schedule"),
        ]
        mock_service = _stub_service_with_runs(runs)
        app.dependency_overrides[get_run_service] = lambda: mock_service
        app.dependency_overrides[get_eval_service] = lambda: _mock_eval_svc()

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
            _make_mock_run("main-branch-run", branch="main"),
            _make_mock_run("feature-branch-run", branch="feat/experiment"),
            _make_mock_run("simulation-branch-run", branch="sim/test/20260330/abc123"),
        ]
        mock_service = _stub_service_with_runs(runs)
        app.dependency_overrides[get_run_service] = lambda: mock_service
        app.dependency_overrides[get_eval_service] = lambda: _mock_eval_svc()

        client = TestClient(app)
        response = client.get("/api/runs?branch=main")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1, f"Expected 1 main-branch run, got {len(data['items'])}"
        assert data["items"][0]["id"] == "main-branch-run"
        assert data["items"][0]["branch"] == "main"

    def test_branch_feature_returns_only_feature_runs(self):
        """GET /api/runs?branch=feat/experiment must return only that branch."""
        runs = [
            _make_mock_run("main-branch-run", branch="main"),
            _make_mock_run("feature-branch-run", branch="feat/experiment"),
        ]
        mock_service = _stub_service_with_runs(runs)
        app.dependency_overrides[get_run_service] = lambda: mock_service
        app.dependency_overrides[get_eval_service] = lambda: _mock_eval_svc()

        client = TestClient(app)
        response = client.get("/api/runs?branch=feat/experiment")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1, (
            f"Expected 1 run for feat/experiment, got {len(data['items'])}"
        )
        assert data["items"][0]["id"] == "feature-branch-run"

    def test_branch_filter_empty_result(self):
        """GET /api/runs?branch=nonexistent returns empty list."""
        runs = [
            _make_mock_run("main-branch-run", branch="main"),
            _make_mock_run("develop-branch-run", branch="develop"),
        ]
        mock_service = _stub_service_with_runs(runs)
        app.dependency_overrides[get_run_service] = lambda: mock_service
        app.dependency_overrides[get_eval_service] = lambda: _mock_eval_svc()

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
            _make_mock_run("manual-main-run", source="manual", branch="main"),
            _make_mock_run("simulation-main-run", source="simulation", branch="main"),
            _make_mock_run("manual-feature-run", source="manual", branch="feat/x"),
            _make_mock_run("simulation-feature-run", source="simulation", branch="feat/x"),
        ]
        mock_service = _stub_service_with_runs(runs)
        app.dependency_overrides[get_run_service] = lambda: mock_service
        app.dependency_overrides[get_eval_service] = lambda: _mock_eval_svc()

        client = TestClient(app)
        response = client.get("/api/runs?source=manual&branch=main")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1, f"Expected 1 manual+main run, got {len(data['items'])}"
        assert data["items"][0]["id"] == "manual-main-run"
        assert data["items"][0]["source"] == "manual"
        assert data["items"][0]["branch"] == "main"

    def test_source_and_status_combined(self):
        """GET /api/runs?source=manual&status=completed returns only completed manual runs."""
        runs = [
            _make_mock_run("completed-manual-run", source="manual", status=RunStatus.completed),
            _make_mock_run("running-manual-run", source="manual", status=RunStatus.running),
            _make_mock_run(
                "completed-simulation-run", source="simulation", status=RunStatus.completed
            ),
        ]
        mock_service = _stub_service_with_runs(runs)
        app.dependency_overrides[get_run_service] = lambda: mock_service
        app.dependency_overrides[get_eval_service] = lambda: _mock_eval_svc()

        client = TestClient(app)
        response = client.get("/api/runs?source=manual&status=completed")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1, f"Expected 1 completed manual run, got {len(data['items'])}"
        assert data["items"][0]["id"] == "completed-manual-run"

    def test_source_branch_and_status_combined(self):
        """All three filters applied simultaneously."""
        runs = [
            _make_mock_run(
                "matching-filter-run", source="manual", branch="main", status=RunStatus.completed
            ),
            _make_mock_run(
                "wrong-source-run", source="simulation", branch="main", status=RunStatus.completed
            ),
            _make_mock_run(
                "wrong-branch-run", source="manual", branch="feat/x", status=RunStatus.completed
            ),
            _make_mock_run(
                "wrong-status-run", source="manual", branch="main", status=RunStatus.running
            ),
        ]
        mock_service = _stub_service_with_runs(runs)
        app.dependency_overrides[get_run_service] = lambda: mock_service
        app.dependency_overrides[get_eval_service] = lambda: _mock_eval_svc()

        client = TestClient(app)
        response = client.get("/api/runs?source=manual&branch=main&status=completed")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1, (
            f"Expected exactly 1 run matching all filters, got {len(data['items'])}"
        )
        assert data["items"][0]["id"] == "matching-filter-run"


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
            _make_mock_run("manual-run", source="manual"),
            _make_mock_run("simulation-run", source="simulation"),
            _make_mock_run("webhook-run", source="webhook"),
            _make_mock_run("schedule-run", source="schedule"),
        ]
        mock_service = _stub_service_with_runs(runs)
        app.dependency_overrides[get_run_service] = lambda: mock_service
        app.dependency_overrides[get_eval_service] = lambda: _mock_eval_svc()

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
            _make_mock_run("main-branch-run", branch="main"),
            _make_mock_run("feature-branch-run", branch="feat/experiment"),
            _make_mock_run("simulation-branch-run", branch="sim/test/20260330/abc123"),
        ]
        mock_service = _stub_service_with_runs(runs)
        app.dependency_overrides[get_run_service] = lambda: mock_service
        app.dependency_overrides[get_eval_service] = lambda: _mock_eval_svc()

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
