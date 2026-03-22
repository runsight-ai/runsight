class RunsightError(Exception):
    """Base exception for all Runsight domain errors."""

    pass


class WorkflowNotFound(RunsightError):
    """Raised when a workflow cannot be found."""

    pass


class RunNotFound(RunsightError):
    """Raised when a run cannot be found."""

    pass


class RunFailed(RunsightError):
    """Raised when a run fails execution."""

    pass


class ProviderNotConfigured(RunsightError):
    """Raised when a required provider is missing or not configured."""

    pass


class SoulNotFound(RunsightError):
    """Raised when a soul cannot be found."""

    pass


class TaskNotFound(RunsightError):
    """Raised when a task cannot be found."""

    pass


class StepNotFound(RunsightError):
    """Raised when a step cannot be found."""

    pass


class ProviderNotFound(RunsightError):
    """Raised when a provider cannot be found."""

    pass
