"""Red tests for RUN-207: Wire StreamingObserver into execution pipeline.

Bug: StreamingObserver exists and so does the observer registry
(register_observer / unregister_observer / subscribe_stream) on ExecutionService,
but _run_workflow() never creates a StreamingObserver, never registers it, and
never adds it to the CompositeObserver chain.  The SSE endpoint therefore never
receives any events during execution.

Fix required:
  1. Create StreamingObserver(run_id=run_id) inside _run_workflow()
  2. Register it via self.register_observer(run_id, streaming_obs)
  3. Add it to the CompositeObserver chain
  4. Unregister in a finally block (cleanup on both success and failure)

All tests should FAIL until the StreamingObserver is wired in.
"""

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest
from runsight_core.state import WorkflowState

from runsight_api.logic.observers.streaming_observer import StreamingObserver
from runsight_api.logic.services.execution_service import ExecutionService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_service(**overrides):
    """Create an ExecutionService with mocked repos."""
    return ExecutionService(
        run_repo=overrides.get("run_repo", Mock()),
        workflow_repo=overrides.get("workflow_repo", Mock()),
        provider_repo=overrides.get("provider_repo", Mock()),
        engine=overrides.get("engine", None),
    )


# ---------------------------------------------------------------------------
# 1. StreamingObserver is created and registered per run
# ---------------------------------------------------------------------------


class TestStreamingObserverCreatedAndRegistered:
    """_run_workflow must create a StreamingObserver and register it via
    self.register_observer(run_id, obs)."""

    @pytest.mark.asyncio
    async def test_streaming_observer_registered_during_run(self):
        """After _run_workflow starts, get_observer(run_id) must return a
        StreamingObserver — meaning register_observer was called.

        Currently FAILS because _run_workflow never calls register_observer.
        """
        svc = _make_service()

        captured_observer = None

        async def fake_wf_run(state, observer=None):
            nonlocal captured_observer
            # At this point the StreamingObserver should be registered
            captured_observer = svc.get_observer("run_reg")
            return state

        mock_wf = Mock()
        mock_wf.run = fake_wf_run

        await svc._run_workflow("run_reg", mock_wf, {"instruction": "test"})

        assert captured_observer is not None, (
            "get_observer('run_reg') returned None during wf.run() — "
            "StreamingObserver was never registered via register_observer()"
        )
        assert isinstance(captured_observer, StreamingObserver), (
            f"Expected StreamingObserver, got {type(captured_observer).__name__}"
        )

    @pytest.mark.asyncio
    async def test_streaming_observer_has_correct_run_id(self):
        """The StreamingObserver registered must have run_id matching the run.

        Currently FAILS because no StreamingObserver is created at all.
        """
        svc = _make_service()
        run_id = "run_id_check"

        captured_observer = None

        async def fake_wf_run(state, observer=None):
            nonlocal captured_observer
            captured_observer = svc.get_observer(run_id)
            return state

        mock_wf = Mock()
        mock_wf.run = fake_wf_run

        await svc._run_workflow(run_id, mock_wf, {"instruction": "test"})

        assert captured_observer is not None, (
            "StreamingObserver not registered — cannot check run_id"
        )
        assert captured_observer.run_id == run_id, (
            f"StreamingObserver.run_id={captured_observer.run_id!r}, expected {run_id!r}"
        )


# ---------------------------------------------------------------------------
# 2. StreamingObserver is part of the CompositeObserver chain
# ---------------------------------------------------------------------------


