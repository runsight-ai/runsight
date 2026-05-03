"""Shared response doubles for child-run transport tests."""

from unittest.mock import Mock


from runsight_api.domain.entities.run import RunStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_RUN_RESPONSE_BASE = dict(
    id="run_parent",
    workflow_id="wf_child_run_queries",
    workflow_name="Child run query workflow",
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
    run_id: str = "run_parent",
    *,
    parent_run_id: str | None = None,
    root_run_id: str | None = None,
    depth: int = 0,
    workflow_id: str = "wf_child_run_queries",
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
    mock_run.warnings_json = None
    mock_run.error = None
    mock_run.regression_count = None
    return mock_run


def _make_mock_node(
    run_id: str = "run_parent",
    node_id: str = "step_child_link",
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
