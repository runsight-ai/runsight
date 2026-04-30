"""Run read model query bounds.

These tests assert bounded query behavior:
  - list_runs() returns the requested rows without hidden caps
  - _count_regressions_for_workflow batch-loads RunNodes within a small query budget
  - get_workflow_health_metrics stays within a small query budget regardless of dataset size
"""

import time

import pytest
from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine

from runsight_api.domain.entities.run import Run, RunNode


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DEFAULT_LIST_RUNS_LIMIT = 100


def _import_run_repository():
    from runsight_api.data.repositories.run_repo import RunRepository

    return RunRepository


def _import_run_read_model():
    from runsight_api.data.repositories.run_read_model import RunReadModel

    return RunReadModel


def _make_engine():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine


def _count_queries(session: Session) -> list[str]:
    """Attach a before_cursor_execute listener and return the recorded statements list."""
    statements: list[str] = []

    def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    engine = session.get_bind()
    event.listen(engine, "before_cursor_execute", _before_cursor_execute)
    return statements


def _remove_query_listener(session: Session, statements: list[str]) -> None:
    """Detach the listener after the measured block so it doesn't leak."""
    engine = session.get_bind()

    def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    try:
        event.remove(engine, "before_cursor_execute", _before_cursor_execute)
    except Exception:
        pass  # Listener may already be detached; safe to ignore.


@pytest.fixture
def db_session():
    engine = _make_engine()
    with Session(engine) as session:
        yield session


def _seed_run(
    session: Session,
    run_id: str,
    *,
    workflow_id: str,
    source: str = "manual",
    total_cost_usd: float = 0.01,
    created_at_offset: float = 0.0,
) -> Run:
    run = Run(
        id=run_id,
        workflow_id=workflow_id,
        workflow_name=f"Workflow {workflow_id}",
        task_json="{}",
        branch="main",
        source=source,
        total_cost_usd=total_cost_usd,
        created_at=time.time() + created_at_offset,
    )
    session.add(run)
    return run


def _seed_node(
    session: Session,
    run_id: str,
    node_id: str,
    *,
    eval_passed: bool | None,
    soul_version: str | None = None,
) -> RunNode:
    node = RunNode(
        id=f"{run_id}:{node_id}",
        run_id=run_id,
        node_id=node_id,
        block_type="llm",
        status="completed",
        eval_passed=eval_passed,
        soul_version=soul_version,
    )
    session.add(node)
    return node


# ---------------------------------------------------------------------------
# Group 1: list_runs default LIMIT
# ---------------------------------------------------------------------------


class TestListRunsDefaultLimit:
    def test_list_runs_returns_all_rows_by_default(self, db_session: Session):
        """list_runs() with no limit argument returns all rows (no cap).

        Internal callers (eval_service, dashboard) need the full history.
        """
        RunRepository = _import_run_repository()

        over_limit = DEFAULT_LIST_RUNS_LIMIT + 20
        for i in range(over_limit):
            _seed_run(
                db_session,
                f"uncapped-history-run-{i:04d}",
                workflow_id="uncapped-history-workflow",
                created_at_offset=float(i),
            )
        db_session.commit()

        repo = RunRepository(db_session)
        result = repo.list_runs()

        assert len(result) == over_limit, (
            f"list_runs() returned {len(result)} rows but should return all "
            f"{over_limit} rows when no limit is specified."
        )

    def test_list_runs_respects_explicit_limit(self, db_session: Session):
        """list_runs(limit=N) caps results at N rows."""
        RunRepository = _import_run_repository()

        over_limit = DEFAULT_LIST_RUNS_LIMIT + 20
        for i in range(over_limit):
            _seed_run(
                db_session,
                f"capped-history-run-{i:04d}",
                workflow_id="capped-history-workflow",
                created_at_offset=float(i),
            )
        db_session.commit()

        repo = RunRepository(db_session)
        result = repo.list_runs(limit=DEFAULT_LIST_RUNS_LIMIT)

        assert len(result) == DEFAULT_LIST_RUNS_LIMIT, (
            f"list_runs(limit={DEFAULT_LIST_RUNS_LIMIT}) returned {len(result)} rows."
        )

    def test_list_runs_returns_all_when_fewer_than_limit(self, db_session: Session):
        """When fewer rows than the default limit exist, all rows are returned."""
        RunRepository = _import_run_repository()

        count = DEFAULT_LIST_RUNS_LIMIT - 10
        for i in range(count):
            _seed_run(
                db_session,
                f"short-history-run-{i:04d}",
                workflow_id="short-history-workflow",
                created_at_offset=float(i),
            )
        db_session.commit()

        repo = RunRepository(db_session)
        result = repo.list_runs()

        assert len(result) == count


