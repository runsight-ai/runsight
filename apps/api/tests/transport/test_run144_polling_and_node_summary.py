"""
RED-TEAM tests for RUN-144: Fix RunDetail polling — enable refetchInterval for active runs.

These tests cover the Python/backend side:

1. NodeSummary schema alignment: domain NodeSummary must NOT have a `killed` field
   (it should have exactly 5 fields: total, completed, running, pending, failed).

2. get_node_summary must return per-status breakdown (completed, running, pending, failed)
   — not just nodes_count, total_cost_usd, total_tokens.

3. The runs router (GET /runs/{id} and GET /runs) must populate node_summary with
   real per-status counts from RunNode records, instead of hardcoded zeros.

4. GET /runs/{id} response must include total_cost_usd and total_tokens computed
   from real node data (not hardcoded 0).

All tests are expected to FAIL against the current implementation because:
- domain/value_objects.py NodeSummary has a `killed` field (6 fields instead of 5)
- RunService.get_node_summary returns only {total_cost_usd, total_tokens, nodes_count}
  without per-status breakdown
- The runs router hardcodes completed=0, running=0, pending=0, failed=0 in NodeSummary
"""

from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from runsight_api.data.repositories.run_repo import RunRepository
from runsight_api.domain.entities.run import Run, RunNode, RunStatus
from runsight_api.domain.value_objects import NodeSummary as DomainNodeSummary
from runsight_api.logic.services.run_service import RunService
from runsight_api.main import app
from runsight_api.transport.deps import get_run_service
from runsight_api.transport.schemas.runs import NodeSummary as TransportNodeSummary

client = TestClient(app)


# ---------------------------------------------------------------------------
# 1. NodeSummary schema alignment — domain must NOT have `killed`
# ---------------------------------------------------------------------------


class TestNodeSummarySchemaAlignment:
    """The domain NodeSummary should match the transport schema exactly: 5 fields."""

    def test_domain_node_summary_has_no_killed_field(self):
        """domain/value_objects.py NodeSummary should not have a 'killed' field."""
        fields = set(DomainNodeSummary.model_fields.keys())
        assert "killed" not in fields, (
            f"NodeSummary in domain/value_objects.py still has 'killed' field. Fields: {fields}"
        )

    def test_domain_node_summary_has_exactly_five_fields(self):
        """Domain NodeSummary should have exactly: total, completed, running, pending, failed."""
        expected = {"total", "completed", "running", "pending", "failed"}
        actual = set(DomainNodeSummary.model_fields.keys())
        assert actual == expected, (
            f"Domain NodeSummary fields mismatch. Expected {expected}, got {actual}"
        )

    def test_domain_and_transport_schemas_match(self):
        """Domain and transport NodeSummary should have the same field set."""
        domain_fields = set(DomainNodeSummary.model_fields.keys())
        transport_fields = set(TransportNodeSummary.model_fields.keys())
        assert domain_fields == transport_fields, (
            f"Schema mismatch: domain={domain_fields}, transport={transport_fields}"
        )


