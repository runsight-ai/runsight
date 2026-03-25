"""Red-team tests for RUN-316: Delta Detection + Regression API.

Tests cover:
- AC1: GET /api/runs/{run_id}/eval returns per-node assertion results
- AC2: Each node includes delta vs baseline (cost_pct, tokens_pct, score_delta, baseline_run_count)
- AC3: If no baseline exists (first run of this soul_version), delta is null
- AC4: GET /api/souls/{soul_id}/eval/history returns time-series of eval scores
- AC5: History endpoint shows soul_version boundaries (when prompt changed)
- AC6: Both endpoints return 404 for non-existent run/soul
- AC7: Response is JSON-serializable
"""

import pytest
from unittest.mock import Mock

from fastapi.testclient import TestClient

from runsight_api.main import app

# -- Imports that will fail until Green creates these modules ----------------
from runsight_api.logic.services.eval_service import EvalService
from runsight_api.transport.schemas.eval import (
    EvalDelta,
    NodeEvalResult,
    RunEvalResponse,
    SoulEvalHistoryResponse,
    SoulVersionEntry,
)
from runsight_api.transport.deps import get_eval_service

client = TestClient(app)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _make_node_eval_result(*, node_id="analyze", with_delta=True):
    """Build a NodeEvalResult-shaped dict as the service would return."""
    delta = None
    if with_delta:
        delta = EvalDelta(
            cost_pct=-12.3,
            tokens_pct=-8.1,
            score_delta=0.02,
            baseline_run_count=487,
        )
    return NodeEvalResult(
        node_id=node_id,
        block_id=node_id,
        soul_id="researcher_v1",
        prompt_hash="sha256:abc123",
        soul_version="sha256:def456",
        eval_score=0.95,
        passed=True,
        assertions=[
            {"type": "contains", "passed": True, "score": 1.0, "reason": "ok"},
        ],
        delta=delta,
    )


def _make_run_eval_response(*, nodes=None):
    """Build a full RunEvalResponse."""
    if nodes is None:
        nodes = [_make_node_eval_result()]
    return RunEvalResponse(
        run_id="run_abc123",
        aggregate_score=0.92,
        passed=True,
        nodes=nodes,
    )


def _make_version_entry(**overrides):
    defaults = dict(
        soul_version="sha256:abc123",
        avg_score=0.94,
        avg_cost=0.003,
        run_count=487,
        first_seen="2026-03-20T00:00:00",
        last_seen="2026-03-25T00:00:00",
    )
    defaults.update(overrides)
    return SoulVersionEntry(**defaults)


# ===========================================================================
# TestEvalSchemas — Pydantic model validation (AC7: JSON-serializable)
# ===========================================================================


class TestEvalSchemas:
    """Test that the new Pydantic response schemas validate and serialize."""

    def test_eval_delta_validates(self):
        """EvalDelta model accepts valid field values."""
        delta = EvalDelta(
            cost_pct=-12.3,
            tokens_pct=-8.1,
            score_delta=0.02,
            baseline_run_count=487,
        )
        assert delta.cost_pct == pytest.approx(-12.3)
        assert delta.tokens_pct == pytest.approx(-8.1)
        assert delta.score_delta == pytest.approx(0.02)
        assert delta.baseline_run_count == 487

    def test_node_eval_result_with_delta_validates(self):
        """NodeEvalResult with a delta object validates."""
        node = _make_node_eval_result(with_delta=True)
        assert node.eval_score == pytest.approx(0.95)
        assert node.passed is True
        assert node.delta is not None
        assert node.delta.baseline_run_count == 487

    def test_node_eval_result_with_null_delta_validates(self):
        """NodeEvalResult with delta=None validates (AC3)."""
        node = _make_node_eval_result(with_delta=False)
        assert node.delta is None

    def test_run_eval_response_serializes_to_json(self):
        """RunEvalResponse round-trips to JSON dict (AC7)."""
        resp = _make_run_eval_response()
        data = resp.model_dump(mode="json")
        assert data["run_id"] == "run_abc123"
        assert isinstance(data["nodes"], list)
        assert len(data["nodes"]) == 1
        assert data["nodes"][0]["node_id"] == "analyze"
        assert data["aggregate_score"] == pytest.approx(0.92)
        assert data["passed"] is True

    def test_soul_version_entry_validates(self):
        """SoulVersionEntry model validates with all fields."""
        entry = _make_version_entry()
        assert entry.soul_version == "sha256:abc123"
        assert entry.avg_score == pytest.approx(0.94)
        assert entry.run_count == 487

    def test_soul_eval_history_response_serializes_to_json(self):
        """SoulEvalHistoryResponse round-trips to JSON dict (AC7)."""
        resp = SoulEvalHistoryResponse(
            soul_id="researcher_v1",
            versions=[_make_version_entry()],
        )
        data = resp.model_dump(mode="json")
        assert data["soul_id"] == "researcher_v1"
        assert isinstance(data["versions"], list)
        assert len(data["versions"]) == 1
        assert data["versions"][0]["run_count"] == 487


