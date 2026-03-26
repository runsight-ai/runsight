"""
RED-TEAM tests for RUN-342: A5 — KPI Eval Pass Rate + Regressions — end-to-end.

These tests verify the GET /api/dashboard endpoint computes real eval KPIs:

  1. eval_pass_rate: AVG(eval_passed) across RunNodes in last 24h
  2. regressions: count where eval_passed=false AND baseline had eval_passed=true
  3. Both still return None when no eval data exists

Expected: ALL tests fail — endpoint currently hardcodes eval_pass_rate=None
and regressions=None regardless of RunNode data.
"""

import time

from fastapi.testclient import TestClient
from unittest.mock import Mock

from runsight_api.main import app
from runsight_api.transport.deps import get_run_service
from runsight_api.domain.entities.run import RunStatus, NodeStatus

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


def _make_mock_node(
    node_id: str = "node_001",
    run_id: str = "run_001",
    eval_passed: bool | None = None,
    eval_score: float | None = None,
    soul_id: str | None = None,
    soul_version: str | None = None,
    created_at: float | None = None,
) -> Mock:
    """Create a mock RunNode with eval fields."""
    mock_node = Mock()
    mock_node.id = f"{run_id}:{node_id}"
    mock_node.run_id = run_id
    mock_node.node_id = node_id
    mock_node.block_type = "llm"
    mock_node.status = NodeStatus.completed
    mock_node.eval_passed = eval_passed
    mock_node.eval_score = eval_score
    mock_node.eval_results = None
    mock_node.soul_id = soul_id
    mock_node.soul_version = soul_version
    mock_node.cost_usd = 0.01
    mock_node.tokens = {"prompt": 50, "completion": 50, "total": 100}
    mock_node.created_at = created_at or time.time()
    mock_node.updated_at = created_at or time.time()
    return mock_node


# ---------------------------------------------------------------------------
# 1. eval_pass_rate computes real percentage from RunNode data
# ---------------------------------------------------------------------------


