"""API source read-model metrics coverage."""

from __future__ import annotations

import pytest
from sqlmodel import Session, SQLModel, create_engine

from runsight_api.domain.entities.run import Run, RunNode, RunStatus


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
    source: str,
    created_at: float,
    eval_passed: bool,
    total_cost_usd: float = 1.0,
) -> None:
    session.add(
        Run(
            id=run_id,
            workflow_id="wf_source_provenance",
            workflow_name="API Provenance Workflow",
            status=RunStatus.completed,
            task_json="{}",
            source=source,
            branch="main" if source != "simulation" else "sim/source-provenance",
            created_at=created_at,
            updated_at=created_at,
            total_cost_usd=total_cost_usd,
        )
    )
    session.add(
        RunNode(
            id=f"{run_id}:node",
            run_id=run_id,
            node_id="node",
            block_type="llm",
            status="completed",
            eval_passed=eval_passed,
            cost_usd=total_cost_usd,
            tokens={"total": 10},
        )
    )


def test_api_runs_are_production_runs_for_workflow_health_metrics(db_session: Session) -> None:
    from runsight_api.data.repositories.run_read_model import RunReadModel

    _seed_run(
        db_session, "source_provenance_manual", source="manual", created_at=100.0, eval_passed=True
    )
    _seed_run(
        db_session, "source_provenance_api", source="api", created_at=200.0, eval_passed=False
    )
    _seed_run(
        db_session,
        "source_provenance_simulation",
        source="simulation",
        created_at=300.0,
        eval_passed=False,
        total_cost_usd=99.0,
    )
    db_session.commit()

    metrics = RunReadModel(db_session).get_workflow_health_metrics(["wf_source_provenance"])

    assert metrics["wf_source_provenance"]["run_count"] == 2
    assert metrics["wf_source_provenance"]["eval_pass_pct"] == 50.0
    assert metrics["wf_source_provenance"]["total_cost_usd"] == 2.0
