from enum import Enum

from sqlmodel import Session

from tests.domain.run_entity_factories import in_memory_engine
from runsight_api.domain.entities.run import NodeStatus, RunNode


def test_node_status_is_exported_string_enum_with_node_lifecycle_values():
    from runsight_api.domain.entities import NodeStatus as ExportedNodeStatus

    assert ExportedNodeStatus is NodeStatus
    assert issubclass(NodeStatus, str)
    assert issubclass(NodeStatus, Enum)
    assert {status.value for status in NodeStatus} == {
        "pending",
        "running",
        "completed",
        "failed",
    }


def test_run_node_defaults_accepts_and_persists_node_status_enum_values():
    assert RunNode(id="r:n", run_id="r", node_id="n", block_type="llm").status == (
        NodeStatus.pending
    )

    engine = in_memory_engine()
    with Session(engine) as session:
        session.add(
            RunNode(
                id="r1:n1",
                run_id="r1",
                node_id="n1",
                block_type="llm",
                status=NodeStatus.completed,
            )
        )
        session.commit()

    with Session(engine) as session:
        loaded = session.get(RunNode, "r1:n1")
        assert loaded is not None
        assert loaded.status == NodeStatus.completed
        assert loaded.status == "completed"
