"""StreamingObserver: bridges core WorkflowObserver protocol to an asyncio.Queue for SSE streaming."""

import asyncio
from typing import Any, Dict

from runsight_core.state import WorkflowState


class StreamingObserver:
    """Implements WorkflowObserver protocol, pushing events to an asyncio.Queue.

    The GUI SSE endpoint drains this queue to stream real-time execution events.
    """

    def __init__(self, *, run_id: str):
        self.run_id = run_id
        self.queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
        self.is_done: bool = False

    def on_workflow_start(self, workflow_name: str, state: WorkflowState) -> None:
        self.queue.put_nowait({"event": "run_started", "data": {"run_id": self.run_id}})

    def on_block_start(self, workflow_name: str, block_id: str, block_type: str) -> None:
        self.queue.put_nowait(
            {"event": "node_started", "data": {"node_id": block_id, "block_type": block_type}}
        )

    def on_block_complete(
        self,
        workflow_name: str,
        block_id: str,
        block_type: str,
        duration_s: float,
        state: WorkflowState,
    ) -> None:
        self.queue.put_nowait(
            {
                "event": "node_completed",
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
                "event": "node_failed",
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
                "event": "run_completed",
                "data": {
                    "run_id": self.run_id,
                    "duration_s": duration_s,
                    "total_cost_usd": state.total_cost_usd,
                    "total_tokens": state.total_tokens,
                },
            }
        )
        self.is_done = True

    def on_workflow_error(self, workflow_name: str, error: Exception, duration_s: float) -> None:
        self.queue.put_nowait(
            {
                "event": "run_failed",
                "data": {
                    "run_id": self.run_id,
                    "error": str(error),
                    "duration_s": duration_s,
                },
            }
        )
        self.is_done = True
