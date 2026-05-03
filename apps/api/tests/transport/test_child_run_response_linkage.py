"""Run detail and node responses expose child-run linkage fields."""

from unittest.mock import Mock

from fastapi.testclient import TestClient

from runsight_api.main import app
from runsight_api.transport.deps import get_eval_service, get_run_service
from tests.transport.child_run_helpers import (
    _make_mock_node,
    _make_mock_run,
    _mock_eval_service,
)


class TestRunDetailIncludesLinkageFields:
    """GET /runs/{run_id} response must include parent_run_id, root_run_id, depth."""

    def test_run_detail_includes_linkage_fields(self):
        """A child run's detail response includes parent linkage fields."""
        child = _make_mock_run(
            "run_child",
            parent_run_id="run_parent",
            root_run_id="run_parent",
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
            response = client.get("/api/runs/run_child")
            assert response.status_code == 200
            body = response.json()
            assert "parent_run_id" in body, "RunResponse must include parent_run_id field"
            assert "root_run_id" in body, "RunResponse must include root_run_id field"
            assert "depth" in body, "RunResponse must include depth field"
            assert body["parent_run_id"] == "run_parent"
            assert body["root_run_id"] == "run_parent"
            assert body["depth"] == 1
            assert body["warnings"] == []
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
            "run_parent",
            "step_wf_call",
            block_type="workflow",
            child_run_id="run_child",
            exit_handle="success",
        )
        mock_service = Mock()
        mock_service.get_run_nodes.return_value = [wf_call_node]

        app.dependency_overrides[get_run_service] = lambda: mock_service
        client = TestClient(app, raise_server_exceptions=False)

        try:
            response = client.get("/api/runs/run_parent/nodes")
            assert response.status_code == 200
            body = response.json()
            assert len(body) == 1
            node = body[0]
            assert "child_run_id" in node, "RunNodeResponse must include child_run_id field"
            assert "exit_handle" in node, "RunNodeResponse must include exit_handle field"
            assert node["child_run_id"] == "run_child"
            assert node["exit_handle"] == "success"
        finally:
            app.dependency_overrides.clear()


# ===========================================================================
# 6. RunService has list_children method
# ===========================================================================
