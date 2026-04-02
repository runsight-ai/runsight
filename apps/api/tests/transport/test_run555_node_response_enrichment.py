"""RUN-555: RunNodeResponse enrichment with 6 missing fields.

Red-team tests — these MUST fail until the implementation adds output,
soul_id, model_name, eval_score, eval_passed, eval_results to:
  1. RunNodeResponse (Pydantic schema)
  2. get_run_nodes() response construction
"""

from unittest.mock import Mock

from fastapi.testclient import TestClient

from runsight_api.main import app
from runsight_api.transport.deps import get_run_service

client = TestClient(app)


def _make_mock_node(
    *,
    node_id: str = "step_1",
    run_id: str = "run_555",
    output: str | None = None,
    soul_id: str | None = None,
    model_name: str | None = None,
    eval_score: float | None = None,
    eval_passed: bool | None = None,
    eval_results: dict | None = None,
):
    """Create a mock RunNode entity with the 6 enrichment fields."""
    node = Mock()
    node.id = f"{run_id}:{node_id}"
    node.run_id = run_id
    node.node_id = node_id
    node.block_type = "llm"
    node.status = "completed"
    node.started_at = 1000.0
    node.completed_at = 2000.0
    node.duration_s = 1.0
    node.cost_usd = 0.05
    node.tokens = {"prompt": 100, "completion": 50, "total": 150}
    node.error = None
    # --- the 6 enrichment fields ---
    node.output = output
    node.soul_id = soul_id
    node.model_name = model_name
    node.eval_score = eval_score
    node.eval_passed = eval_passed
    node.eval_results = eval_results
    return node


# ---------------------------------------------------------------------------
# 1. RunNodeResponse schema accepts the 6 new fields
# ---------------------------------------------------------------------------


class TestRunNodeResponseSchemaFields:
    """RunNodeResponse Pydantic schema must declare all 6 enrichment fields."""

    def test_schema_accepts_output_field(self):
        from runsight_api.transport.schemas.runs import RunNodeResponse

        resp = RunNodeResponse(
            id="r:s",
            run_id="r",
            node_id="s",
            block_type="llm",
            status="completed",
            started_at=1.0,
            completed_at=2.0,
            duration_seconds=1.0,
            cost_usd=0.0,
            tokens={},
            error=None,
            output="Hello world",
        )
        assert resp.output == "Hello world"

    def test_schema_accepts_soul_id_field(self):
        from runsight_api.transport.schemas.runs import RunNodeResponse

        resp = RunNodeResponse(
            id="r:s",
            run_id="r",
            node_id="s",
            block_type="llm",
            status="completed",
            started_at=1.0,
            completed_at=2.0,
            duration_seconds=1.0,
            cost_usd=0.0,
            tokens={},
            error=None,
            soul_id="soul_analyst",
        )
        assert resp.soul_id == "soul_analyst"

    def test_schema_accepts_model_name_field(self):
        from runsight_api.transport.schemas.runs import RunNodeResponse

        resp = RunNodeResponse(
            id="r:s",
            run_id="r",
            node_id="s",
            block_type="llm",
            status="completed",
            started_at=1.0,
            completed_at=2.0,
            duration_seconds=1.0,
            cost_usd=0.0,
            tokens={},
            error=None,
            model_name="gpt-4.1",
        )
        assert resp.model_name == "gpt-4.1"

    def test_schema_accepts_eval_score_field(self):
        from runsight_api.transport.schemas.runs import RunNodeResponse

        resp = RunNodeResponse(
            id="r:s",
            run_id="r",
            node_id="s",
            block_type="llm",
            status="completed",
            started_at=1.0,
            completed_at=2.0,
            duration_seconds=1.0,
            cost_usd=0.0,
            tokens={},
            error=None,
            eval_score=0.95,
        )
        assert resp.eval_score == 0.95

    def test_schema_accepts_eval_passed_field(self):
        from runsight_api.transport.schemas.runs import RunNodeResponse

        resp = RunNodeResponse(
            id="r:s",
            run_id="r",
            node_id="s",
            block_type="llm",
            status="completed",
            started_at=1.0,
            completed_at=2.0,
            duration_seconds=1.0,
            cost_usd=0.0,
            tokens={},
            error=None,
            eval_passed=True,
        )
        assert resp.eval_passed is True

    def test_schema_accepts_eval_results_field(self):
        from runsight_api.transport.schemas.runs import RunNodeResponse

        results = {"assertion_1": {"passed": True}, "assertion_2": {"passed": False}}
        resp = RunNodeResponse(
            id="r:s",
            run_id="r",
            node_id="s",
            block_type="llm",
            status="completed",
            started_at=1.0,
            completed_at=2.0,
            duration_seconds=1.0,
            cost_usd=0.0,
            tokens={},
            error=None,
            eval_results=results,
        )
        assert resp.eval_results == results

    def test_all_six_fields_default_to_none(self):
        from runsight_api.transport.schemas.runs import RunNodeResponse

        resp = RunNodeResponse(
            id="r:s",
            run_id="r",
            node_id="s",
            block_type="llm",
            status="pending",
            started_at=None,
            completed_at=None,
            duration_seconds=None,
            cost_usd=0.0,
            tokens={},
            error=None,
        )
        assert resp.output is None
        assert resp.soul_id is None
        assert resp.model_name is None
        assert resp.eval_score is None
        assert resp.eval_passed is None
        assert resp.eval_results is None