# ===========================================================================
# TestEvalService — get_run_eval (AC1, AC2, AC3)
# ===========================================================================


class TestEvalServiceGetRunEval:
    """Test EvalService.get_run_eval() business logic."""

    def test_returns_per_node_results_for_run_with_eval_data(self):
        """AC1: returns per-node assertion results for a run."""
        repo = Mock()
        # Simulate RunNodes with eval data
        node1 = Mock(
            node_id="analyze",
            block_type="llm",
            soul_id="researcher_v1",
            prompt_hash="sha256:abc",
            soul_version="sha256:def",
            eval_score=0.95,
            eval_passed=True,
            eval_results={
                "assertions": [{"type": "contains", "passed": True, "score": 1.0, "reason": "ok"}]
            },
            cost_usd=0.005,
            tokens={"prompt": 100, "completion": 50, "total": 150},
        )
        repo.list_nodes_for_run.return_value = [node1]
        repo.get_run.return_value = Mock(id="run_abc123")
        repo.get_baseline.return_value = None

        service = EvalService(repo)
        result = service.get_run_eval("run_abc123")

        assert result is not None
        assert result.run_id == "run_abc123"
        assert len(result.nodes) == 1
        assert result.nodes[0].node_id == "analyze"

    def test_includes_eval_fields_per_node(self):
        """AC1: each node contains eval_score, passed, assertions."""
        repo = Mock()
        node1 = Mock(
            node_id="analyze",
            block_type="llm",
            soul_id="researcher_v1",
            prompt_hash="sha256:abc",
            soul_version="sha256:def",
            eval_score=0.95,
            eval_passed=True,
            eval_results={
                "assertions": [{"type": "contains", "passed": True, "score": 1.0, "reason": "ok"}]
            },
            cost_usd=0.005,
            tokens={"prompt": 100, "completion": 50, "total": 150},
        )
        repo.list_nodes_for_run.return_value = [node1]
        repo.get_run.return_value = Mock(id="run_abc123")
        repo.get_baseline.return_value = None

        service = EvalService(repo)
        result = service.get_run_eval("run_abc123")

        node = result.nodes[0]
        assert node.eval_score == pytest.approx(0.95)
        assert node.passed is True
        assert len(node.assertions) == 1

    def test_computes_aggregate_score_from_nodes(self):
        """Aggregate score is the mean of node eval_scores."""
        repo = Mock()
        node1 = Mock(
            node_id="analyze",
            block_type="llm",
            soul_id="s1",
            prompt_hash="h1",
            soul_version="v1",
            eval_score=0.90,
            eval_passed=True,
            eval_results={"assertions": []},
            cost_usd=0.01,
            tokens={"total": 100},
        )
        node2 = Mock(
            node_id="summarize",
            block_type="llm",
            soul_id="s1",
            prompt_hash="h1",
            soul_version="v1",
            eval_score=0.80,
            eval_passed=True,
            eval_results={"assertions": []},
            cost_usd=0.02,
            tokens={"total": 200},
        )
        repo.list_nodes_for_run.return_value = [node1, node2]
        repo.get_run.return_value = Mock(id="run_123")
        repo.get_baseline.return_value = None

        service = EvalService(repo)
        result = service.get_run_eval("run_123")

        # Mean of 0.90 and 0.80 = 0.85
        assert result.aggregate_score == pytest.approx(0.85)

    def test_includes_delta_when_baseline_exists(self):
        """AC2: delta populated with cost_pct, tokens_pct, score_delta, baseline_run_count."""
        repo = Mock()
        node1 = Mock(
            node_id="analyze",
            block_type="llm",
            soul_id="researcher_v1",
            prompt_hash="sha256:abc",
            soul_version="sha256:def",
            eval_score=0.95,
            eval_passed=True,
            eval_results={"assertions": []},
            cost_usd=0.0044,
            tokens={"total": 138},
        )
        repo.list_nodes_for_run.return_value = [node1]
        repo.get_run.return_value = Mock(id="run_abc123")

        from runsight_api.domain.entities.run import BaselineStats

        repo.get_baseline.return_value = BaselineStats(
            avg_cost=0.005,
            avg_tokens=150.0,
            avg_score=0.93,
            run_count=487,
        )

        service = EvalService(repo)
        result = service.get_run_eval("run_abc123")

        delta = result.nodes[0].delta
        assert delta is not None
        assert delta.baseline_run_count == 487
        assert isinstance(delta.cost_pct, float)
        assert isinstance(delta.tokens_pct, float)
        assert isinstance(delta.score_delta, float)

    def test_delta_is_none_when_no_baseline(self):
        """AC3: delta is null when this is the first run of a soul_version."""
        repo = Mock()
        node1 = Mock(
            node_id="analyze",
            block_type="llm",
            soul_id="researcher_v1",
            prompt_hash="sha256:abc",
            soul_version="sha256:def",
            eval_score=0.95,
            eval_passed=True,
            eval_results={"assertions": []},
            cost_usd=0.005,
            tokens={"total": 150},
        )
        repo.list_nodes_for_run.return_value = [node1]
        repo.get_run.return_value = Mock(id="run_abc123")
        repo.get_baseline.return_value = None

        service = EvalService(repo)
        result = service.get_run_eval("run_abc123")

        assert result.nodes[0].delta is None

    def test_returns_none_for_nonexistent_run(self):
        """AC6: returns None for a non-existent run_id."""
        repo = Mock()
        repo.get_run.return_value = None

        service = EvalService(repo)
        result = service.get_run_eval("nonexistent_run")

        assert result is None

    def test_skips_nodes_without_eval_data(self):
        """Nodes that lack eval_score are excluded from the response."""
        repo = Mock()
        node_with_eval = Mock(
            node_id="analyze",
            block_type="llm",
            soul_id="s1",
            prompt_hash="h1",
            soul_version="v1",
            eval_score=0.90,
            eval_passed=True,
            eval_results={"assertions": []},
            cost_usd=0.01,
            tokens={"total": 100},
        )
        node_without_eval = Mock(
            node_id="route",
            block_type="router",
            soul_id=None,
            prompt_hash=None,
            soul_version=None,
            eval_score=None,
            eval_passed=None,
            eval_results=None,
            cost_usd=0.0,
            tokens={"total": 0},
        )
        repo.list_nodes_for_run.return_value = [node_with_eval, node_without_eval]
        repo.get_run.return_value = Mock(id="run_123")
        repo.get_baseline.return_value = None

        service = EvalService(repo)
        result = service.get_run_eval("run_123")

        assert len(result.nodes) == 1
        assert result.nodes[0].node_id == "analyze"

    def test_passed_is_false_when_any_node_fails(self):
        """Run-level passed=False when at least one node eval_passed is False."""
        repo = Mock()
        node_pass = Mock(
            node_id="analyze",
            block_type="llm",
            soul_id="s1",
            prompt_hash="h1",
            soul_version="v1",
            eval_score=0.95,
            eval_passed=True,
            eval_results={"assertions": []},
            cost_usd=0.01,
            tokens={"total": 100},
        )
        node_fail = Mock(
            node_id="summarize",
            block_type="llm",
            soul_id="s1",
            prompt_hash="h1",
            soul_version="v1",
            eval_score=0.30,
            eval_passed=False,
            eval_results={"assertions": []},
            cost_usd=0.01,
            tokens={"total": 100},
        )
        repo.list_nodes_for_run.return_value = [node_pass, node_fail]
        repo.get_run.return_value = Mock(id="run_123")
        repo.get_baseline.return_value = None

        service = EvalService(repo)
        result = service.get_run_eval("run_123")

        assert result.passed is False


