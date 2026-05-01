"""WorkflowService delete behavior and active-run guardrails."""

from unittest.mock import Mock, call

import pytest

from workflow_service_helpers import (
    WorkflowEntity,
    WorkflowHasActiveRuns,
    WorkflowNotFound,
    WorkflowService,
    make_run_read_model,
    make_run_repo,
    make_workflow_repo,
    make_workflow_service,
)


@pytest.fixture
def workflow_repo():
    return make_workflow_repo()


@pytest.fixture
def run_repo():
    return make_run_repo()


@pytest.fixture
def run_read_model():
    return make_run_read_model()


@pytest.fixture
def workflow_service(workflow_repo, run_repo, run_read_model):
    return make_workflow_service(workflow_repo, run_repo, run_read_model)


def test_delete_workflow_cascades_runs_before_deleting_yaml_and_returns_runs_deleted(
    workflow_repo,
    run_repo,
):
    """delete_workflow should remove DB runs before YAML and report the cascade count."""
    tracker = Mock()
    git_service = Mock()
    git_service.is_clean.return_value = False
    workflow_repo.get_by_id.return_value = WorkflowEntity(
        kind="workflow", id="research-workflow", name="Research Flow"
    )
    workflow_repo.delete.return_value = True
    run_repo.delete_runs_for_workflow.return_value = 3
    tracker.attach_mock(run_repo, "run_repo")
    tracker.attach_mock(workflow_repo, "workflow_repo")
    tracker.attach_mock(git_service, "git_service")

    workflow_service = WorkflowService(workflow_repo, run_repo, git_service=git_service)

    result = workflow_service.delete_workflow("research-workflow")

    assert result == {"id": "research-workflow", "deleted": True, "runs_deleted": 3}
    assert tracker.mock_calls[:4] == [
        call.workflow_repo.get_by_id("research-workflow"),
        call.run_repo.delete_runs_for_workflow("research-workflow", force=False),
        call.workflow_repo.delete("research-workflow"),
        call.git_service.is_clean(),
    ]
    git_service.commit_to_branch.assert_called_once()


def test_delete_workflow_force_true_deletes_even_with_active_runs(
    workflow_repo,
    run_repo,
):
    """force=True should cascade runs and still delete the workflow shell."""
    git_service = Mock()
    git_service.is_clean.return_value = False
    workflow_repo.get_by_id.return_value = WorkflowEntity(
        kind="workflow", id="research-workflow", name="Research Flow"
    )
    workflow_repo.delete.return_value = True
    run_repo.delete_runs_for_workflow.return_value = 2

    workflow_service = WorkflowService(workflow_repo, run_repo, git_service=git_service)

    result = workflow_service.delete_workflow("research-workflow", force=True)

    assert result == {"id": "research-workflow", "deleted": True, "runs_deleted": 2}
    run_repo.delete_runs_for_workflow.assert_called_once_with("research-workflow", force=True)
    workflow_repo.delete.assert_called_once_with("research-workflow")
    git_service.commit_to_branch.assert_called_once()


def test_delete_workflow_zero_runs_still_deletes_workflow_cleanly(workflow_repo, run_repo):
    """Deleting a workflow with no historical runs should still remove the workflow."""
    workflow_repo.get_by_id.return_value = WorkflowEntity(
        kind="workflow", id="research-workflow", name="Research Flow"
    )
    workflow_repo.delete.return_value = True
    run_repo.delete_runs_for_workflow.return_value = 0

    workflow_service = WorkflowService(workflow_repo, run_repo)

    result = workflow_service.delete_workflow("research-workflow")

    assert result == {"id": "research-workflow", "deleted": True, "runs_deleted": 0}
    run_repo.delete_runs_for_workflow.assert_called_once_with("research-workflow", force=False)
    workflow_repo.delete.assert_called_once_with("research-workflow")


def test_delete_workflow_raises_workflow_has_active_runs_without_deleting_yaml(
    workflow_repo,
    run_repo,
):
    """Active runs should block workflow deletion until force=True is used."""
    run_repo.delete_runs_for_workflow.side_effect = WorkflowHasActiveRuns(
        "Workflow research-workflow has active runs"
    )

    workflow_service = WorkflowService(workflow_repo, run_repo)

    with pytest.raises(WorkflowHasActiveRuns):
        workflow_service.delete_workflow("research-workflow", force=False)

    workflow_repo.delete.assert_not_called()


def test_delete_workflow_not_found(workflow_service, workflow_repo, run_repo):
    """delete_workflow raises WorkflowNotFound when workflow does not exist."""
    run_repo.delete_runs_for_workflow.return_value = 0
    workflow_repo.delete.return_value = False

    with pytest.raises(WorkflowNotFound, match=r"workflow:missing-workflow"):
        workflow_service.delete_workflow("missing-workflow")