# ---------------------------------------------------------------------------
# Group 2: Query count for _count_regressions_for_workflow
# ---------------------------------------------------------------------------


class TestCountRegressionsQueryCount:
    def test_count_regressions_batch_query_count(self, db_session: Session):
        """With 1 workflow + 5 runs, _count_regressions_for_workflow must issue
        at most 3 queries total (not 1 + N per run)."""
        RunReadModel = _import_run_read_model()

        workflow_id = "batched-regression-workflow"
        num_runs = 5
        for i in range(num_runs):
            run_id = f"alternating-eval-run-{i:04d}"
            _seed_run(db_session, run_id, workflow_id=workflow_id, created_at_offset=float(i))
            _seed_node(
                db_session,
                run_id,
                "quality-review-node",
                eval_passed=(i % 2 == 0),
                soul_version="v1",
            )
            _seed_node(
                db_session,
                run_id,
                "summary-node",
                eval_passed=True,
                soul_version="v1",
            )
        db_session.commit()

        read_model = RunReadModel(db_session)

        # Attach query counter AFTER seeding to measure only the method's queries.
        statements = _count_queries(db_session)
        start_count = len(statements)

        read_model._count_regressions_for_workflow(workflow_id)

        queries_issued = len(statements) - start_count

        assert queries_issued <= 3, (
            f"_count_regressions_for_workflow issued {queries_issued} queries for "
            f"{num_runs} runs. Expected ≤ 3 (batch). Current implementation is N+1."
        )

    def test_count_regressions_preserves_semantics(self, db_session: Session):
        """The batch optimisation must not change regression detection logic.

        Scenario: 3 runs, quality-review-node with soul_version='v1'.
          baseline-pass-run: eval_passed=True
          first-failing-run: eval_passed=False -> regression vs baseline-pass-run
          repeated-failing-run: eval_passed=False -> no regression because previous was also False
        Expected regression_count = 1
        """
        RunReadModel = _import_run_read_model()

        workflow_id = "regression-semantics-workflow"

        _seed_run(db_session, "baseline-pass-run", workflow_id=workflow_id, created_at_offset=0.0)
        _seed_node(
            db_session,
            "baseline-pass-run",
            "quality-review-node",
            eval_passed=True,
            soul_version="v1",
        )

        _seed_run(db_session, "first-failing-run", workflow_id=workflow_id, created_at_offset=1.0)
        _seed_node(
            db_session,
            "first-failing-run",
            "quality-review-node",
            eval_passed=False,
            soul_version="v1",
        )

        _seed_run(
            db_session,
            "repeated-failing-run",
            workflow_id=workflow_id,
            created_at_offset=2.0,
        )
        _seed_node(
            db_session,
            "repeated-failing-run",
            "quality-review-node",
            eval_passed=False,
            soul_version="v1",
        )

        db_session.commit()

        read_model = RunReadModel(db_session)
        count = read_model._count_regressions_for_workflow(workflow_id)

        assert count == 1, (
            f"Expected 1 regression but got {count}. "
            "Batch optimisation must preserve exact regression semantics."
        )

    def test_count_regressions_soul_version_boundary(self, db_session: Session):
        """A soul_version change resets the baseline — no regression should fire."""
        RunReadModel = _import_run_read_model()

        workflow_id = "soul-version-boundary-workflow"

        _seed_run(
            db_session,
            "baseline-soul-version-run",
            workflow_id=workflow_id,
            created_at_offset=0.0,
        )
        _seed_node(
            db_session,
            "baseline-soul-version-run",
            "quality-review-node",
            eval_passed=True,
            soul_version="v1",
        )

        _seed_run(
            db_session,
            "changed-soul-version-run",
            workflow_id=workflow_id,
            created_at_offset=1.0,
        )
        _seed_node(
            db_session,
            "changed-soul-version-run",
            "quality-review-node",
            eval_passed=False,
            soul_version="v2",
        )

        db_session.commit()

        read_model = RunReadModel(db_session)
        count = read_model._count_regressions_for_workflow(workflow_id)

        assert count == 0, f"Expected 0 regressions (soul_version changed) but got {count}."


# ---------------------------------------------------------------------------
# Group 3: Query count for get_workflow_health_metrics
# ---------------------------------------------------------------------------


