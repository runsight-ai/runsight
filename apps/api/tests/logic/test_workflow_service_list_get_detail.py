"""WorkflowService list, get, detail, and commit SHA read behavior."""

from unittest.mock import Mock

import pytest

from workflow_service_helpers import WorkflowEntity, WorkflowService
from workflow_service_helpers import (
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


def test_list_workflows_empty(workflow_service, workflow_repo):
    """list_workflows returns empty list when repo has no workflows."""
    workflow_repo.list_all.return_value = []

    result = workflow_service.list_workflows()

    assert result == []
    workflow_repo.list_all.assert_called_once()


def test_list_workflows_multiple(workflow_service, workflow_repo):
    """list_workflows returns all workflows from repo."""
    design_workflow = WorkflowEntity(kind="workflow", id="design-workflow", name="Design Flow")
    review_workflow = WorkflowEntity(kind="workflow", id="review-workflow", name="Review Flow")
    workflow_repo.list_all.return_value = [design_workflow, review_workflow]

    result = workflow_service.list_workflows()

    assert len(result) == 2
    assert result[0].id == "design-workflow"
    assert result[1].id == "review-workflow"


def test_list_workflows_with_query_filter(workflow_service, workflow_repo):
    """list_workflows filters by query (case-insensitive) in id or name."""
    customer_research = WorkflowEntity(
        kind="workflow", id="customer-research", name="Customer Research"
    )
    market_research = WorkflowEntity(kind="workflow", id="market-research", name="Market Study")
    incident_review = WorkflowEntity(kind="workflow", id="incident-review", name="Incident Review")
    workflow_repo.list_all.return_value = [customer_research, market_research, incident_review]

    result = workflow_service.list_workflows(query="research")

    assert len(result) == 2
    ids = [workflow.id for workflow in result]
    assert "customer-research" in ids
    assert "market-research" in ids
    assert "incident-review" not in ids


def test_list_workflows_query_matches_name(workflow_service, workflow_repo):
    """list_workflows matches query against name when present."""
    research_workflow = WorkflowEntity(
        kind="workflow", id="market-analysis", name="Customer Research"
    )
    review_workflow = WorkflowEntity(kind="workflow", id="support-triage", name="Support Triage")
    workflow_repo.list_all.return_value = [research_workflow, review_workflow]

    result = workflow_service.list_workflows(query="customer research")

    assert len(result) == 1
    assert result[0].id == "market-analysis"


def test_list_workflows_query_empty_string_returns_all(workflow_service, workflow_repo):
    """list_workflows with query='' or None returns all."""
    single_workflow = WorkflowEntity(kind="workflow", id="single-workflow", name="Single Flow")
    workflow_repo.list_all.return_value = [single_workflow]

    result_empty = workflow_service.list_workflows(query="")
    result_none = workflow_service.list_workflows(query=None)

    assert len(result_empty) == 1
    assert len(result_none) == 1


def test_list_workflows_returns_none_commit_sha_without_git_service(
    workflow_repo, run_repo, run_read_model
):
    """Workflow list metadata should keep commit_sha nullable when no git service is wired."""
    workflow_service = WorkflowService(workflow_repo, run_repo, run_read_model=run_read_model)
    workflow_repo.list_all.return_value = [
        WorkflowEntity(kind="workflow", id="workflow-without-git", name="No Git Flow")
    ]
    workflow_repo.get_block_count.return_value = 0
    workflow_repo.get_file_mtime.return_value = None
    result = workflow_service.list_workflows()

    assert len(result) == 1
    assert result[0].id == "workflow-without-git"
    assert result[0].commit_sha is None
    run_read_model.get_workflow_health_metrics.assert_called_once_with(["workflow-without-git"])


def test_list_workflows_returns_none_commit_sha_when_current_branch_lookup_fails(
    workflow_repo,
    run_repo,
    run_read_model,
):
    """Workflow list metadata should not fall back to main when branch lookup fails."""
    git_service = Mock()
    git_service.current_branch.side_effect = RuntimeError("branch lookup failed")
    git_service.get_sha.side_effect = lambda branch, _path: (
        "main-sha-123" if branch == "main" else None
    )
    workflow_service = WorkflowService(
        workflow_repo,
        run_repo,
        git_service=git_service,
        run_read_model=run_read_model,
    )
    workflow_repo.list_all.return_value = [
        WorkflowEntity(kind="workflow", id="branch-lookup-workflow", name="Branch Failure Flow")
    ]
    workflow_repo.get_block_count.return_value = 0
    workflow_repo.get_file_mtime.return_value = None
    result = workflow_service.list_workflows()

    assert len(result) == 1
    assert result[0].id == "branch-lookup-workflow"
    assert result[0].commit_sha is None
    run_read_model.get_workflow_health_metrics.assert_called_once_with(["branch-lookup-workflow"])


def test_list_workflows_returns_none_commit_sha_when_current_branch_has_no_commit(
    workflow_repo,
    run_repo,
    run_read_model,
):
    """Workflow list metadata should stay nullable when current branch has no file commit."""
    git_service = Mock()
    git_service.current_branch.return_value = "feature-x"
    git_service.get_sha.return_value = None
    workflow_service = WorkflowService(
        workflow_repo,
        run_repo,
        git_service=git_service,
        run_read_model=run_read_model,
    )
    workflow_repo.list_all.return_value = [
        WorkflowEntity(kind="workflow", id="feature-only-workflow", name="Feature Branch Flow")
    ]
    workflow_repo.get_block_count.return_value = 0
    workflow_repo.get_file_mtime.return_value = None
    result = workflow_service.list_workflows()

    assert len(result) == 1
    assert result[0].id == "feature-only-workflow"
    assert result[0].commit_sha is None
    git_service.get_sha.assert_called_once_with(
        "feature-x", "custom/workflows/feature-only-workflow.yaml"
    )


@pytest.mark.parametrize(
    ("branch_value", "case_id"),
    [
        ("", "empty"),
        ("HEAD", "detached_head"),
        (None, "non_string"),
    ],
)
def test_list_workflows_returns_none_commit_sha_for_invalid_current_branch_values(
    workflow_repo,
    run_repo,
    run_read_model,
    branch_value,
    case_id,
):
    """Workflow list metadata should treat invalid current branch values as missing SHAs."""
    git_service = Mock()
    git_service.current_branch.return_value = branch_value
    git_service.get_sha.return_value = f"unexpected-sha-for-{case_id}"
    workflow_service = WorkflowService(
        workflow_repo,
        run_repo,
        git_service=git_service,
        run_read_model=run_read_model,
    )
    workflow_repo.list_all.return_value = [
        WorkflowEntity(
            kind="workflow",
            id=f"invalid-branch-{case_id}-workflow",
            name="Invalid Branch Flow",
        )
    ]
    workflow_repo.get_block_count.return_value = 0
    workflow_repo.get_file_mtime.return_value = None
    result = workflow_service.list_workflows()

    assert len(result) == 1
    assert result[0].commit_sha is None


def test_get_workflow_exists(workflow_service, workflow_repo):
    """get_workflow returns workflow when it exists."""
    existing_workflow = WorkflowEntity(
        kind="workflow", id="existing-workflow", name="Existing Workflow"
    )
    workflow_repo.get_by_id.return_value = existing_workflow

    result = workflow_service.get_workflow("existing-workflow")

    assert result is existing_workflow
    assert result.id == "existing-workflow"
    workflow_repo.get_by_id.assert_called_once_with("existing-workflow")


def test_get_workflow_not_found(workflow_service, workflow_repo):
    """get_workflow returns None when workflow does not exist."""
    workflow_repo.get_by_id.return_value = None

    result = workflow_service.get_workflow("missing-workflow")

    assert result is None


def test_get_workflow_detail_uses_main_branch_commit_sha(workflow_repo, run_repo):
    """get_workflow_detail enriches a workflow with commit_sha from main only."""
    git_service = Mock()
    git_service.current_branch.return_value = "feature-x"
    git_service.get_sha.return_value = "main-sha-123"
    workflow_service = WorkflowService(workflow_repo, run_repo, git_service=git_service)
    workflow_repo.get_by_id.return_value = WorkflowEntity(
        kind="workflow",
        id="published-workflow",
        name="Published Flow",
        filename="published-workflow.yaml",
    )

    result = workflow_service.get_workflow_detail("published-workflow")

    assert result.id == "published-workflow"
    assert result.commit_sha == "main-sha-123"
    git_service.get_sha.assert_called_once_with("main", "custom/workflows/published-workflow.yaml")
    workflow_repo.get_by_id.assert_called_once_with("published-workflow")


def test_get_workflow_detail_returns_none_commit_sha_when_not_committed_on_main(
    workflow_repo,
    run_repo,
):
    """get_workflow_detail returns null commit_sha when main has no commit for the file."""
    git_service = Mock()
    git_service.current_branch.return_value = "feature-x"
    git_service.get_sha.return_value = None
    workflow_service = WorkflowService(workflow_repo, run_repo, git_service=git_service)
    workflow_repo.get_by_id.return_value = WorkflowEntity(
        kind="workflow",
        id="unpublished-draft-workflow",
        name="Draft Flow",
        filename="unpublished-draft-workflow.yaml",
    )

    result = workflow_service.get_workflow_detail("unpublished-draft-workflow")

    assert result.id == "unpublished-draft-workflow"
    assert result.commit_sha is None
    git_service.get_sha.assert_called_once_with(
        "main", "custom/workflows/unpublished-draft-workflow.yaml"
    )