# ===========================================================================
# TestEvalServiceGetSoulHistory — (AC4, AC5)
# ===========================================================================


class TestEvalServiceGetSoulHistory:
    """Test EvalService.get_soul_eval_history() business logic."""

    def test_returns_versions_grouped_by_soul_version(self):
        """AC4+AC5: returns entries grouped by soul_version."""
        repo = Mock()
        # Two nodes with different soul_versions
        node1 = Mock(
            soul_id="researcher_v1",
            soul_version="sha256:v1",
            eval_score=0.90,
            cost_usd=0.003,
            created_at=1710892800.0,
        )
        node2 = Mock(
            soul_id="researcher_v1",
            soul_version="sha256:v1",
            eval_score=0.92,
            cost_usd=0.004,
            created_at=1710979200.0,
        )
        node3 = Mock(
            soul_id="researcher_v1",
            soul_version="sha256:v2",
            eval_score=0.95,
            cost_usd=0.002,
            created_at=1711065600.0,
        )
        repo.list_nodes_for_soul.return_value = [node1, node2, node3]

        service = EvalService(repo)
        result = service.get_soul_eval_history("researcher_v1")

        assert result is not None
        assert result.soul_id == "researcher_v1"
        assert len(result.versions) == 2

    def test_returns_empty_versions_for_nonexistent_soul(self):
        """AC6: returns empty versions list for unknown soul_id."""
        repo = Mock()
        repo.list_nodes_for_soul.return_value = []

        service = EvalService(repo)
        result = service.get_soul_eval_history("nonexistent_soul")

        assert result is not None
        assert result.soul_id == "nonexistent_soul"
        assert result.versions == []

    def test_includes_avg_score_avg_cost_run_count_per_version(self):
        """AC4: each version entry has avg_score, avg_cost, run_count."""
        repo = Mock()
        node1 = Mock(
            soul_id="s1",
            soul_version="sha256:v1",
            eval_score=0.90,
            cost_usd=0.002,
            created_at=1710892800.0,
        )
        node2 = Mock(
            soul_id="s1",
            soul_version="sha256:v1",
            eval_score=0.80,
            cost_usd=0.004,
            created_at=1710979200.0,
        )
        repo.list_nodes_for_soul.return_value = [node1, node2]

        service = EvalService(repo)
        result = service.get_soul_eval_history("s1")

        version = result.versions[0]
        assert version.avg_score == pytest.approx(0.85)
        assert version.avg_cost == pytest.approx(0.003)
        assert version.run_count == 2

    def test_orders_versions_by_first_seen(self):
        """AC5: versions ordered chronologically by first_seen."""
        repo = Mock()
        # v2 appears earlier in time than v1 — output should respect time order
        node_v2 = Mock(
            soul_id="s1",
            soul_version="sha256:v2",
            eval_score=0.95,
            cost_usd=0.002,
            created_at=1710806400.0,
        )
        node_v1 = Mock(
            soul_id="s1",
            soul_version="sha256:v1",
            eval_score=0.90,
            cost_usd=0.003,
            created_at=1710892800.0,
        )
        repo.list_nodes_for_soul.return_value = [node_v2, node_v1]

        service = EvalService(repo)
        result = service.get_soul_eval_history("s1")

        assert len(result.versions) == 2
        # First entry should be the earlier soul_version
        assert result.versions[0].first_seen <= result.versions[1].first_seen

    def test_includes_first_seen_and_last_seen_timestamps(self):
        """AC4: each version entry has first_seen and last_seen."""
        repo = Mock()
        node1 = Mock(
            soul_id="s1",
            soul_version="sha256:v1",
            eval_score=0.90,
            cost_usd=0.003,
            created_at=1710892800.0,
        )
        node2 = Mock(
            soul_id="s1",
            soul_version="sha256:v1",
            eval_score=0.92,
            cost_usd=0.004,
            created_at=1710979200.0,
        )
        repo.list_nodes_for_soul.return_value = [node1, node2]

        service = EvalService(repo)
        result = service.get_soul_eval_history("s1")

        version = result.versions[0]
        assert version.first_seen is not None
        assert version.last_seen is not None
        assert version.first_seen <= version.last_seen


