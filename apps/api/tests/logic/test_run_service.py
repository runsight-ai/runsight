"""Comprehensive unit tests for RunService.

Tests document current behavior as guardrails — they break on any behavioral change.
"""

from unittest.mock import Mock

import pytest

from runsight_api.logic.services.run_service import RunService
from runsight_api.domain.entities.run import Run, RunNode, RunStatus
from runsight_api.domain.entities.log import LogEntry
from runsight_api.domain.errors import RunNotFound, WorkflowNotFound


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


# --- create_run ---


def test_create_run_happy_path(run_service, run_repo, workflow_repo):
    """create_run succeeds when workflow exists and task_data is provided."""
    workflow_repo.get_by_id.return_value = Mock(id="wf_1")
    run_repo.create_run.return_value = None  # create_run mutates and passes run

    run = run_service.create_run("wf_1", {"foo": "bar", "task_id": "t1"})

    assert run.workflow_id == "wf_1"
    assert run.workflow_name == "wf_1"
    assert run.status == RunStatus.pending
    assert '"foo"' in run.task_json and '"bar"' in run.task_json
    assert run.id.startswith("run_")
    assert run.started_at is not None
    run_repo.create_run.assert_called_once()
    call_run = run_repo.create_run.call_args[0][0]
    assert call_run.workflow_id == "wf_1"


def test_create_run_workflow_not_found(run_service, workflow_repo):
    """create_run raises WorkflowNotFound when workflow does not exist."""
    workflow_repo.get_by_id.return_value = None

    with pytest.raises(WorkflowNotFound) as exc_info:
        run_service.create_run("non_existent", {"foo": "bar"})

    assert "non_existent" in str(exc_info.value)


def test_create_run_empty_task_data(run_service, run_repo, workflow_repo):
    """create_run accepts empty task_data (serializes to '{}')."""
    workflow_repo.get_by_id.return_value = Mock(id="wf_1")
    run_repo.create_run.return_value = None

    run = run_service.create_run("wf_1", {})

    assert run.task_json == "{}"
    assert run.workflow_id == "wf_1"


# --- get_run ---


def test_get_run_exists(run_service, run_repo):
    """get_run returns run when it exists."""
    expected = Run(
        id="run_1",
        workflow_id="wf_1",
        workflow_name="wf_1",
        status=RunStatus.completed,
        task_json="{}",
    )
    run_repo.get_run.return_value = expected

    result = run_service.get_run("run_1")

    assert result is expected
    assert result.id == "run_1"
    run_repo.get_run.assert_called_once_with("run_1")


def test_get_run_not_found(run_service, run_repo):
    """get_run returns None when run does not exist."""
    run_repo.get_run.return_value = None

    result = run_service.get_run("non_existent")

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
    r1 = Run(
        id="r1", workflow_id="wf", workflow_name="wf", status=RunStatus.pending, task_json="{}"
    )
    r2 = Run(
        id="r2", workflow_id="wf", workflow_name="wf", status=RunStatus.completed, task_json="{}"
    )
    run_repo.list_runs.return_value = [r1, r2]

    result = run_service.list_runs()

    assert len(result) == 2
    assert result[0].id == "r1"
    assert result[1].id == "r2"


# --- cancel_run ---


def test_cancel_run_happy_path(run_service, run_repo):
    """cancel_run sets status=cancelled and updates run."""
    run = Run(
        id="run_1",
        workflow_id="wf_1",
        workflow_name="wf_1",
        status=RunStatus.running,
        task_json="{}",
        started_at=100.0,
    )
    run_repo.get_run.return_value = run
    run_repo.update_run.return_value = run

    result = run_service.cancel_run("run_1")

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
        run_service.cancel_run("non_existent")

    assert "non_existent" in str(exc_info.value)
    run_repo.update_run.assert_not_called()


def test_cancel_run_already_cancelled(run_service, run_repo):
    """cancel_run succeeds when run is already cancelled (idempotent)."""
    run = Run(
        id="run_1",
        workflow_id="wf_1",
        workflow_name="wf_1",
        status=RunStatus.cancelled,
        task_json="{}",
    )
    run_repo.get_run.return_value = run
    run_repo.update_run.return_value = run

    result = run_service.cancel_run("run_1")

    assert result.status == RunStatus.cancelled
    run_repo.update_run.assert_called_once()


# --- get_run_nodes ---


