"""create_run should use actual workflow name, not workflow id.

RunService.create_run() should set workflow_name from workflow.name.
It should use workflow.name (populated from YAML workflow.name field).
"""

from unittest.mock import Mock


def _prepared(inputs: dict[str, object] | None = None):
    from runsight_core.redaction import RunRedactor

    from runsight_api.logic.services.execution_service import PreparedRunInputs

    return PreparedRunInputs(
        normalized_inputs=inputs or {},
        input_redactor=RunRedactor(),
        workflow_inputs={},
        workflow_input_schema={},
    )


class TestCreateRunUsesWorkflowName:
    def test_create_run_sets_workflow_name_from_entity(self):
        """RunService.create_run() should set workflow_name from workflow entity's name."""
        from runsight_api.logic.services.run_service import RunService

        run_repo = Mock()
        run_repo.create_run.return_value = None

        workflow_entity = Mock()
        workflow_entity.id = "my-workflow-k8x3m"
        workflow_entity.name = "My Research Pipeline"

        workflow_repo = Mock()
        workflow_repo.get_by_id.return_value = workflow_entity

        svc = RunService(run_repo, workflow_repo)
        run = svc.create_run(
            "my-workflow-k8x3m",
            _prepared({"instruction": "test"}),
            branch="main",
        )

        # workflow_name should be the human-readable name, not the id
        assert run.workflow_name == "My Research Pipeline"

    def test_create_run_uses_name_not_id(self):
        """create_run must use workflow.name, not workflow.id, for workflow_name field."""
        from runsight_api.logic.services.run_service import RunService

        run_repo = Mock()
        run_repo.create_run.return_value = None

        workflow_entity = Mock()
        workflow_entity.id = "research-pipeline-k8x3m"
        workflow_entity.name = "Research Pipeline"

        workflow_repo = Mock()
        workflow_repo.get_by_id.return_value = workflow_entity

        svc = RunService(run_repo, workflow_repo)
        run = svc.create_run(
            "research-pipeline-k8x3m",
            _prepared({"instruction": "test"}),
            branch="main",
        )

        # The bug: current code does workflow_name=workflow.id
        # It should do workflow_name=workflow.name (or fallback to id)
        assert run.workflow_name != run.workflow_id, (
            "workflow_name should be the human-readable name, not identical to workflow_id"
        )
