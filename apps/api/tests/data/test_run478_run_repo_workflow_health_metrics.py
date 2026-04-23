"""Red tests for RUN-478 workflow health aggregation."""

import pytest
from sqlmodel import Session, SQLModel, create_engine

from runsight_api.domain.entities.run import Run, RunNode


def _import_run_read_model():
    from runsight_api.data.repositories.run_read_model import RunReadModel

    return RunReadModel


def _metric_value(metric, name: str):
    if isinstance(metric, dict):
        return metric.get(name)
    return getattr(metric, name, None)


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
    source: str,
    total_cost_usd: float,
    created_at: float = 100.0,
    deleted_at: float | None = None,
) -> None:
    run = Run(
        id=run_id,
        workflow_id=workflow_id,
        workflow_name=f"Workflow {workflow_id}",
        task_json="{}",
        branch="main",
        source=source,
        total_cost_usd=total_cost_usd,
        created_at=created_at,
        updated_at=created_at,
        deleted_at=deleted_at,
    )
    session.add(run)


def _seed_node(
    session: Session,
    run_id: str,
    node_id: str,
    *,
    eval_passed: bool | None,
    soul_version: str | None = None,
) -> None:
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


class TestWorkflowHealthMetricsRepository:
    def test_get_workflow_health_metrics_excludes_simulation_runs(self, db_session: Session):
        """Simulation runs must not affect workflow KPI aggregates."""
        RunReadModel = _import_run_read_model()

        _seed_run(
            db_session,
            "run_manual",
            workflow_id="wf_1",
            source="manual",
            total_cost_usd=0.10,
        )
        _seed_node(db_session, "run_manual", "node_a", eval_passed=True)

        _seed_run(
            db_session,
            "run_webhook",
            workflow_id="wf_1",
            source="webhook",
            total_cost_usd=0.20,
        )
        _seed_node(db_session, "run_webhook", "node_b", eval_passed=False)

        _seed_run(
            db_session,
            "run_simulation",
            workflow_id="wf_1",
            source="simulation",
            total_cost_usd=9.90,
        )
        _seed_node(db_session, "run_simulation", "node_c", eval_passed=True)
        db_session.commit()

        repo = RunReadModel(db_session)
        result = repo.get_workflow_health_metrics(["wf_1"])
        metric = result["wf_1"]

        assert _metric_value(metric, "run_count") == 2
        assert _metric_value(metric, "eval_pass_pct") == pytest.approx(50.0)
        assert _metric_value(metric, "eval_health") == "danger"
        assert _metric_value(metric, "total_cost_usd") == pytest.approx(0.30)
        # RUN-558: regression_count is now comparison-based (passed->failed,
        # same node_id + soul_version). These two runs have different node_ids
        # and no soul_version, so there are zero regressions.
        assert _metric_value(metric, "regression_count") == 0

    def test_get_workflow_health_metrics_excludes_soft_deleted_runs(self, db_session: Session):
        """Soft-deleted runs must not affect workflow KPI or regression aggregates."""
        RunReadModel = _import_run_read_model()

        _seed_run(
            db_session,
            "run_active",
            workflow_id="wf_deleted",
            source="manual",
            total_cost_usd=0.40,
            created_at=100.0,
        )
        _seed_node(
            db_session,
            "run_active",
            "node_shared",
            eval_passed=True,
            soul_version="v1",
        )

        _seed_run(
            db_session,
            "run_deleted",
            workflow_id="wf_deleted",
            source="manual",
            total_cost_usd=9.90,
            created_at=200.0,
            deleted_at=250.0,
        )
        _seed_node(
            db_session,
            "run_deleted",
            "node_shared",
            eval_passed=False,
            soul_version="v1",
        )
        db_session.commit()

        repo = RunReadModel(db_session)
        result = repo.get_workflow_health_metrics(["wf_deleted"])
        metric = result["wf_deleted"]

        assert _metric_value(metric, "run_count") == 1
        assert _metric_value(metric, "eval_pass_pct") == pytest.approx(100.0)
        assert _metric_value(metric, "eval_health") == "success"
        assert _metric_value(metric, "total_cost_usd") == pytest.approx(0.40)
        assert _metric_value(metric, "regression_count") == 0
