from unittest.mock import Mock

import pytest

from runsight_api.domain.errors import SoulInUse
from runsight_api.domain.value_objects import SoulEntity, WorkflowEntity
from runsight_api.logic.services.soul_service import SoulService
from runsight_api.transport.deps import get_soul_service


def workflow_entity(id: str, name: str, yaml_text: str) -> WorkflowEntity:
    return WorkflowEntity(kind="workflow", id=id, name=name, yaml=yaml_text)


def test_get_soul_service_injects_workflow_repo():
    soul_repo = Mock()
    git_service = Mock()
    workflow_repo = Mock()

    service = get_soul_service(
        soul_repo=soul_repo,
        git_service=git_service,
        workflow_repo=workflow_repo,
    )

    assert service.soul_repo is soul_repo
    assert service.git_service is git_service
    assert service.workflow_repo is workflow_repo


def test_list_souls_uses_injected_workflow_repo_for_counts():
    soul_repo = Mock()
    workflow_repo = Mock()
    soul_repo.list_all.return_value = [
        SoulEntity(id="researcher", kind="soul", name="Researcher", role="Researcher"),
        SoulEntity(id="reviewer", kind="soul", name="Reviewer", role="Reviewer"),
    ]
    workflow_repo.list_all.return_value = [
        workflow_entity(
            "wf_1",
            "Research Flow",
            """
blocks:
  research:
    type: linear
    soul_ref: researcher
""",
        )
    ]
    service = SoulService(soul_repo, workflow_repo=workflow_repo)

    souls = service.list_souls()

    assert [soul.workflow_count for soul in souls] == [1, 0]


def test_get_soul_usages_uses_injected_workflow_repo():
    soul_repo = Mock()
    workflow_repo = Mock()
    soul_repo.get_by_id.return_value = SoulEntity(
        id="researcher", kind="soul", name="Researcher", role="Researcher"
    )
    workflow_repo.list_all.return_value = [
        workflow_entity(
            "wf_1",
            "Research Flow",
            """
blocks:
  research:
    type: linear
    soul_ref: researcher
""",
        )
    ]
    service = SoulService(soul_repo, workflow_repo=workflow_repo)

    usages = service.get_soul_usages("researcher")

    assert usages == [{"workflow_id": "wf_1", "workflow_name": "Research Flow"}]


def test_delete_soul_uses_injected_workflow_repo_for_guarded_delete():
    soul_repo = Mock()
    workflow_repo = Mock()
    soul_repo.get_by_id.return_value = SoulEntity(
        id="researcher", kind="soul", name="Researcher", role="Researcher"
    )
    workflow_repo.list_all.return_value = [
        workflow_entity(
            "wf_1",
            "Research Flow",
            """
blocks:
  research:
    type: linear
    soul_ref: researcher
""",
        )
    ]
    service = SoulService(soul_repo, workflow_repo=workflow_repo)

    with pytest.raises(SoulInUse):
        service.delete_soul("researcher")
