"""StreamingObserver: bridges core WorkflowObserver protocol to an asyncio.Queue for SSE streaming."""

import asyncio
from datetime import datetime
from typing import Any, Dict, Optional

from runsight_core.primitives import Soul
from runsight_core.state import WorkflowState

from ...domain.events import (
    SSE_NODE_COMPLETED,
    SSE_NODE_FAILED,
    SSE_NODE_STARTED,
    SSE_RUN_COMPLETED,
    SSE_RUN_FAILED,
    SSE_RUN_STARTED,
)


class StreamingObserver:
    """Implements WorkflowObserver protocol, pushing events to an asyncio.Queue.

    The GUI SSE endpoint drains this queue to stream real-time execution events.
    """

    def __init__(self, *, run_id: str):
        self.run_id = run_id
        self.queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
        self.is_done: bool = False

    def on_workflow_start(self, workflow_name: str, state: WorkflowState) -> None:
        self.queue.put_nowait({"event": SSE_RUN_STARTED, "data": {"run_id": self.run_id}})

    def on_block_start(
        self, workflow_name: str, block_id: str, block_type: str, *, soul: Optional[Soul] = None
    ) -> None:
        self.queue.put_nowait(
            {"event": SSE_NODE_STARTED, "data": {"node_id": block_id, "block_type": block_type}}
        )

    def on_block_complete(
        self,
        workflow_name: str,
        block_id: str,
        block_type: str,
        duration_s: float,
        state: WorkflowState,
        *,
        soul: Optional[Soul] = None,
    ) -> None:
        self.queue.put_nowait(
            {
                "event": SSE_NODE_COMPLETED,
                "data": {
                    "node_id": block_id,
                    "block_type": block_type,
                    "duration_s": duration_s,
                    "cost_usd": state.total_cost_usd,
                    "tokens": state.total_tokens,
                },
            }
        )

    def on_block_error(
        self,
        workflow_name: str,
        block_id: str,
        block_type: str,
        duration_s: float,
        error: Exception,
    ) -> None:
        self.queue.put_nowait(
            {
                "event": SSE_NODE_FAILED,
                "data": {
                    "node_id": block_id,
                    "block_type": block_type,
                    "duration_s": duration_s,
                    "error": str(error),
                },
            }
        )

    def on_workflow_complete(
        self, workflow_name: str, state: WorkflowState, duration_s: float
    ) -> None:
        self.queue.put_nowait(
            {
                "event": SSE_RUN_COMPLETED,
                "data": {
                    "run_id": self.run_id,
                    "duration_s": duration_s,
                    "total_cost_usd": state.total_cost_usd,
                    "total_tokens": state.total_tokens,
                },
            }
        )
        self.is_done = True

    def on_block_heartbeat(
        self,
        workflow_name: str,
        block_id: str,
        phase: str,
        detail: str,
        timestamp: datetime,
    ) -> None:
        self.queue.put_nowait(
            {
                "event": "node_heartbeat",
                "data": {
                    "node_id": block_id,
                    "phase": phase,
                    "detail": detail,
                },
            }
        )

    def on_workflow_error(self, workflow_name: str, error: Exception, duration_s: float) -> None:
        self.queue.put_nowait(
            {
                "event": SSE_RUN_FAILED,
                "data": {
                    "run_id": self.run_id,
                    "error": str(error),
                    "duration_s": duration_s,
                },
            }
        )
        self.is_done = True
