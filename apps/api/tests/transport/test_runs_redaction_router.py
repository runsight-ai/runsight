"""Router contract tests for prepared inputs on POST /api/runs."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

from fastapi.testclient import TestClient

from runsight_api.domain.entities.run import RunStatus
from runsight_api.logic.services.execution_service import PreparedRunInputs
from runsight_api.main import app
from runsight_api.transport.deps import get_execution_service, get_run_service
from runsight_core.redaction import RunRedactor

SENSITIVE_VALUE = "orchid-sensitive-value"
PUBLIC_VALUE = "orchid-public-value"

client = TestClient(app, raise_server_exceptions=False)


def teardown_function() -> None:
    app.dependency_overrides.clear()


def _mock_run(run_id: str = "run_redaction_router") -> Mock:
    run = Mock()
    run.id = run_id
    run.workflow_id = "wf_inputs"
    run.workflow_name = "wf_inputs"
    run.status = RunStatus.pending
    run.error = None
    run.started_at = None
    run.completed_at = None
    run.duration_s = None
    run.total_cost_usd = 0.0
    run.total_tokens = 0
    run.created_at = 1711900000.0
    run.branch = "main"
    run.source = "manual"
    run.commit_sha = None
    run.run_number = None
    run.eval_pass_pct = None
    run.eval_score_avg = None
    run.regression_count = 0
    run.regression_types = []
    run.warnings_json = []
    run.parent_run_id = None
    run.root_run_id = None
    run.depth = 0
    return run


def _prepared_inputs(values: dict[str, object]) -> PreparedRunInputs:
    return PreparedRunInputs(
        normalized_inputs=dict(values),
        input_redactor=RunRedactor(),
    )


def _services(*, prepared_result: PreparedRunInputs):
    run_service = Mock()
    run_service.create_run.return_value = _mock_run()
    run_service.refresh_run.return_value = _mock_run()

    execution_service = Mock()
    execution_service.launch_execution = AsyncMock()
    execution_service.prepare_run_inputs.return_value = prepared_result

    app.dependency_overrides[get_run_service] = lambda: run_service
    app.dependency_overrides[get_execution_service] = lambda: execution_service
    return run_service, execution_service


def _execution_service_without_callable_prepare_run_inputs():
    class MissingPrepareRunInputsExecutionService:
        def __init__(self) -> None:
            self.launch_execution = AsyncMock()

    return MissingPrepareRunInputsExecutionService()


def _post_run_payload_with_service(execution_service: object, run_service: Mock):
    app.dependency_overrides[get_run_service] = lambda: run_service
    app.dependency_overrides[get_execution_service] = lambda: execution_service
    try:
        return client.post(
            "/api/runs",
            json={
                "workflow_id": "wf_inputs",
                "branch": "main",
                "inputs": {"private_note": SENSITIVE_VALUE},
            },
        )
    finally:
        app.dependency_overrides.clear()


def test_post_runs_uses_canonical_prepared_inputs_contract() -> None:
    run_service, execution_service = _services(
        prepared_result=_prepared_inputs(
            {
                "private_note": SENSITIVE_VALUE,
                "api_token": PUBLIC_VALUE,
            }
        ),
    )

    response = client.post(
        "/api/runs",
        json={
            "workflow_id": "wf_inputs",
            "branch": "main",
            "inputs": {"private_note": SENSITIVE_VALUE},
        },
    )

    assert response.status_code == 200
    execution_service.prepare_run_inputs.assert_called_once_with(
        "wf_inputs",
        {"private_note": SENSITIVE_VALUE},
        branch="main",
    )
    run_service.create_run.assert_called_once()
    execution_service.launch_execution.assert_awaited_once()


def test_post_runs_fails_closed_when_prepare_run_inputs_is_missing() -> None:
    run_service = Mock()
    run_service.create_run.return_value = _mock_run("run_missing_prepare")
    run_service.refresh_run.return_value = _mock_run("run_missing_prepare")
    execution_service = _execution_service_without_callable_prepare_run_inputs()

    response = _post_run_payload_with_service(execution_service, run_service)

    assert (
        response.status_code,
        run_service.create_run.call_count,
        execution_service.launch_execution.call_count,
    ) == (500, 0, 0)


def test_post_runs_fails_closed_when_prepare_run_inputs_is_noncallable() -> None:
    class NonCallablePrepareRunInputsExecutionService:
        def __init__(self) -> None:
            self.prepare_run_inputs = None
            self.launch_execution = AsyncMock()

    run_service = Mock()
    run_service.create_run.return_value = _mock_run("run_noncallable_prepare")
    run_service.refresh_run.return_value = _mock_run("run_noncallable_prepare")
    execution_service = NonCallablePrepareRunInputsExecutionService()

    response = _post_run_payload_with_service(execution_service, run_service)

    assert (
        response.status_code,
        run_service.create_run.call_count,
        execution_service.launch_execution.call_count,
    ) == (500, 0, 0)
