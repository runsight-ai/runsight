"""Regression detection logic.

Tests cover:
- Regression detection uses comparison-based logic, not just eval_passed=False
- get_workflow_health_metrics() regression_count uses passed-before/failed-now
  logic, not a raw eval_passed=False count
- Edge: Run with no eval assertions => 0 regressions
- Edge: First run of a workflow (no baseline) => 0 regressions
- Edge: Run where soul was deleted after execution => regression still computed
"""

from unittest.mock import Mock

from sqlmodel import Session

from runsight_api.data.repositories.run_read_model import RunReadModel
from runsight_api.logic.services.eval_service import EvalService
from apps.api.tests.logic.regression_fixtures import (
    db_session as _db_session_fixture,  # noqa: F401
    make_mock_node as _make_mock_node,
    make_mock_run as _make_mock_run,
    seed_node as _seed_node,
    seed_run as _seed_run,
)


# ===========================================================================
# get_run_regressions uses comparison-based detection
# ===========================================================================


class TestGetRunRegressions:
    """EvalService.get_run_regressions() must use comparison-based logic."""

    def test_method_exists_on_eval_service(self):
        """EvalService must expose get_run_regressions()."""
        repo = Mock()
        service = EvalService(repo)
        assert hasattr(service, "get_run_regressions")
        assert callable(service.get_run_regressions)

    def test_assertion_regression_detected_when_passed_before_failed_now(self):
        """A node that passed on the previous run and fails now is an assertion_regression."""
        repo = Mock()

        current_run = _make_mock_run("current-regression-run", created_at=200.0)
        previous_run = _make_mock_run("baseline-regression-run", created_at=100.0)

        # Previous node: eval_passed=True
        prev_node = _make_mock_node(
            node_id="analyze",
            run_id="baseline-regression-run",
            eval_passed=True,
            eval_score=0.95,
            cost_usd=0.005,
            created_at=100.0,
        )
        # Current node: eval_passed=False (same soul_version)
        curr_node = _make_mock_node(
            node_id="analyze",
            run_id="current-regression-run",
            eval_passed=False,
            eval_score=0.30,
            cost_usd=0.005,
            created_at=200.0,
        )

        repo.get_run.return_value = current_run
        repo.list_runs.return_value = [current_run, previous_run]
        repo.list_nodes_for_run.side_effect = lambda run_id: (
            [curr_node] if run_id == "current-regression-run" else [prev_node]
        )

        service = EvalService(repo)
        result = service.get_run_regressions("current-regression-run")

        assert result is not None
        assert result["count"] >= 1
        types = {i["type"] for i in result["issues"]}
        assert "assertion_regression" in types

    def test_missing_branch_run_is_not_treated_as_production_main(self):
        """A run without branch must not become the baseline production run."""
        repo = Mock()

        previous_run = _make_mock_run("baseline-regression-run", created_at=100.0)
        delattr(previous_run, "branch")
        current_run = _make_mock_run("current-regression-run", created_at=200.0, branch="main")

        prev_node = _make_mock_node(
            node_id="analyze",
            run_id="baseline-regression-run",
            eval_passed=True,
            eval_score=0.95,
            cost_usd=0.005,
            created_at=100.0,
        )
        curr_node = _make_mock_node(
            node_id="analyze",
            run_id="current-regression-run",
            eval_passed=False,
            eval_score=0.30,
            cost_usd=0.005,
            created_at=200.0,
        )

        repo.get_run.return_value = current_run
        repo.list_runs.return_value = [current_run, previous_run]
        repo.list_nodes_for_run.side_effect = lambda run_id: (
            [curr_node] if run_id == "current-regression-run" else [prev_node]
        )

        service = EvalService(repo)
        result = service.get_run_regressions("current-regression-run")

        assert result is not None
        assert result["count"] == 0
        assert result["issues"] == []

    def test_no_regression_when_both_runs_fail(self):
        """A node that failed on both runs is NOT a regression (was already broken)."""
        repo = Mock()

        current_run = _make_mock_run("current-regression-run", created_at=200.0)
        previous_run = _make_mock_run("baseline-regression-run", created_at=100.0)

        prev_node = _make_mock_node(
            node_id="analyze",
            run_id="baseline-regression-run",
            eval_passed=False,
            eval_score=0.30,
            created_at=100.0,
        )
        curr_node = _make_mock_node(
            node_id="analyze",
            run_id="current-regression-run",
            eval_passed=False,
            eval_score=0.25,
            created_at=200.0,
        )

        repo.get_run.return_value = current_run
        repo.list_runs.return_value = [current_run, previous_run]
        repo.list_nodes_for_run.side_effect = lambda run_id: (
            [curr_node] if run_id == "current-regression-run" else [prev_node]
        )

        service = EvalService(repo)
        result = service.get_run_regressions("current-regression-run")

        assert result is not None
        assertion_issues = [i for i in result["issues"] if i["type"] == "assertion_regression"]
        assert len(assertion_issues) == 0

    def test_cost_spike_detected_when_cost_increases_over_20_pct(self):
        """A cost increase >20% vs previous production run is a cost_spike regression."""
        repo = Mock()

        current_run = _make_mock_run("current-regression-run", created_at=200.0)
        previous_run = _make_mock_run("baseline-regression-run", created_at=100.0)

        prev_node = _make_mock_node(
            node_id="analyze",
            run_id="baseline-regression-run",
            cost_usd=0.005,
            eval_passed=True,
            created_at=100.0,
        )
        curr_node = _make_mock_node(
            node_id="analyze",
            run_id="current-regression-run",
            cost_usd=0.010,  # 100% increase
            eval_passed=True,
            created_at=200.0,
        )

        repo.get_run.return_value = current_run
        repo.list_runs.return_value = [current_run, previous_run]
        repo.list_nodes_for_run.side_effect = lambda run_id: (
            [curr_node] if run_id == "current-regression-run" else [prev_node]
        )

        service = EvalService(repo)
        result = service.get_run_regressions("current-regression-run")

        assert result is not None
        cost_issues = [i for i in result["issues"] if i["type"] == "cost_spike"]
        assert len(cost_issues) >= 1

    def test_quality_drop_detected_when_score_drops_over_0_1(self):
        """An eval_score drop >0.1 vs previous production run is a quality_drop."""
        repo = Mock()

        current_run = _make_mock_run("current-regression-run", created_at=200.0)
        previous_run = _make_mock_run("baseline-regression-run", created_at=100.0)

        prev_node = _make_mock_node(
            node_id="analyze",
            run_id="baseline-regression-run",
            eval_score=0.95,
            eval_passed=True,
            created_at=100.0,
        )
        curr_node = _make_mock_node(
            node_id="analyze",
            run_id="current-regression-run",
            eval_score=0.70,  # dropped 0.25
            eval_passed=True,
            created_at=200.0,
        )

        repo.get_run.return_value = current_run
        repo.list_runs.return_value = [current_run, previous_run]
        repo.list_nodes_for_run.side_effect = lambda run_id: (
            [curr_node] if run_id == "current-regression-run" else [prev_node]
        )

        service = EvalService(repo)
        result = service.get_run_regressions("current-regression-run")

        assert result is not None
        quality_issues = [i for i in result["issues"] if i["type"] == "quality_drop"]
        assert len(quality_issues) >= 1

    def test_returns_none_for_nonexistent_run(self):
        """Returns None when run does not exist."""
        repo = Mock()
        repo.get_run.return_value = None

        service = EvalService(repo)
        result = service.get_run_regressions("nonexistent")

        assert result is None


