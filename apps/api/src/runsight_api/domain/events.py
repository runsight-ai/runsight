from dataclasses import dataclass
from typing import Optional

# ---------------------------------------------------------------------------
# SSE event type constants
# ---------------------------------------------------------------------------
# Used by StreamingObserver (producer) and ExecutionService.subscribe_stream
# (consumer) so that event names are defined in exactly one place.

SSE_RUN_STARTED: str = "run_started"
SSE_RUN_COMPLETED: str = "run_completed"
SSE_RUN_FAILED: str = "run_failed"

SSE_NODE_STARTED: str = "node_started"
SSE_NODE_COMPLETED: str = "node_completed"
SSE_NODE_FAILED: str = "node_failed"
SSE_CONTEXT_RESOLUTION: str = "context_resolution"

SSE_CHILD_RUN_COMPLETED: str = "child_run_completed"

# Terminal events that signal the end of an SSE stream.
SSE_TERMINAL_EVENTS: tuple[str, ...] = (SSE_RUN_COMPLETED, SSE_RUN_FAILED)


@dataclass
class RunStarted:
    run_id: str
    timestamp: float


@dataclass
class NodeCompleted:
    run_id: str
    node_id: str
    timestamp: float
    output: Optional[str] = None
    cost_usd: float = 0.0


@dataclass
class NodeFailed:
    run_id: str
    node_id: str
    timestamp: float
    error: str


@dataclass
class RunCompleted:
    run_id: str
    timestamp: float


@dataclass
class RunFailed:
    run_id: str
    timestamp: float
    error: str


@dataclass
class RunCancelled:
    run_id: str
    timestamp: float
    reason: Optional[str] = None