class TestHealthMetricsQueryCount:
    def test_health_metrics_batch_query_count(self, db_session: Session):
        """With 5 workflows × 10 runs × 2 nodes, get_workflow_health_metrics must
        issue ≤ 5 queries total (not 50+ from the per-workflow N+1 loop)."""
        RunReadModel = _import_run_read_model()

        workflow_ids = [
            "health-alpha-workflow",
            "health-beta-workflow",
            "health-gamma-workflow",
            "health-delta-workflow",
            "health-epsilon-workflow",
        ]
        for workflow_idx, workflow_id in enumerate(workflow_ids):
            for run_idx in range(10):
                run_id = f"health-workflow-{workflow_idx}-history-run-{run_idx:04d}"
                _seed_run(
                    db_session,
                    run_id,
                    workflow_id=workflow_id,
                    created_at_offset=float(run_idx),
                )
                _seed_node(
                    db_session,
                    run_id,
                    "health-review-node",
                    eval_passed=(run_idx % 3 != 0),
                    soul_version="v1",
                )
                _seed_node(
                    db_session,
                    run_id,
                    "health-summary-node",
                    eval_passed=True,
                    soul_version="v1",
                )
        db_session.commit()

        read_model = RunReadModel(db_session)

        statements = _count_queries(db_session)
        start_count = len(statements)

        read_model.get_workflow_health_metrics(workflow_ids)

        queries_issued = len(statements) - start_count

        assert queries_issued <= 5, (
            f"get_workflow_health_metrics issued {queries_issued} queries for "
            f"5 workflows. Expected ≤ 5 (batched). Current implementation calls "
            f"_count_regressions_for_workflow per workflow, causing N+1."
        )

    def test_health_metrics_preserves_regression_count(self, db_session: Session):
        """Regression counts per workflow must be correct after the batch rewrite.

        workflow-with-one-regression: 1 regression
        workflow-without-regression: 0 regressions
        workflow-with-two-regressions: 2 regressions
        """
        RunReadModel = _import_run_read_model()

        _seed_run(
            db_session,
            "one-regression-baseline-run",
            workflow_id="workflow-with-one-regression",
            created_at_offset=0.0,
        )
        _seed_node(
            db_session,
            "one-regression-baseline-run",
            "quality-review-node",
            eval_passed=True,
            soul_version="v1",
        )

        _seed_run(
            db_session,
            "one-regression-failing-run",
            workflow_id="workflow-with-one-regression",
            created_at_offset=1.0,
        )
        _seed_node(
            db_session,
            "one-regression-failing-run",
            "quality-review-node",
            eval_passed=False,
            soul_version="v1",
        )

        _seed_run(
            db_session,
            "clean-history-baseline-run",
            workflow_id="workflow-without-regression",
            created_at_offset=0.0,
        )
        _seed_node(
            db_session,
            "clean-history-baseline-run",
            "quality-review-node",
            eval_passed=True,
            soul_version="v1",
        )

        _seed_run(
            db_session,
            "clean-history-followup-run",
            workflow_id="workflow-without-regression",
            created_at_offset=1.0,
        )
        _seed_node(
            db_session,
            "clean-history-followup-run",
            "quality-review-node",
            eval_passed=True,
            soul_version="v1",
        )

        _seed_run(
            db_session,
            "two-regressions-baseline-run",
            workflow_id="workflow-with-two-regressions",
            created_at_offset=0.0,
        )
        _seed_node(
            db_session,
            "two-regressions-baseline-run",
            "quality-review-node",
            eval_passed=True,
            soul_version="v1",
        )
        _seed_node(
            db_session,
            "two-regressions-baseline-run",
            "summary-node",
            eval_passed=True,
            soul_version="v1",
        )

        _seed_run(
            db_session,
            "two-regressions-failing-run",
            workflow_id="workflow-with-two-regressions",
            created_at_offset=1.0,
        )
        _seed_node(
            db_session,
            "two-regressions-failing-run",
            "quality-review-node",
            eval_passed=False,
            soul_version="v1",
        )
        _seed_node(
            db_session,
            "two-regressions-failing-run",
            "summary-node",
            eval_passed=False,
            soul_version="v1",
        )

        db_session.commit()

        read_model = RunReadModel(db_session)
        result = read_model.get_workflow_health_metrics(
            [
                "workflow-with-one-regression",
                "workflow-without-regression",
                "workflow-with-two-regressions",
            ]
        )

        assert result["workflow-with-one-regression"]["regression_count"] == 1, (
            "workflow-with-one-regression: expected 1 regression, got "
            f"{result['workflow-with-one-regression']['regression_count']}"
        )
        assert result["workflow-without-regression"]["regression_count"] == 0, (
            "workflow-without-regression: expected 0 regressions, got "
            f"{result['workflow-without-regression']['regression_count']}"
        )
        assert result["workflow-with-two-regressions"]["regression_count"] == 2, (
            "workflow-with-two-regressions: expected 2 regressions, got "
            f"{result['workflow-with-two-regressions']['regression_count']}"
        )
