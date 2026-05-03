import asyncio

import pytest

from runsight_api.domain.events import SSE_RUN_COMPLETED, SSE_RUN_FAILED
from runsight_api.logic.observers.streaming_observer import StreamingObserver
from runsight_api.logic.services.execution_stream_registry import ExecutionStreamRegistry


def test_unregister_clears_non_terminal_observer_event_state() -> None:
    registry = ExecutionStreamRegistry()
    observer = StreamingObserver(run_id="run_cleanup_pending")

    registry.register("run_cleanup_pending", observer)

    assert "run_cleanup_pending" in registry._observer_events

    registry.unregister("run_cleanup_pending")

    assert registry.get("run_cleanup_pending") is None
    assert "run_cleanup_pending" not in registry._observer_events
    assert "run_cleanup_pending" not in registry._completed_streams


def test_completed_stream_cache_is_bounded() -> None:
    registry = ExecutionStreamRegistry()

    for index in range(registry.COMPLETED_STREAM_CACHE_SIZE + 5):
        run_id = f"run_completed_{index}"
        observer = StreamingObserver(run_id=run_id)
        registry.register(run_id, observer)
        observer.is_done = True
        registry.unregister(run_id)

    assert len(registry._completed_streams) == registry.COMPLETED_STREAM_CACHE_SIZE
    assert "run_completed_0" not in registry._completed_streams
    assert (
        f"run_completed_{registry.COMPLETED_STREAM_CACHE_SIZE + 4}" in registry._completed_streams
    )


async def _drain_completed_subscription(registry: ExecutionStreamRegistry, run_id: str):
    observed = []
    async for event in registry.subscribe(run_id):
        observed.append(event)
    return observed


@pytest.mark.parametrize("terminal_event", [SSE_RUN_COMPLETED, SSE_RUN_FAILED])
def test_completed_stream_marker_allows_one_late_terminal_drain(terminal_event: str) -> None:
    registry = ExecutionStreamRegistry()
    run_id = "run_completed_late_subscriber"
    observer = StreamingObserver(run_id=run_id)

    registry.register(run_id, observer)
    observer.queue.put_nowait({"event": terminal_event, "data": {"run_id": run_id}})
    observer.is_done = True
    registry.unregister(run_id)

    observed = asyncio.run(_drain_completed_subscription(registry, run_id))
    observed_again = asyncio.run(_drain_completed_subscription(registry, run_id))

    assert observed == [{"event": terminal_event, "data": {"run_id": run_id}}]
    assert observed_again == []


def test_subscribe_timeout_cleans_placeholder_ready_event() -> None:
    registry = ExecutionStreamRegistry()
    registry.OBSERVER_REGISTRATION_TIMEOUT_S = 0.01

    observed = asyncio.run(_drain_completed_subscription(registry, "run_never_registered"))

    assert observed == []
    assert "run_never_registered" not in registry._observer_events
