"""Red tests for RUN-928 router fail-closed behavior around prepared inputs."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

from fastapi.testclient import TestClient

from runsight_api.domain.entities.run import RunStatus
from runsight_api.main import app
from runsight_api.transport.deps import get_execution_service, get_run_service

SENSITIVE_VALUE = "orchid-928-sensitive-value"
PUBLIC_VALUE = "orchid-928-public-value"

client = TestClient(app, raise_server_exceptions=False)


def teardown_function() -> None:
    app.dependency_overrides.clear()


def _mock_run(run_id: str = "run_928_router") -> Mock:
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


def _services(*, prepared_result: object):
    run_service = Mock()
    run_service.create_run.return_value = _mock_run()
    run_service.refresh_run.return_value = _mock_run()

    execution_service = Mock()
    execution_service.launch_execution = AsyncMock()
    execution_service.prepare_run_inputs.return_value = prepared_result

    app.dependency_overrides[get_run_service] = lambda: run_service
    app.dependency_overrides[get_execution_service] = lambda: execution_service
    return run_service, execution_service


def test_post_runs_rejects_plain_mapping_prepare_run_inputs_result() -> None:
    run_service, execution_service = _services(
        prepared_result={
            "private_note": SENSITIVE_VALUE,
            "api_token": PUBLIC_VALUE,
        }
    )

    response = client.post(
        "/api/runs",
        json={"workflow_id": "wf_inputs", "inputs": {"private_note": SENSITIVE_VALUE}},
    )

    assert response.status_code >= 400
    execution_service.prepare_run_inputs.assert_called_once_with(
        "wf_inputs",
        {"private_note": SENSITIVE_VALUE},
        branch="main",
    )
    run_service.create_run.assert_not_called()
    execution_service.launch_execution.assert_not_called()
