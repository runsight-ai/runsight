"""Red tests for RUN-952 stream subscription coordination."""

import asyncio
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from runsight_api.logic.observers.streaming_observer import StreamingObserver
from runsight_api.logic.services.execution_service import ExecutionService


def _make_service() -> ExecutionService:
    return ExecutionService(
        run_repo=Mock(),
        workflow_repo=Mock(),
        provider_repo=Mock(),
    )


class TestLateStreamSubscribers:
    @pytest.mark.asyncio
    async def test_subscribe_stream_waits_for_late_observer_registration(self):
        """Subscribers that connect before launch completes should not be dropped."""

        service = _make_service()
        run_id = "run_952_stream_wait"
        events = []

        async def consume() -> None:
            async for event in service.subscribe_stream(run_id):
                events.append(event)

        consumer = asyncio.create_task(consume())
        await asyncio.sleep(0.05)

        assert not consumer.done(), (
            "subscribe_stream should stay pending while the stream coordinator waits "
            "for the run's observer/registry to appear."
        )

        observer = StreamingObserver(run_id=run_id)
        service.register_observer(run_id, observer)
        observer.queue.put_nowait({"event": "run_completed", "data": {"run_id": run_id}})

        await asyncio.wait_for(consumer, timeout=1)

        assert events == [{"event": "run_completed", "data": {"run_id": run_id}}]

    @pytest.mark.asyncio
    async def test_stream_endpoint_waits_for_late_registration_and_emits_terminal_event(self):
        """GET /runs/{id}/stream must stay connected until the live stream is available."""

        from runsight_api.transport.deps import get_execution_service, get_run_service
        from runsight_api.transport.routers import sse_stream

        run_id = "run_952_stream_http"
        service = _make_service()
        run_service = Mock()
        run_service.get_run.return_value = Mock(id=run_id)
        run_service.get_run_logs.return_value = []

        app = FastAPI()
        app.include_router(sse_stream.router, prefix="/api")
        app.dependency_overrides[get_execution_service] = lambda: service
        app.dependency_overrides[get_run_service] = lambda: run_service

        async def publish_terminal_event() -> None:
            await asyncio.sleep(0.05)
            observer = StreamingObserver(run_id=run_id)
            service.register_observer(run_id, observer)
            observer.queue.put_nowait({"event": "run_completed", "data": {"run_id": run_id}})

        publisher = asyncio.create_task(publish_terminal_event())

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            chunks = []
            async with client.stream(
                "GET",
                f"/api/runs/{run_id}/stream",
                headers={"Accept": "text/event-stream"},
            ) as response:
                assert response.status_code == 200
                async for chunk in response.aiter_text():
                    chunks.append(chunk)
                    if "event:run_completed" in chunk:
                        break

        await asyncio.wait_for(publisher, timeout=1)

        assert any("event:run_completed" in chunk for chunk in chunks), (
            "The SSE endpoint should wait for the stream registry to attach and "
            "then deliver the terminal event to an already-connected subscriber."
        )
