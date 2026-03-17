"""Comprehensive unit tests for WorkflowService.

Tests document current behavior as guardrails — they break on any behavioral change.
"""

from unittest.mock import Mock

import pytest

from runsight_api.logic.services.workflow_service import WorkflowService
from runsight_api.domain.value_objects import WorkflowEntity
from runsight_api.domain.errors import WorkflowNotFound


# --- Fixtures ---


@pytest.fixture
def workflow_repo():
    return Mock()


@pytest.fixture
def workflow_service(workflow_repo):
    return WorkflowService(workflow_repo)


# --- list_workflows ---


def test_list_workflows_empty(workflow_service, workflow_repo):
    """list_workflows returns empty list when repo has no workflows."""
    workflow_repo.list_all.return_value = []

    result = workflow_service.list_workflows()

    assert result == []
    workflow_repo.list_all.assert_called_once()


def test_list_workflows_multiple(workflow_service, workflow_repo):
    """list_workflows returns all workflows from repo."""
    w1 = WorkflowEntity(id="wf_1", name="First")
    w2 = WorkflowEntity(id="wf_2", name="Second")
    workflow_repo.list_all.return_value = [w1, w2]

    result = workflow_service.list_workflows()

    assert len(result) == 2
    assert result[0].id == "wf_1"
    assert result[1].id == "wf_2"


def test_list_workflows_with_query_filter(workflow_service, workflow_repo):
    """list_workflows filters by query (case-insensitive) in id or name."""
    w1 = WorkflowEntity(id="alpha_beta", name="Alpha")
    w2 = WorkflowEntity(id="beta_gamma", name="Gamma")
    w3 = WorkflowEntity(id="other", name="Other")
    workflow_repo.list_all.return_value = [w1, w2, w3]

    result = workflow_service.list_workflows(query="beta")

    assert len(result) == 2
    ids = [w.id for w in result]
    assert "alpha_beta" in ids
    assert "beta_gamma" in ids
    assert "other" not in ids


def test_list_workflows_query_matches_name(workflow_service, workflow_repo):
    """list_workflows matches query against name when present."""
    w1 = WorkflowEntity(id="wf_1", name="MyWorkflow")
    w2 = WorkflowEntity(id="wf_2", name="OtherWorkflow")
    workflow_repo.list_all.return_value = [w1, w2]

    result = workflow_service.list_workflows(query="myworkflow")

    assert len(result) == 1
    assert result[0].id == "wf_1"


def test_list_workflows_query_empty_string_returns_all(workflow_service, workflow_repo):
    """list_workflows with query='' or None returns all (falsy query = no filter)."""
    w1 = WorkflowEntity(id="wf_1", name="One")
    workflow_repo.list_all.return_value = [w1]

    result_empty = workflow_service.list_workflows(query="")
    result_none = workflow_service.list_workflows(query=None)

    assert len(result_empty) == 1
    assert len(result_none) == 1


# --- get_workflow ---


def test_get_workflow_exists(workflow_service, workflow_repo):
    """get_workflow returns workflow when it exists."""
    w = WorkflowEntity(id="wf_1", name="Test")
    workflow_repo.get_by_id.return_value = w

    result = workflow_service.get_workflow("wf_1")

    assert result is w
    assert result.id == "wf_1"
    workflow_repo.get_by_id.assert_called_once_with("wf_1")


def test_get_workflow_not_found(workflow_service, workflow_repo):
    """get_workflow returns None when workflow does not exist."""
    workflow_repo.get_by_id.return_value = None

    result = workflow_service.get_workflow("non_existent")

    assert result is None


# --- create_workflow ---


def test_create_workflow_happy_path(workflow_service, workflow_repo):
    """create_workflow creates and returns workflow when data has id."""
    data = {"id": "wf_new", "name": "New Workflow"}
    created = WorkflowEntity(**data)
    workflow_repo.create.return_value = created

    result = workflow_service.create_workflow(data)

    assert result.id == "wf_new"
    assert result.name == "New Workflow"
    workflow_repo.create.assert_called_once_with(data)


def test_create_workflow_without_id(workflow_service, workflow_repo):
    """create_workflow works without id — repo generates it from filename."""
    data = {"name": "No ID Needed"}
    created = WorkflowEntity(id="no-id-needed-abc12", name="No ID Needed")
    workflow_repo.create.return_value = created

    result = workflow_service.create_workflow(data)

    assert result.id == "no-id-needed-abc12"
    workflow_repo.create.assert_called_once_with(data)


# --- update_workflow ---


def test_update_workflow_happy_path(workflow_service, workflow_repo):
    """update_workflow updates and returns workflow when it exists."""
    data = {"name": "Updated Name"}
    updated = WorkflowEntity(id="wf_1", name="Updated Name")
    workflow_repo.update.return_value = updated

    result = workflow_service.update_workflow("wf_1", data)

    assert result.id == "wf_1"
    assert result.name == "Updated Name"
    workflow_repo.update.assert_called_once_with("wf_1", data)


def test_update_workflow_not_found(workflow_service, workflow_repo):
    """update_workflow raises WorkflowNotFound when workflow does not exist."""
    workflow_repo.update.side_effect = WorkflowNotFound("Workflow wf_missing not found")

    with pytest.raises(WorkflowNotFound) as exc_info:
        workflow_service.update_workflow("wf_missing", {"name": "New"})

    assert "wf_missing" in str(exc_info.value)


# --- delete_workflow ---


def test_delete_workflow_happy_path(workflow_service, workflow_repo):
    """delete_workflow returns True when workflow exists and is deleted."""
    workflow_repo.delete.return_value = True

    result = workflow_service.delete_workflow("wf_1")

    assert result is True
    workflow_repo.delete.assert_called_once_with("wf_1")


def test_delete_workflow_not_found(workflow_service, workflow_repo):
    """delete_workflow raises WorkflowNotFound when workflow does not exist."""
    workflow_repo.delete.return_value = False

    with pytest.raises(WorkflowNotFound) as exc_info:
        workflow_service.delete_workflow("non_existent")

    assert "non_existent" in str(exc_info.value)
