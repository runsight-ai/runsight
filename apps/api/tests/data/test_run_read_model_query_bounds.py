"""Representative bounded-query smoke coverage for run read models."""

from collections.abc import Callable

import pytest
from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine

from runsight_api.data.repositories.run_read_model import RunReadModel
from runsight_api.domain.entities.run import Run, RunNode, RunStatus


@pytest.fixture
def db_session() -> Session:
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
    created_at: float,
) -> None:
    session.add(
        Run(
            id=run_id,
            workflow_id=workflow_id,
            workflow_name=workflow_id.replace("_", " ").title(),
            status=RunStatus.completed,
            task_json="{}",
            branch="main",
            source=source,
            created_at=created_at,
            updated_at=created_at,
        )
    )


def _seed_node(
    session: Session,
    run_id: str,
    node_id: str,
    *,
    eval_passed: bool,
    soul_version: str = "v1",
) -> None:
    session.add(
        RunNode(
            id=f"{run_id}:{node_id}",
            run_id=run_id,
            node_id=node_id,
            block_type="linear",
            status="completed",
            eval_passed=eval_passed,
            soul_version=soul_version,
        )
    )


def _record_queries(session: Session) -> tuple[list[str], Callable[..., None]]:
    statements: list[str] = []

    def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        del conn, cursor, parameters, context, executemany
        statements.append(statement)

    event.listen(session.get_bind(), "before_cursor_execute", _before_cursor_execute)
    return statements, _before_cursor_execute


def _stop_recording(session: Session, listener: Callable[..., None]) -> None:
    event.remove(session.get_bind(), "before_cursor_execute", listener)


def test_count_regressions_for_workflow_uses_bounded_queries(db_session: Session) -> None:
    workflow_id = "query-bound-regressions"
    for index in range(30):
        run_id = f"regression-run-{index}"
        _seed_run(db_session, run_id, workflow_id=workflow_id, created_at=float(index))
        _seed_node(
            db_session,
            run_id,
            "review",
            eval_passed=index % 2 == 0,
        )
    db_session.commit()

    statements, listener = _record_queries(db_session)
    try:
        regression_count = RunReadModel(db_session)._count_regressions_for_workflow(workflow_id)
    finally:
        _stop_recording(db_session, listener)

    assert regression_count > 0
    assert len(statements) <= 2


def test_workflow_health_metrics_stays_bounded_for_many_workflows(db_session: Session) -> None:
    workflow_ids = [f"query-bound-health-{index}" for index in range(5)]
    for workflow_index, workflow_id in enumerate(workflow_ids):
        for run_index in range(8):
            run_id = f"{workflow_id}-run-{run_index}"
            _seed_run(
                db_session,
                run_id,
                workflow_id=workflow_id,
                created_at=float(workflow_index * 100 + run_index),
            )
            _seed_node(db_session, run_id, "review", eval_passed=run_index % 2 == 0)
            _seed_node(db_session, run_id, "cost", eval_passed=True, soul_version="v2")
    db_session.commit()

    statements, listener = _record_queries(db_session)
    try:
        metrics = RunReadModel(db_session).get_workflow_health_metrics(workflow_ids)
    finally:
        _stop_recording(db_session, listener)

    assert set(metrics) == set(workflow_ids)
    assert all(metric["run_count"] == 8 for metric in metrics.values())
    assert all(metric["regression_count"] > 0 for metric in metrics.values())
    assert len(statements) <= 4
