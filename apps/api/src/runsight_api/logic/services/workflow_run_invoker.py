from __future__ import annotations

import asyncio
import copy
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Literal, Mapping

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
    status_code: int | None = None
    details: dict[str, Any] | None = None
    commit_sha: str | None = None

    @classmethod
    def failure(
        cls,
        failure_code: WorkflowRunInvocationFailureCode | str,
        *,
        run_id: str | None = None,
        status: RunStatus | str | None = None,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> WorkflowRunInvocationResult:
        return cls(
            accepted=False,
            run_id=run_id,
            status=status,
            failure_code=failure_code,
            status_code=status_code,
            details=details,
        )


class WorkflowRunInvoker:
    def __init__(self, *, run_service: Any, execution_service: Any, runtime_admission: Any):
        self.run_service = run_service
        self.execution_service = execution_service
        self.runtime_admission = runtime_admission

    async def invoke(self, invocation: WorkflowRunInvocation) -> WorkflowRunInvocationResult:
        acquire = getattr(self.runtime_admission, "acquire_external_invocation", None)
        release = getattr(self.runtime_admission, "release_external_invocation", None)
        if callable(acquire) and callable(release):
            decision = acquire(invocation)
            admission_failure = self._admission_decision_failure(decision)
            if admission_failure is not None:
                return admission_failure

            release_on_return = True
            try:
                result, completion = await self._invoke_admitted(invocation)
                release_on_return = not self._release_on_completion(completion, release)
                return result
            finally:
                if release_on_return:
                    release()

        admission_failure = self._check_admission_failure(invocation)
        if admission_failure is not None:
            return admission_failure

        result, _completion = await self._invoke_admitted(invocation)
        return result

    async def _invoke_admitted(
        self, invocation: WorkflowRunInvocation
    ) -> tuple[WorkflowRunInvocationResult, Any | None]:
        try:
            resolved_snapshot, prepared_inputs = await asyncio.to_thread(
                self._resolve_and_prepare, invocation
            )
            workflow_snapshot = resolved_snapshot.workflow
        except InputValidationError as exc:
            return (
                WorkflowRunInvocationResult.failure(
                    WorkflowRunInvocationFailureCode.workflow_input_validation_failed,
                    details=exc.to_dict(),
                ),
                None,
            )
        except WorkflowNotFound:
            return (
                WorkflowRunInvocationResult.failure(
                    WorkflowRunInvocationFailureCode.workflow_not_found
                ),
                None,
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
            completion = await self.execution_service.launch_execution_from_snapshot(
                run.id,
                run.workflow_id,
                prepared_inputs,
                snapshot=resolved_snapshot,
            )
            if isinstance(completion, asyncio.Future):
                await completion
        except Exception as exc:
            failed_run = self.run_service.fail_run(run.id, str(exc))
            return (
                WorkflowRunInvocationResult.failure(
                    WorkflowRunInvocationFailureCode.execution_launch_failed,
                    run_id=run.id,
                    status=getattr(failed_run, "status", None),
                ),
                None,
            )

        refreshed = self.run_service.get_run(run.id) or run
        if getattr(refreshed, "status", None) in {RunStatus.failed, RunStatus.failed.value}:
            return (
                WorkflowRunInvocationResult.failure(
                    WorkflowRunInvocationFailureCode.execution_launch_failed,
                    run_id=run.id,
                    status=getattr(refreshed, "status", None),
                ),
                completion,
            )
        return (
            WorkflowRunInvocationResult(
                accepted=True,
                run_id=run.id,
                status=getattr(refreshed, "status", None),
                commit_sha=getattr(refreshed, "commit_sha", None),
            ),
            completion,
        )

    def _resolve_and_prepare(self, invocation: WorkflowRunInvocation) -> tuple[Any, Any]:
        resolved_snapshot = self.execution_service.resolve_workflow_run_snapshot(
            invocation.workflow_id, branch=invocation.branch
        )
        workflow_snapshot = getattr(resolved_snapshot, "workflow", None)
        if _workflow_snapshot_is_explicitly_disabled(workflow_snapshot):
            raise WorkflowNotFound(
                f"Workflow {invocation.workflow_id!r} not found on {invocation.branch!r}"
            )
        prepared_inputs = self.execution_service.prepare_run_inputs_from_snapshot(
            resolved_snapshot,
            invocation.inputs,
        )
        return resolved_snapshot, prepared_inputs

    def _release_on_completion(
        self,
        completion: Any,
        release: Callable[[], None],
    ) -> bool:
        add_done_callback = getattr(completion, "add_done_callback", None)
        if not callable(add_done_callback):
            return False
        if not getattr(completion, "release_external_invocation_on_done", False):
            return False

        done = getattr(completion, "done", None)
        if callable(done) and done():
            return False

        add_done_callback(lambda _task: release())
        return True

    def _check_admission_failure(
        self, invocation: WorkflowRunInvocation
    ) -> WorkflowRunInvocationResult | None:
        decision = self._check_admission(invocation)
        return self._admission_decision_failure(decision)

    def _admission_decision_failure(self, decision: Any) -> WorkflowRunInvocationResult | None:
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
        status_code = getattr(decision, "status_code", None)
        details = getattr(decision, "details", None)
        reason = getattr(decision, "reason", None)
        if details is None and reason:
            details = {"reason": reason}
        return WorkflowRunInvocationResult.failure(
            failure_code,
            status_code=status_code,
            details=details,
        )

    def _check_admission(self, invocation: WorkflowRunInvocation) -> Any:
        for method_name in ("check_external_invocation", "check", "admit"):
            method = getattr(self.runtime_admission, method_name, None)
            if method is not None:
                return method(invocation)
        return True


def _workflow_snapshot_is_explicitly_disabled(workflow_snapshot: Any) -> bool:
    if getattr(workflow_snapshot, "enabled", True) is not False:
        return False

    fields_set = getattr(workflow_snapshot, "model_fields_set", None)
    if fields_set is None:
        fields_set = getattr(workflow_snapshot, "__fields_set__", None)
    if isinstance(fields_set, set):
        return "enabled" in fields_set
    return True
