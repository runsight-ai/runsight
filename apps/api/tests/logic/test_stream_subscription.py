"""Stream subscription coordination."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from runsight_core.context_governance import ContextAuditEventV1, ContextAuditRecordV1

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
    async def test_subscribe_stream_stays_attached_while_run_is_queued_before_task_start(self):
        """Queue delay must not close the stream before observer registration.

        A run that is valid but blocked behind the execution semaphore has not
        created its StreamingObserver yet. A subscriber connecting during that
        queue window must stay attached until execution starts and a terminal
        event can be delivered.
        """

        from runsight_api.domain.events import SSE_TERMINAL_EVENTS

        service = ExecutionService(
            run_repo=Mock(),
            workflow_repo=Mock(),
            provider_repo=Mock(),
            max_concurrent_runs=1,
        )
        run_id = "run_stream_queued"
        events = []

        await service._runtime.semaphore.acquire()

        async def fake_run(state, observer=None, **kwargs):
            if observer is not None:
                observer.on_workflow_complete("queued_workflow", state, 0.01)
            return state

        wf = Mock()
        wf.run = fake_run

        async def consume() -> None:
            async for event in service.subscribe_stream(run_id):
                events.append(event)

        queued_run = asyncio.create_task(service._run_workflow(run_id, wf, {"instruction": "wait"}))
        await asyncio.sleep(0)

        consumer = asyncio.create_task(consume())

        await asyncio.sleep(service._OBSERVER_REGISTRATION_TIMEOUT_S + 0.1)

        assert not consumer.done(), (
            "A stream subscriber for a queued run should remain attached while the run "
            "is still waiting for a semaphore slot."
        )

        service._runtime.semaphore.release()

        await asyncio.wait_for(queued_run, timeout=1)
        await asyncio.wait_for(consumer, timeout=1)

        assert events, "Queued stream subscriber should eventually receive live events"
        assert events[-1]["event"] in SSE_TERMINAL_EVENTS, (
            "Queued stream subscriber should receive the eventual terminal event once "
            "observer registration happens after the queue delay."
        )

    @pytest.mark.asyncio
    async def test_subscribe_stream_terminates_when_queued_run_is_cancelled_before_start(self):
        """Cancelling a queued run must not leave an attached stream hanging forever."""

        service = ExecutionService(
            run_repo=Mock(),
            workflow_repo=Mock(),
            provider_repo=Mock(),
            max_concurrent_runs=1,
        )
        run_id = "run_stream_cancelled_queued"

        await service._runtime.semaphore.acquire()

        async def fake_run(state, observer=None, **kwargs):
            if observer is not None:
                observer.on_workflow_complete("queued_workflow", state, 0.01)
            return state

        wf = Mock()
        wf.run = fake_run

        events = []

        async def consume() -> None:
            async for event in service.subscribe_stream(run_id):
                events.append(event)

        queued_run = asyncio.create_task(service._run_workflow(run_id, wf, {"instruction": "wait"}))
        await asyncio.sleep(0)

        consumer = asyncio.create_task(consume())

        await asyncio.sleep(0.05)
        assert not consumer.done(), "Stream should still be attached while the run is queued"

        queued_run.cancel()
        with pytest.raises(asyncio.CancelledError):
            await queued_run

        try:
            await asyncio.wait_for(consumer, timeout=0.5)
        finally:
            if service._runtime.semaphore.locked():
                service._runtime.semaphore.release()

        assert consumer.done(), (
            "A subscriber attached to a queued run should terminate promptly after that run "
            "is cancelled before task start."
        )
        assert events == [] or events[-1]["event"] in {
            "run_cancelled",
            "run_failed",
            "run_completed",
        }, (
            "Queued-cancel stream should either close cleanly or yield a terminal event, "
            "but it must not hang indefinitely on an empty queue."
        )

    @pytest.mark.asyncio
    async def test_subscribe_stream_waits_for_late_observer_registration(self):
        """Subscribers that connect before launch completes should not be dropped."""

        service = _make_service()
        run_id = "run_stream_wait"
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
        service._streams.register(run_id, observer)
        observer.queue.put_nowait({"event": "run_completed", "data": {"run_id": run_id}})

        await asyncio.wait_for(consumer, timeout=1)

        assert events == [{"event": "run_completed", "data": {"run_id": run_id}}]

    @pytest.mark.asyncio
    async def test_stream_endpoint_waits_for_late_registration_and_emits_terminal_event(self):
        """GET /runs/{id}/stream must stay connected until the live stream is available."""

        from runsight_api.transport.deps import get_execution_service, get_run_service
        from runsight_api.transport.routers import sse_stream

        run_id = "run_stream_http"
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
            service._streams.register(run_id, observer)
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


class TestChildRunStreamOwnership:
    @pytest.mark.asyncio
    async def test_child_stream_gets_child_owned_terminal_event(self):
        service = _make_service()
        parent = StreamingObserver(run_id="run_stream_parent")
        child = parent.clone_for_child_run(child_run_id="run_stream_child")
        service._streams.register(parent.run_id, parent)
        service._streams.register(child.run_id, child)

        child_state = Mock(total_cost_usd=0.01, total_tokens=42)

        stream = service.subscribe_stream(child.run_id)
        child.on_workflow_complete("child_workflow", child_state, 0.25)
        event = await asyncio.wait_for(anext(stream), timeout=1)
        await stream.aclose()

        assert event["event"] == "run_completed", (
            "A child run's own stream must terminate with child-owned terminal traffic, "
            "not a parent-summary event."
        )
        assert event["data"]["run_id"] == child.run_id

    @pytest.mark.asyncio
    async def test_late_child_subscriber_still_receives_completed_terminal_event(self):
        service = _make_service()
        parent = StreamingObserver(
            run_id="run_stream_parent",
            register_stream=service._streams.register,
            unregister_stream=service._streams.unregister,
        )
        service._streams.register(parent.run_id, parent)
        child = parent.clone_for_child_run(child_run_id="run_stream_child_complete")
        assert service._streams.get(child.run_id) is child
        assert child.parent_run_id == parent.run_id

        child.on_workflow_complete(
            "child_workflow",
            Mock(total_cost_usd=0.01, total_tokens=42),
            0.25,
        )

        events = [event async for event in service.subscribe_stream(child.run_id)]

        assert [event["event"] for event in events] == ["run_completed"], (
            "A late child subscriber must still observe the child's live run_completed event "
            "even after the child stream unregisters itself on terminal completion."
        )
        assert events[0]["data"]["run_id"] == child.run_id

    @pytest.mark.asyncio
    async def test_late_child_subscriber_still_receives_failed_terminal_event(self):
        service = _make_service()
        parent = StreamingObserver(
            run_id="run_stream_parent",
            register_stream=service._streams.register,
            unregister_stream=service._streams.unregister,
        )
        service._streams.register(parent.run_id, parent)
        child = parent.clone_for_child_run(child_run_id="run_stream_child_failed")
        assert service._streams.get(child.run_id) is child
        assert child.parent_run_id == parent.run_id

        child.on_workflow_error("child_workflow", RuntimeError("child boom"), 0.25)

        events = [event async for event in service.subscribe_stream(child.run_id)]

        assert [event["event"] for event in events] == ["run_failed"], (
            "A late child subscriber must still observe the child's live run_failed event "
            "even after the child stream unregisters itself on terminal failure."
        )
        assert events[0]["data"]["run_id"] == child.run_id

    @pytest.mark.asyncio
    async def test_parent_stream_stays_open_and_filters_child_raw_events(self):
        service = _make_service()
        parent = StreamingObserver(run_id="run_stream_parent")
        child = parent.clone_for_child_run(child_run_id="run_stream_child")
        service._streams.register(parent.run_id, parent)
        service._streams.register(child.run_id, child)

        parent_state = Mock(total_cost_usd=0.02, total_tokens=84)
        child_state = Mock(total_cost_usd=0.01, total_tokens=42)
        events: list[dict] = []

        async def consume_parent() -> None:
            async for event in service.subscribe_stream(parent.run_id):
                events.append(event)

        consumer = asyncio.create_task(consume_parent())
        await asyncio.sleep(0)

        child.on_block_start("child_workflow", "child_step", "workflow")
        child.on_block_heartbeat(
            "child_workflow",
            "child_step",
            "running",
            "still working",
            datetime.now(timezone.utc),
        )
        child.on_workflow_complete("child_workflow", child_state, 0.25)

        await asyncio.sleep(0.05)
        assert not consumer.done(), (
            "A parent stream must remain open after child completion until the parent itself "
            "enqueues terminal traffic."
        )

        parent.on_workflow_complete("parent_workflow", parent_state, 0.5)
        await asyncio.wait_for(consumer, timeout=1)

        event_types = [event["event"] for event in events]
        assert event_types[-1] == "run_completed"
        assert set(event_types) <= {"child_run_completed", "run_completed"}, (
            "Parent streams may carry an explicit child summary signal, but they must not "
            "receive raw child node lifecycle traffic."
        )

    @pytest.mark.asyncio
    async def test_child_failure_terminates_only_child_stream(self):
        service = _make_service()
        parent = StreamingObserver(run_id="run_stream_parent")
        child = parent.clone_for_child_run(child_run_id="run_stream_child")
        service._streams.register(parent.run_id, parent)
        service._streams.register(child.run_id, child)

        events: list[dict] = []

        async def consume_parent() -> None:
            async for event in service.subscribe_stream(parent.run_id):
                events.append(event)

        consumer = asyncio.create_task(consume_parent())
        await asyncio.sleep(0)

        child.on_workflow_error("child_workflow", RuntimeError("child boom"), 0.25)

        await asyncio.sleep(0.05)
        assert not consumer.done(), (
            "A child failure must terminate only the child stream; the parent subscriber "
            "should stay attached until the parent emits its own terminal event."
        )

        child_stream = service.subscribe_stream(child.run_id)
        event = await asyncio.wait_for(anext(child_stream), timeout=1)
        await child_stream.aclose()

        assert event["event"] == "run_failed"
        assert event["data"]["run_id"] == child.run_id

        parent.on_workflow_complete(
            "parent_workflow", Mock(total_cost_usd=0.02, total_tokens=84), 0.5
        )
        await asyncio.wait_for(consumer, timeout=1)

        assert events[-1]["event"] == "run_completed"
        assert all(parent_event["event"] != "run_failed" for parent_event in events), (
            "Parent streams must not receive child run_failed traffic."
        )

    @pytest.mark.asyncio
    async def test_parent_stream_filters_child_context_resolution_events(self):
        service = _make_service()
        parent = StreamingObserver(run_id="run_stream_parent")
        child = parent.clone_for_child_run(child_run_id="run_stream_child")
        service._streams.register(parent.run_id, parent)
        service._streams.register(child.run_id, child)

        events: list[dict] = []

        async def consume_parent() -> None:
            async for event in service.subscribe_stream(parent.run_id):
                events.append(event)

        consumer = asyncio.create_task(consume_parent())
        await asyncio.sleep(0)

        child.on_context_resolution(
            ContextAuditEventV1(
                run_id=child.run_id,
                workflow_name="child_workflow",
                node_id="resolve_context",
                block_type="linear",
                access="declared",
                mode="strict",
                records=[
                    ContextAuditRecordV1(
                        input_name="query",
                        from_ref="results.query",
                        namespace="results",
                        source="query",
                        field_path="query",
                        status="resolved",
                        severity="allow",
                        value_type="str",
                        preview="bounded preview",
                        reason=None,
                    )
                ],
                resolved_count=1,
                denied_count=0,
                warning_count=0,
                emitted_at=datetime.now(timezone.utc),
            )
        )

        await asyncio.sleep(0.05)
        assert events == [], "Parent streams must not receive raw child context_resolution traffic."
        assert not consumer.done(), (
            "A child context-resolution event must not terminate the parent stream."
        )

        parent.on_workflow_complete(
            "parent_workflow", Mock(total_cost_usd=0.02, total_tokens=84), 0.5
        )
        await asyncio.wait_for(consumer, timeout=1)


@pytest.mark.parametrize(
    "attr",
    [
        "register_observer",
        "get_observer",
        "unregister_observer",
    ],
)
def test_execution_service_no_longer_exposes_observer_facade_methods(attr):
    service = _make_service()

    assert not hasattr(service, attr), f"ExecutionService should not expose compat seam {attr}"


@pytest.mark.parametrize(
    "attr",
    [
        "_observers",
        "_running_tasks",
        "_semaphore",
    ],
)
def test_execution_service_no_longer_exposes_runtime_compat_aliases(attr):
    service = _make_service()

    assert not hasattr(service, attr), f"ExecutionService should not expose compat seam {attr}"
