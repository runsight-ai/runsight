"""Dashboard eval KPI test builders."""

from __future__ import annotations

import time
from unittest.mock import Mock

from runsight_api.domain.entities.run import NodeStatus, RunStatus


def make_mock_run(
    run_id: str = "run_eval_kpi",
    status: RunStatus = RunStatus.completed,
    total_cost_usd: float = 0.0,
    created_at: float | None = None,
) -> Mock:
    """Create a mock Run with the given attributes."""
    created_at = created_at or time.time()
    mock_run = Mock()
    mock_run.id = run_id
    mock_run.workflow_id = "wf_eval_kpis"
    mock_run.workflow_name = "Eval KPI workflow"
    mock_run.status = status
    mock_run.started_at = created_at - 10
    mock_run.completed_at = created_at
    mock_run.duration_s = 10.0
    mock_run.total_cost_usd = total_cost_usd
    mock_run.total_tokens = 100
    mock_run.created_at = created_at
    mock_run.updated_at = created_at
    mock_run.source = "manual"
    mock_run.branch = "main"
    return mock_run


def make_mock_node(
    node_id: str = "node_eval_primary",
    run_id: str = "run_eval_kpi",
    eval_passed: bool | None = None,
    eval_score: float | None = None,
    soul_id: str | None = None,
    soul_version: str | None = None,
    created_at: float | None = None,
) -> Mock:
    """Create a mock RunNode with eval fields."""
    created_at = created_at or time.time()
    mock_node = Mock()
    mock_node.id = f"{run_id}:{node_id}"
    mock_node.run_id = run_id
    mock_node.node_id = node_id
    mock_node.block_type = "llm"
    mock_node.status = NodeStatus.completed
    mock_node.eval_passed = eval_passed
    mock_node.eval_score = eval_score
    mock_node.eval_results = None
    mock_node.soul_id = soul_id
    mock_node.soul_version = soul_version
    mock_node.cost_usd = 0.01
    mock_node.tokens = {"prompt": 50, "completion": 50, "total": 100}
    mock_node.created_at = created_at
    mock_node.updated_at = created_at
    return mock_node
