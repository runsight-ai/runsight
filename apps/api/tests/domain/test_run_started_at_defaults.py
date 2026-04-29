"""Run started_at lifecycle defaults."""

from __future__ import annotations

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


class TestRunStartedAtDefault:
    def test_run_started_at_default_is_none(self):
        """Run.started_at defaults to None before execution starts."""
        from runsight_api.domain.entities.run import Run, RunStatus

        run = Run(
            id="run_test",
            workflow_id="workflow_started_at_defaults",
            workflow_name="Started-at workflow",
            status=RunStatus.pending,
            task_json="{}",
            branch="main",
        )

        assert run.started_at is None

    def test_run_started_at_can_be_set_explicitly(self):
        """Run.started_at preserves an explicit execution-start timestamp."""
        from runsight_api.domain.entities.run import Run, RunStatus

        run = Run(
            id="run_test2",
            workflow_id="workflow_started_at_defaults",
            workflow_name="Started-at workflow",
            status=RunStatus.pending,
            task_json="{}",
            branch="main",
            started_at=999.0,
        )

        assert run.started_at == 999.0


class TestCreateRunStartedAt:
    def test_create_run_leaves_started_at_unset_for_pending_run(self):
        """RunService.create_run leaves started_at unset until execution starts."""
        from runsight_api.domain.entities.run import RunStatus
        from runsight_api.logic.services.run_service import RunService

        run_repo = Mock()
        workflow_repo = Mock()
        workflow_repo.get_by_id.return_value = Mock(
            id="workflow_started_at_defaults",
            name="Started-at workflow",
        )
        run_repo.create_run.return_value = None

        svc = RunService(run_repo, workflow_repo)
        run = svc.create_run(
            "workflow_started_at_defaults",
            _prepared({"instruction": "test"}),
            branch="main",
        )

        assert run.started_at is None
        assert run.status == RunStatus.pending
