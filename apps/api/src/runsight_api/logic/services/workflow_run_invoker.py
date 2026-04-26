from __future__ import annotations

import copy
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterator, Literal, Mapping

from ...domain.entities.run import RunStatus, validate_source_metadata
from ...domain.errors import InputValidationError, WorkflowNotFound

DIRECT_API_BRANCH = "main"


class WorkflowRunInvocationFailureCode(str, Enum):
    runtime_unavailable = "runtime_unavailable"
    admission_saturated = "admission_saturated"
    workflow_input_validation_failed = "workflow_input_validation_failed"
    workflow_not_found = "workflow_not_found"
    execution_launch_failed = "execution_launch_failed"


@dataclass(frozen=True, slots=True)
class WorkflowRunInvocation:
    workflow_id: str
    caller: Literal["api"]
    source: Literal["api"]
    inputs: dict[str, Any]
    branch: Literal["main"] = DIRECT_API_BRANCH
    commit_sha: None = None
    source_correlation_id: str | None = None
    source_metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def direct_api(
        cls,
        *,
        workflow_id: str,
        inputs: Mapping[str, Any] | None,
        source_correlation_id: str | None = None,
        source_metadata: Mapping[str, Any] | None = None,
    ) -> WorkflowRunInvocation:
        safe_metadata = validate_source_metadata(dict(source_metadata or {}))
        return cls(
            workflow_id=workflow_id,
            caller="api",
            source="api",
            inputs=dict(inputs or {}),
            source_correlation_id=source_correlation_id,
            source_metadata=copy.deepcopy(safe_metadata),
        )


@dataclass(frozen=True, slots=True)
class WorkflowRunInvocationResult:
    accepted: bool
    run_id: str | None = None
    status: RunStatus | str | None = None
    failure_code: WorkflowRunInvocationFailureCode | str | None = None
    details: dict[str, Any] | None = None
    commit_sha: str | None = None

    @classmethod
    def failure(
        cls,
        failure_code: WorkflowRunInvocationFailureCode | str,
        *,
        run_id: str | None = None,
        status: RunStatus | str | None = None,
        details: dict[str, Any] | None = None,
    ) -> WorkflowRunInvocationResult:
        return cls(
            accepted=False,
            run_id=run_id,
            status=status,
            failure_code=failure_code,
            details=details,
        )


class WorkflowRunInvoker:
    def __init__(self, *, run_service: Any, execution_service: Any, runtime_admission: Any):
        self.run_service = run_service
        self.execution_service = execution_service
        self.runtime_admission = runtime_admission

    async def invoke(self, invocation: WorkflowRunInvocation) -> WorkflowRunInvocationResult:
        admission_failure = self._admission_failure(invocation)
        if admission_failure is not None:
            return admission_failure

        try:
            prepared_inputs = self.execution_service.prepare_run_inputs(
                invocation.workflow_id,
                invocation.inputs,
                branch=invocation.branch,
            )
            workflow_snapshot = self.execution_service.workflow_snapshot_for_run(
                invocation.workflow_id,
                branch=invocation.branch,
            )
        except InputValidationError as exc:
            return WorkflowRunInvocationResult.failure(
                WorkflowRunInvocationFailureCode.workflow_input_validation_failed,
                details=exc.to_dict(),
            )
        except WorkflowNotFound:
            return WorkflowRunInvocationResult.failure(
                WorkflowRunInvocationFailureCode.workflow_not_found
            )

        run = self.run_service.create_run(
            invocation.workflow_id,
            prepared_inputs,
            branch=invocation.branch,
            source=invocation.source,
            source_correlation_id=invocation.source_correlation_id,
            source_metadata=invocation.source_metadata,
            workflow_snapshot=workflow_snapshot,
        )

        try:
            with self._temporary_run_update_sink():
                await self.execution_service.launch_execution(
                    run.id,
                    run.workflow_id,
                    prepared_inputs,
                    branch=invocation.branch,
                )
        except Exception as exc:
            failed_run = self.run_service.fail_run(run.id, str(exc))
            return WorkflowRunInvocationResult.failure(
                WorkflowRunInvocationFailureCode.execution_launch_failed,
                run_id=run.id,
                status=getattr(failed_run, "status", None),
            )

        refreshed = self.run_service.get_run(run.id) or run
        return WorkflowRunInvocationResult(
            accepted=True,
            run_id=run.id,
            status=getattr(refreshed, "status", None),
            commit_sha=getattr(refreshed, "commit_sha", None),
        )

    def _admission_failure(
        self, invocation: WorkflowRunInvocation
    ) -> WorkflowRunInvocationResult | None:
        decision = self._check_admission(invocation)
        if decision is None or decision is True:
            return None
        if decision is False:
            return WorkflowRunInvocationResult.failure(
                WorkflowRunInvocationFailureCode.runtime_unavailable
            )
        allowed = getattr(decision, "allowed", True)
        if allowed:
            return None
        failure_code = getattr(
            decision,
            "failure_code",
            WorkflowRunInvocationFailureCode.runtime_unavailable,
        )
        return WorkflowRunInvocationResult.failure(failure_code)

    def _check_admission(self, invocation: WorkflowRunInvocation) -> Any:
        for method_name in ("check_external_invocation", "check", "admit"):
            method = getattr(self.runtime_admission, method_name, None)
            if method is not None:
                return method(invocation)
        return True

    @contextmanager
    def _temporary_run_update_sink(self) -> Iterator[None]:
        execution_run_service = getattr(self.execution_service, "run_service", None)
        if execution_run_service is not self.run_service or hasattr(self.run_service, "run_repo"):
            yield
            return

        self.run_service.run_repo = _RunUpdateSink()
        try:
            yield
        finally:
            del self.run_service.run_repo


class _RunUpdateSink:
    def update_run(self, run: Any) -> Any:
        return run