class TestStreamingObserverInCompositeChain:
    """The StreamingObserver must be included in the CompositeObserver that
    gets passed to wf.run().  CompositeObserver.__init__ receives *observers;
    the StreamingObserver must be among them."""

    @pytest.mark.asyncio
    async def test_composite_observer_includes_streaming_observer(self):
        """CompositeObserver must be constructed with a StreamingObserver
        among its observers.

        Currently FAILS because only LoggingObserver (and optionally
        ExecutionObserver) are passed to CompositeObserver.
        """
        svc = _make_service()

        composite_observers = None

        async def fake_wf_run(state, observer=None):
            nonlocal composite_observers
            # Inspect the CompositeObserver's internal list
            if hasattr(observer, "observers"):
                composite_observers = observer.observers
            return state

        mock_wf = Mock()
        mock_wf.run = fake_wf_run

        await svc._run_workflow("run_chain", mock_wf, {"instruction": "test"})

        assert composite_observers is not None, (
            "wf.run() did not receive a CompositeObserver (no .observers attribute)"
        )

        streaming_observers = [
            obs for obs in composite_observers if isinstance(obs, StreamingObserver)
        ]
        assert len(streaming_observers) == 1, (
            f"Expected exactly 1 StreamingObserver in CompositeObserver chain, "
            f"found {len(streaming_observers)}. Observer types present: "
            f"{[type(o).__name__ for o in composite_observers]}"
        )

    @pytest.mark.asyncio
    async def test_streaming_observer_receives_events_via_composite(self):
        """When wf.run() triggers observer events, the StreamingObserver queue
        must receive them through the CompositeObserver fan-out.

        Currently FAILS because StreamingObserver is not in the chain.
        """
        svc = _make_service()

        async def fake_wf_run(state, observer=None):
            if observer:
                observer.on_workflow_start("test_wf", state)
                observer.on_workflow_complete("test_wf", state, 1.0)
            return state

        mock_wf = Mock()
        mock_wf.run = fake_wf_run

        await svc._run_workflow("run_events", mock_wf, {"instruction": "test"})

        # After run, the observer would have been registered (and cleaned up).
        # We need to capture events during the run, not after cleanup.
        svc2 = _make_service()
        events = []

        async def fake_wf_run_capture(state, observer=None):
            if observer:
                observer.on_workflow_start("test_wf", state)
            # Now check the registered StreamingObserver's queue
            streaming_obs = svc2.get_observer("run_events2")
            if streaming_obs:
                while not streaming_obs.queue.empty():
                    events.append(streaming_obs.queue.get_nowait())
            if observer:
                observer.on_workflow_complete("test_wf", state, 1.0)
            return state

        mock_wf2 = Mock()
        mock_wf2.run = fake_wf_run_capture

        await svc2._run_workflow("run_events2", mock_wf2, {"instruction": "test"})

        assert len(events) >= 1, (
            f"Expected at least 1 event in StreamingObserver queue after on_workflow_start, "
            f"got {len(events)}. StreamingObserver is not in the CompositeObserver chain."
        )
        assert events[0]["event"] == "run_started", (
            f"First event should be 'run_started', got {events[0]['event']!r}"
        )


# ---------------------------------------------------------------------------
# 3. StreamingObserver cleanup after successful run
# ---------------------------------------------------------------------------


class TestStreamingObserverCleanupOnSuccess:
    """After _run_workflow completes successfully, the StreamingObserver must
    be unregistered via unregister_observer(run_id)."""

    @pytest.mark.asyncio
    async def test_observer_unregistered_after_success(self):
        """get_observer(run_id) must return None after a successful run,
        proving unregister_observer was called in the finally block.

        Currently FAILS because StreamingObserver is never registered
        (and therefore there's nothing to unregister).
        """
        svc = _make_service()

        was_registered = False

        async def fake_wf_run(state, observer=None):
            nonlocal was_registered
            # Verify it IS registered during execution
            was_registered = svc.get_observer("run_clean_ok") is not None
            return state

        mock_wf = Mock()
        mock_wf.run = fake_wf_run

        await svc._run_workflow("run_clean_ok", mock_wf, {"instruction": "test"})

        # Must have been registered during execution
        assert was_registered, "StreamingObserver was not registered during execution"

        # Must be unregistered after completion
        assert svc.get_observer("run_clean_ok") is None, (
            "StreamingObserver still registered after successful run — "
            "unregister_observer() was not called in finally block"
        )


# ---------------------------------------------------------------------------
# 4. StreamingObserver cleanup after failed run
# ---------------------------------------------------------------------------


class TestStreamingObserverCleanupOnFailure:
    """After _run_workflow fails, the StreamingObserver must still be
    unregistered (cleanup in finally block)."""

    @pytest.mark.asyncio
    async def test_observer_unregistered_after_failure(self):
        """get_observer(run_id) must return None after a failed run,
        proving unregister_observer was called in the finally block.

        Currently FAILS because StreamingObserver is never registered.
        """
        svc = _make_service()

        was_registered = False

        async def fake_wf_run(state, observer=None):
            nonlocal was_registered
            was_registered = svc.get_observer("run_clean_fail") is not None
            raise RuntimeError("LLM exploded")

        mock_wf = Mock()
        mock_wf.run = fake_wf_run

        await svc._run_workflow("run_clean_fail", mock_wf, {"instruction": "test"})

        # Must have been registered during execution
        assert was_registered, "StreamingObserver was not registered during execution"

        # Must be unregistered even after failure
        assert svc.get_observer("run_clean_fail") is None, (
            "StreamingObserver still registered after failed run — "
            "unregister_observer() was not called in finally block"
        )


# ---------------------------------------------------------------------------
# 5. subscribe_stream yields events from wired observer
# ---------------------------------------------------------------------------


