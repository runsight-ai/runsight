from __future__ import annotations

from unittest.mock import AsyncMock, Mock

from fastapi.testclient import TestClient

from runsight_api.domain.entities.run import RunStatus
from runsight_api.domain.errors import InputValidationError
from runsight_api.main import app
from runsight_api.transport.deps import get_execution_service, get_run_service


client = TestClient(app, raise_server_exceptions=False)


def teardown_function():
    app.dependency_overrides.clear()


def _validation_error(field: str, code: str, *, expected_type: str | None, actual_type: str | None):
    return InputValidationError(
        "Workflow input validation failed",
        error_code="WORKFLOW_INPUT_VALIDATION_ERROR",
        status_code=422,
        details={
            "kind": "workflow_input_validation",
            "workflow_id": "wf_inputs",
            "fields": [
                {
                    "field": field,
                    "code": code,
                    "message": f"Input '{field}' is invalid.",
                    "input_path": ["inputs", field],
                    "expected_type": expected_type,
                    "actual_type": actual_type,
                }
            ],
        },
    )


def _mock_run(run_id: str = "run_896"):
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


def _services(*, normalized_inputs: dict | None = None, validation_error: Exception | None = None):
    run_service = Mock()
    run_service.create_run.return_value = _mock_run()
    run_service.refresh_run.return_value = _mock_run()

    execution_service = Mock()
    execution_service.launch_execution = AsyncMock()
    if validation_error is not None:
        execution_service.prepare_run_inputs.side_effect = validation_error
    else:
        execution_service.prepare_run_inputs.return_value = dict(normalized_inputs or {})

    app.dependency_overrides[get_run_service] = lambda: run_service
    app.dependency_overrides[get_execution_service] = lambda: execution_service
    return run_service, execution_service


class TestRunInputValidationRouter:
    def test_missing_required_input_returns_422_and_creates_no_run(self):
        run_service, execution_service = _services(
            validation_error=_validation_error(
                "query",
                "required",
                expected_type="string",
                actual_type=None,
            )
        )

        response = client.post("/api/runs", json={"workflow_id": "wf_inputs", "inputs": {}})

        assert response.status_code == 422
        payload = response.json()
        assert payload["error"] == "Workflow input validation failed"
        assert payload["error_code"] == "WORKFLOW_INPUT_VALIDATION_ERROR"
        assert payload["details"]["fields"][0]["code"] == "required"
        run_service.create_run.assert_not_called()
        execution_service.launch_execution.assert_not_called()

    def test_type_mismatch_returns_expected_and_actual_type_without_echoing_value(self):
        run_service, execution_service = _services(
            validation_error=_validation_error(
                "max_results",
                "type_mismatch",
                expected_type="number",
                actual_type="string",
            )
        )

        response = client.post(
            "/api/runs",
            json={"workflow_id": "wf_inputs", "inputs": {"query": "search", "max_results": "ten"}},
        )

        assert response.status_code == 422
        field = response.json()["details"]["fields"][0]
        assert field["code"] == "type_mismatch"
        assert field["expected_type"] == "number"
        assert field["actual_type"] == "string"
        assert "ten" not in response.text
        run_service.create_run.assert_not_called()
        execution_service.launch_execution.assert_not_called()

    def test_unknown_input_returns_422_and_creates_no_run(self):
        run_service, execution_service = _services(
            validation_error=_validation_error(
                "debug",
                "unknown",
                expected_type=None,
                actual_type="boolean",
            )
        )

        response = client.post(
            "/api/runs",
            json={"workflow_id": "wf_inputs", "inputs": {"query": "search", "debug": True}},
        )

        assert response.status_code == 422
        assert response.json()["details"]["fields"][0]["code"] == "unknown"
        run_service.create_run.assert_not_called()
        execution_service.launch_execution.assert_not_called()

    def test_optional_defaults_are_passed_to_run_creation_and_execution(self):
        run_service, execution_service = _services(
            normalized_inputs={"query": "search", "max_results": 10}
        )

        response = client.post(
            "/api/runs",
            json={"workflow_id": "wf_inputs", "inputs": {"query": "search"}},
        )

        assert response.status_code == 200
        run_service.create_run.assert_called_once_with(
            "wf_inputs",
            {"query": "search", "max_results": 10},
            source="manual",
            branch="main",
        )
        execution_service.launch_execution.assert_called_once_with(
            "run_896",
            "wf_inputs",
            {"query": "search", "max_results": 10},
            branch="main",
        )

    def test_no_schema_no_inputs_still_uses_immediate_no_input_path(self):
        run_service, execution_service = _services(normalized_inputs={})

        response = client.post("/api/runs", json={"workflow_id": "wf_inputs"})

        assert response.status_code == 200
        execution_service.prepare_run_inputs.assert_called_once_with("wf_inputs", {}, branch="main")
        run_service.create_run.assert_called_once_with(
            "wf_inputs",
            {},
            source="manual",
            branch="main",
        )
        execution_service.launch_execution.assert_called_once_with(
            "run_896",
            "wf_inputs",
            {},
            branch="main",
        )
