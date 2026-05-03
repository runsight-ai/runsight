"""RunService aggregates node counts by execution status."""

from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from runsight_api.data.repositories.run_repo import RunRepository
from runsight_api.domain.entities.run import Run, RunNode
from runsight_api.logic.services.run_service import RunService
from runsight_api.main import app

client = TestClient(app)


@pytest.fixture(name="db_session")
def db_session_fixture():
    engine = create_engine("sqlite:///:memory:", echo=False)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="seeded_run")
def seeded_run_fixture(db_session):
    """Create a run with mixed-status nodes."""
    repo = RunRepository(db_session)
    run = Run(
        id="run_node_summary",
        workflow_id="wf_node_summary",
        workflow_name="Test WF",
        task_json="{}",
        branch="main",
    )
    repo.create_run(run)

    # 2 completed, 1 running, 1 pending, 1 failed = 5 total
    nodes = [
        RunNode(
            id="run_node_summary:n1",
            run_id="run_node_summary",
            node_id="n1",
            block_type="llm",
            status="completed",
            cost_usd=0.01,
            tokens={"prompt": 100, "completion": 50, "total": 150},
        ),
        RunNode(
            id="run_node_summary:n2",
            run_id="run_node_summary",
            node_id="n2",
            block_type="llm",
            status="completed",
            cost_usd=0.02,
            tokens={"prompt": 200, "completion": 100, "total": 300},
        ),
        RunNode(
            id="run_node_summary:n3",
            run_id="run_node_summary",
            node_id="n3",
            block_type="llm",
            status="running",
            cost_usd=0.0,
            tokens={"prompt": 0, "completion": 0, "total": 0},
        ),
        RunNode(
            id="run_node_summary:n4",
            run_id="run_node_summary",
            node_id="n4",
            block_type="condition",
            status="pending",
            cost_usd=0.0,
            tokens={"prompt": 0, "completion": 0, "total": 0},
        ),
        RunNode(
            id="run_node_summary:n5",
            run_id="run_node_summary",
            node_id="n5",
            block_type="llm",
            status="failed",
            cost_usd=0.005,
            tokens={"prompt": 50, "completion": 0, "total": 50},
        ),
    ]
    for n in nodes:
        repo.create_node(n)

    return run


class TestGetNodeSummaryPerStatus:
    """RunService.get_node_summary must return per-status counts."""

    def test_returns_completed_count(self, db_session, seeded_run):
        workflow_repo = Mock()
        svc = RunService(RunRepository(db_session), workflow_repo)
        summary = svc.get_node_summary("run_node_summary")
        assert "completed" in summary, "get_node_summary must return 'completed' count"
        assert summary["completed"] == 2

    def test_returns_running_count(self, db_session, seeded_run):
        workflow_repo = Mock()
        svc = RunService(RunRepository(db_session), workflow_repo)
        summary = svc.get_node_summary("run_node_summary")
        assert "running" in summary, "get_node_summary must return 'running' count"
        assert summary["running"] == 1

    def test_returns_pending_count(self, db_session, seeded_run):
        workflow_repo = Mock()
        svc = RunService(RunRepository(db_session), workflow_repo)
        summary = svc.get_node_summary("run_node_summary")
        assert "pending" in summary, "get_node_summary must return 'pending' count"
        assert summary["pending"] == 1

    def test_returns_failed_count(self, db_session, seeded_run):
        workflow_repo = Mock()
        svc = RunService(RunRepository(db_session), workflow_repo)
        summary = svc.get_node_summary("run_node_summary")
        assert "failed" in summary, "get_node_summary must return 'failed' count"
        assert summary["failed"] == 1

    def test_returns_total_count(self, db_session, seeded_run):
        workflow_repo = Mock()
        svc = RunService(RunRepository(db_session), workflow_repo)
        summary = svc.get_node_summary("run_node_summary")
        assert "total" in summary
        assert summary["total"] == 5

    def test_zero_nodes_returns_all_zeros(self, db_session):
        """Run with zero nodes should return all-zero summary."""
        repo = RunRepository(db_session)
        run = Run(
            id="run-empty",
            workflow_id="wf_node_summary",
            workflow_name="Empty WF",
            task_json="{}",
            branch="main",
        )
        repo.create_run(run)

        workflow_repo = Mock()
        svc = RunService(repo, workflow_repo)
        summary = svc.get_node_summary("run-empty")

        assert summary["total"] == 0
        assert summary["completed"] == 0
        assert summary["running"] == 0
        assert summary["pending"] == 0
        assert summary["failed"] == 0


# ---------------------------------------------------------------------------
# 3. Runs router populates node_summary with real counts (not hardcoded 0)
# ---------------------------------------------------------------------------
