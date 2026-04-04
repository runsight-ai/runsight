"""RED tests for RUN-612: child run drill-down queries.

Problem: The run detail page needs to surface child runs for the current run,
and per-workflow run history needs to surface child-run relationships. Currently
there is no ``GET /runs/{run_id}/children`` endpoint to list child runs for a
given parent.

AC:
1. Current run view surfaces child runs for that run.
2. Per-workflow run history surfaces child-run relationships.
3. Header remains root-run totals only.
4. No UI fallback that reconstructs relationships heuristically.

Changes required:
- New ``GET /runs/{run_id}/children`` endpoint returning a list of RunResponse.
- ``GET /runs/{run_id}`` must include parent_run_id, root_run_id, depth in response.
- ``GET /runs/{run_id}/nodes`` must include child_run_id on workflow-call nodes.
- RunService gains ``list_children(parent_run_id)`` method.
"""

from unittest.mock import Mock

from fastapi.testclient import TestClient

from runsight_api.domain.entities.run import RunStatus
from runsight_api.main import app
from runsight_api.transport.deps import get_eval_service, get_run_service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_RUN_RESPONSE_BASE = dict(
    id="run_612_parent",
    workflow_id="wf_1",
    workflow_name="Workflow wf_1",
    status=RunStatus.completed,
    started_at=100.0,
    completed_at=120.0,
    duration_s=20.0,
    total_cost_usd=0.5,
    total_tokens=500,
    created_at=100.0,
    branch="main",
    source="manual",
    commit_sha=None,
    run_number=1,
    eval_pass_pct=None,
)


def _make_mock_run(
    run_id: str = "run_612_parent",
    *,
    parent_run_id: str | None = None,
    root_run_id: str | None = None,
    depth: int = 0,
    workflow_id: str = "wf_1",
    status: RunStatus = RunStatus.completed,
):
    mock_run = Mock()
    mock_run.id = run_id
    mock_run.workflow_id = workflow_id
    mock_run.workflow_name = f"Workflow {workflow_id}"
    mock_run.status = status
    mock_run.started_at = 100.0
    mock_run.completed_at = 120.0
    mock_run.duration_s = 20.0
    mock_run.total_cost_usd = 0.5
    mock_run.total_tokens = 500
    mock_run.created_at = 100.0
    mock_run.source = "manual"
    mock_run.branch = "main"
    mock_run.commit_sha = None
    mock_run.run_number = 1
    mock_run.eval_pass_pct = None
    mock_run.parent_run_id = parent_run_id
    mock_run.root_run_id = root_run_id
    mock_run.depth = depth
    return mock_run


def _make_mock_node(
    run_id: str = "run_612_parent",
    node_id: str = "step_1",
    *,
    block_type: str = "llm",
    child_run_id: str | None = None,
    exit_handle: str | None = None,
):
    mock_node = Mock()
    mock_node.id = f"{run_id}:{node_id}"
    mock_node.run_id = run_id
    mock_node.node_id = node_id
    mock_node.block_type = block_type
    mock_node.status = "completed"
    mock_node.started_at = 100.0
    mock_node.completed_at = 110.0
    mock_node.duration_s = 10.0
    mock_node.cost_usd = 0.05
    mock_node.tokens = {"prompt": 100, "completion": 50, "total": 150}
    mock_node.error = None
    mock_node.output = None
    mock_node.soul_id = None
    mock_node.model_name = None
    mock_node.eval_score = None
    mock_node.eval_passed = None
    mock_node.eval_results = None
    mock_node.child_run_id = child_run_id
    mock_node.exit_handle = exit_handle
    return mock_node


def _mock_eval_service():
    mock_eval = Mock()
    mock_eval.get_run_regressions.return_value = {"count": 0, "issues": []}
    return mock_eval


def _mock_run_service_with_children(parent_run, child_runs, *, nodes=None, node_summary=None):
    """Build a mock RunService that supports list_children and standard ops."""
    mock_service = Mock()

    mock_service.get_run.return_value = parent_run
    mock_service.list_children.return_value = child_runs
    mock_service.get_run_nodes.return_value = nodes or []
    mock_service.get_node_summary.return_value = node_summary or {
        "total_cost_usd": 0.5,
        "total_tokens": 500,
        "nodes_count": 1,
        "total": 1,
        "completed": 1,
        "running": 0,
        "pending": 0,
        "failed": 0,
    }
    mock_service.get_node_summaries_batch.return_value = {}
    return mock_service


