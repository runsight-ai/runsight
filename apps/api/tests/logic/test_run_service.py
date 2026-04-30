"""Comprehensive unit tests for RunService.

Tests document current behavior as guardrails — they break on any behavioral change.
"""

from unittest.mock import Mock

import pytest

from runsight_api.domain.entities.log import LogEntry
from runsight_api.domain.entities.run import Run, RunNode, RunStatus
from runsight_api.domain.errors import RunNotFound, WorkflowNotFound
from runsight_api.logic.services.run_service import RunService

# --- Fixtures ---


@pytest.fixture
def run_repo():
    return Mock()


@pytest.fixture
def workflow_repo():
    return Mock()


@pytest.fixture
def run_service(run_repo, workflow_repo):
    return RunService(run_repo, workflow_repo)


def _prepared(inputs: dict[str, object] | None = None):
    from runsight_core.redaction import RunRedactor

    from runsight_api.logic.services.execution_service import PreparedRunInputs

    return PreparedRunInputs(
        normalized_inputs=inputs or {},
        input_redactor=RunRedactor(),
        workflow_inputs={},
        workflow_input_schema={},
    )


# --- create_run ---


def test_create_run_creates_pending_run_for_existing_workflow(run_service, run_repo, workflow_repo):
    """create_run succeeds when workflow exists and task_data is provided."""
    workflow_repo.get_by_id.return_value = Mock(id="research-workflow")
    run_repo.create_run.return_value = None  # create_run mutates and passes run

    run = run_service.create_run(
        "research-workflow",
        _prepared({"instruction": "summarize findings", "task_id": "research-task"}),
        branch="main",
    )

    assert run.workflow_id == "research-workflow"
    assert run.workflow_name == "research-workflow"
    assert run.status == RunStatus.pending
    assert run.task_json == "{}"
    assert run.id.startswith("run_")
    assert run.started_at is None
    run_repo.create_run.assert_called_once()
    call_run = run_repo.create_run.call_args[0][0]
    assert call_run.workflow_id == "research-workflow"


def test_create_run_workflow_not_found(run_service, workflow_repo):
    """create_run raises WorkflowNotFound when workflow does not exist."""
    workflow_repo.get_by_id.return_value = None

    with pytest.raises(WorkflowNotFound) as exc_info:
        run_service.create_run(
            "missing-workflow",
            _prepared({"instruction": "summarize findings"}),
            branch="main",
        )

    assert "missing-workflow" in str(exc_info.value)


def test_create_run_accepts_branch_and_source(run_service, run_repo, workflow_repo):
    """create_run should preserve the canonical simulation branch/source pair."""
    workflow = Mock()
    workflow.id = "simulation-workflow"
    workflow.name = "Simulation Flow"
    workflow_repo.get_by_id.return_value = workflow
    run_repo.create_run.return_value = None

    run = run_service.create_run(
        "simulation-workflow",
        _prepared({"instruction": "simulate branch-aware execution"}),
        source="simulation",
        branch="sim/simulation-workflow/20260330/abc12",
    )

    assert run.source == "simulation"
    assert run.branch == "sim/simulation-workflow/20260330/abc12"
    stored_run = run_repo.create_run.call_args[0][0]
    assert stored_run.source == "simulation"
    assert stored_run.branch == "sim/simulation-workflow/20260330/abc12"


def test_create_run_empty_task_data(run_service, run_repo, workflow_repo):
    """create_run accepts empty task_data (serializes to '{}')."""
    workflow_repo.get_by_id.return_value = Mock(id="empty-input-workflow")
    run_repo.create_run.return_value = None

    run = run_service.create_run("empty-input-workflow", _prepared(), branch="main")

    assert run.task_json == "{}"
    assert run.workflow_id == "empty-input-workflow"


# --- get_run ---


def test_get_run_exists(run_service, run_repo):
    """get_run returns run when it exists."""
    expected = Run(
        id="existing-run",
        workflow_id="research-workflow",
        workflow_name="Research workflow",
        status=RunStatus.completed,
        task_json="{}",
        branch="main",
    )
    run_repo.get_run.return_value = expected

    result = run_service.get_run("existing-run")

    assert result is expected
    assert result.id == "existing-run"
    run_repo.get_run.assert_called_once_with("existing-run")


def test_get_run_not_found(run_service, run_repo):
    """get_run returns None when run does not exist."""
    run_repo.get_run.return_value = None

    result = run_service.get_run("missing-run")

    assert result is None


# --- list_runs ---


def test_list_runs_empty(run_service, run_repo):
    """list_runs returns empty list when no runs exist."""
    run_repo.list_runs.return_value = []

    result = run_service.list_runs()

    assert result == []
    run_repo.list_runs.assert_called_once()


def test_list_runs_multiple(run_service, run_repo):
    """list_runs returns all runs in repo order."""
    pending_run = Run(
        id="pending-listed-run",
        workflow_id="listing-workflow",
        workflow_name="Listing workflow",
        status=RunStatus.pending,
        task_json="{}",
        branch="main",
    )
    completed_run = Run(
        id="completed-listed-run",
        workflow_id="listing-workflow",
        workflow_name="Listing workflow",
        status=RunStatus.completed,
        task_json="{}",
        branch="main",
    )
    run_repo.list_runs.return_value = [pending_run, completed_run]

    result = run_service.list_runs()

    assert len(result) == 2
    assert result[0].id == "pending-listed-run"
    assert result[1].id == "completed-listed-run"


