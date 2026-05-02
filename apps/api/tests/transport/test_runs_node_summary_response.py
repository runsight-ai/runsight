"""Runs transport responses use service-provided node summaries."""

from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from runsight_api.domain.entities.run import RunStatus
from runsight_api.main import app
from runsight_api.transport.deps import get_eval_service, get_run_service

client = TestClient(app)


def _make_mock_run(run_id="run_abc", status=RunStatus.running):
    mock_run = Mock()
    mock_run.id = run_id
    mock_run.workflow_id = "wf_node_summary"
    mock_run.workflow_name = "Node summary workflow"
    mock_run.status = status
    mock_run.started_at = 1000.0
    mock_run.completed_at = None
    mock_run.duration_s = None
    mock_run.total_cost_usd = 0.03
    mock_run.total_tokens = 500
    mock_run.created_at = 999.0
    mock_run.source = "manual"
    mock_run.branch = "main"
    mock_run.commit_sha = None
    mock_run.run_number = None
    mock_run.eval_pass_pct = None
    mock_run.regression_count = None
    mock_run.error = None
    mock_run.parent_run_id = None
    mock_run.root_run_id = None
    mock_run.depth = 0
    return mock_run


class TestRunsRouterNodeSummaryNotHardcoded:
    """The router must pass real per-status counts to NodeSummary, not zeros."""

    def _mock_eval_svc(self):
        mock_eval = Mock()
        mock_eval.get_run_regressions.return_value = {"count": 0, "issues": []}
        return mock_eval

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
        app.dependency_overrides[get_eval_service] = lambda: self._mock_eval_svc()
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
        app.dependency_overrides[get_eval_service] = lambda: self._mock_eval_svc()
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
        app.dependency_overrides[get_eval_service] = lambda: self._mock_eval_svc()
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
        mock_run = _make_mock_run()
        mock_service = Mock()
        summary = {
            "total_cost_usd": 0.03,
            "total_tokens": 500,
            "nodes_count": 5,
            "total": 5,
            "completed": 2,
            "running": 2,
            "pending": 1,
            "failed": 0,
        }
        mock_service.list_runs_paginated.return_value = ([mock_run], 1)
        mock_service.get_node_summaries_batch.return_value = {mock_run.id: summary}
        mock_service.get_node_summary.return_value = summary
        app.dependency_overrides[get_run_service] = lambda: mock_service
        app.dependency_overrides[get_eval_service] = lambda: self._mock_eval_svc()
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

    def _mock_eval_svc(self):
        mock_eval = Mock()
        mock_eval.get_run_regressions.return_value = {"count": 0, "issues": []}
        return mock_eval

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
        app.dependency_overrides[get_eval_service] = lambda: self._mock_eval_svc()
        try:
            response = client.get("/api/runs/run_abc")
            data = response.json()
            assert data["total_cost_usd"] == pytest.approx(0.035), (
                "total_cost_usd should come from node summary aggregation"
            )
            assert data["total_tokens"] == 500
        finally:
            app.dependency_overrides.clear()