# ===========================================================================
# get_workflow_regressions
# ===========================================================================


class TestGetWorkflowRegressions:
    """EvalService.get_workflow_regressions() must exist and use comparison logic."""

    def test_method_exists_on_eval_service(self):
        """EvalService must expose get_workflow_regressions()."""
        repo = Mock()
        service = EvalService(repo)
        assert hasattr(service, "get_workflow_regressions")
        assert callable(service.get_workflow_regressions)

    def test_returns_issues_with_run_id_and_run_number(self):
        """Workflow regression issues must include run_id and run_number."""
        repo = Mock()

        baseline_run = _make_mock_run(
            "baseline-regression-run", workflow_id="regression-workflow", created_at=100.0
        )
        current_run = _make_mock_run(
            "current-regression-run", workflow_id="regression-workflow", created_at=200.0
        )
        baseline_run.run_number = 1
        current_run.run_number = 2

        prev_node = _make_mock_node(
            node_id="analyze",
            run_id="baseline-regression-run",
            eval_passed=True,
            created_at=100.0,
        )
        curr_node = _make_mock_node(
            node_id="analyze",
            run_id="current-regression-run",
            eval_passed=False,
            created_at=200.0,
        )

        repo.list_runs.return_value = [current_run, baseline_run]
        repo.list_nodes_for_run.side_effect = lambda run_id: (
            [curr_node] if run_id == "current-regression-run" else [prev_node]
        )

        service = EvalService(repo)
        result = service.get_workflow_regressions("regression-workflow")

        assert result is not None
        assert result["count"] >= 1
        issue = result["issues"][0]
        assert "run_id" in issue
        assert "run_number" in issue


