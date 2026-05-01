"""WorkflowService create and update validation and persistence behavior."""

from unittest.mock import Mock

import pytest

from workflow_service_helpers import (
    InputValidationError,
    WorkflowEntity,
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


def test_create_workflow_returns_created_entity(workflow_service, workflow_repo):
    """create_workflow creates and returns workflow when data has id."""
    data = {"id": "created-workflow", "name": "Created Workflow"}
    created = WorkflowEntity(kind="workflow", **data)
    workflow_repo.create.return_value = created

    result = workflow_service.create_workflow(data)

    assert result.id == "created-workflow"
    assert result.name == "Created Workflow"
    workflow_repo.create.assert_called_once_with(data)


def test_create_workflow_without_id(workflow_service, workflow_repo):
    """create_workflow works without id because the repo generates it from filename."""
    data = {"name": "No ID Needed"}
    created = WorkflowEntity(kind="workflow", id="generated-workflow-abc12", name="No ID Needed")
    workflow_repo.create.return_value = created

    result = workflow_service.create_workflow(data)

    assert result.id == "generated-workflow-abc12"
    workflow_repo.create.assert_called_once_with(data)


def test_create_workflow_commit_true_uses_repo_relative_yaml_path(workflow_repo, run_repo):
    """create_workflow should auto-commit the YAML file using the repo-relative path."""
    git_service = Mock()
    git_service.is_clean.return_value = False
    git_service.commit_to_branch.return_value = "abc123def456"
    workflow_service = WorkflowService(workflow_repo, run_repo, git_service=git_service)
    workflow_repo.create.return_value = WorkflowEntity(
        kind="workflow",
        id="created-workflow",
        name="Created Workflow",
    )

    result = workflow_service.create_workflow({"name": "Created Workflow"})

    assert result.id == "created-workflow"
    git_service.commit_to_branch.assert_called_once_with(
        "main",
        ["custom/workflows/created-workflow.yaml"],
        "Create workflow: Created Workflow",
    )


def test_create_workflow_commit_false_skips_auto_commit(workflow_repo, run_repo):
    """create_workflow(commit=False) must not auto-commit the new workflow."""
    git_service = Mock()
    workflow_service = WorkflowService(workflow_repo, run_repo, git_service=git_service)
    workflow_repo.create.return_value = WorkflowEntity(
        kind="workflow",
        id="draft-only-workflow",
        name="No Commit Workflow",
    )

    result = workflow_service.create_workflow({"name": "No Commit Workflow"}, commit=False)

    assert result.id == "draft-only-workflow"
    workflow_repo.create.assert_called_once_with({"name": "No Commit Workflow"})
    git_service.commit_to_branch.assert_not_called()


def test_create_workflow_requires_yaml(workflow_service, workflow_repo):
    """create_workflow should surface the canonical YAML-only contract."""
    workflow_repo.create.side_effect = InputValidationError("yaml is required")

    with pytest.raises(InputValidationError, match="yaml is required"):
        workflow_service.create_workflow({"name": "No YAML"})


def test_create_workflow_does_not_fail_when_auto_commit_errors(workflow_repo):
    """Workflow creation should succeed even if the convenience git auto-commit cannot run."""
    git_service = Mock()
    git_service.is_clean.return_value = False
    git_service.commit_to_branch.side_effect = RuntimeError("checkout main failed")
    created = WorkflowEntity(kind="workflow", id="created-workflow", name="New Workflow")
    workflow_repo.create.return_value = created
    workflow_service = WorkflowService(workflow_repo, Mock(), git_service=git_service)

    result = workflow_service.create_workflow({"name": "New Workflow"})

    assert result == created
    workflow_repo.create.assert_called_once_with({"name": "New Workflow"})
    git_service.commit_to_branch.assert_called_once()


def test_update_workflow_returns_updated_entity(workflow_service, workflow_repo):
    """update_workflow updates and returns workflow when it exists."""
    data = {"name": "Updated Name"}
    updated = WorkflowEntity(kind="workflow", id="editable-workflow", name="Updated Name")
    workflow_repo.update.return_value = updated

    result = workflow_service.update_workflow("editable-workflow", data)

    assert result.id == "editable-workflow"
    assert result.name == "Updated Name"
    workflow_repo.update.assert_called_once_with("editable-workflow", data)


def test_update_workflow_not_found(workflow_service, workflow_repo):
    """update_workflow raises WorkflowNotFound when workflow does not exist."""
    workflow_repo.update.side_effect = WorkflowNotFound("Workflow missing-workflow not found")

    with pytest.raises(WorkflowNotFound) as exc_info:
        workflow_service.update_workflow("missing-workflow", {"name": "New"})

    assert "missing-workflow" in str(exc_info.value)


def test_update_workflow_requires_yaml(workflow_service, workflow_repo):
    """update_workflow should reject name-only updates that bypass raw YAML."""
    workflow_repo.update.side_effect = InputValidationError("yaml is required")

    with pytest.raises(InputValidationError, match="yaml is required"):
        workflow_service.update_workflow("editable-workflow", {"name": "Renamed"})
