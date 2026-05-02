from __future__ import annotations

from unittest.mock import Mock, patch

from runsight_api.logic.services.execution_service import PreparedRunInputs
from runsight_core.redaction import RunRedactor

CONCURRENCY_WORKFLOW_ID = "concurrency-workflow"
CONCURRENCY_WORKFLOW_NAME = "Concurrency Workflow"
CONCURRENCY_WORKFLOW_YAML = (
    "workflow:\n"
    f"  name: {CONCURRENCY_WORKFLOW_NAME}\n"
    "  entry: process_request\n"
    "  transitions: []\n"
    "blocks:\n"
    "  process_request:\n"
    "    type: linear\n"
    "    soul_ref: concurrency-soul\n"
    "souls: {}\n"
    "config: {}"
)


def make_service(max_concurrent_runs=None):
    from runsight_api.logic.services.execution_service import ExecutionService

    run_repo = Mock()
    workflow_repo = Mock()
    provider_repo = Mock()

    mock_entity = Mock()
    mock_entity.yaml = CONCURRENCY_WORKFLOW_YAML
    workflow_repo.get_by_id.return_value = mock_entity
    provider_repo.get_by_type.return_value = None

    kwargs = {
        "run_repo": run_repo,
        "workflow_repo": workflow_repo,
        "provider_repo": provider_repo,
    }
    if max_concurrent_runs is not None:
        kwargs["max_concurrent_runs"] = max_concurrent_runs

    return ExecutionService(**kwargs), run_repo, workflow_repo, provider_repo


def patch_parse_workflow(run_coro):
    mock_wf = Mock()
    mock_wf.run = run_coro
    return patch(
        "runsight_api.logic.services.execution_service.parse_workflow_yaml",
        return_value=mock_wf,
    )


def prepared_inputs(inputs: dict[str, object]) -> PreparedRunInputs:
    return PreparedRunInputs(
        normalized_inputs=inputs,
        input_redactor=RunRedactor(),
    )


def concurrency_inputs() -> PreparedRunInputs:
    return prepared_inputs({"instruction": "process queued request"})
