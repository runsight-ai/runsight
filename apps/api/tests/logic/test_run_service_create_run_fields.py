from unittest.mock import Mock

import pytest
from runsight_core.redaction import RunRedactor

from tests.domain.run_entity_factories import EXPLICIT_BRANCH
from runsight_api.logic.services.execution_service import PreparedRunInputs


def _prepared(inputs: dict[str, object] | None = None):
    return PreparedRunInputs(
        normalized_inputs=inputs or {},
        input_redactor=RunRedactor(),
        workflow_inputs={},
        workflow_input_schema={},
    )


def _service_with_workflow(*, warnings=None, include_warnings=True):
    from runsight_api.logic.services.run_service import RunService

    mock_run_repo = Mock()
    mock_run_repo.create_run.side_effect = lambda run: run
    mock_workflow = Mock()
    mock_workflow.name = "Data model workflow"
    mock_workflow.id = "workflow-data-model"
    if include_warnings:
        mock_workflow.warnings = warnings or []
    mock_wf_repo = Mock()
    mock_wf_repo.get_by_id.return_value = mock_workflow
    return RunService(run_repo=mock_run_repo, workflow_repo=mock_wf_repo), mock_workflow


def test_create_run_requires_explicit_branch_argument():
    service, _ = _service_with_workflow()

    with pytest.raises(TypeError):
        service.create_run(
            "workflow-data-model",
            _prepared({"instruction": "summarize research notes"}),
        )


def test_create_run_sets_branch_and_source():
    service, _ = _service_with_workflow()

    run = service.create_run(
        "workflow-data-model",
        _prepared({"instruction": "summarize research notes"}),
        branch=EXPLICIT_BRANCH,
        source="webhook",
    )

    assert run.branch == EXPLICIT_BRANCH
    assert run.source == "webhook"


def test_create_run_snapshots_non_empty_workflow_warnings():
    warnings = [
        {
            "message": "Tool definition warning",
            "source": "tool_definitions",
            "context": "fetcher",
        }
    ]
    service, workflow = _service_with_workflow(warnings=warnings)

    run = service.create_run(
        "workflow-data-model",
        _prepared({"instruction": "summarize research notes"}),
        branch=EXPLICIT_BRANCH,
    )

    assert run.warnings_json == warnings
    assert run.warnings_json is not workflow.warnings

    workflow.warnings[0]["message"] = "mutated after creation"
    assert run.warnings_json[0]["message"] == "Tool definition warning"


@pytest.mark.parametrize(
    "warnings, include_warnings",
    [
        ([], True),
        (Mock(name="not_a_warning_list"), True),
        (None, False),
    ],
)
def test_create_run_ignores_empty_missing_or_non_list_workflow_warnings(
    warnings,
    include_warnings,
):
    service, _ = _service_with_workflow(warnings=warnings, include_warnings=include_warnings)

    run = service.create_run(
        "workflow-data-model",
        _prepared({"instruction": "summarize research notes"}),
        branch=EXPLICIT_BRANCH,
    )

    assert run.warnings_json is None
