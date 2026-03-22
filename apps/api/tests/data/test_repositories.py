import pytest
from sqlmodel import SQLModel, Session, create_engine
from runsight_api.domain.entities import Run, RunNode
from runsight_api.data.repositories import RunRepository


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite:///:memory:", echo=False)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_run_repository(session: Session):
    repo = RunRepository(session)
    run = Run(id="run-1", workflow_id="wf-1", workflow_name="WF", task_json="{}")
    repo.create_run(run)

    fetched_run = repo.get_run("run-1")
    assert fetched_run is not None
    assert fetched_run.id == "run-1"

    node = RunNode(id="run-1:node-1", run_id="run-1", node_id="node-1", block_type="llm")
    repo.create_node(node)

    nodes = repo.list_nodes_for_run("run-1")
    assert len(nodes) == 1
    assert nodes[0].id == "run-1:node-1"