def test_get_run_nodes_with_nodes(run_service, run_repo):
    """get_run_nodes returns nodes for the run."""
    nodes = [
        RunNode(id="r1:n1", run_id="r1", node_id="n1", block_type="soul", status="completed"),
        RunNode(id="r1:n2", run_id="r1", node_id="n2", block_type="soul", status="pending"),
    ]
    run_repo.list_nodes_for_run.return_value = nodes

    result = run_service.get_run_nodes("r1")

    assert len(result) == 2
    assert result[0].node_id == "n1"
    assert result[1].node_id == "n2"
    run_repo.list_nodes_for_run.assert_called_once_with("r1")


def test_get_run_nodes_empty(run_service, run_repo):
    """get_run_nodes returns empty list when no nodes exist."""
    run_repo.list_nodes_for_run.return_value = []

    result = run_service.get_run_nodes("run_1")

    assert result == []


# --- get_run_logs ---


def test_get_run_logs_with_logs(run_service, run_repo):
    """get_run_logs returns logs for the run."""
    logs = [
        LogEntry(run_id="r1", message="msg1", level="info"),
        LogEntry(run_id="r1", message="msg2", level="error"),
    ]
    run_repo.list_logs_for_run.return_value = logs

    result = run_service.get_run_logs("r1")

    assert len(result) == 2
    assert result[0].message == "msg1"
    assert result[1].message == "msg2"
    run_repo.list_logs_for_run.assert_called_once_with("r1")


def test_get_run_logs_empty(run_service, run_repo):
    """get_run_logs returns empty list when no logs exist."""
    run_repo.list_logs_for_run.return_value = []

    result = run_service.get_run_logs("run_1")

    assert result == []


# --- compute_summaries ---


def test_compute_summaries_aggregates_cost_and_tokens(run_service, run_repo):
    """compute_summaries aggregates cost_usd and tokens from nodes, updates run."""
    run = Run(
        id="run_1",
        workflow_id="wf_1",
        workflow_name="wf_1",
        status=RunStatus.completed,
        task_json="{}",
    )
    nodes = [
        RunNode(
            id="r1:n1",
            run_id="r1",
            node_id="n1",
            block_type="soul",
            cost_usd=1.5,
            tokens={"prompt": 100, "completion": 50, "total": 150},
        ),
        RunNode(
            id="r1:n2",
            run_id="r1",
            node_id="n2",
            block_type="soul",
            cost_usd=2.0,
            tokens={"prompt": 200, "completion": 100, "total": 300},
        ),
    ]
    run_repo.get_run.return_value = run
    run_repo.list_nodes_for_run.return_value = nodes
    run_repo.update_run.return_value = run

    result = run_service.compute_summaries("run_1")

    assert result["total_cost_usd"] == 3.5
    assert result["total_tokens"] == 450
    assert result["nodes_count"] == 2
    run_repo.update_run.assert_called_once()
    updated = run_repo.update_run.call_args[0][0]
    assert updated.total_cost_usd == 3.5
    assert updated.total_tokens == 450


def test_compute_summaries_run_not_found(run_service, run_repo):
    """compute_summaries still returns aggregates from nodes when run is None; no update."""
    run_repo.get_run.return_value = None
    nodes = [
        RunNode(
            id="r1:n1",
            run_id="r1",
            node_id="n1",
            block_type="soul",
            cost_usd=1.0,
            tokens={"total": 50},
        ),
    ]
    run_repo.list_nodes_for_run.return_value = nodes

    result = run_service.compute_summaries("run_1")

    assert result["total_cost_usd"] == 1.0
    assert result["total_tokens"] == 50
    assert result["nodes_count"] == 1
    run_repo.update_run.assert_not_called()


def test_compute_summaries_empty_nodes(run_service, run_repo):
    """compute_summaries returns zeros when no nodes."""
    run = Run(
        id="run_1",
        workflow_id="wf_1",
        workflow_name="wf_1",
        status=RunStatus.completed,
        task_json="{}",
    )
    run_repo.get_run.return_value = run
    run_repo.list_nodes_for_run.return_value = []

    result = run_service.compute_summaries("run_1")

    assert result["total_cost_usd"] == 0.0
    assert result["total_tokens"] == 0
    assert result["nodes_count"] == 0


def test_compute_summaries_nodes_missing_cost_usd_raises(run_service, run_repo):
    """compute_summaries raises AttributeError when node lacks cost_usd (current brittle behavior)."""
    run = Run(
        id="run_1",
        workflow_id="wf_1",
        workflow_name="wf_1",
        status=RunStatus.completed,
        task_json="{}",
    )
    # Mock node without cost_usd (e.g. from non-RunNode source)
    node_without_cost = Mock(spec=[])  # no attributes
    run_repo.get_run.return_value = run
    run_repo.list_nodes_for_run.return_value = [node_without_cost]

    with pytest.raises(AttributeError):
        run_service.compute_summaries("run_1")