class TestSubscribeStreamYieldsEvents:
    """subscribe_stream(run_id) must yield events that flow through
    the wired StreamingObserver during execution."""

    @pytest.mark.asyncio
    async def test_subscribe_stream_returns_events_from_wired_observer(self):
        """Start a run, connect subscribe_stream concurrently, and verify
        it yields the events produced by the StreamingObserver.

        Currently FAILS because StreamingObserver is never registered,
        so subscribe_stream returns immediately (observer is None).
        """
        svc = _make_service()
        run_id = "run_sub"
        collected_events = []

        async def fake_wf_run(state, observer=None):
            # Give consumer a moment to start reading
            await asyncio.sleep(0.01)
            if observer:
                observer.on_workflow_start("test_wf", state)
                observer.on_block_start("test_wf", "block_1", "llm")
                observer.on_block_complete("test_wf", "block_1", "llm", 0.5, state)
                observer.on_workflow_complete("test_wf", state, 1.0)
            return state

        mock_wf = Mock()
        mock_wf.run = fake_wf_run

        async def consume_stream():
            async for event in svc.subscribe_stream(run_id):
                collected_events.append(event)

        # Run both tasks concurrently: execution + stream consumption.
        # subscribe_stream must be called AFTER register_observer but
        # BEFORE wf.run() completes. We delay wf.run() events slightly.
        # However, since register_observer isn't called yet, we need to
        # allow time for it to be registered before consuming.

        # Start execution as a task
        exec_task = asyncio.create_task(svc._run_workflow(run_id, mock_wf, {"instruction": "test"}))
        # Small delay to let _run_workflow register the observer
        await asyncio.sleep(0.005)

        # Start consuming
        consumer_task = asyncio.create_task(consume_stream())

        # Wait for execution to finish
        await exec_task

        # Give consumer a bit more time to drain
        try:
            await asyncio.wait_for(consumer_task, timeout=2.0)
        except asyncio.TimeoutError:
            consumer_task.cancel()

        assert len(collected_events) >= 2, (
            f"Expected at least 2 events from subscribe_stream, got {len(collected_events)}. "
            f"StreamingObserver is not wired — subscribe_stream gets no events."
        )

    @pytest.mark.asyncio
    async def test_subscribe_stream_returns_nothing_when_observer_not_wired(self):
        """This test documents the current broken behavior: subscribe_stream
        returns immediately because no observer is registered.

        After the fix, this test will verify that subscribe_stream does NOT
        return empty when the observer IS wired (inverse assertion).

        Currently PASSES (documenting the bug) but after fix this assertion
        should be inverted — we keep the inverse assertion here so the test
        FAILS until the fix lands.
        """
        svc = _make_service()
        run_id = "run_sub_empty"

        mock_wf = Mock()
        mock_wf.run = AsyncMock(return_value=WorkflowState())

        await svc._run_workflow(run_id, mock_wf, {"instruction": "test"})

        # After the run, try subscribe_stream — should NOT be empty if wired
        events = []
        async for event in svc.subscribe_stream(run_id):
            events.append(event)

        # After fix: observer is cleaned up (None) but was registered during run.
        # We assert it was registered at some point by checking that _observers
        # was populated. Since we can't retroactively check, we verify the
        # subscribe_stream contract works when the observer IS present.

        # Register manually and verify subscribe_stream can yield from it
        manual_obs = StreamingObserver(run_id=run_id)
        svc.register_observer(run_id, manual_obs)
        manual_obs.queue.put_nowait({"event": "run_completed", "data": {}})

        manual_events = []
        async for event in svc.subscribe_stream(run_id):
            manual_events.append(event)

        # This works with manual registration.  The fix must make
        # _run_workflow do this automatically. We verify via test 1-4.
        assert len(manual_events) == 1

        # Now verify the REAL question: was it auto-registered during _run_workflow?
        # Run again and capture during execution.
        svc2 = _make_service()
        run_id2 = "run_sub_empty2"
        obs_during_run = None

        async def capture_run(state, observer=None):
            nonlocal obs_during_run
            obs_during_run = svc2.get_observer(run_id2)
            return state

        mock_wf2 = Mock()
        mock_wf2.run = capture_run

        await svc2._run_workflow(run_id2, mock_wf2, {"instruction": "test"})

        assert obs_during_run is not None, (
            "StreamingObserver was not auto-registered during _run_workflow — "
            "subscribe_stream cannot yield any events"
        )


# ---------------------------------------------------------------------------
# 6. End-to-end: events flow wf.run() -> observer -> queue -> subscribe_stream
# ---------------------------------------------------------------------------


