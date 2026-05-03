"""Workflow-scoped Direct API invocation route coverage."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from runsight_core.redaction import RunRedactor

from runsight_api.domain.entities.run import RunStatus
from runsight_api.domain.errors import InputValidationError, WorkflowNotFound
from runsight_api.domain.value_objects import WorkflowEntity
from runsight_api.logic.services.execution_service import PreparedRunInputs
from runsight_api.main import app
from runsight_api.transport.deps import (
    get_execution_service,
    get_external_invocation_admission,
    get_run_service,
)


WORKFLOW_ID = "direct_route_workflow"
COMMITTED_MAIN_SHA = "932" * 13 + "9"
SECRET_INPUT = "secret-direct-route-input"
SECRET_AUTH = "Bearer secret-direct-route-auth"

client = TestClient(app, raise_server_exceptions=False)


def teardown_function() -> None:
    app.dependency_overrides.clear()
    app.openapi_schema = None


@dataclass(frozen=True)
class _AdmissionDecision:
    allowed: bool
    failure_code: str | None = None
    status_code: int | None = None
    reason: str | None = None


@dataclass(frozen=True)
class _ResolvedWorkflowSnapshot:
    workflow: Any
    branch: str = "main"
    commit_sha: str = COMMITTED_MAIN_SHA


class _RuntimeAdmission:
    def __init__(self, decision: _AdmissionDecision | None = None) -> None:
        self.decision = decision or _AdmissionDecision(allowed=True)
        self.calls: list[Any] = []

    def check_external_invocation(self, invocation: Any) -> _AdmissionDecision:
        self.calls.append(invocation)
        return self.decision


class _CanonicalExecutionService:
    def __init__(
        self,
        *,
        prepare_error: Exception | None = None,
        resolve_error: Exception | None = None,
    ) -> None:
        self.prepare_error = prepare_error
        self.resolve_error = resolve_error
        self.resolved_snapshot = _ResolvedWorkflowSnapshot(
            workflow=Mock(
                name="Committed Main Workflow",
                warnings=[{"message": "from committed main", "source": "parser", "context": None}],
            )
        )
        self.resolve_calls: list[dict[str, Any]] = []
        self.prepare_snapshot_calls: list[dict[str, Any]] = []
        self.launch_snapshot_calls: list[dict[str, Any]] = []

    def resolve_workflow_run_snapshot(
        self, workflow_id: str, *, branch: str
    ) -> _ResolvedWorkflowSnapshot:
        self.resolve_calls.append({"workflow_id": workflow_id, "branch": branch})
        if self.resolve_error is not None:
            raise self.resolve_error
        return self.resolved_snapshot

    def prepare_run_inputs_from_snapshot(
        self,
        snapshot: _ResolvedWorkflowSnapshot,
        inputs: dict[str, object],
    ) -> PreparedRunInputs:
        self.prepare_snapshot_calls.append({"snapshot": snapshot, "inputs": dict(inputs)})
        if self.prepare_error is not None:
            raise self.prepare_error
        return PreparedRunInputs(normalized_inputs=dict(inputs), input_redactor=RunRedactor())

    async def launch_execution_from_snapshot(
        self,
        run_id: str,
        workflow_id: str,
        prepared: PreparedRunInputs,
        *,
        snapshot: _ResolvedWorkflowSnapshot,
    ) -> None:
        self.launch_snapshot_calls.append(
            {
                "run_id": run_id,
                "workflow_id": workflow_id,
                "inputs": prepared.normalized_inputs,
                "branch": snapshot.branch,
                "commit_sha": snapshot.commit_sha,
            }
        )

    def prepare_run_inputs(self, *args: Any, **kwargs: Any) -> None:
        raise AssertionError("direct API route must not use dirty GUI prepare_run_inputs")

    async def launch_execution(self, *args: Any, **kwargs: Any) -> None:
        raise AssertionError("direct API route must not use dirty GUI launch_execution")


class _RecordingRunService:
    def __init__(self) -> None:
        self.created_run = _mock_run()
        self.create_calls: list[dict[str, Any]] = []

    def create_run(
        self,
        workflow_id: str,
        inputs: PreparedRunInputs,
        **kwargs: Any,
    ) -> Mock:
        self.create_calls.append(
            {
                "workflow_id": workflow_id,
                "inputs": inputs.normalized_inputs,
                **kwargs,
            }
        )
        self.created_run.workflow_id = workflow_id
        self.created_run.source = kwargs.get("source")
        self.created_run.branch = kwargs.get("branch")
        self.created_run.source_correlation_id = kwargs.get("source_correlation_id")
        self.created_run.source_metadata = kwargs.get("source_metadata") or {}
        self.created_run.commit_sha = COMMITTED_MAIN_SHA
        self.created_run.workflow_name = "Committed Main Workflow"
        return self.created_run

    def get_run(self, run_id: str) -> Mock | None:
        return self.created_run if run_id == self.created_run.id else None

    def refresh_run(self, run_id: str) -> Mock | None:
        return self.get_run(run_id)

    def fail_run(self, run_id: str, error: str) -> Mock:
        self.created_run.status = RunStatus.failed
        self.created_run.error = error
        return self.created_run


def _mock_run() -> Mock:
    run = Mock()
    run.id = "direct_route_api"
    run.workflow_id = WORKFLOW_ID
    run.workflow_name = "Committed Main Workflow"
    run.status = RunStatus.pending
    run.error = None
    run.started_at = None
    run.completed_at = None
    run.duration_s = None
    run.total_cost_usd = 0.0
    run.total_tokens = 0
    run.created_at = 1711900932.0
    run.branch = "main"
    run.source = "api"
    run.commit_sha = COMMITTED_MAIN_SHA
    run.source_correlation_id = "corr-direct-route"
    run.source_metadata = {"entry_path": "direct_api"}
    run.run_number = None
    run.eval_pass_pct = None
    run.eval_score_avg = None
    run.regression_count = 0
    run.regression_types = []
    run.warnings_json = [{"message": "from committed main", "source": "parser", "context": None}]
    run.parent_run_id = None
    run.root_run_id = None
    run.depth = 0
    run.workflow_inputs = None
    run.workflow_input_schema = {"query": {"type": "string"}}
    return run


def _install_services(
    *,
    admission: _RuntimeAdmission | None = None,
    execution: _CanonicalExecutionService | None = None,
    run_service: _RecordingRunService | None = None,
) -> tuple[_RecordingRunService, _CanonicalExecutionService, _RuntimeAdmission]:
    run_service = run_service or _RecordingRunService()
    execution = execution or _CanonicalExecutionService()
    admission = admission or _RuntimeAdmission()

    app.dependency_overrides[get_run_service] = lambda: run_service
    app.dependency_overrides[get_execution_service] = lambda: execution
    app.dependency_overrides[get_external_invocation_admission] = lambda: admission
    return run_service, execution, admission


def _assert_sanitized_error_response(response, expected_status: int) -> dict[str, Any]:
    assert response.status_code == expected_status
    body = response.json()
    assert body["status_code"] == expected_status
    assert isinstance(body.get("error_code"), str)
    assert "detail" not in body
    rendered = response.text
    assert SECRET_INPUT not in rendered
    assert SECRET_AUTH not in rendered
    return body


def _validation_error() -> InputValidationError:
    return InputValidationError(
        "Workflow input validation failed",
        error_code="WORKFLOW_INPUT_VALIDATION_ERROR",
        status_code=422,
        details={
            "kind": "workflow_input_validation",
            "workflow_id": WORKFLOW_ID,
            "fields": [
                {
                    "field": "query",
                    "code": "type_mismatch",
                    "message": "Input 'query' is invalid.",
                    "input_path": ["inputs", "query"],
                    "expected_type": "string",
                    "actual_type": "number",
                }
            ],
        },
    )


def test_direct_api_route_invokes_committed_main_snapshot_not_gui_run_contract() -> None:
    run_service, execution, admission = _install_services()

    response = client.post(
        f"/api/workflows/{WORKFLOW_ID}/runs",
        json={"inputs": {"query": "from api", "api_token": SECRET_INPUT}},
        headers={"x-request-id": "corr-direct-route", "authorization": SECRET_AUTH},
    )

    assert response.status_code in {200, 202}
    body = response.json()
    assert body["id"] == "direct_route_api"
    assert body["status"] == "pending"
    assert body["source"] == "api"
    assert body["branch"] == "main"
    assert body["commit_sha"] == COMMITTED_MAIN_SHA
    assert body["source_correlation_id"] == "corr-direct-route"
    assert body["source_metadata"]["entry_path"] == "direct_api"
    assert body["workflow_name"] == "Committed Main Workflow"
    assert SECRET_INPUT not in response.text

    assert admission.calls
    assert execution.resolve_calls == [{"workflow_id": WORKFLOW_ID, "branch": "main"}]
    assert execution.prepare_snapshot_calls[0]["inputs"] == {
        "query": "from api",
        "api_token": SECRET_INPUT,
    }
    assert execution.launch_snapshot_calls == [
        {
            "run_id": "direct_route_api",
            "workflow_id": WORKFLOW_ID,
            "inputs": {"query": "from api", "api_token": SECRET_INPUT},
            "branch": "main",
            "commit_sha": COMMITTED_MAIN_SHA,
        }
    ]
    assert len(run_service.create_calls) == 1
    create_call = run_service.create_calls[0]
    assert create_call["workflow_id"] == WORKFLOW_ID
    assert create_call["inputs"] == {"query": "from api", "api_token": SECRET_INPUT}
    assert create_call["branch"] == "main"
    assert create_call["source"] == "api"
    assert create_call["source_correlation_id"] == "corr-direct-route"
    assert create_call["source_metadata"]["entry_path"] == "direct_api"
    assert create_call["source_metadata"]["request_path"] == f"/api/workflows/{WORKFLOW_ID}/runs"
    assert SECRET_INPUT not in str(create_call["source_metadata"])
    assert create_call["workflow_snapshot"] is execution.resolved_snapshot.workflow


@pytest.mark.parametrize(
    "extra_field",
    [
        "source",
        "branch",
        "commit_sha",
        "trigger_id",
        "delivery_id",
        "debug",
        "simulation",
        "simulation_id",
        "simulation_branch",
        "idempotency_key",
        "idempotency_token",
        "caller",
        "source_metadata",
        "source_correlation_id",
        "provenance",
    ],
)
def test_direct_api_body_rejects_privileged_and_idempotency_fields(extra_field: str) -> None:
    run_service, execution, _ = _install_services()

    response = client.post(
        f"/api/workflows/{WORKFLOW_ID}/runs",
        json={"inputs": {"query": "from api"}, extra_field: SECRET_INPUT},
        headers={"authorization": SECRET_AUTH},
    )

    body = _assert_sanitized_error_response(response, 422)
    assert body["details"]["kind"] == "workflow_input_validation"
    assert body["details"]["fields"][0]["field"] == extra_field
    assert body["details"]["fields"][0]["code"] in {"unknown", "extra_forbidden"}
    assert run_service.create_calls == []
    assert execution.resolve_calls == []
    assert execution.launch_snapshot_calls == []


def test_direct_api_runtime_unavailable_returns_503_before_run_creation() -> None:
    run_service, execution, _ = _install_services(
        admission=_RuntimeAdmission(
            _AdmissionDecision(
                allowed=False,
                failure_code="runtime_unavailable",
                status_code=503,
                reason="external invocation disabled by runtime config",
            )
        )
    )

    response = client.post(
        f"/api/workflows/{WORKFLOW_ID}/runs",
        json={"inputs": {"query": SECRET_INPUT}},
        headers={"authorization": SECRET_AUTH},
    )

    body = _assert_sanitized_error_response(response, 503)
    assert body["error_code"] == "RUNTIME_UNAVAILABLE"
    assert run_service.create_calls == []
    assert execution.resolve_calls == []
    assert execution.launch_snapshot_calls == []


def test_direct_api_admission_saturation_returns_429_before_run_creation() -> None:
    run_service, execution, _ = _install_services(
        admission=_RuntimeAdmission(
            _AdmissionDecision(
                allowed=False,
                failure_code="admission_saturated",
                status_code=429,
                reason="external invocation admission is saturated",
            )
        )
    )

    response = client.post(
        f"/api/workflows/{WORKFLOW_ID}/runs",
        json={"inputs": {"query": SECRET_INPUT}},
        headers={"authorization": SECRET_AUTH},
    )

    body = _assert_sanitized_error_response(response, 429)
    assert body["error_code"] == "ADMISSION_SATURATED"
    assert run_service.create_calls == []
    assert execution.resolve_calls == []
    assert execution.launch_snapshot_calls == []


def test_direct_api_workflow_missing_on_saved_main_returns_404_without_run_creation() -> None:
    run_service, execution, _ = _install_services(
        execution=_CanonicalExecutionService(
            resolve_error=WorkflowNotFound(f"Workflow {WORKFLOW_ID!r} not found on main")
        )
    )

    response = client.post(
        f"/api/workflows/{WORKFLOW_ID}/runs",
        json={"inputs": {"query": SECRET_INPUT}},
        headers={"authorization": SECRET_AUTH},
    )

    body = _assert_sanitized_error_response(response, 404)
    assert body["error_code"] == "WORKFLOW_NOT_FOUND"
    assert execution.resolve_calls == [{"workflow_id": WORKFLOW_ID, "branch": "main"}]
    assert run_service.create_calls == []
    assert execution.launch_snapshot_calls == []


def test_direct_api_disabled_saved_main_snapshot_returns_404_without_run_creation() -> None:
    run_service, execution, _ = _install_services()
    execution.resolved_snapshot = _ResolvedWorkflowSnapshot(
        workflow=WorkflowEntity(
            kind="workflow",
            id=WORKFLOW_ID,
            name="Disabled Main Workflow",
            enabled=False,
        )
    )

    response = client.post(
        f"/api/workflows/{WORKFLOW_ID}/runs",
        json={"inputs": {"query": SECRET_INPUT}},
        headers={"authorization": SECRET_AUTH},
    )

    body = _assert_sanitized_error_response(response, 404)
    assert body["error_code"] == "WORKFLOW_NOT_FOUND"
    assert execution.resolve_calls == [{"workflow_id": WORKFLOW_ID, "branch": "main"}]
    assert run_service.create_calls == []
    assert execution.launch_snapshot_calls == []


def test_direct_api_omitted_enabled_saved_main_snapshot_returns_404_without_run_creation() -> None:
    run_service, execution, _ = _install_services()
    execution.resolved_snapshot = _ResolvedWorkflowSnapshot(
        workflow=WorkflowEntity(
            kind="workflow",
            id=WORKFLOW_ID,
            name="Omitted Enabled Main Workflow",
            yaml="id: direct_route_workflow\nkind: workflow\nworkflow:\n  name: Omitted Enabled Main Workflow\n",
        )
    )

    response = client.post(
        f"/api/workflows/{WORKFLOW_ID}/runs",
        json={"inputs": {"query": SECRET_INPUT}},
        headers={"authorization": SECRET_AUTH},
    )

    body = _assert_sanitized_error_response(response, 404)
    assert body["error_code"] == "WORKFLOW_NOT_FOUND"
    assert execution.resolve_calls == [{"workflow_id": WORKFLOW_ID, "branch": "main"}]
    assert execution.prepare_snapshot_calls == []
    assert run_service.create_calls == []
    assert execution.launch_snapshot_calls == []


def test_direct_api_canonical_input_validation_returns_422_without_run_creation() -> None:
    run_service, execution, _ = _install_services(
        execution=_CanonicalExecutionService(prepare_error=_validation_error())
    )

    response = client.post(
        f"/api/workflows/{WORKFLOW_ID}/runs",
        json={"inputs": {"query": 932, "api_token": SECRET_INPUT}},
        headers={"authorization": SECRET_AUTH},
    )

    body = _assert_sanitized_error_response(response, 422)
    assert body["error_code"] == "WORKFLOW_INPUT_VALIDATION_ERROR"
    assert body["details"]["fields"][0]["code"] == "type_mismatch"
    assert run_service.create_calls == []
    assert execution.launch_snapshot_calls == []


def test_direct_api_body_too_large_returns_413_before_route_parsing_or_storage() -> None:
    run_service, execution, _ = _install_services()

    response = client.post(
        f"/api/workflows/{WORKFLOW_ID}/runs",
        content=b'{"inputs":{"query":"' + (b"x" * 1_100_000) + b'"}}',
        headers={"content-type": "application/json", "authorization": SECRET_AUTH},
    )

    body = _assert_sanitized_error_response(response, 413)
    assert body["error_code"] == "REQUEST_BODY_TOO_LARGE"
    assert run_service.create_calls == []
    assert execution.resolve_calls == []
    assert execution.launch_snapshot_calls == []


def test_openapi_exposes_distinct_direct_api_invocation_schema() -> None:
    app.openapi_schema = None
    spec = app.openapi()

    operation = spec["paths"]["/api/workflows/{workflow_id}/runs"]["post"]
    request_schema = operation["requestBody"]["content"]["application/json"]["schema"]
    schema_ref = request_schema.get("$ref", "")
    assert not schema_ref.endswith("/RunCreate")

    schema_name = schema_ref.rsplit("/", 1)[-1]
    assert schema_name != "RunCreate"
    schema = spec["components"]["schemas"][schema_name]
    assert set(schema["properties"]) == {"inputs"}
    assert "workflow_id" not in schema["properties"]
    assert "source" not in schema["properties"]
    assert "branch" not in schema["properties"]
    assert "idempotency_key" not in schema["properties"]
    assert "source_metadata" not in schema["properties"]
    assert {"404", "422", "429", "503"}.issubset(operation["responses"])


@pytest.mark.parametrize("status", ["404", "429", "503", "413"])
def test_openapi_models_direct_api_error_responses_as_json(status: str) -> None:
    app.openapi_schema = None
    spec = app.openapi()

    operation = spec["paths"]["/api/workflows/{workflow_id}/runs"]["post"]
    response = operation["responses"][status]

    assert response["content"]["application/json"]["schema"]
