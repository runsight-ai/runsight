import pytest
from sqlmodel import Session, SQLModel, create_engine

from runsight_api.data.repositories import RunRepository
from runsight_api.domain.entities import Run, RunNode


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite:///:memory:", echo=False)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_run_repository(session: Session):
    repo = RunRepository(session)
    run = Run(
        id="run-primary",
        workflow_id="wf-primary",
        workflow_name="WF",
        task_json="{}",
        branch="main",
    )
    repo.create_run(run)

    fetched_run = repo.get_run("run-primary")
    assert fetched_run is not None
    assert fetched_run.id == "run-primary"

    node = RunNode(
        id="run-primary:node-primary",
        run_id="run-primary",
        node_id="node-primary",
        block_type="llm",
    )
    repo.create_node(node)

    nodes = repo.list_nodes_for_run("run-primary")
    assert len(nodes) == 1
    assert nodes[0].id == "run-primary:node-primary"