# ===========================================================================
# Edge: No eval assertions => 0 regressions
# ===========================================================================


class TestNoEvalAssertionsEdge:
    """Runs/workflows with no eval assertions configured yield zero regressions."""

    def test_run_with_no_eval_assertions_returns_zero(self):
        """A run with no eval assertions should have 0 regressions."""
        repo = Mock()

        run = _make_mock_run("no-eval-run", created_at=200.0)
        node = _make_mock_node(
            node_id="route",
            run_id="no-eval-run",
            soul_id=None,
            soul_version=None,
            eval_score=None,
            eval_passed=None,
            created_at=200.0,
        )

        repo.get_run.return_value = run
        repo.list_runs.return_value = [run]
        repo.list_nodes_for_run.return_value = [node]

        service = EvalService(repo)
        result = service.get_run_regressions("no-eval-run")

        assert result is not None
        assert result["count"] == 0
        assert result["issues"] == []


# ===========================================================================
# Edge: First run (no baseline) => 0 regressions
# ===========================================================================


class TestFirstRunEdge:
    """First run of a workflow has no baseline to regress against."""

    def test_first_run_returns_zero_regressions(self):
        """The very first run of a workflow must have 0 regressions."""
        repo = Mock()

        run = _make_mock_run("first-workflow-run", created_at=100.0)
        node = _make_mock_node(
            node_id="analyze",
            run_id="first-workflow-run",
            eval_passed=False,  # fails, but no baseline => not a regression
            eval_score=0.30,
            created_at=100.0,
        )

        repo.get_run.return_value = run
        repo.list_runs.return_value = [run]  # only run in the workflow
        repo.list_nodes_for_run.return_value = [node]

        service = EvalService(repo)
        result = service.get_run_regressions("first-workflow-run")

        assert result is not None
        assert result["count"] == 0
        assert result["issues"] == []


# ===========================================================================
# Edge: Soul deleted after execution => regression still computed
# ===========================================================================


