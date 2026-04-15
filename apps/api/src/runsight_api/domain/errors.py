from __future__ import annotations

from runsight_api.core.context import (
    block_id as _block_id_var,
)
from runsight_api.core.context import (
    run_id as _run_id_var,
)
from runsight_api.core.context import (
    workflow_name as _workflow_name_var,
)


class RunsightError(Exception):
    """Base exception for all Runsight domain errors."""

    error_code: str = "RUNSIGHT_ERROR"
    status_code: int = 500

    def __init__(
        self,
        message: str,
        *,
        error_code: str | None = None,
        status_code: int | None = None,
        run_id: str | None = None,
        block_id: str | None = None,
        workflow_name: str | None = None,
        details: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if error_code is not None:
            self.error_code = error_code
        if status_code is not None:
            self.status_code = status_code

        # Auto-read from contextvars if not explicitly passed
        self.run_id = run_id if run_id is not None else (_run_id_var.get() or None)
        self.block_id = block_id if block_id is not None else (_block_id_var.get() or None)
        self.workflow_name = (
            workflow_name if workflow_name is not None else (_workflow_name_var.get() or None)
        )
        self.details = details

    def to_dict(self) -> dict:
        """Return a structured dict representation of this error."""
        result: dict = {
            "error": self.message,
            "error_code": self.error_code,
            "status_code": self.status_code,
        }
        if self.run_id:
            result["run_id"] = self.run_id
        if self.block_id:
            result["block_id"] = self.block_id
        if self.workflow_name:
            result["workflow_name"] = self.workflow_name
        if self.details:
            result["details"] = self.details
        return result


class WorkflowNotFound(RunsightError):
    """Raised when a workflow cannot be found."""

    error_code: str = "WORKFLOW_NOT_FOUND"
    status_code: int = 404


class WorkflowHasActiveRuns(RunsightError):
    """Raised when a workflow cannot be deleted because active runs still exist."""

    error_code: str = "WORKFLOW_HAS_ACTIVE_RUNS"
    status_code: int = 409


class RunNotFound(RunsightError):
    """Raised when a run cannot be found."""

    error_code: str = "RUN_NOT_FOUND"
    status_code: int = 404


class RunFailed(RunsightError):
    """Raised when a run fails execution."""

    error_code: str = "RUN_FAILED"
    status_code: int = 500


class ProviderNotConfigured(RunsightError):
    """Raised when a required provider is missing or not configured."""

    error_code: str = "PROVIDER_NOT_CONFIGURED"
    status_code: int = 400


class SoulNotFound(RunsightError):
    """Raised when a soul cannot be found."""

    error_code: str = "SOUL_NOT_FOUND"
    status_code: int = 404


class SoulAlreadyExists(RunsightError):
    """Raised when attempting to create a soul that already exists."""

    error_code: str = "SOUL_ALREADY_EXISTS"
    status_code: int = 409


class SoulInUse(RunsightError):
    """Raised when attempting to delete or replace a soul that is still referenced."""

    error_code: str = "SOUL_IN_USE"
    status_code: int = 409


class StepNotFound(RunsightError):
    """Raised when a step cannot be found."""

    error_code: str = "STEP_NOT_FOUND"
    status_code: int = 404


class ProviderNotFound(RunsightError):
    """Raised when a provider cannot be found."""

    error_code: str = "PROVIDER_NOT_FOUND"
    status_code: int = 404


class GitError(RunsightError):
    """Raised when a git operation fails."""

    error_code: str = "GIT_ERROR"
    status_code: int = 400


class EvalNotFound(RunsightError):
    """Raised when eval data for a run cannot be found."""

    error_code: str = "EVAL_NOT_FOUND"
    status_code: int = 404


class ServiceUnavailable(RunsightError):
    """Raised when a required service is not available."""

    error_code: str = "SERVICE_UNAVAILABLE"
    status_code: int = 503


class InputValidationError(RunsightError):
    """Raised when input validation fails."""

    error_code: str = "VALIDATION_ERROR"
    status_code: int = 400
