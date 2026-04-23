"""Stream-registry collaborator for live execution observers."""

import asyncio
from collections import OrderedDict
from typing import Any, AsyncGenerator, Dict, Optional

from ...domain.events import SSE_TERMINAL_EVENTS
from ..observers.streaming_observer import StreamingObserver


class ExecutionStreamRegistry:
    """Owns stream observer registration and subscriber coordination."""

    OBSERVER_REGISTRATION_TIMEOUT_S = 0.25
    COMPLETED_STREAM_CACHE_SIZE = 256
    STREAM_CLOSED_EVENT = "__stream_closed__"

    def __init__(self):
        self._observers: Dict[str, StreamingObserver] = {}
        self._observer_events: Dict[str, asyncio.Event] = {}
        self._completed_streams: "OrderedDict[str, None]" = OrderedDict()

    def register(self, run_id: str, observer: StreamingObserver) -> None:
        self._observers[run_id] = observer
        self._completed_streams.pop(run_id, None)
        ready_event = self._observer_events.setdefault(run_id, asyncio.Event())
        ready_event.set()

    def get(self, run_id: str) -> Optional[StreamingObserver]:
        return self._observers.get(run_id)

    def unregister(self, run_id: str) -> None:
        observer = self._observers.pop(run_id, None)
        ready_event = self._observer_events.pop(run_id, None)
        if observer is not None and observer.is_done:
            self._mark_completed(run_id)
            if ready_event is not None:
                ready_event.set()
            return
        if ready_event is not None:
            ready_event.clear()

    def close_stream(self, run_id: str, observer: Optional[StreamingObserver] = None) -> None:
        target = observer or self._observers.get(run_id)
        if target is None or target.is_done:
            return
        target.is_done = True
        target.queue.put_nowait(
            {
                "event": self.STREAM_CLOSED_EVENT,
                "data": {"run_id": run_id},
            }
        )

    async def subscribe(self, run_id: str) -> AsyncGenerator[Dict[str, Any], None]:
        observer = self._observers.get(run_id)
        if observer is None:
            if run_id in self._completed_streams:
                return
            created_ready_event = run_id not in self._observer_events
            ready_event = self._observer_events.setdefault(run_id, asyncio.Event())
            try:
                await asyncio.wait_for(
                    ready_event.wait(),
                    timeout=self.OBSERVER_REGISTRATION_TIMEOUT_S,
                )
            except asyncio.TimeoutError:
                if (
                    created_ready_event
                    and run_id not in self._observers
                    and run_id not in self._completed_streams
                ):
                    self._observer_events.pop(run_id, None)
                return
            observer = self._observers.get(run_id)
            if observer is None:
                if run_id in self._completed_streams:
                    return
                if created_ready_event:
                    self._observer_events.pop(run_id, None)
                return

        while True:
            try:
                event = await asyncio.wait_for(observer.queue.get(), timeout=30.0)
            except asyncio.TimeoutError:
                continue

            if event["event"] == self.STREAM_CLOSED_EVENT:
                break

            yield event

            if event["event"] in SSE_TERMINAL_EVENTS:
                break

    def _mark_completed(self, run_id: str) -> None:
        self._completed_streams.pop(run_id, None)
        self._completed_streams[run_id] = None
        while len(self._completed_streams) > self.COMPLETED_STREAM_CACHE_SIZE:
            self._completed_streams.popitem(last=False)