# ---------------------------------------------------------------------------
# 2. GET /api/runs/:id/nodes returns the 6 fields when populated
# ---------------------------------------------------------------------------


class TestGetRunNodesEnrichedResponse:
    """GET /api/runs/:id/nodes must include the 6 enrichment fields."""

    def test_nodes_response_includes_output(self):
        node = _make_mock_node(output="The capital of France is Paris.")
        mock_service = Mock()
        mock_service.get_run_nodes.return_value = [node]
        app.dependency_overrides[get_run_service] = lambda: mock_service

        try:
            response = client.get("/api/runs/run_555/nodes")
            assert response.status_code == 200
            body = response.json()
            assert len(body) == 1
            assert body[0]["output"] == "The capital of France is Paris."
        finally:
            app.dependency_overrides.clear()

    def test_nodes_response_includes_soul_id(self):
        node = _make_mock_node(soul_id="soul_analyst")
        mock_service = Mock()
        mock_service.get_run_nodes.return_value = [node]
        app.dependency_overrides[get_run_service] = lambda: mock_service

        try:
            response = client.get("/api/runs/run_555/nodes")
            assert response.status_code == 200
            assert response.json()[0]["soul_id"] == "soul_analyst"
        finally:
            app.dependency_overrides.clear()

    def test_nodes_response_includes_model_name(self):
        node = _make_mock_node(model_name="claude-3-5-sonnet")
        mock_service = Mock()
        mock_service.get_run_nodes.return_value = [node]
        app.dependency_overrides[get_run_service] = lambda: mock_service

        try:
            response = client.get("/api/runs/run_555/nodes")
            assert response.status_code == 200
            assert response.json()[0]["model_name"] == "claude-3-5-sonnet"
        finally:
            app.dependency_overrides.clear()

    def test_nodes_response_includes_eval_score(self):
        node = _make_mock_node(eval_score=0.87)
        mock_service = Mock()
        mock_service.get_run_nodes.return_value = [node]
        app.dependency_overrides[get_run_service] = lambda: mock_service

        try:
            response = client.get("/api/runs/run_555/nodes")
            assert response.status_code == 200
            assert response.json()[0]["eval_score"] == 0.87
        finally:
            app.dependency_overrides.clear()

    def test_nodes_response_includes_eval_passed(self):
        node = _make_mock_node(eval_passed=True)
        mock_service = Mock()
        mock_service.get_run_nodes.return_value = [node]
        app.dependency_overrides[get_run_service] = lambda: mock_service

        try:
            response = client.get("/api/runs/run_555/nodes")
            assert response.status_code == 200
            assert response.json()[0]["eval_passed"] is True
        finally:
            app.dependency_overrides.clear()

    def test_nodes_response_includes_eval_results_dict(self):
        eval_results = {
            "coherence": {"score": 0.9, "passed": True},
            "factuality": {"score": 0.7, "passed": False},
        }
        node = _make_mock_node(eval_results=eval_results)
        mock_service = Mock()
        mock_service.get_run_nodes.return_value = [node]
        app.dependency_overrides[get_run_service] = lambda: mock_service

        try:
            response = client.get("/api/runs/run_555/nodes")
            assert response.status_code == 200
            assert response.json()[0]["eval_results"] == eval_results
        finally:
            app.dependency_overrides.clear()

    def test_nodes_response_all_six_fields_populated(self):
        """All 6 enrichment fields present in a single response object."""
        eval_results = {"check_1": {"passed": True}}
        node = _make_mock_node(
            output="Full LLM response text here",
            soul_id="soul_planner",
            model_name="gpt-4.1",
            eval_score=0.95,
            eval_passed=True,
            eval_results=eval_results,
        )
        mock_service = Mock()
        mock_service.get_run_nodes.return_value = [node]
        app.dependency_overrides[get_run_service] = lambda: mock_service

        try:
            response = client.get("/api/runs/run_555/nodes")
            assert response.status_code == 200
            body = response.json()[0]
            assert body["output"] == "Full LLM response text here"
            assert body["soul_id"] == "soul_planner"
            assert body["model_name"] == "gpt-4.1"
            assert body["eval_score"] == 0.95
            assert body["eval_passed"] is True
            assert body["eval_results"] == eval_results
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 3. Null semantics: fields are null when not populated
# ---------------------------------------------------------------------------


