"""Red tests for RUN-607: Nested run lifecycle and parent-child linkage.

Tests verify:
1. Run model has parent_run_id, parent_node_id, root_run_id, depth fields
2. RunNode model has child_run_id field
3. Child run created as separate record with parent linkage
4. Child completion does not finalize root run
5. Parent node stores child_run_id
6. root_run_id set on child run
7. Nested child-of-child depth tracking

All tests should FAIL until the implementation exists.
"""

from __future__ import annotations

import pytest
from runsight_core.observer import CompositeObserver, build_child_observer
from runsight_core.state import BlockResult, WorkflowState
from sqlmodel import Session, SQLModel, create_engine, select

from runsight_api.domain.entities.run import Run, RunNode, RunStatus
from runsight_api.logic.observers.execution_observer import ExecutionObserver


# ---------------------------------------------------------------------------
# Shared DB fixture — in-memory SQLite with Run/RunNode/LogEntry tables
# ---------------------------------------------------------------------------


@pytest.fixture
def db_engine():
    """Create an in-memory SQLite engine with all needed tables."""
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine


def _create_run(
    session: Session,
    *,
    run_id: str,
    workflow_id: str = "wf_parent",
    workflow_name: str = "Parent Workflow",
    status: RunStatus = RunStatus.running,
    parent_run_id: str | None = None,
    parent_node_id: str | None = None,
    root_run_id: str | None = None,
    depth: int = 0,
) -> Run:
    """Insert a Run record with optional parent-child fields."""
    run = Run(
        id=run_id,
        workflow_id=workflow_id,
        workflow_name=workflow_name,
        status=status,
        task_json="{}",
        parent_run_id=parent_run_id,
        parent_node_id=parent_node_id,
        root_run_id=root_run_id,
        depth=depth,
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


# ---------------------------------------------------------------------------
# 1. Run model has parent linkage fields
# ---------------------------------------------------------------------------


class TestRunModelHasParentLinkageFields:
    """AC-1/3: Run model must have parent_run_id, parent_node_id, root_run_id, depth."""

    def test_run_has_parent_run_id_field(self, db_engine):
        """Run model exposes a parent_run_id attribute (nullable)."""
        with Session(db_engine) as session:
            run = Run(
                id="run_field_test_1",
                workflow_id="wf_1",
                workflow_name="Test",
                task_json="{}",
                parent_run_id=None,
            )
            session.add(run)
            session.commit()
            session.refresh(run)
            assert hasattr(run, "parent_run_id")
            assert run.parent_run_id is None

    def test_run_has_parent_node_id_field(self, db_engine):
        """Run model exposes a parent_node_id attribute (nullable)."""
        with Session(db_engine) as session:
            run = Run(
                id="run_field_test_2",
                workflow_id="wf_1",
                workflow_name="Test",
                task_json="{}",
                parent_node_id=None,
            )
            session.add(run)
            session.commit()
            session.refresh(run)
            assert hasattr(run, "parent_node_id")
            assert run.parent_node_id is None

    def test_run_has_root_run_id_field(self, db_engine):
        """Run model exposes a root_run_id attribute (nullable)."""
        with Session(db_engine) as session:
            run = Run(
                id="run_field_test_3",
                workflow_id="wf_1",
                workflow_name="Test",
                task_json="{}",
                root_run_id=None,
            )
            session.add(run)
            session.commit()
            session.refresh(run)
            assert hasattr(run, "root_run_id")
            assert run.root_run_id is None

    def test_run_has_depth_field(self, db_engine):
        """Run model exposes a depth attribute (int, default 0)."""
        with Session(db_engine) as session:
            run = Run(
                id="run_field_test_4",
                workflow_id="wf_1",
                workflow_name="Test",
                task_json="{}",
            )
            session.add(run)
            session.commit()
            session.refresh(run)
            assert hasattr(run, "depth")
            assert run.depth == 0

    def test_run_parent_linkage_fields_persist_round_trip(self, db_engine):
        """Parent linkage fields survive a DB round-trip with non-null values."""
        with Session(db_engine) as session:
            _create_run(
                session,
                run_id="child_rt",
                workflow_id="wf_child",
                workflow_name="Child",
                parent_run_id="parent_rt",
                parent_node_id="parent_rt:call_child",
                root_run_id="parent_rt",
                depth=1,
            )

        with Session(db_engine) as session:
            child = session.get(Run, "child_rt")
            assert child is not None
            assert child.parent_run_id == "parent_rt"
            assert child.parent_node_id == "parent_rt:call_child"
            assert child.root_run_id == "parent_rt"
            assert child.depth == 1


# ---------------------------------------------------------------------------
# 2. RunNode model has child_run_id field
# ---------------------------------------------------------------------------


class TestRunNodeModelHasChildRunIdField:
    """AC-3/4: RunNode for workflow-call blocks must carry child_run_id."""

    def test_run_node_has_child_run_id_field(self, db_engine):
        """RunNode model exposes a child_run_id attribute (nullable)."""
        with Session(db_engine) as session:
            node = RunNode(
                id="run_1:call_child",
                run_id="run_1",
                node_id="call_child",
                block_type="workflow",
                child_run_id=None,
            )
            session.add(node)
            session.commit()
            session.refresh(node)
            assert hasattr(node, "child_run_id")
            assert node.child_run_id is None

    def test_run_node_child_run_id_persists_round_trip(self, db_engine):
        """child_run_id survives a DB round-trip with a non-null value."""
        with Session(db_engine) as session:
            node = RunNode(
                id="run_1:call_child",
                run_id="run_1",
                node_id="call_child",
                block_type="workflow",
                child_run_id="child_run_1",
            )
            session.add(node)
            session.commit()

        with Session(db_engine) as session:
            node = session.get(RunNode, "run_1:call_child")
            assert node is not None
            assert node.child_run_id == "child_run_1"


# ---------------------------------------------------------------------------
# 3. Child run created as separate record
# ---------------------------------------------------------------------------


class TestChildRunCreatedAsSeparateRecord:
    """AC-1: Parent and child runs are separate records.
    AC-3: Parent workflow-call node stores child_run_id.
    """

    def test_child_run_is_separate_from_parent(self, db_engine):
        """When a workflow-type block is executed, a child Run record should be
        created with parent_run_id pointing to the parent Run. The child should
        have depth=1 and be a distinct record from the parent."""
        with Session(db_engine) as session:
            _create_run(
                session,
                run_id="parent_run",
                workflow_id="wf_parent",
                workflow_name="Parent",
                depth=0,
            )

        # Simulate ExecutionObserver creating a child run for a workflow block.
        # The observer should detect block_type="workflow" and create a child Run.
        obs = ExecutionObserver(engine=db_engine, run_id="parent_run")
        obs.on_block_start("Parent", "call_child", "workflow")

        with Session(db_engine) as session:
            # There should be a child Run record linked to the parent
            children = list(
                session.exec(select(Run).where(Run.parent_run_id == "parent_run")).all()
            )
            assert len(children) == 1, (
                "Expected exactly one child Run record with parent_run_id='parent_run'"
            )
            child = children[0]
            assert child.depth == 1
            assert child.parent_run_id == "parent_run"
            assert child.id != "parent_run"


# ---------------------------------------------------------------------------
# 4. Child completion does not finalize root run
# ---------------------------------------------------------------------------


class TestChildCompletionDoesNotFinalizeRootRun:
    """AC-2: Child completion does not finalize the root run."""

    def test_root_stays_running_after_child_completes(self, db_engine):
        """After a child workflow completes, the root Run should remain in
        'running' status. Only when the parent workflow itself completes
        should the root finalize.

        This test requires the parent linkage fields to exist on Run so we
        can verify the structural relationship. If the fields don't exist
        the test must fail.
        """
        with Session(db_engine) as session:
            _create_run(
                session,
                run_id="root_run",
                workflow_id="wf_parent",
                workflow_name="Parent",
                status=RunStatus.running,
                depth=0,
            )
            _create_run(
                session,
                run_id="child_run",
                workflow_id="wf_child",
                workflow_name="Child",
                status=RunStatus.running,
                parent_run_id="root_run",
                parent_node_id="root_run:call_child",
                root_run_id="root_run",
                depth=1,
            )

        # Verify structural precondition: child must have linkage fields persisted
        with Session(db_engine) as session:
            child_pre = session.get(Run, "child_run")
            assert child_pre.parent_run_id == "root_run", (
                "Precondition: child Run must have parent_run_id field persisted"
            )
            assert child_pre.root_run_id == "root_run", (
                "Precondition: child Run must have root_run_id field persisted"
            )
            assert child_pre.depth == 1, "Precondition: child Run must have depth=1"

        # Child observer completes the child workflow
        child_obs = ExecutionObserver(engine=db_engine, run_id="child_run")
        from runsight_core.state import WorkflowState

        child_obs.on_workflow_complete("Child", WorkflowState(), 2.0)

        with Session(db_engine) as session:
            child = session.get(Run, "child_run")
            root = session.get(Run, "root_run")

            # Child should be completed
            assert child.status == RunStatus.completed
            # Root must still be running — child completion must NOT cascade
            assert root.status == RunStatus.running, (
                f"Root run should remain 'running' after child completes, "
                f"but got '{root.status.value}'"
            )


# ---------------------------------------------------------------------------
# 5. Parent node stores child_run_id
# ---------------------------------------------------------------------------


class TestParentNodeStoresChildRunId:
    """AC-3: Parent workflow-call node stores child_run_id."""

    def test_workflow_block_node_gets_child_run_id(self, db_engine):
        """When the observer starts a workflow-type block, the resulting RunNode
        should have child_run_id set to the child Run's ID."""
        with Session(db_engine) as session:
            _create_run(
                session,
                run_id="parent_run_node",
                workflow_id="wf_parent",
                workflow_name="Parent",
                depth=0,
            )

        obs = ExecutionObserver(engine=db_engine, run_id="parent_run_node")
        obs.on_block_start("Parent", "call_child", "workflow")

        with Session(db_engine) as session:
            node = session.get(RunNode, "parent_run_node:call_child")
            assert node is not None
            assert node.child_run_id is not None, (
                "RunNode for a workflow-type block must have child_run_id set"
            )
            # Verify the child_run_id points to an actual Run record
            child_run = session.get(Run, node.child_run_id)
            assert child_run is not None, (
                f"child_run_id '{node.child_run_id}' should reference an existing Run"
            )

    def test_child_observer_persists_child_nodes_on_child_run(self, db_engine):
        """Child workflow events must be persisted on the child run, not the parent run."""
        with Session(db_engine) as session:
            _create_run(
                session,
                run_id="parent_run_nested",
                workflow_id="wf_parent",
                workflow_name="Parent",
                status=RunStatus.running,
                depth=0,
            )

        parent_observer = CompositeObserver(
            ExecutionObserver(engine=db_engine, run_id="parent_run_nested")
        )
        parent_observer.on_block_start(
            "Parent",
            "call_child",
            "WorkflowBlock",
            child_workflow_id="wf_real_child",
            child_workflow_name="Child Workflow",
        )

        child_observer, child_run_id = build_child_observer(parent_observer, block_id="call_child")
        assert child_run_id is not None, "workflow block start should allocate a child run id"

        child_state = WorkflowState().model_copy(
            update={
                "results": {
                    "child_step": BlockResult(output="child ok"),
                    "final_summary": "child ok",
                }
            }
        )

        child_observer.on_workflow_start("Child", WorkflowState())
        child_observer.on_block_start("Child", "child_step", "CodeBlock")
        child_observer.on_block_complete("Child", "child_step", "CodeBlock", 0.1, child_state)
        child_observer.on_workflow_complete("Child", child_state, 0.2)

        with Session(db_engine) as session:
            parent_run = session.get(Run, "parent_run_nested")
            child_run = session.get(Run, child_run_id)
            parent_node = session.get(RunNode, "parent_run_nested:call_child")
            child_node = session.get(RunNode, f"{child_run_id}:child_step")

            assert parent_run is not None
            assert child_run is not None
            assert parent_node is not None
            assert child_node is not None

            assert parent_run.status == RunStatus.running
            assert parent_node.child_run_id == child_run_id
            assert child_run.parent_run_id == "parent_run_nested"
            assert child_run.workflow_id == "wf_real_child"
            assert child_run.workflow_name == "Child Workflow"
            assert child_run.status == RunStatus.completed
            assert child_node.run_id == child_run_id
            assert child_node.status == "completed"


# ---------------------------------------------------------------------------
# 6. root_run_id set on child
# ---------------------------------------------------------------------------


class TestRootRunIdSetOnChild:
    """AC-6: Child Run should have root_run_id pointing to the outermost ancestor."""

    def test_child_has_root_run_id(self, db_engine):
        """A child Run created for a workflow block must have root_run_id
        pointing to the root run (the run that started the chain)."""
        with Session(db_engine) as session:
            _create_run(
                session,
                run_id="root_for_607",
                workflow_id="wf_parent",
                workflow_name="Parent",
                depth=0,
            )

        obs = ExecutionObserver(engine=db_engine, run_id="root_for_607")
        obs.on_block_start("Parent", "call_child", "workflow")

        with Session(db_engine) as session:
            children = list(
                session.exec(select(Run).where(Run.parent_run_id == "root_for_607")).all()
            )
            assert len(children) == 1
            child = children[0]
            assert child.root_run_id == "root_for_607", (
                f"Expected root_run_id='root_for_607', got '{child.root_run_id}'"
            )

    def test_root_run_has_null_root_run_id(self, db_engine):
        """A root run (depth=0, no parent) should have root_run_id=None."""
        with Session(db_engine) as session:
            run = Run(
                id="root_only",
                workflow_id="wf_1",
                workflow_name="Root",
                task_json="{}",
                depth=0,
            )
            session.add(run)
            session.commit()
            session.refresh(run)
            # Root runs have no parent, so root_run_id should be None
            assert run.root_run_id is None


# ---------------------------------------------------------------------------
# 7. Nested child-of-child depth
# ---------------------------------------------------------------------------


class TestNestedChildOfChildDepth:
    """Edge case: parent -> child -> grandchild depth tracking."""

    def test_grandchild_has_depth_2(self, db_engine):
        """For parent(depth=0) -> child(depth=1) -> grandchild(depth=2),
        the grandchild Run should have depth=2, parent_run_id = child Run ID,
        and root_run_id = root Run ID."""
        with Session(db_engine) as session:
            # Root run
            _create_run(
                session,
                run_id="gc_root",
                workflow_id="wf_parent",
                workflow_name="Root",
                depth=0,
            )
            # Child run (created by parent's observer for a workflow block)
            _create_run(
                session,
                run_id="gc_child",
                workflow_id="wf_child",
                workflow_name="Child",
                parent_run_id="gc_root",
                parent_node_id="gc_root:call_child",
                root_run_id="gc_root",
                depth=1,
            )

        # Child observer starts a workflow block, which should create grandchild
        child_obs = ExecutionObserver(engine=db_engine, run_id="gc_child")
        child_obs.on_block_start("Child", "call_grandchild", "workflow")

        with Session(db_engine) as session:
            grandchildren = list(
                session.exec(select(Run).where(Run.parent_run_id == "gc_child")).all()
            )
            assert len(grandchildren) == 1, (
                "Expected one grandchild Run with parent_run_id='gc_child'"
            )
            grandchild = grandchildren[0]
            assert grandchild.depth == 2, f"Expected grandchild depth=2, got {grandchild.depth}"
            assert grandchild.parent_run_id == "gc_child"
            assert grandchild.root_run_id == "gc_root", (
                f"Grandchild root_run_id should be 'gc_root', got '{grandchild.root_run_id}'"
            )

    def test_reused_child_workflow_across_different_parents(self, db_engine):
        """Edge case: same child workflow used by two different parent runs
        should produce two separate child Run records."""
        with Session(db_engine) as session:
            _create_run(
                session,
                run_id="parent_A",
                workflow_id="wf_parent_a",
                workflow_name="Parent A",
                depth=0,
            )
            _create_run(
                session,
                run_id="parent_B",
                workflow_id="wf_parent_b",
                workflow_name="Parent B",
                depth=0,
            )

        obs_a = ExecutionObserver(engine=db_engine, run_id="parent_A")
        obs_a.on_block_start("Parent A", "call_shared", "workflow")

        obs_b = ExecutionObserver(engine=db_engine, run_id="parent_B")
        obs_b.on_block_start("Parent B", "call_shared", "workflow")

        with Session(db_engine) as session:
            children_a = list(
                session.exec(select(Run).where(Run.parent_run_id == "parent_A")).all()
            )
            children_b = list(
                session.exec(select(Run).where(Run.parent_run_id == "parent_B")).all()
            )
            assert len(children_a) == 1
            assert len(children_b) == 1
            assert children_a[0].id != children_b[0].id, (
                "Reused child workflow should produce distinct Run records per parent"
            )