# --- cancel_run ---


def test_cancel_running_run_records_user_cancellation(run_service, run_repo):
    """cancel_run sets status=cancelled and updates run."""
    run = Run(
        id="running-run-for-cancel",
        workflow_id="cancellable-workflow",
        workflow_name="Cancellable workflow",
        status=RunStatus.running,
        task_json="{}",
        branch="main",
        started_at=100.0,
    )
    run_repo.get_run.return_value = run
    run_repo.update_run.return_value = run

    result = run_service.cancel_run("running-run-for-cancel")

    assert result.status == RunStatus.cancelled
    assert result.cancelled_reason == "Cancelled by user"
    assert result.completed_at is not None
    assert result.duration_s is not None
    run_repo.update_run.assert_called_once()
    updated = run_repo.update_run.call_args[0][0]
    assert updated.status == RunStatus.cancelled


def test_cancel_run_not_found(run_service, run_repo):
    """cancel_run raises RunNotFound when run does not exist."""
    run_repo.get_run.return_value = None

    with pytest.raises(RunNotFound) as exc_info:
        run_service.cancel_run("missing-run")

    assert "missing-run" in str(exc_info.value)
    run_repo.update_run.assert_not_called()


def test_cancel_run_already_cancelled(run_service, run_repo):
    """cancel_run succeeds when run is already cancelled (idempotent)."""
    run = Run(
        id="already-cancelled-run",
        workflow_id="cancellable-workflow",
        workflow_name="Cancellable workflow",
        status=RunStatus.cancelled,
        task_json="{}",
        branch="main",
    )
    run_repo.get_run.return_value = run
    run_repo.update_run.return_value = run

    result = run_service.cancel_run("already-cancelled-run")

    assert result.status == RunStatus.cancelled
    run_repo.update_run.assert_called_once()


# --- get_run_nodes ---


def test_get_run_nodes_with_nodes(run_service, run_repo):
    """get_run_nodes returns nodes for the run."""
    nodes = [
        RunNode(
            id="node-row-research",
            run_id="run-with-nodes",
            node_id="research-node",
            block_type="soul",
            status="completed",
        ),
        RunNode(
            id="node-row-review",
            run_id="run-with-nodes",
            node_id="review-node",
            block_type="soul",
            status="pending",
        ),
    ]
    run_repo.list_nodes_for_run.return_value = nodes

    result = run_service.get_run_nodes("run-with-nodes")

    assert len(result) == 2
    assert result[0].node_id == "research-node"
    assert result[1].node_id == "review-node"
    run_repo.list_nodes_for_run.assert_called_once_with("run-with-nodes")


def test_get_run_nodes_empty(run_service, run_repo):
    """get_run_nodes returns empty list when no nodes exist."""
    run_repo.list_nodes_for_run.return_value = []

    result = run_service.get_run_nodes("run-without-nodes")

    assert result == []


# --- get_run_logs ---


def test_get_run_logs_with_logs(run_service, run_repo):
    """get_run_logs returns logs for the run."""
    logs = [
        LogEntry(run_id="run-with-logs", message="Node started", level="info"),
        LogEntry(run_id="run-with-logs", message="Node failed", level="error"),
    ]
    run_repo.list_logs_for_run.return_value = logs

    result = run_service.get_run_logs("run-with-logs")

    assert len(result) == 2
    assert result[0].message == "Node started"
    assert result[1].message == "Node failed"
    run_repo.list_logs_for_run.assert_called_once_with("run-with-logs")


def test_get_run_logs_empty(run_service, run_repo):
    """get_run_logs returns empty list when no logs exist."""
    run_repo.list_logs_for_run.return_value = []

    result = run_service.get_run_logs("run-without-logs")

    assert result == []


# --- get_node_summary ---


def test_get_node_summary_aggregates_cost_and_tokens(run_service, run_repo):
    """get_node_summary aggregates cost_usd and tokens from nodes (read-only)."""
    nodes = [
        RunNode(
            id="summary-row-research",
            run_id="run-with-node-costs",
            node_id="research-node",
            block_type="soul",
            cost_usd=1.5,
            tokens={"prompt": 100, "completion": 50, "total": 150},
        ),
        RunNode(
            id="summary-row-review",
            run_id="run-with-node-costs",
            node_id="review-node",
            block_type="soul",
            cost_usd=2.0,
            tokens={"prompt": 200, "completion": 100, "total": 300},
        ),
    ]
    run_repo.list_nodes_for_run.return_value = nodes

    result = run_service.get_node_summary("run-with-node-costs")

    assert result["total_cost_usd"] == 3.5
    assert result["total_tokens"] == 450
    assert result["nodes_count"] == 2
    run_repo.update_run.assert_not_called()


def test_get_node_summary_empty_nodes(run_service, run_repo):
    """get_node_summary returns zeros when no nodes."""
    run_repo.list_nodes_for_run.return_value = []

    result = run_service.get_node_summary("run-without-node-costs")

    assert result["total_cost_usd"] == 0.0
    assert result["total_tokens"] == 0
    assert result["nodes_count"] == 0


def test_get_node_summary_nodes_missing_cost_usd_raises(run_service, run_repo):
    """get_node_summary raises AttributeError when node lacks cost_usd."""
    node_without_cost = Mock(spec=[])  # no attributes
    run_repo.list_nodes_for_run.return_value = [node_without_cost]

    with pytest.raises(AttributeError):
        run_service.get_node_summary("run-with-malformed-node")
