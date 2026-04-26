"""RED tests for RUN-944 WorkflowRunInvoker runtime guardrails."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest


WORKFLOW_ID = "run944_runtime_guardrails"


def _invoker_contract():
    from runsight_api.logic.services.workflow_run_invoker import (
        WorkflowRunInvocation,
        WorkflowRunInvoker,
    )

    return WorkflowRunInvoker, WorkflowRunInvocation


def _direct_api_invocation(**overrides: Any):
    _, WorkflowRunInvocation = _invoker_contract()
    payload = {
        "workflow_id": WORKFLOW_ID,
        "inputs": {"query": "from api"},
        "source_correlation_id": "corr-run-944",
        "source_metadata": {
            "entry_path": "direct_api",
            "request_path": f"/api/workflows/{WORKFLOW_ID}/runs",
        },
    }
    payload.update(overrides)
    return WorkflowRunInvocation.direct_api(**payload)


def _value(value: Any) -> Any:
    return getattr(value, "value", value)


def _field(result: Any, name: str) -> Any:
    if isinstance(result, dict):
        return result.get(name)
    return getattr(result, name)


@dataclass(frozen=True)
class _AdmissionDecision:
    allowed: bool
    failure_code: str | None = None
    status_code: int | None = None
    reason: str | None = None


class _RuntimeAdmission:
    def __init__(self, decision: _AdmissionDecision) -> None:
        self.decision = decision
        self.calls: list[Any] = []

    def check_external_invocation(self, invocation: Any) -> _AdmissionDecision:
        self.calls.append(invocation)
        return self.decision


class _NoCallExecutionService:
    def resolve_workflow_run_snapshot(self, *args: Any, **kwargs: Any) -> None:
        raise AssertionError("pre-run admission failure must not resolve workflow snapshots")

    def prepare_run_inputs_from_snapshot(self, *args: Any, **kwargs: Any) -> None:
        raise AssertionError("pre-run admission failure must not validate inputs")

    async def launch_execution_from_snapshot(self, *args: Any, **kwargs: Any) -> None:
        raise AssertionError("pre-run admission failure must not launch execution")


class _RecordingRunService:
    def __init__(self) -> None:
        self.create_calls: list[Any] = []

    def create_run(self, *args: Any, **kwargs: Any) -> None:
        self.create_calls.append((args, kwargs))
        raise AssertionError("pre-run admission failure must not create runs")


@pytest.mark.asyncio
async def test_runtime_disabled_returns_typed_503_before_snapshot_or_run_creation() -> None:
    WorkflowRunInvoker, _ = _invoker_contract()
    run_service = _RecordingRunService()
    admission = _RuntimeAdmission(
        _AdmissionDecision(
            allowed=False,
            failure_code="runtime_unavailable",
            status_code=503,
            reason="external invocation disabled by runtime config",
        )
    )
    invoker = WorkflowRunInvoker(
        run_service=run_service,
        execution_service=_NoCallExecutionService(),
        runtime_admission=admission,
    )

    result = await invoker.invoke(_direct_api_invocation())

    assert _field(result, "accepted") is False
    assert _value(_field(result, "failure_code")) == "runtime_unavailable"
    assert _field(result, "status_code") == 503
    assert _field(result, "details") == {"reason": "external invocation disabled by runtime config"}
    assert admission.calls
    assert run_service.create_calls == []


@pytest.mark.asyncio
async def test_admission_saturation_returns_typed_429_before_run_creation() -> None:
    WorkflowRunInvoker, _ = _invoker_contract()
    run_service = _RecordingRunService()
    admission = _RuntimeAdmission(
        _AdmissionDecision(
            allowed=False,
            failure_code="admission_saturated",
            status_code=429,
            reason="external invocation admission is saturated",
        )
    )
    invoker = WorkflowRunInvoker(
        run_service=run_service,
        execution_service=_NoCallExecutionService(),
        runtime_admission=admission,
    )

    result = await invoker.invoke(_direct_api_invocation())

    assert _field(result, "accepted") is False
    assert _value(_field(result, "failure_code")) == "admission_saturated"
    assert _field(result, "status_code") == 429
    assert _field(result, "details") == {"reason": "external invocation admission is saturated"}
    assert admission.calls
    assert run_service.create_calls == []


def test_external_admission_uses_shared_runtime_config_primitives() -> None:
    from runsight_api.logic.services.trigger_runtime import (
        ExternalInvocationAdmission,
        TriggerRuntimeConfig,
    )

    config = TriggerRuntimeConfig(
        external_invocation_enabled=False,
        max_concurrent_runs=1,
        max_pending_external_invocations=1,
        body_limit_bytes=1_048_576,
        public_base_url=None,
    )
    admission = ExternalInvocationAdmission(config)

    decision = admission.check_external_invocation(_direct_api_invocation())

    assert decision.allowed is False
    assert decision.failure_code == "runtime_unavailable"
    assert decision.status_code == 503
