"""Red tests for RUN-330: NodeStatus enum — replace magic strings on RunNode.

Tests target:
  - apps/api/src/runsight_api/domain/entities/run.py (NodeStatus enum, RunNode.status type)
  - apps/api/src/runsight_api/logic/observers/execution_observer.py (enum usage)
  - apps/api/src/runsight_api/logic/services/run_service.py (enum usage)

All tests should FAIL until the implementation exists.
"""

import inspect

import pytest
from sqlmodel import Session, SQLModel, create_engine

from runsight_api.domain.entities.run import Run, RunNode, RunStatus

# ---------------------------------------------------------------------------
# 1. NodeStatus enum existence and values
# ---------------------------------------------------------------------------


class TestNodeStatusEnumExists:
    def test_can_import_node_status(self):
        """NodeStatus can be imported from domain.entities.run."""
        from runsight_api.domain.entities.run import NodeStatus

        assert NodeStatus is not None

    def test_node_status_is_str_enum(self):
        """NodeStatus is a str Enum (same pattern as RunStatus)."""
        from enum import Enum

        from runsight_api.domain.entities.run import NodeStatus

        assert issubclass(NodeStatus, str)
        assert issubclass(NodeStatus, Enum)

    def test_node_status_has_pending(self):
        """NodeStatus has a 'pending' member equal to 'pending'."""
        from runsight_api.domain.entities.run import NodeStatus

        assert NodeStatus.pending == "pending"

    def test_node_status_has_running(self):
        """NodeStatus has a 'running' member equal to 'running'."""
        from runsight_api.domain.entities.run import NodeStatus

        assert NodeStatus.running == "running"

    def test_node_status_has_completed(self):
        """NodeStatus has a 'completed' member equal to 'completed'."""
        from runsight_api.domain.entities.run import NodeStatus

        assert NodeStatus.completed == "completed"

    def test_node_status_has_failed(self):
        """NodeStatus has a 'failed' member equal to 'failed'."""
        from runsight_api.domain.entities.run import NodeStatus

        assert NodeStatus.failed == "failed"

    def test_node_status_has_exactly_four_members(self):
        """NodeStatus has exactly 4 members (no cancelled — nodes don't cancel independently)."""
        from runsight_api.domain.entities.run import NodeStatus

        assert len(NodeStatus) == 4

    def test_node_status_exported_from_entities_init(self):
        """NodeStatus is re-exported from domain.entities.__init__."""
        from runsight_api.domain.entities import NodeStatus  # noqa: F401

        assert NodeStatus is not None


# ---------------------------------------------------------------------------
# 2. RunNode.status type uses NodeStatus
# ---------------------------------------------------------------------------


class TestRunNodeStatusType:
    def test_run_node_default_status_is_node_status_pending(self):
        """RunNode default status is NodeStatus.pending (not the string 'pending')."""
        from runsight_api.domain.entities.run import NodeStatus

        node = RunNode(id="r:n", run_id="r", node_id="n", block_type="llm")
        assert node.status == NodeStatus.pending
        assert isinstance(node.status, NodeStatus)

    def test_run_node_status_accepts_node_status_enum(self):
        """RunNode.status can be set using NodeStatus enum values."""
        from runsight_api.domain.entities.run import NodeStatus

        node = RunNode(
            id="r:n",
            run_id="r",
            node_id="n",
            block_type="llm",
            status=NodeStatus.running,
        )
        assert node.status == NodeStatus.running

    def test_run_node_status_round_trips_through_db(self):
        """NodeStatus values survive a DB write-read round trip."""
        from runsight_api.domain.entities.run import NodeStatus

        engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(engine)

        with Session(engine) as session:
            node = RunNode(
                id="r1:n1",
                run_id="r1",
                node_id="n1",
                block_type="llm",
                status=NodeStatus.completed,
            )
            session.add(node)
            session.commit()

        with Session(engine) as session:
            loaded = session.get(RunNode, "r1:n1")
            assert loaded.status == NodeStatus.completed
            assert loaded.status == "completed"  # str compatibility


# ---------------------------------------------------------------------------
# 3. Zero magic strings in execution_observer.py
# ---------------------------------------------------------------------------