# ---------------------------------------------------------------------------
# 2. RunService.get_node_summary returns per-status breakdown
# ---------------------------------------------------------------------------


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
    run = Run(id="run-144", workflow_id="wf-1", workflow_name="Test WF", task_json="{}")
    repo.create_run(run)

    # 2 completed, 1 running, 1 pending, 1 failed = 5 total
    nodes = [
        RunNode(
            id="run-144:n1",
            run_id="run-144",
            node_id="n1",
            block_type="llm",
            status="completed",
            cost_usd=0.01,
            tokens={"prompt": 100, "completion": 50, "total": 150},
        ),
        RunNode(
            id="run-144:n2",
            run_id="run-144",
            node_id="n2",
            block_type="llm",
            status="completed",
            cost_usd=0.02,
            tokens={"prompt": 200, "completion": 100, "total": 300},
        ),
        RunNode(
            id="run-144:n3",
            run_id="run-144",
            node_id="n3",
            block_type="llm",
            status="running",
            cost_usd=0.0,
            tokens={"prompt": 0, "completion": 0, "total": 0},
        ),
        RunNode(
            id="run-144:n4",
            run_id="run-144",
            node_id="n4",
            block_type="condition",
            status="pending",
            cost_usd=0.0,
            tokens={"prompt": 0, "completion": 0, "total": 0},
        ),
        RunNode(
            id="run-144:n5",
            run_id="run-144",
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
        summary = svc.get_node_summary("run-144")
        assert "completed" in summary, "get_node_summary must return 'completed' count"
        assert summary["completed"] == 2

    def test_returns_running_count(self, db_session, seeded_run):
        workflow_repo = Mock()
        svc = RunService(RunRepository(db_session), workflow_repo)
        summary = svc.get_node_summary("run-144")
        assert "running" in summary, "get_node_summary must return 'running' count"
        assert summary["running"] == 1

    def test_returns_pending_count(self, db_session, seeded_run):
        workflow_repo = Mock()
        svc = RunService(RunRepository(db_session), workflow_repo)
        summary = svc.get_node_summary("run-144")
        assert "pending" in summary, "get_node_summary must return 'pending' count"
        assert summary["pending"] == 1

    def test_returns_failed_count(self, db_session, seeded_run):
        workflow_repo = Mock()
        svc = RunService(RunRepository(db_session), workflow_repo)
        summary = svc.get_node_summary("run-144")
        assert "failed" in summary, "get_node_summary must return 'failed' count"
        assert summary["failed"] == 1

    def test_returns_total_count(self, db_session, seeded_run):
        workflow_repo = Mock()
        svc = RunService(RunRepository(db_session), workflow_repo)
        summary = svc.get_node_summary("run-144")
        assert "total" in summary
        assert summary["total"] == 5

    def test_zero_nodes_returns_all_zeros(self, db_session):
        """Run with zero nodes should return all-zero summary."""
        repo = RunRepository(db_session)
        run = Run(id="run-empty", workflow_id="wf-1", workflow_name="Empty WF", task_json="{}")
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


def _make_mock_run(run_id="run_abc", status=RunStatus.running):
    mock_run = Mock()
    mock_run.id = run_id
    mock_run.workflow_id = "wf_1"
    mock_run.workflow_name = "Test Workflow"
    mock_run.status = status
    mock_run.started_at = 1000.0
    mock_run.completed_at = None
    mock_run.duration_s = None
    mock_run.total_cost_usd = 0.03
    mock_run.total_tokens = 500
    mock_run.created_at = 999.0
    return mock_run


class TestRunsRouterNodeSummaryNotHardcoded:
    """The router must pass real per-status counts to NodeSummary, not zeros."""

    def test_get_run_node_summary_has_real_completed_count(self):
        mock_service = Mock()
        mock_service.get_run.return_value = _make_mock_run()
        mock_service.get_node_summary.return_value = {
            "total_cost_usd": 0.03,
            "total_tokens": 500,
            "nodes_count": 5,
            "total": 5,
            "completed": 3,
            "running": 1,
            "pending": 0,
            "failed": 1,
        }
        app.dependency_overrides[get_run_service] = lambda: mock_service
        try:
            response = client.get("/api/runs/run_abc")
            assert response.status_code == 200
            ns = response.json()["node_summary"]
            assert ns["completed"] == 3, (
                f"Expected completed=3 from summary, got {ns['completed']}. "
                "Router is likely hardcoding completed=0."
            )
        finally:
            app.dependency_overrides.clear()

    def test_get_run_node_summary_has_real_running_count(self):
        mock_service = Mock()
        mock_service.get_run.return_value = _make_mock_run()
        mock_service.get_node_summary.return_value = {
            "total_cost_usd": 0.03,
            "total_tokens": 500,
            "nodes_count": 5,
            "total": 5,
            "completed": 3,
            "running": 1,
            "pending": 0,
            "failed": 1,
        }
        app.dependency_overrides[get_run_service] = lambda: mock_service
        try:
            response = client.get("/api/runs/run_abc")
            ns = response.json()["node_summary"]
            assert ns["running"] == 1, (
                f"Expected running=1, got {ns['running']}. Router hardcodes running=0."
            )
        finally:
            app.dependency_overrides.clear()

    def test_get_run_node_summary_has_real_failed_count(self):
        mock_service = Mock()
        mock_service.get_run.return_value = _make_mock_run()
        mock_service.get_node_summary.return_value = {
            "total_cost_usd": 0.03,
            "total_tokens": 500,
            "nodes_count": 5,
            "total": 5,
            "completed": 3,
            "running": 1,
            "pending": 0,
            "failed": 1,
        }
        app.dependency_overrides[get_run_service] = lambda: mock_service
        try:
            response = client.get("/api/runs/run_abc")
            ns = response.json()["node_summary"]
            assert ns["failed"] == 1, (
                f"Expected failed=1, got {ns['failed']}. Router hardcodes failed=0."
            )
        finally:
            app.dependency_overrides.clear()

    def test_list_runs_node_summary_has_real_counts(self):
        """GET /runs should also propagate real per-status counts."""
        mock_service = Mock()
        mock_service.list_runs.return_value = [_make_mock_run()]
        mock_service.get_node_summary.return_value = {
            "total_cost_usd": 0.03,
            "total_tokens": 500,
            "nodes_count": 5,
            "total": 5,
            "completed": 2,
            "running": 2,
            "pending": 1,
            "failed": 0,
        }
        app.dependency_overrides[get_run_service] = lambda: mock_service
        try:
            response = client.get("/api/runs")
            assert response.status_code == 200
            ns = response.json()["items"][0]["node_summary"]
            assert ns["completed"] == 2, (
                f"Expected completed=2, got {ns['completed']}. "
                "list_runs router hardcodes completed=0."
            )
            assert ns["running"] == 2
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 4. Router uses summary cost/tokens (already works for list, verify get too)
# ---------------------------------------------------------------------------


class TestRunsRouterCostAndTokens:
    """GET /runs/{id} must return total_cost_usd and total_tokens from node summary."""

    def test_get_run_returns_aggregated_cost(self):
        mock_service = Mock()
        mock_service.get_run.return_value = _make_mock_run()
        mock_service.get_node_summary.return_value = {
            "total_cost_usd": 0.035,
            "total_tokens": 500,
            "nodes_count": 5,
            "total": 5,
            "completed": 3,
            "running": 1,
            "pending": 0,
            "failed": 1,
        }
        app.dependency_overrides[get_run_service] = lambda: mock_service
        try:
            response = client.get("/api/runs/run_abc")
            data = response.json()
            assert data["total_cost_usd"] == pytest.approx(0.035), (
                "total_cost_usd should come from node summary aggregation"
            )
            assert data["total_tokens"] == 500
        finally:
            app.dependency_overrides.clear()
