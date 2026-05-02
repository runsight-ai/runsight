"""StreamingObserver lifecycle smoke coverage."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from runsight_core.state import WorkflowState

from runsight_api.domain.events import (
    SSE_NODE_COMPLETED,
    SSE_NODE_FAILED,
    SSE_NODE_STARTED,
    SSE_RUN_COMPLETED,
    SSE_RUN_FAILED,
    SSE_RUN_STARTED,
)
from runsight_api.logic.observers.streaming_observer import StreamingObserver
from runsight_api.logic.services.execution_runtime import ExecutionRuntimeCoordinator


def _drain(observer: StreamingObserver) -> list[dict]:
    events = []
    while not observer.queue.empty():
        events.append(observer.queue.get_nowait())
    return events


def test_streaming_observer_emits_lifecycle_events() -> None:
    observer = StreamingObserver(run_id="stream-smoke-run")
    state = WorkflowState(total_cost_usd=0.02, total_tokens=9)

    observer.on_workflow_start("stream-smoke-flow", state)
    observer.on_block_start("stream-smoke-flow", "analyze", "LinearBlock")
    observer.on_block_heartbeat(
        "stream-smoke-flow",
        "analyze",
        "llm_call",
        "calling model",
        datetime.now(timezone.utc),
    )
    observer.on_block_complete("stream-smoke-flow", "analyze", "LinearBlock", 0.3, state)
    observer.on_workflow_complete("stream-smoke-flow", state, 0.4)

    events = _drain(observer)
    assert [event["event"] for event in events] == [
        SSE_RUN_STARTED,
        SSE_NODE_STARTED,
        "node_heartbeat",
        SSE_NODE_COMPLETED,
        SSE_RUN_COMPLETED,
    ]
    assert events[-1]["data"]["run_id"] == "stream-smoke-run"
    assert observer.is_done is True


def test_streaming_observer_emits_failure_events_and_marks_run_done() -> None:
    observer = StreamingObserver(run_id="stream-failure-run")

    observer.on_block_error("stream-failure-flow", "draft", "LinearBlock", 0.2, ValueError("bad"))
    observer.on_workflow_error("stream-failure-flow", RuntimeError("boom"), 0.4)

    events = _drain(observer)
    assert [event["event"] for event in events] == [SSE_NODE_FAILED, SSE_RUN_FAILED]
    assert events[-1]["data"]["run_id"] == "stream-failure-run"
    assert observer.is_done is True


@pytest.mark.asyncio
async def test_runtime_registers_streaming_observer_and_unregisters_on_success() -> None:
    registered: dict[str, StreamingObserver] = {}
    calls: list[tuple[str, str]] = []

    class _Streams:
        def register(self, run_id: str, observer: StreamingObserver) -> None:
            calls.append(("register", run_id))
            registered[run_id] = observer

        def unregister(self, run_id: str) -> None:
            calls.append(("unregister", run_id))
            registered.pop(run_id, None)

        def close_stream(self, run_id: str, observer=None) -> None:
            calls.append(("close", run_id))

    persistence = Mock()
    persistence.is_run_cancelled.return_value = False
    persistence.set_status.return_value = True
    runtime = ExecutionRuntimeCoordinator(
        engine=None,
        persistence=persistence,
        streams=_Streams(),
    )
    captured = None

    async def _run(state, observer=None, inputs=None):
        del inputs
        nonlocal captured
        captured = registered["runtime-stream-smoke"]
        observer.on_workflow_start("runtime-stream-smoke", state)
        observer.on_workflow_complete("runtime-stream-smoke", state, 0.1)

    await runtime.run_workflow(
        "runtime-stream-smoke",
        SimpleNamespace(run=_run),
        {"instruction": "smoke"},
    )

    assert calls == [
        ("register", "runtime-stream-smoke"),
        ("unregister", "runtime-stream-smoke"),
    ]
    assert [event["event"] for event in _drain(captured)] == [SSE_RUN_STARTED, SSE_RUN_COMPLETED]
