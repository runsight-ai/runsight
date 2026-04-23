"""StreamingObserver: bridges core WorkflowObserver protocol to an asyncio.Queue for SSE streaming."""

import asyncio
from datetime import datetime
from typing import Any, Callable, Dict, Optional

from runsight_core.context_governance import (
    ContextAuditEventV1,
    redact_context_audit_event_preview,
)
from runsight_core.primitives import Soul
from runsight_core.redaction import redact_runtime_value_for_state, redact_text_for_state
from runsight_core.state import WorkflowState

from ...domain.events import (
    SSE_CHILD_RUN_COMPLETED,
    SSE_CONTEXT_RESOLUTION,
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

    def __init__(
        self,
        *,
        run_id: str,
        parent_run_id: Optional[str] = None,
        queue: asyncio.Queue[Dict[str, Any]] | None = None,
        parent_summary_queue: asyncio.Queue[Dict[str, Any]] | None = None,
        register_stream: Callable[[str, "StreamingObserver"], None] | None = None,
        unregister_stream: Callable[[str], None] | None = None,
        child_owns_terminal_stream: bool = False,
    ):
        self.run_id = run_id
        self.parent_run_id = parent_run_id
        self.queue: asyncio.Queue[Dict[str, Any]] = queue or asyncio.Queue()
        self.parent_summary_queue = parent_summary_queue
        self._register_stream = register_stream
        self._unregister_stream = unregister_stream
        self._child_owns_terminal_stream = child_owns_terminal_stream
        self._child_queues: dict[str, asyncio.Queue[Dict[str, Any]]] = {}
        self.is_done: bool = False

    def child_queue_for_run(self, child_run_id: str) -> asyncio.Queue[Dict[str, Any]]:
        queue = self._child_queues.get(child_run_id)
        if queue is None:
            queue = asyncio.Queue()
            self._child_queues[child_run_id] = queue
        return queue

    def clone_for_child_run(self, *, child_run_id: str) -> "StreamingObserver":
        child = StreamingObserver(
            run_id=child_run_id,
            parent_run_id=self.run_id,
            queue=self.child_queue_for_run(child_run_id),
            parent_summary_queue=self.queue,
            register_stream=self._register_stream,
            unregister_stream=self._unregister_stream,
            child_owns_terminal_stream=True,
        )
        if self._register_stream is not None:
            self._register_stream(child_run_id, child)
        return child

    def on_workflow_start(self, workflow_name: str, state: WorkflowState) -> None:
        self.queue.put_nowait({"event": SSE_RUN_STARTED, "data": {"run_id": self.run_id}})

    def on_block_start(
        self,
        workflow_name: str,
        block_id: str,
        block_type: str,
        *,
        soul: Optional[Soul] = None,
        **kwargs: Any,
    ) -> None:
        data: Dict[str, Any] = {"node_id": block_id, "block_type": block_type}
        if "child_run_id" in kwargs:
            data["child_run_id"] = kwargs["child_run_id"]
        self.queue.put_nowait({"event": SSE_NODE_STARTED, "data": data})

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
        *,
        state: WorkflowState | None = None,
    ) -> None:
        self.queue.put_nowait(
            redact_runtime_value_for_state(
                {
                    "event": SSE_NODE_FAILED,
                    "data": {
                        "node_id": block_id,
                        "block_type": block_type,
                        "duration_s": duration_s,
                        "error": str(error),
                    },
                },
                state,
            )
        )

    def on_workflow_complete(
        self, workflow_name: str, state: WorkflowState, duration_s: float
    ) -> None:
        if self.parent_run_id is not None and self._child_owns_terminal_stream:
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
            if self.parent_summary_queue is not None:
                self.parent_summary_queue.put_nowait(
                    {
                        "event": SSE_CHILD_RUN_COMPLETED,
                        "data": {
                            "run_id": self.run_id,
                            "parent_run_id": self.parent_run_id,
                            "child_run_id": self.run_id,
                            "duration_s": duration_s,
                            "total_cost_usd": state.total_cost_usd,
                            "total_tokens": state.total_tokens,
                        },
                    }
                )
            if self._unregister_stream is not None:
                self._unregister_stream(self.run_id)
        elif self.parent_run_id is not None:
            # Compatibility path for manually-constructed child observers.
            self.queue.put_nowait(
                {
                    "event": SSE_CHILD_RUN_COMPLETED,
                    "data": {
                        "run_id": self.run_id,
                        "parent_run_id": self.parent_run_id,
                        "child_run_id": self.run_id,
                        "duration_s": duration_s,
                        "total_cost_usd": state.total_cost_usd,
                        "total_tokens": state.total_tokens,
                    },
                }
            )
        else:
            # Root run: terminal event
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

    def on_workflow_error(
        self,
        workflow_name: str,
        error: Exception,
        duration_s: float,
        *,
        state: WorkflowState | None = None,
    ) -> None:
        self.queue.put_nowait(
            {
                "event": SSE_RUN_FAILED,
                "data": {
                    "run_id": self.run_id,
                    "error": redact_text_for_state(str(error), state),
                    "duration_s": duration_s,
                },
            }
        )
        self.is_done = True
        if self.parent_run_id is not None and self._child_owns_terminal_stream:
            if self._unregister_stream is not None:
                self._unregister_stream(self.run_id)

    def on_context_resolution(self, event: ContextAuditEventV1) -> None:
        event = redact_context_audit_event_preview(event)
        self.queue.put_nowait(
            {
                "event": SSE_CONTEXT_RESOLUTION,
                "data": event.model_dump(mode="json"),
            }
        )