# ===========================================================================
# 1. GET /runs/{run_id}/children endpoint exists and returns 200 with a list
# ===========================================================================


class TestGetChildrenEndpointExists:
    """The ``GET /runs/{run_id}/children`` endpoint must exist and return a list."""

    def test_get_children_endpoint_exists(self):
        """GET /runs/{run_id}/children returns 200 with a list response."""
        parent = _make_mock_run("run_612_parent")
        child = _make_mock_run(
            "run_612_child",
            parent_run_id="run_612_parent",
            root_run_id="run_612_parent",
            depth=1,
        )

        mock_service = _mock_run_service_with_children(parent, [child])
        mock_eval = _mock_eval_service()

        app.dependency_overrides[get_run_service] = lambda: mock_service
        app.dependency_overrides[get_eval_service] = lambda: mock_eval
        client = TestClient(app, raise_server_exceptions=False)

        try:
            response = client.get("/api/runs/run_612_parent/children")
            assert response.status_code == 200, (
                f"Expected 200 from GET /runs/{{run_id}}/children, got {response.status_code}. "
                "The endpoint likely does not exist yet."
            )
            body = response.json()
            assert isinstance(body, list), (
                f"Expected a list response from /children, got {type(body).__name__}"
            )
        finally:
            app.dependency_overrides.clear()


# ===========================================================================
# 2. GET /runs/{run_id}/children returns only child runs
# ===========================================================================


class TestGetChildrenReturnsChildRunsOnly:
    """The children endpoint must return only runs whose parent_run_id matches."""

    def test_get_children_returns_child_runs_only(self):
        """Create parent + child + unrelated. Endpoint returns only the child."""
        parent = _make_mock_run("run_612_parent")
        child = _make_mock_run(
            "run_612_child",
            parent_run_id="run_612_parent",
            root_run_id="run_612_parent",
            depth=1,
        )
        # The unrelated run should NOT appear — it's not set up on the mock
        # service's list_children return.
        mock_service = _mock_run_service_with_children(parent, [child])
        mock_eval = _mock_eval_service()

        app.dependency_overrides[get_run_service] = lambda: mock_service
        app.dependency_overrides[get_eval_service] = lambda: mock_eval
        client = TestClient(app, raise_server_exceptions=False)

        try:
            response = client.get("/api/runs/run_612_parent/children")
            assert response.status_code == 200
            body = response.json()
            assert len(body) == 1, f"Expected exactly 1 child run, got {len(body)}"
            assert body[0]["id"] == "run_612_child"
            assert body[0]["parent_run_id"] == "run_612_parent"
            assert body[0]["root_run_id"] == "run_612_parent"
            assert body[0]["depth"] == 1
        finally:
            app.dependency_overrides.clear()


# ===========================================================================
# 3. GET /runs/{run_id}/children returns empty list for leaf runs
# ===========================================================================


class TestGetChildrenEmptyForLeafRun:
    """A run with no children returns an empty list from the children endpoint."""

    def test_get_children_empty_for_leaf_run(self):
        """Leaf run (no children) returns []."""
        leaf = _make_mock_run("run_612_leaf")
        mock_service = _mock_run_service_with_children(leaf, [])
        mock_eval = _mock_eval_service()

        app.dependency_overrides[get_run_service] = lambda: mock_service
        app.dependency_overrides[get_eval_service] = lambda: mock_eval
        client = TestClient(app, raise_server_exceptions=False)

        try:
            response = client.get("/api/runs/run_612_leaf/children")
            assert response.status_code == 200
            body = response.json()
            assert body == [], f"Expected empty list for leaf run, got {body}"
        finally:
            app.dependency_overrides.clear()


# ===========================================================================
# 4. GET /runs/{run_id} includes linkage fields in response
# ===========================================================================