class TestEvalPassRateComputed:
    """eval_pass_rate must return AVG(eval_passed) as a float 0.0-1.0 when
    RunNodes in the last 24h have eval_passed data."""

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_all_nodes_passed_returns_1_0(self):
        """When all RunNodes have eval_passed=True, eval_pass_rate should be 1.0."""
        now = time.time()
        run = _make_mock_run("run_1", RunStatus.completed, 0.5, now - 3600)

        nodes = [
            _make_mock_node(
                "n1", "run_1", eval_passed=True, eval_score=0.95, created_at=now - 3600
            ),
            _make_mock_node(
                "n2", "run_1", eval_passed=True, eval_score=0.88, created_at=now - 3600
            ),
            _make_mock_node(
                "n3", "run_1", eval_passed=True, eval_score=0.92, created_at=now - 3600
            ),
        ]

        mock_service = Mock()
        mock_service.list_runs.return_value = [run]
        mock_service.get_run_nodes.return_value = nodes
        app.dependency_overrides[get_run_service] = lambda: mock_service

        data = client.get("/api/dashboard").json()
        assert data["eval_pass_rate"] == 1.0

    def test_mixed_pass_fail_returns_correct_ratio(self):
        """When 3/4 nodes pass, eval_pass_rate should be 0.75."""
        now = time.time()
        run = _make_mock_run("run_1", RunStatus.completed, 0.5, now - 3600)

        nodes = [
            _make_mock_node("n1", "run_1", eval_passed=True, eval_score=0.9, created_at=now - 3600),
            _make_mock_node(
                "n2", "run_1", eval_passed=True, eval_score=0.85, created_at=now - 3600
            ),
            _make_mock_node("n3", "run_1", eval_passed=True, eval_score=0.8, created_at=now - 3600),
            _make_mock_node(
                "n4", "run_1", eval_passed=False, eval_score=0.3, created_at=now - 3600
            ),
        ]

        mock_service = Mock()
        mock_service.list_runs.return_value = [run]
        mock_service.get_run_nodes.return_value = nodes
        app.dependency_overrides[get_run_service] = lambda: mock_service

        data = client.get("/api/dashboard").json()
        assert data["eval_pass_rate"] == 0.75

    def test_all_nodes_failed_returns_0_0(self):
        """When all RunNodes have eval_passed=False, eval_pass_rate should be 0.0."""
        now = time.time()
        run = _make_mock_run("run_1", RunStatus.completed, 0.5, now - 3600)

        nodes = [
            _make_mock_node(
                "n1", "run_1", eval_passed=False, eval_score=0.2, created_at=now - 3600
            ),
            _make_mock_node(
                "n2", "run_1", eval_passed=False, eval_score=0.1, created_at=now - 3600
            ),
        ]

        mock_service = Mock()
        mock_service.list_runs.return_value = [run]
        mock_service.get_run_nodes.return_value = nodes
        app.dependency_overrides[get_run_service] = lambda: mock_service

        data = client.get("/api/dashboard").json()
        assert data["eval_pass_rate"] == 0.0

    def test_aggregates_across_multiple_recent_runs(self):
        """eval_pass_rate aggregates RunNodes from ALL recent runs, not just one."""
        now = time.time()
        run_1 = _make_mock_run("run_1", RunStatus.completed, 0.5, now - 3600)
        run_2 = _make_mock_run("run_2", RunStatus.completed, 0.3, now - 7200)

        # run_1: 2 passed, run_2: 1 failed => 2/3 = 0.6667
        nodes_run_1 = [
            _make_mock_node("n1", "run_1", eval_passed=True, eval_score=0.9, created_at=now - 3600),
            _make_mock_node(
                "n2", "run_1", eval_passed=True, eval_score=0.85, created_at=now - 3600
            ),
        ]
        nodes_run_2 = [
            _make_mock_node(
                "n3", "run_2", eval_passed=False, eval_score=0.3, created_at=now - 7200
            ),
        ]

        mock_service = Mock()
        mock_service.list_runs.return_value = [run_1, run_2]
        mock_service.get_run_nodes.side_effect = lambda rid: (
            nodes_run_1 if rid == "run_1" else nodes_run_2
        )
        app.dependency_overrides[get_run_service] = lambda: mock_service

        data = client.get("/api/dashboard").json()
        # 2 passed out of 3 total => ~0.6667
        assert data["eval_pass_rate"] is not None
        assert abs(data["eval_pass_rate"] - 2 / 3) < 0.01

    def test_ignores_nodes_without_eval_data(self):
        """RunNodes with eval_passed=None are excluded from the average."""
        now = time.time()
        run = _make_mock_run("run_1", RunStatus.completed, 0.5, now - 3600)

        nodes = [
            _make_mock_node("n1", "run_1", eval_passed=True, eval_score=0.9, created_at=now - 3600),
            _make_mock_node(
                "n2", "run_1", eval_passed=None, eval_score=None, created_at=now - 3600
            ),
            _make_mock_node(
                "n3", "run_1", eval_passed=False, eval_score=0.3, created_at=now - 3600
            ),
        ]

        mock_service = Mock()
        mock_service.list_runs.return_value = [run]
        mock_service.get_run_nodes.return_value = nodes
        app.dependency_overrides[get_run_service] = lambda: mock_service

        data = client.get("/api/dashboard").json()
        # Only n1 (True) and n3 (False) count => 1/2 = 0.5
        assert data["eval_pass_rate"] == 0.5

    def test_excludes_nodes_from_old_runs(self):
        """Only RunNodes from runs within the 24h window are included."""
        now = time.time()
        recent_run = _make_mock_run("run_recent", RunStatus.completed, 0.5, now - 3600)
        old_run = _make_mock_run("run_old", RunStatus.completed, 0.5, now - 48 * 3600)

        recent_nodes = [
            _make_mock_node(
                "n1", "run_recent", eval_passed=True, eval_score=0.9, created_at=now - 3600
            ),
        ]
        old_nodes = [
            _make_mock_node(
                "n2", "run_old", eval_passed=False, eval_score=0.2, created_at=now - 48 * 3600
            ),
        ]

        mock_service = Mock()
        mock_service.list_runs.return_value = [recent_run, old_run]
        mock_service.get_run_nodes.side_effect = lambda rid: (
            recent_nodes if rid == "run_recent" else old_nodes
        )
        app.dependency_overrides[get_run_service] = lambda: mock_service

        data = client.get("/api/dashboard").json()
        # Only recent run's node (passed=True) counts => 1.0
        assert data["eval_pass_rate"] == 1.0


# ---------------------------------------------------------------------------
# 2. regressions computes real count
# ---------------------------------------------------------------------------


