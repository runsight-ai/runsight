"""Stream-registry collaborator for live execution observers."""

import asyncio
from typing import Any, AsyncGenerator, Dict, Optional

from ...domain.events import SSE_TERMINAL_EVENTS
from ..observers.streaming_observer import StreamingObserver


class ExecutionStreamRegistry:
    """Owns stream observer registration and subscriber coordination."""

    OBSERVER_REGISTRATION_TIMEOUT_S = 0.25
    STREAM_CLOSED_EVENT = "__stream_closed__"

    def __init__(self):
        self._observers: Dict[str, StreamingObserver] = {}
        self._observer_events: Dict[str, asyncio.Event] = {}
        self._completed_streams: set[str] = set()

    def register(self, run_id: str, observer: StreamingObserver) -> None:
        self._observers[run_id] = observer
        self._completed_streams.discard(run_id)
        ready_event = self._observer_events.setdefault(run_id, asyncio.Event())
        ready_event.set()

    def get(self, run_id: str) -> Optional[StreamingObserver]:
        return self._observers.get(run_id)

    def unregister(self, run_id: str) -> None:
        observer = self._observers.pop(run_id, None)
        ready_event = self._observer_events.setdefault(run_id, asyncio.Event())
        if observer is not None and observer.is_done:
            self._completed_streams.add(run_id)
            ready_event.set()
            return
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
            ready_event = self._observer_events.setdefault(run_id, asyncio.Event())
            try:
                await asyncio.wait_for(
                    ready_event.wait(),
                    timeout=self.OBSERVER_REGISTRATION_TIMEOUT_S,
                )
            except asyncio.TimeoutError:
                return
            observer = self._observers.get(run_id)
            if observer is None:
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