class TestEndToEndEventPipeline:
    """Integration test: verify the full event pipeline from workflow
    execution through to subscribe_stream consumption."""

    @pytest.mark.asyncio
    async def test_full_pipeline_success_path(self):
        """Events from wf.run() must flow through CompositeObserver ->
        StreamingObserver.queue -> subscribe_stream() -> consumer.

        Tests the full pipeline for a successful run.
        Currently FAILS because StreamingObserver is not in the chain.
        """
        svc = _make_service()
        run_id = "run_e2e_ok"
        collected = []

        async def fake_wf_run(state, observer=None):
            await asyncio.sleep(0.01)  # Let consumer attach
            if observer:
                observer.on_workflow_start("test_wf", state)
                observer.on_block_start("test_wf", "b1", "llm")
                observer.on_block_complete("test_wf", "b1", "llm", 0.3, state)
                observer.on_workflow_complete("test_wf", state, 0.5)
            return state

        mock_wf = Mock()
        mock_wf.run = fake_wf_run

        async def consume():
            async for event in svc.subscribe_stream(run_id):
                collected.append(event)

        exec_task = asyncio.create_task(svc._run_workflow(run_id, mock_wf, {"instruction": "test"}))
        await asyncio.sleep(0.005)
        consumer_task = asyncio.create_task(consume())

        await exec_task
        try:
            await asyncio.wait_for(consumer_task, timeout=2.0)
        except asyncio.TimeoutError:
            consumer_task.cancel()

        # Expect: run_started, node_started, node_completed, run_completed
        event_names = [e["event"] for e in collected]
        assert "run_started" in event_names, (
            f"Missing 'run_started' event. Got: {event_names}. "
            f"StreamingObserver not wired into CompositeObserver."
        )
        assert "node_started" in event_names, f"Missing 'node_started' event. Got: {event_names}"
        assert "node_completed" in event_names, (
            f"Missing 'node_completed' event. Got: {event_names}"
        )
        assert "run_completed" in event_names, f"Missing 'run_completed' event. Got: {event_names}"

    @pytest.mark.asyncio
    async def test_full_pipeline_failure_path(self):
        """Events from wf.run() must flow through the pipeline even
        when the workflow fails.

        Currently FAILS because StreamingObserver is not in the chain.
        """
        svc = _make_service()
        run_id = "run_e2e_fail"
        collected = []
        error = RuntimeError("LLM quota exceeded")

        async def fake_wf_run(state, observer=None):
            await asyncio.sleep(0.01)
            if observer:
                observer.on_workflow_start("test_wf", state)
                observer.on_block_start("test_wf", "b1", "llm")
                observer.on_block_error("test_wf", "b1", "llm", 0.2, error)
                observer.on_workflow_error("test_wf", error, 0.3)
            raise error

        mock_wf = Mock()
        mock_wf.run = fake_wf_run

        async def consume():
            async for event in svc.subscribe_stream(run_id):
                collected.append(event)

        exec_task = asyncio.create_task(svc._run_workflow(run_id, mock_wf, {"instruction": "test"}))
        await asyncio.sleep(0.005)
        consumer_task = asyncio.create_task(consume())

        await exec_task
        try:
            await asyncio.wait_for(consumer_task, timeout=2.0)
        except asyncio.TimeoutError:
            consumer_task.cancel()

        event_names = [e["event"] for e in collected]
        assert "run_started" in event_names, (
            f"Missing 'run_started' event. Got: {event_names}. "
            f"StreamingObserver not wired into CompositeObserver."
        )
        assert "node_failed" in event_names, f"Missing 'node_failed' event. Got: {event_names}"
        assert "run_failed" in event_names, f"Missing 'run_failed' event. Got: {event_names}"

    @pytest.mark.asyncio
    async def test_observer_cleanup_does_not_prevent_final_events(self):
        """The finally-block cleanup (unregister_observer) must happen AFTER
        wf.run() returns, so terminal events (run_completed/run_failed) have
        already been queued before cleanup.

        Currently FAILS because StreamingObserver is never wired at all.
        """
        svc = _make_service()
        run_id = "run_e2e_timing"

        events_before_cleanup = []

        async def fake_wf_run(state, observer=None):
            if observer:
                observer.on_workflow_start("test_wf", state)
                observer.on_workflow_complete("test_wf", state, 0.5)

            # Capture what's in the queue at this point (before cleanup)
            streaming_obs = svc.get_observer(run_id)
            if streaming_obs:
                while not streaming_obs.queue.empty():
                    events_before_cleanup.append(streaming_obs.queue.get_nowait())
            return state

        mock_wf = Mock()
        mock_wf.run = fake_wf_run

        await svc._run_workflow(run_id, mock_wf, {"instruction": "test"})

        assert len(events_before_cleanup) >= 2, (
            f"Expected at least 2 events queued before cleanup, got "
            f"{len(events_before_cleanup)}. StreamingObserver not wired."
        )

        event_types = [e["event"] for e in events_before_cleanup]
        assert "run_started" in event_types
        assert "run_completed" in event_types
