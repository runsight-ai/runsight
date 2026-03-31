import pytest
from unittest.mock import Mock

from runsight_api.domain.errors import WorkflowNotFound
from runsight_api.domain.value_objects import WorkflowEntity
from runsight_api.logic.services.workflow_service import WorkflowService


def test_set_workflow_enabled_uses_targeted_repo_helper():
    workflow_repo = Mock()
    run_repo = Mock()
    workflow_repo.set_enabled.return_value = WorkflowEntity(
        id="wf_research",
        name="Research & Review",
        enabled=True,
    )
    service = WorkflowService(workflow_repo, run_repo)

    result = service.set_workflow_enabled("wf_research", True)

    assert result.enabled is True
    workflow_repo.set_enabled.assert_called_once_with("wf_research", True)
    workflow_repo.update.assert_not_called()


def test_set_workflow_enabled_raises_not_found_when_repo_cannot_find_workflow():
    workflow_repo = Mock()
    run_repo = Mock()
    workflow_repo.set_enabled.side_effect = WorkflowNotFound("Workflow wf_missing not found")
    service = WorkflowService(workflow_repo, run_repo)

    with pytest.raises(WorkflowNotFound, match="wf_missing"):
        service.set_workflow_enabled("wf_missing", False)