class TestGetRunNodesNullFields:
    """Nodes that never executed or lack eval must return null for all 6 fields."""

    def test_pending_node_returns_all_six_fields_as_null(self):
        """A pending node that never ran should have all 6 enrichment fields as null."""
        node = _make_mock_node()
        node.status = "pending"
        node.started_at = None
        node.completed_at = None
        node.duration_s = None
        # All 6 enrichment fields are None on the mock (default)
        mock_service = Mock()
        mock_service.get_run_nodes.return_value = [node]
        app.dependency_overrides[get_run_service] = lambda: mock_service

        try:
            response = client.get("/api/runs/run_555/nodes")
            assert response.status_code == 200
            body = response.json()[0]
            assert body["output"] is None
            assert body["soul_id"] is None
            assert body["model_name"] is None
            assert body["eval_score"] is None
            assert body["eval_passed"] is None
            assert body["eval_results"] is None
        finally:
            app.dependency_overrides.clear()

    def test_completed_node_without_eval_returns_eval_fields_as_null(self):
        """A completed node without eval should have eval_* fields as null."""
        node = _make_mock_node(
            output="Some output",
            soul_id="soul_worker",
            model_name="gpt-4o-mini",
        )
        # eval_score, eval_passed, eval_results remain None
        mock_service = Mock()
        mock_service.get_run_nodes.return_value = [node]
        app.dependency_overrides[get_run_service] = lambda: mock_service

        try:
            response = client.get("/api/runs/run_555/nodes")
            assert response.status_code == 200
            body = response.json()[0]
            # output, soul_id, model_name are populated
            assert body["output"] == "Some output"
            assert body["soul_id"] == "soul_worker"
            assert body["model_name"] == "gpt-4o-mini"
            # eval fields are null
            assert body["eval_score"] is None
            assert body["eval_passed"] is None
            assert body["eval_results"] is None
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 4. Edge case: output can be large (no truncation)
# ---------------------------------------------------------------------------


class TestGetRunNodesLargeOutput:
    """Output field can be large — no truncation should occur."""

    def test_large_output_is_returned_without_truncation(self):
        large_output = "x" * 50_000  # 50 KB of text
        node = _make_mock_node(output=large_output)
        mock_service = Mock()
        mock_service.get_run_nodes.return_value = [node]
        app.dependency_overrides[get_run_service] = lambda: mock_service

        try:
            response = client.get("/api/runs/run_555/nodes")
            assert response.status_code == 200
            assert response.json()[0]["output"] == large_output
            assert len(response.json()[0]["output"]) == 50_000
        finally:
            app.dependency_overrides.clear()
