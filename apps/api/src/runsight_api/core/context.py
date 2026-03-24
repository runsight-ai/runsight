"""ContextVars for request/execution tracing, bridged to structlog."""

import sys
from contextvars import ContextVar

import structlog

request_id: ContextVar[str] = ContextVar("request_id", default="")
run_id: ContextVar[str] = ContextVar("run_id", default="")
block_id: ContextVar[str] = ContextVar("block_id", default="")
workflow_name: ContextVar[str] = ContextVar("workflow_name", default="")

# Keep references that won't be shadowed by parameter names
_module = sys.modules[__name__]


def bind_request_context(rid: str) -> None:
    """Set request_id in both ContextVar and structlog context."""
    request_id.set(rid)
    structlog.contextvars.bind_contextvars(request_id=rid)


def bind_execution_context(*, run_id: str, workflow_name: str) -> None:
    """Set run_id and workflow_name in both ContextVar and structlog context."""
    getattr(_module, "run_id").set(run_id)
    getattr(_module, "workflow_name").set(workflow_name)
    structlog.contextvars.bind_contextvars(run_id=run_id, workflow_name=workflow_name)


def bind_block_context(bid: str) -> None:
    """Set block_id in both ContextVar and structlog context."""
    block_id.set(bid)
    structlog.contextvars.bind_contextvars(block_id=bid)


def clear_block_context() -> None:
    """Reset block_id but leave execution context intact."""
    block_id.set("")
    structlog.contextvars.unbind_contextvars("block_id")


def clear_execution_context() -> None:
    """Reset run_id, workflow_name, and block_id."""
    run_id.set("")
    workflow_name.set("")
    block_id.set("")
    structlog.contextvars.unbind_contextvars("run_id", "workflow_name", "block_id")