class TestRegressionsComputed:
    """regressions must return the count of RunNodes where eval_passed=False
    AND the baseline for that soul had eval_passed=True."""

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_regression_detected_when_node_fails_with_passing_baseline(self):
        """A node that fails eval when baseline passed = 1 regression."""
        now = time.time()
        run = _make_mock_run("run_1", RunStatus.completed, 0.5, now - 3600)

        # Node fails eval, but has a soul_id/version for baseline lookup
        node = _make_mock_node(
            "n1",
            "run_1",
            eval_passed=False,
            eval_score=0.3,
            soul_id="soul_a",
            soul_version="v1",
            created_at=now - 3600,
        )

        mock_service = Mock()
        mock_service.list_runs.return_value = [run]
        mock_service.get_run_nodes.return_value = [node]
        app.dependency_overrides[get_run_service] = lambda: mock_service

        data = client.get("/api/dashboard").json()
        assert data["regressions"] is not None
        assert data["regressions"] >= 1

    def test_zero_regressions_when_all_evals_pass(self):
        """When all RunNodes pass eval, regressions should be 0."""
        now = time.time()
        run = _make_mock_run("run_1", RunStatus.completed, 0.5, now - 3600)

        nodes = [
            _make_mock_node("n1", "run_1", eval_passed=True, eval_score=0.9, created_at=now - 3600),
            _make_mock_node(
                "n2", "run_1", eval_passed=True, eval_score=0.85, created_at=now - 3600
            ),
        ]

        mock_service = Mock()
        mock_service.list_runs.return_value = [run]
        mock_service.get_run_nodes.return_value = nodes
        app.dependency_overrides[get_run_service] = lambda: mock_service

        data = client.get("/api/dashboard").json()
        assert data["regressions"] == 0

    def test_multiple_regressions_counted(self):
        """Multiple failing nodes each count as a regression."""
        now = time.time()
        run = _make_mock_run("run_1", RunStatus.completed, 0.5, now - 3600)

        nodes = [
            _make_mock_node(
                "n1",
                "run_1",
                eval_passed=False,
                eval_score=0.2,
                soul_id="soul_a",
                soul_version="v1",
                created_at=now - 3600,
            ),
            _make_mock_node(
                "n2",
                "run_1",
                eval_passed=False,
                eval_score=0.1,
                soul_id="soul_b",
                soul_version="v1",
                created_at=now - 3600,
            ),
            _make_mock_node("n3", "run_1", eval_passed=True, eval_score=0.9, created_at=now - 3600),
        ]

        mock_service = Mock()
        mock_service.list_runs.return_value = [run]
        mock_service.get_run_nodes.return_value = nodes
        app.dependency_overrides[get_run_service] = lambda: mock_service

        data = client.get("/api/dashboard").json()
        assert data["regressions"] is not None
        assert data["regressions"] >= 2

    def test_regressions_excludes_old_runs(self):
        """Regressions are only counted from runs within the 24h window."""
        now = time.time()
        recent_run = _make_mock_run("run_recent", RunStatus.completed, 0.5, now - 3600)
        old_run = _make_mock_run("run_old", RunStatus.completed, 0.5, now - 48 * 3600)

        recent_nodes = [
            _make_mock_node(
                "n1", "run_recent", eval_passed=True, eval_score=0.9, created_at=now - 3600
            ),
        ]
        old_nodes = [
            _make_mock_node(
                "n2",
                "run_old",
                eval_passed=False,
                eval_score=0.2,
                soul_id="soul_a",
                soul_version="v1",
                created_at=now - 48 * 3600,
            ),
        ]

        mock_service = Mock()
        mock_service.list_runs.return_value = [recent_run, old_run]
        mock_service.get_run_nodes.side_effect = lambda rid: (
            recent_nodes if rid == "run_recent" else old_nodes
        )
        app.dependency_overrides[get_run_service] = lambda: mock_service

        data = client.get("/api/dashboard").json()
        # Only recent run counted; it has 0 regressions
        assert data["regressions"] == 0


# ---------------------------------------------------------------------------
# 3. Both return None when no eval data exists
# ---------------------------------------------------------------------------


class TestNullWhenNoEvalData:
    """When no RunNodes have eval data, both fields should remain None."""

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_null_when_no_runs(self):
        """No runs at all => both eval fields are None."""
        mock_service = Mock()
        mock_service.list_runs.return_value = []
        app.dependency_overrides[get_run_service] = lambda: mock_service

        data = client.get("/api/dashboard").json()
        assert data["eval_pass_rate"] is None
        assert data["regressions"] is None

    def test_null_when_runs_have_no_eval_nodes(self):
        """Runs exist but RunNodes have no eval_passed data => None."""
        now = time.time()
        run = _make_mock_run("run_1", RunStatus.completed, 0.5, now - 3600)

        nodes = [
            _make_mock_node(
                "n1", "run_1", eval_passed=None, eval_score=None, created_at=now - 3600
            ),
            _make_mock_node(
                "n2", "run_1", eval_passed=None, eval_score=None, created_at=now - 3600
            ),
        ]

        mock_service = Mock()
        mock_service.list_runs.return_value = [run]
        mock_service.get_run_nodes.return_value = nodes
        app.dependency_overrides[get_run_service] = lambda: mock_service

        data = client.get("/api/dashboard").json()
        assert data["eval_pass_rate"] is None
        assert data["regressions"] is None

    def test_null_when_no_nodes_at_all(self):
        """Runs exist but have zero RunNodes => None."""
        now = time.time()
        run = _make_mock_run("run_1", RunStatus.completed, 0.5, now - 3600)

        mock_service = Mock()
        mock_service.list_runs.return_value = [run]
        mock_service.get_run_nodes.return_value = []
        app.dependency_overrides[get_run_service] = lambda: mock_service

        data = client.get("/api/dashboard").json()
        assert data["eval_pass_rate"] is None
        assert data["regressions"] is None