class TestDeletedSoulEdge:
    """Regressions still computed from stored RunNode data even if soul is deleted."""

    def test_regression_computed_when_soul_deleted(self):
        """Regression should be detected from stored data even when soul YAML is gone."""
        repo = Mock()

        current_run = _make_mock_run("current-regression-run", created_at=200.0)
        previous_run = _make_mock_run("baseline-regression-run", created_at=100.0)

        # soul_id is stored on the RunNode from execution time
        prev_node = _make_mock_node(
            node_id="analyze",
            run_id="baseline-regression-run",
            soul_id="deleted-soul",
            soul_version="sha256:old",
            eval_passed=True,
            created_at=100.0,
        )
        curr_node = _make_mock_node(
            node_id="analyze",
            run_id="current-regression-run",
            soul_id="deleted-soul",
            soul_version="sha256:old",
            eval_passed=False,
            created_at=200.0,
        )

        repo.get_run.return_value = current_run
        repo.list_runs.return_value = [current_run, previous_run]
        repo.list_nodes_for_run.side_effect = lambda run_id: (
            [curr_node] if run_id == "current-regression-run" else [prev_node]
        )

        service = EvalService(repo)
        result = service.get_run_regressions("current-regression-run")

        assert result is not None
        assert result["count"] >= 1
        types = {i["type"] for i in result["issues"]}
        assert "assertion_regression" in types


# ===========================================================================
# get_workflow_health_metrics() regression_count uses comparison logic
# ===========================================================================


class TestHealthMetricsProperRegressionLogic:
    """get_workflow_health_metrics() must use comparison-based regression counting."""

    def test_regression_count_is_not_raw_eval_failed_count(self, db_session: Session):
        """Only same-node failures with a passing baseline count as regressions.

        Setup:
        - baseline run: assertion-node eval_passed=True
        - current run: assertion-node eval_passed=False
        - repeated failure run: assertion-node eval_passed=False
        """
        _seed_run(
            db_session,
            "baseline-regression-run",
            workflow_id="regression-workflow",
            branch="main",
        )
        _seed_node(
            db_session,
            "baseline-regression-run",
            "assertion-node",
            eval_passed=True,
            soul_version="sha256:v1",
        )

        _seed_run(
            db_session, "current-regression-run", workflow_id="regression-workflow", branch="main"
        )
        _seed_node(
            db_session,
            "current-regression-run",
            "assertion-node",
            eval_passed=False,
            soul_version="sha256:v1",
        )

        _seed_run(
            db_session, "repeated-failure-run", workflow_id="regression-workflow", branch="main"
        )
        _seed_node(
            db_session,
            "repeated-failure-run",
            "assertion-node",
            eval_passed=False,
            soul_version="sha256:v1",
        )

        db_session.commit()

        read_model = RunReadModel(db_session)
        result = read_model.get_workflow_health_metrics(["regression-workflow"])
        metric = result["regression-workflow"]

        assert metric["regression_count"] == 1

    def test_no_regression_when_first_run_fails(self, db_session: Session):
        """First run with eval_passed=False is NOT a regression (no baseline)."""
        _seed_run(db_session, "first-failing-run", workflow_id="first-run-workflow", branch="main")
        _seed_node(
            db_session,
            "first-failing-run",
            "assertion-node",
            eval_passed=False,
            soul_version="sha256:v1",
        )
        db_session.commit()

        read_model = RunReadModel(db_session)
        result = read_model.get_workflow_health_metrics(["first-run-workflow"])
        metric = result["first-run-workflow"]

        assert metric["regression_count"] == 0

    def test_regression_only_counted_for_same_soul_version(self, db_session: Session):
        """A fail after a pass is only a regression if soul_version matches."""
        _seed_run(
            db_session,
            "baseline-regression-run",
            workflow_id="versioned-soul-workflow",
            branch="main",
        )
        _seed_node(
            db_session,
            "baseline-regression-run",
            "assertion-node",
            eval_passed=True,
            soul_version="sha256:v1",
        )

        _seed_run(
            db_session,
            "current-regression-run",
            workflow_id="versioned-soul-workflow",
            branch="main",
        )
        _seed_node(
            db_session,
            "current-regression-run",
            "assertion-node",
            eval_passed=False,
            soul_version="sha256:v2",  # different version => not a regression
        )

        db_session.commit()

        read_model = RunReadModel(db_session)
        result = read_model.get_workflow_health_metrics(["versioned-soul-workflow"])
        metric = result["versioned-soul-workflow"]

        assert metric["regression_count"] == 0
