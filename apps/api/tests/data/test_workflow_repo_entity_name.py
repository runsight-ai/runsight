"""Workflow repository entity-name behavior."""

from __future__ import annotations

from runsight_api.data.filesystem.workflow_repo import WorkflowRepository


def _workflow_yaml(*, workflow_id: str, workflow_name: str) -> str:
    return f"""id: {workflow_id}
kind: workflow
version: '1.0'
workflow:
  name: {workflow_name}
  entry: b1
  transitions: []
blocks:
  b1:
    type: linear
    soul_ref: test
souls: {{}}
config: {{}}
"""


class TestWorkflowEntityNameFromYaml:
    def test_create_populates_workflow_entity_name_from_yaml(self, tmp_path):
        repo = WorkflowRepository(tmp_path)

        entity = repo.create(
            {
                "name": "Request Payload Name",
                "yaml": _workflow_yaml(
                    workflow_id="my-cool-workflow",
                    workflow_name="My Cool Workflow",
                ),
            }
        )

        assert entity.name == "My Cool Workflow"

    def test_get_by_id_populates_workflow_entity_name_from_yaml(self, tmp_path):
        repo = WorkflowRepository(tmp_path)

        created = repo.create(
            {
                "name": "Research Pipeline",
                "yaml": _workflow_yaml(
                    workflow_id="research-pipeline",
                    workflow_name="Research Pipeline",
                ),
            }
        )
        retrieved = repo.get_by_id(created.id)

        assert retrieved is not None
        assert retrieved.name == "Research Pipeline"

    def test_list_all_populates_workflow_entity_names_from_yaml(self, tmp_path):
        repo = WorkflowRepository(tmp_path)

        repo.create(
            {
                "name": "Listed Workflow",
                "yaml": _workflow_yaml(
                    workflow_id="listed-workflow",
                    workflow_name="Listed Workflow",
                ),
            }
        )
        workflows = repo.list_all()

        names = [workflow.name for workflow in workflows]
        assert "Listed Workflow" in names
