from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ...domain.errors import InputValidationError, RunFailed, RunNotFound, RunsightError
from .workflow_run_invoker import (
    WorkflowRunInvocation,
    WorkflowRunInvocationFailureCode,
    WorkflowRunInvoker,
)


class ApiRunService:
    """Route-facing service for external Direct API workflow invocations."""

    def __init__(
        self,
        *,
        run_service: Any,
        execution_service: Any,
        runtime_admission: Any,
    ) -> None:
        self.run_service = run_service
        self.execution_service = execution_service
        self.runtime_admission = runtime_admission

    async def create_direct_api_run(
        self,
        *,
        workflow_id: str,
        inputs: Mapping[str, Any],
        source_correlation_id: str | None,
        source_metadata: Mapping[str, Any],
    ) -> Any:
        if self.execution_service is None:
            raise RunsightError(
                "Execution runtime is unavailable",
                error_code="RUNTIME_UNAVAILABLE",
                status_code=503,
            )

        invocation = WorkflowRunInvocation.direct_api(
            workflow_id=workflow_id,
            inputs=inputs,
            source_correlation_id=source_correlation_id,
            source_metadata=source_metadata,
        )
        result = await WorkflowRunInvoker(
            run_service=self.run_service,
            execution_service=self.execution_service,
            runtime_admission=self.runtime_admission,
        ).invoke(invocation)

        if not result.accepted:
            self._raise_failure(result)

        if result.run_id is None:
            raise RunFailed("Run failed during launch")
        run = self.run_service.get_run(result.run_id)
        if run is None:
            raise RunNotFound(f"Run {result.run_id} not found")
        return run

    def _raise_failure(self, result: Any) -> None:
        failure_code = _failure_code_value(result.failure_code)
        if failure_code == WorkflowRunInvocationFailureCode.runtime_unavailable.value:
            raise RunsightError(
                "Execution runtime is unavailable",
                error_code="RUNTIME_UNAVAILABLE",
                status_code=result.status_code or 503,
                details=_safe_details(result.details),
            )
        if failure_code == WorkflowRunInvocationFailureCode.admission_saturated.value:
            raise RunsightError(
                "External invocation admission is saturated",
                error_code="ADMISSION_SATURATED",
                status_code=result.status_code or 429,
                details=_safe_details(result.details),
            )
        if failure_code == WorkflowRunInvocationFailureCode.workflow_not_found.value:
            raise RunsightError(
                "Workflow not found",
                error_code="WORKFLOW_NOT_FOUND",
                status_code=404,
            )
        if failure_code == WorkflowRunInvocationFailureCode.workflow_input_validation_failed.value:
            error_payload = result.details if isinstance(result.details, dict) else {}
            details = error_payload.get("details")
            raise InputValidationError(
                "Workflow input validation failed",
                error_code="WORKFLOW_INPUT_VALIDATION_ERROR",
                status_code=422,
                details=details if isinstance(details, dict) else None,
            )
        if failure_code == WorkflowRunInvocationFailureCode.execution_launch_failed.value:
            raise RunFailed("Run failed during launch", run_id=result.run_id)
        raise RunsightError("Run invocation failed", status_code=result.status_code or 500)


def _failure_code_value(value: Any) -> str:
    return str(getattr(value, "value", value))


def _safe_details(value: Any) -> dict[str, Any] | None:
    return value if isinstance(value, dict) else None