class TestExecutionObserverUsesEnum:
    def test_on_block_start_uses_node_status_running(self):
        """execution_observer.py must import NodeStatus."""
        source = inspect.getsource(
            __import__(
                "runsight_api.logic.observers.execution_observer",
                fromlist=["ExecutionObserver"],
            )
        )
        assert "NodeStatus" in source, "execution_observer.py must import NodeStatus"

    def test_no_magic_status_strings_in_execution_observer(self):
        """execution_observer.py has zero bare status string assignments."""
        source = inspect.getsource(
            __import__(
                "runsight_api.logic.observers.execution_observer",
                fromlist=["ExecutionObserver"],
            )
        )
        forbidden = [
            'status="running"',
            'status="completed"',
            'status="failed"',
            'status="pending"',
            "status='running'",
            "status='completed'",
            "status='failed'",
            "status='pending'",
        ]
        violations = [f for f in forbidden if f in source]
        assert violations == [], (
            f"Magic status strings found in execution_observer.py: {violations}"
        )


# ---------------------------------------------------------------------------
# 4. Zero magic strings in run_service.py
# ---------------------------------------------------------------------------


class TestRunServiceUsesEnum:
    def test_run_service_imports_node_status(self):
        """run_service.py imports NodeStatus."""
        source = inspect.getsource(
            __import__("runsight_api.logic.services.run_service", fromlist=["RunService"])
        )
        assert "NodeStatus" in source, "run_service.py must import NodeStatus"

    def test_no_magic_status_strings_in_run_service(self):
        """run_service.py has zero bare status string comparisons."""
        source = inspect.getsource(
            __import__("runsight_api.logic.services.run_service", fromlist=["RunService"])
        )
        forbidden = [
            '== "running"',
            '== "completed"',
            '== "failed"',
            '== "pending"',
            "== 'running'",
            "== 'completed'",
            "== 'failed'",
            "== 'pending'",
        ]
        violations = [f for f in forbidden if f in source]
        assert violations == [], f"Magic status strings found in run_service.py: {violations}"


# ---------------------------------------------------------------------------
# 5. Integration: observer writes NodeStatus, read-back is NodeStatus
# ---------------------------------------------------------------------------


class TestObserverIntegration:
    @pytest.fixture
    def db_engine(self):
        engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(engine)
        return engine

    @pytest.fixture
    def seed_run(self, db_engine):
        run_id = "run_330"
        with Session(db_engine) as session:
            run = Run(
                id=run_id,
                workflow_id="wf_1",
                workflow_name="test_wf",
                status=RunStatus.pending,
                task_json="{}",
            )
            session.add(run)
            session.commit()
        return db_engine, run_id

    def test_block_start_persists_node_status_running(self, seed_run):
        """After on_block_start, RunNode.status in DB is NodeStatus.running."""
        from runsight_api.domain.entities.run import NodeStatus
        from runsight_api.logic.observers.execution_observer import ExecutionObserver

        engine, run_id = seed_run
        obs = ExecutionObserver(engine=engine, run_id=run_id)
        obs.on_block_start("wf", "b1", "llm")

        with Session(engine) as session:
            node = session.get(RunNode, f"{run_id}:b1")
            assert node.status == NodeStatus.running

    def test_block_complete_persists_node_status_completed(self, seed_run):
        """After on_block_complete, RunNode.status in DB is NodeStatus.completed."""
        from runsight_core.state import WorkflowState

        from runsight_api.domain.entities.run import NodeStatus
        from runsight_api.logic.observers.execution_observer import ExecutionObserver

        engine, run_id = seed_run
        obs = ExecutionObserver(engine=engine, run_id=run_id)
        obs.on_block_start("wf", "b1", "llm")
        obs.on_block_complete("wf", "b1", "llm", 1.0, WorkflowState())

        with Session(engine) as session:
            node = session.get(RunNode, f"{run_id}:b1")
            assert node.status == NodeStatus.completed

    def test_block_error_persists_node_status_failed(self, seed_run):
        """After on_block_error, RunNode.status in DB is NodeStatus.failed."""
        from runsight_api.domain.entities.run import NodeStatus
        from runsight_api.logic.observers.execution_observer import ExecutionObserver

        engine, run_id = seed_run
        obs = ExecutionObserver(engine=engine, run_id=run_id)
        obs.on_block_start("wf", "b1", "llm")
        obs.on_block_error("wf", "b1", "llm", 1.0, RuntimeError("boom"))

        with Session(engine) as session:
            node = session.get(RunNode, f"{run_id}:b1")
            assert node.status == NodeStatus.failed
