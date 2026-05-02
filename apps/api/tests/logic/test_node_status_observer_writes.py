import pytest
from sqlmodel import Session, SQLModel, create_engine

from runsight_api.domain.entities.run import NodeStatus, Run, RunNode, RunStatus


@pytest.fixture
def seeded_run_engine():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    run_id = "run_node_status"
    with Session(engine) as session:
        session.add(
            Run(
                id=run_id,
                workflow_id="workflow_node_status",
                workflow_name="Node status workflow",
                status=RunStatus.pending,
                task_json="{}",
                branch="main",
            )
        )
        session.commit()
    return engine, run_id


def test_block_start_persists_node_status_running(seeded_run_engine):
    from runsight_api.logic.observers.execution_observer import ExecutionObserver

    engine, run_id = seeded_run_engine
    ExecutionObserver(engine=engine, run_id=run_id).on_block_start(
        "Node status workflow", "b1", "llm"
    )

    with Session(engine) as session:
        assert session.get(RunNode, f"{run_id}:b1").status == NodeStatus.running


def test_block_complete_persists_node_status_completed(seeded_run_engine):
    from runsight_core.state import WorkflowState

    from runsight_api.logic.observers.execution_observer import ExecutionObserver

    engine, run_id = seeded_run_engine
    observer = ExecutionObserver(engine=engine, run_id=run_id)
    observer.on_block_start("Node status workflow", "b1", "llm")
    observer.on_block_complete("Node status workflow", "b1", "llm", 1.0, WorkflowState())

    with Session(engine) as session:
        assert session.get(RunNode, f"{run_id}:b1").status == NodeStatus.completed


def test_block_error_persists_node_status_failed(seeded_run_engine):
    from runsight_api.logic.observers.execution_observer import ExecutionObserver

    engine, run_id = seeded_run_engine
    observer = ExecutionObserver(engine=engine, run_id=run_id)
    observer.on_block_start("Node status workflow", "b1", "llm")
    observer.on_block_error("Node status workflow", "b1", "llm", 1.0, RuntimeError("boom"))

    with Session(engine) as session:
        assert session.get(RunNode, f"{run_id}:b1").status == NodeStatus.failed
