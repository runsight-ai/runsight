from __future__ import annotations

import asyncio
from unittest.mock import Mock

from runsight_api.logic.observers.streaming_observer import StreamingObserver
from runsight_api.logic.services.execution_service import ExecutionService


def make_service(**kwargs) -> ExecutionService:
    return ExecutionService(
        run_repo=Mock(),
        workflow_repo=Mock(),
        provider_repo=Mock(),
        **kwargs,
    )


async def collect_stream(service: ExecutionService, run_id: str, events: list[dict]) -> None:
    async for event in service.subscribe_stream(run_id):
        events.append(event)


def terminal_observer(run_id: str, event: str = "run_completed") -> StreamingObserver:
    observer = StreamingObserver(run_id=run_id)
    observer.queue.put_nowait({"event": event, "data": {"run_id": run_id}})
    return observer


async def publish_registered_terminal_event(
    service: ExecutionService,
    run_id: str,
    *,
    delay: float = 0.05,
) -> None:
    await asyncio.sleep(delay)
    service._streams.register(run_id, terminal_observer(run_id))


def registered_parent_and_child(
    service: ExecutionService,
    *,
    parent_run_id: str = "run_stream_parent",
    child_run_id: str = "run_stream_child",
):
    parent = StreamingObserver(run_id=parent_run_id)
    child = parent.clone_for_child_run(child_run_id=child_run_id)
    service._streams.register(parent.run_id, parent)
    service._streams.register(child.run_id, child)
    return parent, child