# ===========================================================================
# TestEvalRouter — route registration (AC1, AC4)
# ===========================================================================


class TestEvalRouter:
    """Verify eval router module exists and routes are registered."""

    def test_eval_router_module_importable(self):
        """The eval router module must exist."""
        from runsight_api.transport.routers import eval as eval_router_mod

        assert hasattr(eval_router_mod, "router")

    def test_get_run_eval_route_registered(self):
        """GET /api/runs/{run_id}/eval must be a registered route."""
        routes = [r.path for r in app.routes]
        assert "/api/runs/{run_id}/eval" in routes

    def test_get_soul_eval_history_route_registered(self):
        """GET /api/souls/{soul_id}/eval/history must be a registered route."""
        routes = [r.path for r in app.routes]
        assert "/api/souls/{soul_id}/eval/history" in routes

    def test_get_run_eval_returns_404_for_missing_run(self):
        """AC6: GET /api/runs/{run_id}/eval returns 404 for non-existent run."""
        mock_service = Mock()
        mock_service.get_run_eval.return_value = None
        app.dependency_overrides[get_eval_service] = lambda: mock_service

        response = client.get("/api/runs/nonexistent/eval")
        assert response.status_code == 404
        app.dependency_overrides.clear()

    def test_get_run_eval_returns_200_with_data(self):
        """AC1: GET /api/runs/{run_id}/eval returns eval data."""
        mock_service = Mock()
        mock_service.get_run_eval.return_value = _make_run_eval_response()
        app.dependency_overrides[get_eval_service] = lambda: mock_service

        response = client.get("/api/runs/run_abc123/eval")
        assert response.status_code == 200
        data = response.json()
        assert data["run_id"] == "run_abc123"
        assert "nodes" in data
        assert "aggregate_score" in data
        app.dependency_overrides.clear()

    def test_get_soul_eval_history_returns_200(self):
        """AC4: GET /api/souls/{soul_id}/eval/history returns history."""
        mock_service = Mock()
        mock_service.get_soul_eval_history.return_value = SoulEvalHistoryResponse(
            soul_id="researcher_v1",
            versions=[_make_version_entry()],
        )
        app.dependency_overrides[get_eval_service] = lambda: mock_service

        response = client.get("/api/souls/researcher_v1/eval/history")
        assert response.status_code == 200
        data = response.json()
        assert data["soul_id"] == "researcher_v1"
        assert isinstance(data["versions"], list)
        app.dependency_overrides.clear()

    def test_get_soul_eval_history_returns_empty_for_unknown_soul(self):
        """AC6: returns empty versions for non-existent soul."""
        mock_service = Mock()
        mock_service.get_soul_eval_history.return_value = SoulEvalHistoryResponse(
            soul_id="unknown_soul",
            versions=[],
        )
        app.dependency_overrides[get_eval_service] = lambda: mock_service

        response = client.get("/api/souls/unknown_soul/eval/history")
        assert response.status_code == 200
        data = response.json()
        assert data["versions"] == []
        app.dependency_overrides.clear()
