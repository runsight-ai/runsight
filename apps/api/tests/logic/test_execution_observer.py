"""ExecutionObserver persistence smoke coverage."""

import json

import pytest
from runsight_core.state import BlockResult, WorkflowState
from sqlmodel import Session, SQLModel, create_engine, select

from runsight_api.domain.entities.log import LogEntry
from runsight_api.domain.entities.run import Run, RunNode, RunStatus
from runsight_api.logic.observers.execution_observer import ExecutionObserver


@pytest.fixture
def db_engine():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine


def _seed_run(engine, run_id: str) -> None:
    with Session(engine) as session:
        session.add(
            Run(
                id=run_id,
                workflow_id="observer-smoke-flow",
                workflow_name="Observer Smoke Flow",
                status=RunStatus.pending,
                task_json="{}",
                branch="main",
            )
        )
        session.commit()


def _log_events(engine, run_id: str) -> list[str]:
    with Session(engine) as session:
        logs = session.exec(select(LogEntry).where(LogEntry.run_id == run_id)).all()
    return [json.loads(log.message)["event"] for log in logs if log.message.startswith("{")]


def test_observer_persists_success_lifecycle_smoke(db_engine) -> None:
    run_id = "observer-success-smoke"
    _seed_run(db_engine, run_id)
    observer = ExecutionObserver(engine=db_engine, run_id=run_id)

    observer.on_workflow_start("observer-smoke-flow", WorkflowState())
    observer.on_block_start("observer-smoke-flow", "analyze", "LinearBlock")
    observer.on_block_heartbeat(
        workflow_name="observer-smoke-flow",
        block_id="analyze",
        phase="llm_call",
        detail="calling model",
        timestamp=None,
    )
    state = WorkflowState(
        total_cost_usd=0.12,
        total_tokens=42,
        results={"analyze": BlockResult(output="analysis complete")},
    )
    observer.on_block_complete("observer-smoke-flow", "analyze", "LinearBlock", 0.25, state)
    observer.on_workflow_complete("observer-smoke-flow", state, 0.5)

    with Session(db_engine) as session:
        run = session.get(Run, run_id)
        node = session.get(RunNode, f"{run_id}:analyze")

    assert run.status == RunStatus.completed
    assert run.total_cost_usd == pytest.approx(0.12)
    assert run.total_tokens == 42
    assert "analysis complete" in run.results_json
    assert node.status == "completed"
    assert node.output == "analysis complete"
    assert node.last_phase == "llm_call"
    assert {"workflow_start", "block_start", "block_complete", "workflow_complete"}.issubset(
        set(_log_events(db_engine, run_id))
    )


def test_observer_persists_workflow_error_smoke(db_engine) -> None:
    run_id = "observer-error-smoke"
    _seed_run(db_engine, run_id)
    observer = ExecutionObserver(engine=db_engine, run_id=run_id)

    observer.on_workflow_start("observer-smoke-flow", WorkflowState())
    observer.on_workflow_error(
        "observer-smoke-flow",
        RuntimeError("smoke failure"),
        0.1,
        state=WorkflowState(),
    )

    with Session(db_engine) as session:
        run = session.get(Run, run_id)

    assert run.status == RunStatus.failed
    assert "smoke failure" in run.error
    assert "workflow_error" in _log_events(db_engine, run_id)
