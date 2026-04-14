"""Red tests for RUN-849: N+1 query fixes in run_repo.py and unbounded list_runs.

These tests assert the optimised behaviour that does NOT exist yet:
  - list_runs() must apply a sensible default LIMIT
  - _count_regressions_for_workflow must batch-load RunNodes (≤ 3 queries total)
  - get_workflow_health_metrics must stay within 2-5 queries regardless of dataset size
"""

import time

import pytest
from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine

from runsight_api.domain.entities.run import Run, RunNode


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DEFAULT_LIST_RUNS_LIMIT = 100  # expected safety-net value post-fix


def _import_run_repository():
    from runsight_api.data.repositories.run_repo import RunRepository

    return RunRepository


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
    def test_list_runs_returns_max_default_limit(self, db_session: Session):
        """Seeding more than DEFAULT_LIST_RUNS_LIMIT rows must still return only
        DEFAULT_LIST_RUNS_LIMIT rows — the safety-net LIMIT is applied."""
        RunRepository = _import_run_repository()

        over_limit = DEFAULT_LIST_RUNS_LIMIT + 20
        for i in range(over_limit):
            _seed_run(
                db_session,
                f"run_{i:04d}",
                workflow_id="wf_limit",
                created_at_offset=float(i),
            )
        db_session.commit()

        repo = RunRepository(db_session)
        result = repo.list_runs()

        assert len(result) <= DEFAULT_LIST_RUNS_LIMIT, (
            f"list_runs() returned {len(result)} rows but should be capped at "
            f"{DEFAULT_LIST_RUNS_LIMIT}. No LIMIT is applied yet (N+1 issue)."
        )

    def test_list_runs_returns_all_when_fewer_than_limit(self, db_session: Session):
        """When fewer rows than the default limit exist, all rows are returned."""
        RunRepository = _import_run_repository()

        count = DEFAULT_LIST_RUNS_LIMIT - 10
        for i in range(count):
            _seed_run(
                db_session,
                f"run_few_{i:04d}",
                workflow_id="wf_few",
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
        RunRepository = _import_run_repository()

        wf_id = "wf_batch_regression"
        num_runs = 5
        for i in range(num_runs):
            run_id = f"run_reg_{i}"
            _seed_run(db_session, run_id, workflow_id=wf_id, created_at_offset=float(i))
            _seed_node(
                db_session,
                run_id,
                "node_a",
                eval_passed=(i % 2 == 0),
                soul_version="v1",
            )
            _seed_node(
                db_session,
                run_id,
                "node_b",
                eval_passed=True,
                soul_version="v1",
            )
        db_session.commit()

        repo = RunRepository(db_session)

        # Attach query counter AFTER seeding to measure only the method's queries.
        statements = _count_queries(db_session)
        start_count = len(statements)

        repo._count_regressions_for_workflow(wf_id)

        queries_issued = len(statements) - start_count

        assert queries_issued <= 3, (
            f"_count_regressions_for_workflow issued {queries_issued} queries for "
            f"{num_runs} runs. Expected ≤ 3 (batch). Current implementation is N+1."
        )

    def test_count_regressions_preserves_semantics(self, db_session: Session):
        """The batch optimisation must not change regression detection logic.

        Scenario: 3 runs, node_a with soul_version='v1'.
          run_0: eval_passed=True
          run_1: eval_passed=False  → regression vs run_0
          run_2: eval_passed=False  → NO regression (prev was also False)
        Expected regression_count = 1
        """
        RunRepository = _import_run_repository()

        wf_id = "wf_semantics"

        # run_0: pass
        _seed_run(db_session, "r0", workflow_id=wf_id, created_at_offset=0.0)
        _seed_node(db_session, "r0", "node_a", eval_passed=True, soul_version="v1")

        # run_1: fail  → regression
        _seed_run(db_session, "r1", workflow_id=wf_id, created_at_offset=1.0)
        _seed_node(db_session, "r1", "node_a", eval_passed=False, soul_version="v1")

        # run_2: fail  → NOT a regression (prev was already False)
        _seed_run(db_session, "r2", workflow_id=wf_id, created_at_offset=2.0)
        _seed_node(db_session, "r2", "node_a", eval_passed=False, soul_version="v1")

        db_session.commit()

        repo = RunRepository(db_session)
        count = repo._count_regressions_for_workflow(wf_id)

        assert count == 1, (
            f"Expected 1 regression but got {count}. "
            "Batch optimisation must preserve exact regression semantics."
        )

    def test_count_regressions_soul_version_boundary(self, db_session: Session):
        """A soul_version change resets the baseline — no regression should fire."""
        RunRepository = _import_run_repository()

        wf_id = "wf_soul_version_boundary"

        # run_0: node_a v1 pass
        _seed_run(db_session, "sv_r0", workflow_id=wf_id, created_at_offset=0.0)
        _seed_node(db_session, "sv_r0", "node_a", eval_passed=True, soul_version="v1")

        # run_1: node_a v2 fail — soul_version changed so NOT a regression
        _seed_run(db_session, "sv_r1", workflow_id=wf_id, created_at_offset=1.0)
        _seed_node(db_session, "sv_r1", "node_a", eval_passed=False, soul_version="v2")

        db_session.commit()

        repo = RunRepository(db_session)
        count = repo._count_regressions_for_workflow(wf_id)

        assert count == 0, f"Expected 0 regressions (soul_version changed) but got {count}."


# ---------------------------------------------------------------------------
# Group 3: Query count for get_workflow_health_metrics
# ---------------------------------------------------------------------------


class TestHealthMetricsQueryCount:
    def test_health_metrics_batch_query_count(self, db_session: Session):
        """With 5 workflows × 10 runs × 2 nodes, get_workflow_health_metrics must
        issue ≤ 5 queries total (not 50+ from the per-workflow N+1 loop)."""
        RunRepository = _import_run_repository()

        workflow_ids = [f"wf_hm_{i}" for i in range(5)]
        for wf_idx, wf_id in enumerate(workflow_ids):
            for run_idx in range(10):
                run_id = f"run_{wf_idx}_{run_idx}"
                _seed_run(
                    db_session,
                    run_id,
                    workflow_id=wf_id,
                    created_at_offset=float(run_idx),
                )
                _seed_node(
                    db_session,
                    run_id,
                    "node_x",
                    eval_passed=(run_idx % 3 != 0),
                    soul_version="v1",
                )
                _seed_node(
                    db_session,
                    run_id,
                    "node_y",
                    eval_passed=True,
                    soul_version="v1",
                )
        db_session.commit()

        repo = RunRepository(db_session)

        statements = _count_queries(db_session)
        start_count = len(statements)

        repo.get_workflow_health_metrics(workflow_ids)

        queries_issued = len(statements) - start_count

        assert queries_issued <= 5, (
            f"get_workflow_health_metrics issued {queries_issued} queries for "
            f"5 workflows. Expected ≤ 5 (batched). Current implementation calls "
            f"_count_regressions_for_workflow per workflow, causing N+1."
        )

    def test_health_metrics_preserves_regression_count(self, db_session: Session):
        """Regression counts per workflow must be correct after the batch rewrite.

        wf_a: 1 regression (node passes then fails, same soul_version)
        wf_b: 0 regressions (all pass)
        wf_c: 2 regressions (two independent nodes each regress once)
        """
        RunRepository = _import_run_repository()

        # ── wf_a: 1 regression ──────────────────────────────────────────────
        _seed_run(db_session, "a_r0", workflow_id="wf_a", created_at_offset=0.0)
        _seed_node(db_session, "a_r0", "node_1", eval_passed=True, soul_version="v1")

        _seed_run(db_session, "a_r1", workflow_id="wf_a", created_at_offset=1.0)
        _seed_node(db_session, "a_r1", "node_1", eval_passed=False, soul_version="v1")

        # ── wf_b: 0 regressions ─────────────────────────────────────────────
        _seed_run(db_session, "b_r0", workflow_id="wf_b", created_at_offset=0.0)
        _seed_node(db_session, "b_r0", "node_1", eval_passed=True, soul_version="v1")

        _seed_run(db_session, "b_r1", workflow_id="wf_b", created_at_offset=1.0)
        _seed_node(db_session, "b_r1", "node_1", eval_passed=True, soul_version="v1")

        # ── wf_c: 2 regressions (node_1 and node_2 each regress once) ───────
        _seed_run(db_session, "c_r0", workflow_id="wf_c", created_at_offset=0.0)
        _seed_node(db_session, "c_r0", "node_1", eval_passed=True, soul_version="v1")
        _seed_node(db_session, "c_r0", "node_2", eval_passed=True, soul_version="v1")

        _seed_run(db_session, "c_r1", workflow_id="wf_c", created_at_offset=1.0)
        _seed_node(db_session, "c_r1", "node_1", eval_passed=False, soul_version="v1")
        _seed_node(db_session, "c_r1", "node_2", eval_passed=False, soul_version="v1")

        db_session.commit()

        repo = RunRepository(db_session)
        result = repo.get_workflow_health_metrics(["wf_a", "wf_b", "wf_c"])

        assert result["wf_a"]["regression_count"] == 1, (
            f"wf_a: expected 1 regression, got {result['wf_a']['regression_count']}"
        )
        assert result["wf_b"]["regression_count"] == 0, (
            f"wf_b: expected 0 regressions, got {result['wf_b']['regression_count']}"
        )
        assert result["wf_c"]["regression_count"] == 2, (
            f"wf_c: expected 2 regressions, got {result['wf_c']['regression_count']}"
        )
