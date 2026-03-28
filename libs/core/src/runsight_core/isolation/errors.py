"""Error types for process-isolated block execution."""


class BlockExecutionError(Exception):
    """Raised when a block subprocess exits with a non-zero code or reports an error."""

    def __init__(self, message: str, original_error_type: str | None = None):
        super().__init__(message)
        self.original_error_type = original_error_type


class BlockStallError(Exception):
    """Raised when a block subprocess stalls (heartbeat or phase timeout)."""