class TestRunDetailIncludesLinkageFields:
    """GET /runs/{run_id} response must include parent_run_id, root_run_id, depth."""

    def test_run_detail_includes_linkage_fields(self):
        """A child run's detail response includes parent linkage fields."""
        child = _make_mock_run(
            "run_612_child",
            parent_run_id="run_612_parent",
            root_run_id="run_612_parent",
            depth=1,
        )
        mock_service = Mock()
        mock_service.get_run.return_value = child
        mock_service.get_node_summary.return_value = {
            "total_cost_usd": 0.5,
            "total_tokens": 500,
            "nodes_count": 1,
            "total": 1,
            "completed": 1,
            "running": 0,
            "pending": 0,
            "failed": 0,
        }
        mock_eval = _mock_eval_service()

        app.dependency_overrides[get_run_service] = lambda: mock_service
        app.dependency_overrides[get_eval_service] = lambda: mock_eval
        client = TestClient(app, raise_server_exceptions=False)

        try:
            response = client.get("/api/runs/run_612_child")
            assert response.status_code == 200
            body = response.json()
            assert "parent_run_id" in body, "RunResponse must include parent_run_id field"
            assert "root_run_id" in body, "RunResponse must include root_run_id field"
            assert "depth" in body, "RunResponse must include depth field"
            assert body["parent_run_id"] == "run_612_parent"
            assert body["root_run_id"] == "run_612_parent"
            assert body["depth"] == 1
        finally:
            app.dependency_overrides.clear()


# ===========================================================================
# 5. GET /runs/{run_id}/nodes includes child_run_id on workflow-call nodes
# ===========================================================================


class TestRunNodesIncludeChildRunId:
    """GET /runs/{run_id}/nodes must include child_run_id on workflow-call nodes."""

    def test_run_nodes_include_child_run_id(self):
        """A workflow-call node's response includes child_run_id."""
        wf_call_node = _make_mock_node(
            "run_612_parent",
            "step_wf_call",
            block_type="workflow",
            child_run_id="run_612_child",
            exit_handle="success",
        )
        mock_service = Mock()
        mock_service.get_run_nodes.return_value = [wf_call_node]

        app.dependency_overrides[get_run_service] = lambda: mock_service
        client = TestClient(app, raise_server_exceptions=False)

        try:
            response = client.get("/api/runs/run_612_parent/nodes")
            assert response.status_code == 200
            body = response.json()
            assert len(body) == 1
            node = body[0]
            assert "child_run_id" in node, "RunNodeResponse must include child_run_id field"
            assert "exit_handle" in node, "RunNodeResponse must include exit_handle field"
            assert node["child_run_id"] == "run_612_child"
            assert node["exit_handle"] == "success"
        finally:
            app.dependency_overrides.clear()


# ===========================================================================
# 6. RunService has list_children method
# ===========================================================================


class TestRunServiceListChildren:
    """RunService must expose a list_children(parent_run_id) method that queries
    the repository for runs with a matching parent_run_id."""

    def test_run_service_has_list_children_method(self):
        """RunService must have a list_children method."""
        from runsight_api.logic.services.run_service import RunService

        assert hasattr(RunService, "list_children"), (
            "RunService must expose a list_children method for the children endpoint"
        )

    def test_run_service_list_children_returns_only_direct_children(self):
        """list_children must query and return only runs with matching parent_run_id."""
        from runsight_api.logic.services.run_service import RunService

        mock_repo = Mock()
        mock_workflow_repo = Mock()

        child = _make_mock_run(
            "run_612_child",
            parent_run_id="run_612_parent",
            root_run_id="run_612_parent",
            depth=1,
        )
        mock_repo.list_children.return_value = [child]

        service = RunService(mock_repo, mock_workflow_repo)
        children = service.list_children("run_612_parent")

        assert len(children) == 1
        assert children[0].id == "run_612_child"
        mock_repo.list_children.assert_called_once_with("run_612_parent")


# ===========================================================================
# 7. RunRepository has list_children method
# ===========================================================================


class TestRunRepositoryListChildren:
    """RunRepository must expose a list_children(parent_run_id) method."""

    def test_run_repository_has_list_children_method(self):
        """RunRepository must have a list_children method."""
        from runsight_api.data.repositories.run_repo import RunRepository

        assert hasattr(RunRepository, "list_children"), (
            "RunRepository must expose a list_children method"
        )
