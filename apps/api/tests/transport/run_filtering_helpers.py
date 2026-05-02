"""Shared run and service doubles for source/branch filtering tests."""

import time
from unittest.mock import Mock


from runsight_api.domain.entities.run import RunStatus

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_run(
    run_id: str = "source-filter-run",
    workflow_id: str = "source-branch-workflow",
    status: RunStatus = RunStatus.completed,
    source: str = "manual",
    branch: str = "main",
    total_cost_usd: float = 0.0,
    created_at: float | None = None,
) -> Mock:
    """Create a mock Run with source and branch attributes."""
    mock_run = Mock()
    mock_run.id = run_id
    mock_run.workflow_id = workflow_id
    mock_run.workflow_name = f"Workflow {workflow_id}"
    mock_run.status = status
    mock_run.started_at = (created_at or time.time()) - 10
    mock_run.completed_at = created_at or time.time()
    mock_run.duration_s = 10.0
    mock_run.total_cost_usd = total_cost_usd
    mock_run.total_tokens = 100
    mock_run.created_at = created_at or time.time()
    mock_run.source = source
    mock_run.branch = branch
    mock_run.commit_sha = None
    mock_run.run_number = None
    mock_run.eval_pass_pct = None
    mock_run.regression_count = None
    mock_run.error = None
    return mock_run


def _mock_eval_svc():
    """Return a mock EvalService that returns zero regressions."""
    mock_eval = Mock()
    mock_eval.get_run_regressions.return_value = {"count": 0, "issues": []}
    return mock_eval


def _stub_service_with_runs(runs):
    """Wire up a mock RunService that filters by status, workflow_id, source, and branch."""
    mock_service = Mock()

    def paginated(offset=0, limit=20, status=None, workflow_id=None, source=None, branch=None):
        filtered = runs
        if status:
            filtered = [r for r in filtered if r.status in status]
        if workflow_id:
            filtered = [r for r in filtered if r.workflow_id == workflow_id]
        if source:
            filtered = [r for r in filtered if r.source in source]
        if branch:
            filtered = [r for r in filtered if r.branch == branch]
        page = filtered[offset : offset + limit]
        return page, len(filtered)

    mock_service.list_runs_paginated = paginated
    mock_service.list_runs.return_value = runs
    mock_service.get_node_summaries_batch.return_value = {
        r.id: {
            "total_cost_usd": r.total_cost_usd,
            "total_tokens": r.total_tokens,
            "total": 1,
            "completed": 1,
            "running": 0,
            "pending": 0,
            "failed": 0,
        }
        for r in runs
    }
    mock_service.get_node_summary.return_value = {
        "total_cost_usd": 0.0,
        "total_tokens": 0,
        "nodes_count": 0,
        "total": 0,
        "completed": 0,
        "running": 0,
        "pending": 0,
        "failed": 0,
    }
    return mock_service


# ===========================================================================
# 1. Router accepts source param
# ===========================================================================
