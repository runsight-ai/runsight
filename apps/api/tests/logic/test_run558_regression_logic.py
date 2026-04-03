"""Red-team tests for RUN-558: Regression detection logic.

Tests cover:
- AC5: Regression detection uses same logic as EvalService.get_attention_items()
        (comparison-based, not just eval_passed=False)
- AC6: get_workflow_health_metrics() regression_count uses proper regression
        logic (passed before -> failed now), not raw eval_passed=False count
- Edge: Run with no eval assertions => 0 regressions
- Edge: First run of a workflow (no baseline) => 0 regressions
- Edge: Run where soul was deleted after execution => regression still computed
"""

from unittest.mock import Mock

import pytest
from sqlmodel import Session, SQLModel, create_engine

from runsight_api.domain.entities.run import Run, RunNode
from runsight_api.logic.services.eval_service import EvalService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_run(
    run_id: str,
    *,
    workflow_id: str = "wf_1",
    workflow_name: str = "Research Flow",
    source: str = "manual",
    branch: str = "main",
    created_at: float = 100.0,
):
    run = Mock()
    run.id = run_id
    run.workflow_id = workflow_id
    run.workflow_name = workflow_name
    run.source = source
    run.branch = branch
    run.created_at = created_at
    return run


def _make_mock_node(
    *,
    node_id: str = "analyze",
    run_id: str = "run_001",
    soul_id: str | None = "researcher_v1",
    soul_version: str | None = "sha256:abc",
    eval_score: float | None = 0.95,
    eval_passed: bool | None = True,
    cost_usd: float = 0.005,
    tokens: dict | None = None,
    created_at: float = 100.0,
):
    m = Mock()
    m.node_id = node_id
    m.run_id = run_id
    m.soul_id = soul_id
    m.soul_version = soul_version
    m.eval_score = eval_score
    m.eval_passed = eval_passed
    m.cost_usd = cost_usd
    m.tokens = tokens or {"prompt": 100, "completion": 50, "total": 150}
    m.created_at = created_at
    return m


