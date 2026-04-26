"""RED tests for RUN-944 WorkflowRunInvoker runtime guardrails."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import pytest

from runsight_api.domain.entities.run import RunStatus


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


@dataclass(frozen=True)
class _ResolvedWorkflowSnapshot:
    workflow_id: str
    branch: str
    workflow: Any
    commit_sha: str = "9449449449449449449449449449449449449449"


class _SlotRunService:
    def __init__(self) -> None:
        self.created_runs: dict[str, Any] = {}
        self.create_calls: list[dict[str, Any]] = []
        self.fail_calls: list[dict[str, Any]] = []

    def create_run(
        self,
        workflow_id: str,
        inputs: Any,
        *,
        branch: str,
        source: str,
        source_correlation_id: str | None = None,
        source_metadata: dict[str, Any] | None = None,
        workflow_snapshot: Any | None = None,
    ) -> Any:
        run_id = f"run_slot_{len(self.created_runs) + 1}"
        self.create_calls.append(
            {
                "workflow_id": workflow_id,
                "inputs": inputs,
                "branch": branch,
                "source": source,
                "source_correlation_id": source_correlation_id,
                "source_metadata": source_metadata,
                "workflow_snapshot": workflow_snapshot,
            }
        )
        run = SimpleNamespace(
            id=run_id,
            workflow_id=workflow_id,
            status=RunStatus.pending,
            commit_sha=None,
        )
        self.created_runs[run_id] = run
        return run

    def get_run(self, run_id: str) -> Any | None:
        return self.created_runs.get(run_id)

    def fail_run(self, run_id: str, error: str) -> Any:
        self.fail_calls.append({"run_id": run_id, "error": error})
        run = self.created_runs[run_id]
        run.status = RunStatus.failed
        run.error = error
        return run


class _SlotHoldingExecutionService:
    def __init__(
        self,
        *,
        entered_launch: asyncio.Event | None = None,
        release_launch: asyncio.Event | None = None,
        launch_error: Exception | None = None,
    ) -> None:
        self.entered_launch = entered_launch
        self.release_launch = release_launch
        self.launch_error = launch_error
        self.resolve_calls: list[dict[str, Any]] = []
        self.prepare_calls: list[dict[str, Any]] = []
        self.launch_calls: list[dict[str, Any]] = []

    def resolve_workflow_run_snapshot(
        self, workflow_id: str, *, branch: str
    ) -> _ResolvedWorkflowSnapshot:
        self.resolve_calls.append({"workflow_id": workflow_id, "branch": branch})
        return _ResolvedWorkflowSnapshot(
            workflow_id=workflow_id,
            branch=branch,
            workflow=SimpleNamespace(name="Committed Main Workflow"),
        )

    def prepare_run_inputs_from_snapshot(
        self,
        snapshot: _ResolvedWorkflowSnapshot,
        inputs: dict[str, Any],
    ) -> dict[str, Any]:
        self.prepare_calls.append(
            {"workflow_id": snapshot.workflow_id, "branch": snapshot.branch, "inputs": inputs}
        )
        return {"normalized_inputs": dict(inputs)}

    async def launch_execution_from_snapshot(
        self,
        run_id: str,
        workflow_id: str,
        inputs: Any,
        *,
        snapshot: _ResolvedWorkflowSnapshot,
    ) -> None:
        self.launch_calls.append(
            {
                "run_id": run_id,
                "workflow_id": workflow_id,
                "inputs": inputs,
                "branch": snapshot.branch,
            }
        )
        if self.entered_launch is not None:
            self.entered_launch.set()
        if self.release_launch is not None:
            await self.release_launch.wait()
        if self.launch_error is not None:
            raise self.launch_error


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


def test_external_admission_tracks_pending_capacity_and_releases() -> None:
    from runsight_api.logic.services.trigger_runtime import (
        ExternalInvocationAdmission,
        TriggerRuntimeConfig,
    )

    config = TriggerRuntimeConfig(
        external_invocation_enabled=True,
        max_concurrent_runs=3,
        max_pending_external_invocations=2,
        body_limit_bytes=1_048_576,
        public_base_url=None,
    )
    admission = ExternalInvocationAdmission(config)

    first = admission.acquire_external_invocation(_direct_api_invocation())
    second = admission.acquire_external_invocation(_direct_api_invocation())
    saturated = admission.acquire_external_invocation(_direct_api_invocation())

    assert first.allowed is True
    assert second.allowed is True
    assert saturated.allowed is False
    assert saturated.failure_code == "admission_saturated"
    assert saturated.status_code == 429
    assert admission.pending_external_invocations == 2

    admission.release_external_invocation()

    after_release = admission.acquire_external_invocation(_direct_api_invocation())
    assert after_release.allowed is True
    assert admission.pending_external_invocations == 2


def test_external_admission_respects_concurrent_run_capacity() -> None:
    from runsight_api.logic.services.trigger_runtime import (
        ExternalInvocationAdmission,
        TriggerRuntimeConfig,
    )

    config = TriggerRuntimeConfig(
        external_invocation_enabled=True,
        max_concurrent_runs=1,
        max_pending_external_invocations=5,
        body_limit_bytes=1_048_576,
        public_base_url=None,
    )
    admission = ExternalInvocationAdmission(config)

    admitted = admission.acquire_external_invocation(_direct_api_invocation())
    saturated = admission.acquire_external_invocation(_direct_api_invocation())

    assert admitted.allowed is True
    assert saturated.allowed is False
    assert saturated.failure_code == "admission_saturated"
    assert saturated.status_code == 429


@pytest.mark.asyncio
async def test_invoker_uses_external_invocation_slot_for_capacity_and_release() -> None:
    from runsight_api.logic.services.trigger_runtime import (
        ExternalInvocationAdmission,
        TriggerRuntimeConfig,
    )

    WorkflowRunInvoker, _ = _invoker_contract()
    config = TriggerRuntimeConfig(
        external_invocation_enabled=True,
        max_concurrent_runs=1,
        max_pending_external_invocations=1,
        body_limit_bytes=1_048_576,
        public_base_url=None,
    )
    admission = ExternalInvocationAdmission(config)
    run_service = _SlotRunService()
    entered_launch = asyncio.Event()
    release_launch = asyncio.Event()
    invoker = WorkflowRunInvoker(
        run_service=run_service,
        execution_service=_SlotHoldingExecutionService(
            entered_launch=entered_launch,
            release_launch=release_launch,
        ),
        runtime_admission=admission,
    )

    first_task = asyncio.create_task(invoker.invoke(_direct_api_invocation()))
    await asyncio.wait_for(entered_launch.wait(), timeout=1)

    assert admission.pending_external_invocations == 1

    saturated = await invoker.invoke(_direct_api_invocation())

    assert _field(saturated, "accepted") is False
    assert _value(_field(saturated, "failure_code")) == "admission_saturated"
    assert _field(saturated, "status_code") == 429
    assert admission.pending_external_invocations == 1
    assert len(run_service.create_calls) == 1

    release_launch.set()
    first = await asyncio.wait_for(first_task, timeout=1)

    assert _field(first, "accepted") is True
    assert admission.pending_external_invocations == 0

    after_release = await invoker.invoke(_direct_api_invocation())

    assert _field(after_release, "accepted") is True
    assert admission.pending_external_invocations == 0


@pytest.mark.asyncio
async def test_invoker_releases_external_invocation_slot_after_launch_exception() -> None:
    from runsight_api.logic.services.trigger_runtime import (
        ExternalInvocationAdmission,
        TriggerRuntimeConfig,
    )

    WorkflowRunInvoker, _ = _invoker_contract()
    config = TriggerRuntimeConfig(
        external_invocation_enabled=True,
        max_concurrent_runs=1,
        max_pending_external_invocations=1,
        body_limit_bytes=1_048_576,
        public_base_url=None,
    )
    admission = ExternalInvocationAdmission(config)
    invoker = WorkflowRunInvoker(
        run_service=_SlotRunService(),
        execution_service=_SlotHoldingExecutionService(
            launch_error=RuntimeError("snapshot launch failed")
        ),
        runtime_admission=admission,
    )

    result = await invoker.invoke(_direct_api_invocation())

    assert _field(result, "accepted") is False
    assert _value(_field(result, "failure_code")) == "execution_launch_failed"
    assert admission.pending_external_invocations == 0