# ===========================================================================
# AC5: get_run_regressions uses comparison-based detection
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

        current_run = _make_mock_run("run_002", created_at=200.0)
        previous_run = _make_mock_run("run_001", created_at=100.0)

        # Previous node: eval_passed=True
        prev_node = _make_mock_node(
            node_id="analyze",
            run_id="run_001",
            eval_passed=True,
            eval_score=0.95,
            cost_usd=0.005,
            created_at=100.0,
        )
        # Current node: eval_passed=False (same soul_version)
        curr_node = _make_mock_node(
            node_id="analyze",
            run_id="run_002",
            eval_passed=False,
            eval_score=0.30,
            cost_usd=0.005,
            created_at=200.0,
        )

        repo.get_run.return_value = current_run
        repo.list_runs.return_value = [current_run, previous_run]
        repo.list_nodes_for_run.side_effect = lambda run_id: (
            [curr_node] if run_id == "run_002" else [prev_node]
        )

        service = EvalService(repo)
        result = service.get_run_regressions("run_002")

        assert result is not None
        assert result["count"] >= 1
        types = {i["type"] for i in result["issues"]}
        assert "assertion_regression" in types

    def test_no_regression_when_both_runs_fail(self):
        """A node that failed on both runs is NOT a regression (was already broken)."""
        repo = Mock()

        current_run = _make_mock_run("run_002", created_at=200.0)
        previous_run = _make_mock_run("run_001", created_at=100.0)

        prev_node = _make_mock_node(
            node_id="analyze",
            run_id="run_001",
            eval_passed=False,
            eval_score=0.30,
            created_at=100.0,
        )
        curr_node = _make_mock_node(
            node_id="analyze",
            run_id="run_002",
            eval_passed=False,
            eval_score=0.25,
            created_at=200.0,
        )

        repo.get_run.return_value = current_run
        repo.list_runs.return_value = [current_run, previous_run]
        repo.list_nodes_for_run.side_effect = lambda run_id: (
            [curr_node] if run_id == "run_002" else [prev_node]
        )

        service = EvalService(repo)
        result = service.get_run_regressions("run_002")

        assert result is not None
        assertion_issues = [i for i in result["issues"] if i["type"] == "assertion_regression"]
        assert len(assertion_issues) == 0

    def test_cost_spike_detected_when_cost_increases_over_20_pct(self):
        """A cost increase >20% vs previous production run is a cost_spike regression."""
        repo = Mock()

        current_run = _make_mock_run("run_002", created_at=200.0)
        previous_run = _make_mock_run("run_001", created_at=100.0)

        prev_node = _make_mock_node(
            node_id="analyze",
            run_id="run_001",
            cost_usd=0.005,
            eval_passed=True,
            created_at=100.0,
        )
        curr_node = _make_mock_node(
            node_id="analyze",
            run_id="run_002",
            cost_usd=0.010,  # 100% increase
            eval_passed=True,
            created_at=200.0,
        )

        repo.get_run.return_value = current_run
        repo.list_runs.return_value = [current_run, previous_run]
        repo.list_nodes_for_run.side_effect = lambda run_id: (
            [curr_node] if run_id == "run_002" else [prev_node]
        )

        service = EvalService(repo)
        result = service.get_run_regressions("run_002")

        assert result is not None
        cost_issues = [i for i in result["issues"] if i["type"] == "cost_spike"]
        assert len(cost_issues) >= 1

    def test_quality_drop_detected_when_score_drops_over_0_1(self):
        """An eval_score drop >0.1 vs previous production run is a quality_drop."""
        repo = Mock()

        current_run = _make_mock_run("run_002", created_at=200.0)
        previous_run = _make_mock_run("run_001", created_at=100.0)

        prev_node = _make_mock_node(
            node_id="analyze",
            run_id="run_001",
            eval_score=0.95,
            eval_passed=True,
            created_at=100.0,
        )
        curr_node = _make_mock_node(
            node_id="analyze",
            run_id="run_002",
            eval_score=0.70,  # dropped 0.25
            eval_passed=True,
            created_at=200.0,
        )

        repo.get_run.return_value = current_run
        repo.list_runs.return_value = [current_run, previous_run]
        repo.list_nodes_for_run.side_effect = lambda run_id: (
            [curr_node] if run_id == "run_002" else [prev_node]
        )

        service = EvalService(repo)
        result = service.get_run_regressions("run_002")

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
# AC5 continued: get_workflow_regressions
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

        run_1 = _make_mock_run("run_001", workflow_id="wf_1", created_at=100.0)
        run_2 = _make_mock_run("run_002", workflow_id="wf_1", created_at=200.0)
        run_1.run_number = 1
        run_2.run_number = 2

        prev_node = _make_mock_node(
            node_id="analyze",
            run_id="run_001",
            eval_passed=True,
            created_at=100.0,
        )
        curr_node = _make_mock_node(
            node_id="analyze",
            run_id="run_002",
            eval_passed=False,
            created_at=200.0,
        )

        repo.list_runs.return_value = [run_2, run_1]
        repo.list_nodes_for_run.side_effect = lambda run_id: (
            [curr_node] if run_id == "run_002" else [prev_node]
        )

        service = EvalService(repo)
        result = service.get_workflow_regressions("wf_1")

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

        run = _make_mock_run("run_no_eval", created_at=200.0)
        node = _make_mock_node(
            node_id="route",
            run_id="run_no_eval",
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
        result = service.get_run_regressions("run_no_eval")

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

        run = _make_mock_run("run_first", created_at=100.0)
        node = _make_mock_node(
            node_id="analyze",
            run_id="run_first",
            eval_passed=False,  # fails, but no baseline => not a regression
            eval_score=0.30,
            created_at=100.0,
        )

        repo.get_run.return_value = run
        repo.list_runs.return_value = [run]  # only run in the workflow
        repo.list_nodes_for_run.return_value = [node]

        service = EvalService(repo)
        result = service.get_run_regressions("run_first")

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

        current_run = _make_mock_run("run_002", created_at=200.0)
        previous_run = _make_mock_run("run_001", created_at=100.0)

        # soul_id is stored on the RunNode from execution time
        prev_node = _make_mock_node(
            node_id="analyze",
            run_id="run_001",
            soul_id="deleted_soul",
            soul_version="sha256:old",
            eval_passed=True,
            created_at=100.0,
        )
        curr_node = _make_mock_node(
            node_id="analyze",
            run_id="run_002",
            soul_id="deleted_soul",
            soul_version="sha256:old",
            eval_passed=False,
            created_at=200.0,
        )

        repo.get_run.return_value = current_run
        repo.list_runs.return_value = [current_run, previous_run]
        repo.list_nodes_for_run.side_effect = lambda run_id: (
            [curr_node] if run_id == "run_002" else [prev_node]
        )

        service = EvalService(repo)
        result = service.get_run_regressions("run_002")

        assert result is not None
        assert result["count"] >= 1
        types = {i["type"] for i in result["issues"]}
        assert "assertion_regression" in types


# ===========================================================================
# AC6: get_workflow_health_metrics() regression_count uses proper logic
# ===========================================================================


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _seed_run(
    session: Session,
    run_id: str,
    *,
    workflow_id: str,
    source: str = "manual",
    total_cost_usd: float = 0.0,
) -> None:
    run = Run(
        id=run_id,
        workflow_id=workflow_id,
        workflow_name=f"Workflow {workflow_id}",
        task_json="{}",
        source=source,
        total_cost_usd=total_cost_usd,
    )
    session.add(run)


def _seed_node(
    session: Session,
    run_id: str,
    node_id: str,
    *,
    eval_passed: bool | None,
    soul_version: str | None = None,
    eval_score: float | None = None,
    cost_usd: float = 0.0,
) -> None:
    node = RunNode(
        id=f"{run_id}:{node_id}",
        run_id=run_id,
        node_id=node_id,
        block_type="llm",
        status="completed",
        eval_passed=eval_passed,
        soul_version=soul_version,
        eval_score=eval_score,
        cost_usd=cost_usd,
    )
    session.add(node)


class TestHealthMetricsProperRegressionLogic:
    """get_workflow_health_metrics() must use comparison-based regression counting."""

    def test_regression_count_is_not_raw_eval_failed_count(self, db_session: Session):
        """The bug: current impl counts all eval_passed=False as regressions.

        Correct: only count cases where the same node (same soul_version)
        passed on a previous run and failed on the current one.

        Setup:
        - run_001: node_a eval_passed=True (baseline)
        - run_002: node_a eval_passed=False (regression: was True before)
        - run_003: node_a eval_passed=False (NOT a regression: was already False)

        Current buggy behavior: regression_count = 2 (both False nodes)
        Correct behavior: regression_count = 1 (only run_002 is a regression)
        """
        from runsight_api.data.repositories.run_repo import RunRepository

        _seed_run(db_session, "run_001", workflow_id="wf_1")
        _seed_node(
            db_session,
            "run_001",
            "node_a",
            eval_passed=True,
            soul_version="sha256:v1",
        )

        _seed_run(db_session, "run_002", workflow_id="wf_1")
        _seed_node(
            db_session,
            "run_002",
            "node_a",
            eval_passed=False,
            soul_version="sha256:v1",
        )

        _seed_run(db_session, "run_003", workflow_id="wf_1")
        _seed_node(
            db_session,
            "run_003",
            "node_a",
            eval_passed=False,
            soul_version="sha256:v1",
        )

        db_session.commit()

        repo = RunRepository(db_session)
        result = repo.get_workflow_health_metrics(["wf_1"])
        metric = result["wf_1"]

        # The fix: regression_count should be 1, not 2
        assert metric["regression_count"] == 1

    def test_no_regression_when_first_run_fails(self, db_session: Session):
        """First run with eval_passed=False is NOT a regression (no baseline)."""
        from runsight_api.data.repositories.run_repo import RunRepository

        _seed_run(db_session, "run_001", workflow_id="wf_first")
        _seed_node(
            db_session,
            "run_001",
            "node_a",
            eval_passed=False,
            soul_version="sha256:v1",
        )
        db_session.commit()

        repo = RunRepository(db_session)
        result = repo.get_workflow_health_metrics(["wf_first"])
        metric = result["wf_first"]

        assert metric["regression_count"] == 0

    def test_regression_only_counted_for_same_soul_version(self, db_session: Session):
        """A fail after a pass is only a regression if soul_version matches."""
        from runsight_api.data.repositories.run_repo import RunRepository

        _seed_run(db_session, "run_001", workflow_id="wf_ver")
        _seed_node(
            db_session,
            "run_001",
            "node_a",
            eval_passed=True,
            soul_version="sha256:v1",
        )

        _seed_run(db_session, "run_002", workflow_id="wf_ver")
        _seed_node(
            db_session,
            "run_002",
            "node_a",
            eval_passed=False,
            soul_version="sha256:v2",  # different version => not a regression
        )

        db_session.commit()

        repo = RunRepository(db_session)
        result = repo.get_workflow_health_metrics(["wf_ver"])
        metric = result["wf_ver"]

        assert metric["regression_count"] == 0
