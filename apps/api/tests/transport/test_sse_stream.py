"""RED phase tests for RUN-6: SSE stream real-time execution events.

Tests target:
- GET /api/runs/{run_id}/stream — SSE endpoint
- StreamingObserver — pushes events to asyncio.Queue
- Late-join replay of missed events
- Cleanup on run completion
- Observer registry in ExecutionService
"""

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from runsight_api.domain.entities.run import RunStatus
from runsight_api.main import app
from runsight_api.transport.deps import get_execution_service, get_run_service

client = TestClient(app)
SSE_STREAM_PATH = (
    Path(__file__).resolve().parents[2] / "src/runsight_api/transport/routers/sse_stream.py"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_run(run_id="run_sse_1", status=RunStatus.running):
    mock_run = Mock()
    mock_run.id = run_id
    mock_run.workflow_id = "wf_1"
    mock_run.workflow_name = "wf_1"
    mock_run.status = status
    mock_run.started_at = 100.0
    mock_run.completed_at = None
    mock_run.duration_s = None
    mock_run.total_cost_usd = 0.0
    mock_run.total_tokens = 0
    mock_run.created_at = 100.0
    return mock_run


def _parse_sse_events(raw: str) -> list[dict]:
    """Parse SSE text into a list of {event, data} dicts."""
    events = []
    current_event = None
    current_data = []

    for line in raw.split("\n"):
        if line.startswith("event:"):
            current_event = line[len("event:") :].strip()
        elif line.startswith("data:"):
            current_data.append(line[len("data:") :].strip())
        elif line == "" and current_event is not None:
            data_str = "\n".join(current_data)
            try:
                data = json.loads(data_str)
            except json.JSONDecodeError:
                data = data_str
            events.append({"event": current_event, "data": data})
            current_event = None
            current_data = []

    return events


# ---------------------------------------------------------------------------
# 1. SSE endpoint returns text/event-stream content type
# ---------------------------------------------------------------------------


class TestSSEContentType:
    def test_stream_endpoint_returns_event_stream_content_type(self):
        """GET /api/runs/{id}/stream should return Content-Type: text/event-stream."""
        mock_run_service = Mock()
        mock_run_service.get_run.return_value = _make_mock_run()

        mock_exec_service = Mock()

        # subscribe_stream returns an async generator that yields one terminal event
        async def _fake_stream(run_id):
            yield {"event": "run_completed", "data": {"run_id": run_id}}

        mock_exec_service.subscribe_stream = _fake_stream

        app.dependency_overrides[get_run_service] = lambda: mock_run_service
        app.dependency_overrides[get_execution_service] = lambda: mock_exec_service

        try:
            with client.stream("GET", "/api/runs/run_sse_1/stream") as response:
                assert response.status_code == 200
                assert "text/event-stream" in response.headers["content-type"]
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 2. Events arrive for block lifecycle
# ---------------------------------------------------------------------------


class TestBlockLifecycleEvents:
    def test_node_started_event_emitted(self):
        """Stream should emit node_started when a block begins execution."""
        mock_run_service = Mock()
        mock_run_service.get_run.return_value = _make_mock_run()

        mock_exec_service = Mock()

        async def _fake_stream(run_id):
            yield {"event": "node_started", "data": {"node_id": "block_1", "block_type": "llm"}}
            yield {"event": "run_completed", "data": {"run_id": run_id}}

        mock_exec_service.subscribe_stream = _fake_stream

        app.dependency_overrides[get_run_service] = lambda: mock_run_service
        app.dependency_overrides[get_execution_service] = lambda: mock_exec_service

        try:
            with client.stream("GET", "/api/runs/run_sse_1/stream") as response:
                body = response.read().decode()
            events = _parse_sse_events(body)
            event_types = [e["event"] for e in events]
            assert "node_started" in event_types
        finally:
            app.dependency_overrides.clear()

    def test_node_completed_event_emitted(self):
        """Stream should emit node_completed when a block finishes successfully."""
        mock_run_service = Mock()
        mock_run_service.get_run.return_value = _make_mock_run()

        mock_exec_service = Mock()

        async def _fake_stream(run_id):
            yield {"event": "node_completed", "data": {"node_id": "block_1", "duration_s": 1.5}}
            yield {"event": "run_completed", "data": {"run_id": run_id}}

        mock_exec_service.subscribe_stream = _fake_stream

        app.dependency_overrides[get_run_service] = lambda: mock_run_service
        app.dependency_overrides[get_execution_service] = lambda: mock_exec_service

        try:
            with client.stream("GET", "/api/runs/run_sse_1/stream") as response:
                body = response.read().decode()
            events = _parse_sse_events(body)
            event_types = [e["event"] for e in events]
            assert "node_completed" in event_types
        finally:
            app.dependency_overrides.clear()

    def test_node_failed_event_emitted(self):
        """Stream should emit node_failed when a block errors."""
        mock_run_service = Mock()
        mock_run_service.get_run.return_value = _make_mock_run()

        mock_exec_service = Mock()

        async def _fake_stream(run_id):
            yield {"event": "node_failed", "data": {"node_id": "block_1", "error": "timeout"}}
            yield {"event": "run_completed", "data": {"run_id": run_id}}

        mock_exec_service.subscribe_stream = _fake_stream

        app.dependency_overrides[get_run_service] = lambda: mock_run_service
        app.dependency_overrides[get_execution_service] = lambda: mock_exec_service

        try:
            with client.stream("GET", "/api/runs/run_sse_1/stream") as response:
                body = response.read().decode()
            events = _parse_sse_events(body)
            event_types = [e["event"] for e in events]
            assert "node_failed" in event_types
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 3. run_completed is terminal event
# ---------------------------------------------------------------------------


class TestTerminalEvents:
    def test_run_completed_closes_stream(self):
        """After run_completed, the SSE stream should close (no more events)."""
        mock_run_service = Mock()
        mock_run_service.get_run.return_value = _make_mock_run()

        mock_exec_service = Mock()

        async def _fake_stream(run_id):
            yield {"event": "node_started", "data": {"node_id": "block_1"}}
            yield {"event": "run_completed", "data": {"run_id": run_id}}

        mock_exec_service.subscribe_stream = _fake_stream

        app.dependency_overrides[get_run_service] = lambda: mock_run_service
        app.dependency_overrides[get_execution_service] = lambda: mock_exec_service

        try:
            with client.stream("GET", "/api/runs/run_sse_1/stream") as response:
                body = response.read().decode()
            events = _parse_sse_events(body)
            assert events[-1]["event"] == "run_completed"
        finally:
            app.dependency_overrides.clear()

    def test_run_failed_closes_stream(self):
        """After run_failed, the SSE stream should close."""
        mock_run_service = Mock()
        mock_run_service.get_run.return_value = _make_mock_run()

        mock_exec_service = Mock()

        async def _fake_stream(run_id):
            yield {"event": "node_started", "data": {"node_id": "block_1"}}
            yield {"event": "run_failed", "data": {"run_id": run_id, "error": "kaboom"}}

        mock_exec_service.subscribe_stream = _fake_stream

        app.dependency_overrides[get_run_service] = lambda: mock_run_service
        app.dependency_overrides[get_execution_service] = lambda: mock_exec_service

        try:
            with client.stream("GET", "/api/runs/run_sse_1/stream") as response:
                body = response.read().decode()
            events = _parse_sse_events(body)
            assert events[-1]["event"] == "run_failed"
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 4. 404 for non-existent run
# ---------------------------------------------------------------------------


class TestStreamNotFound:
    def test_stream_returns_404_for_missing_run(self):
        """GET /api/runs/{id}/stream should 404 when run_id doesn't exist."""
        mock_run_service = Mock()
        mock_run_service.get_run.return_value = None

        app.dependency_overrides[get_run_service] = lambda: mock_run_service

        try:
            response = client.get("/api/runs/nonexistent/stream")
            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 5. Late-join replays missed events (B3 fix: deterministic replay assertions)
# ---------------------------------------------------------------------------


class TestLateJoinReplay:
    def test_late_join_replays_prior_events_from_db(self):
        """Connecting to a running run should replay events that already happened.

        Replayed events must use the 'replay' event type and carry data matching
        the persisted log entries, arriving strictly before any live events.
        """
        mock_run_service = Mock()
        mock_run_service.get_run.return_value = _make_mock_run()

        # Simulate prior events already persisted in DB
        mock_log_1 = Mock()
        mock_log_1.message = json.dumps({"event": "block_start", "block_id": "b1"})
        mock_log_1.level = "info"
        mock_log_2 = Mock()
        mock_log_2.message = json.dumps({"event": "block_complete", "block_id": "b1"})
        mock_log_2.level = "info"
        mock_run_service.get_run_logs.return_value = [mock_log_1, mock_log_2]

        mock_exec_service = Mock()

        async def _fake_stream(run_id):
            yield {"event": "node_started", "data": {"node_id": "b2"}}
            yield {"event": "run_completed", "data": {"run_id": run_id}}

        mock_exec_service.subscribe_stream = _fake_stream

        app.dependency_overrides[get_run_service] = lambda: mock_run_service
        app.dependency_overrides[get_execution_service] = lambda: mock_exec_service

        try:
            with client.stream("GET", "/api/runs/run_sse_1/stream") as response:
                body = response.read().decode()
            events = _parse_sse_events(body)

            # Exactly 4 events: 2 replay + 2 live
            assert len(events) == 4

            # First two events must be replay type carrying the original log data
            assert events[0]["event"] == "replay"
            assert events[0]["data"]["event"] == "block_start"
            assert events[0]["data"]["block_id"] == "b1"

            assert events[1]["event"] == "replay"
            assert events[1]["data"]["event"] == "block_complete"
            assert events[1]["data"]["block_id"] == "b1"

            # Live events follow after all replays
            assert events[2]["event"] == "node_started"
            assert events[2]["data"]["node_id"] == "b2"

            assert events[3]["event"] == "run_completed"
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 6. Cleanup after completion
# ---------------------------------------------------------------------------


class TestStreamCleanup:
    @pytest.mark.asyncio
    async def test_observer_queue_removed_after_run_completes(self):
        """After run_completed, the streaming observer queue should be cleaned up."""
        from runsight_api.logic.observers.streaming_observer import StreamingObserver

        observer = StreamingObserver(run_id="run_cleanup_1")

        # Simulate block lifecycle
        observer.on_block_start("wf", "b1", "llm")
        observer.on_block_complete("wf", "b1", "llm", 1.0, Mock())
        observer.on_workflow_complete("wf", Mock(), 2.0)

        # After workflow_complete, the queue should signal completion
        assert observer.is_done is True

    def test_streaming_observer_implements_workflow_observer(self):
        """StreamingObserver should satisfy the WorkflowObserver protocol."""
        from runsight_core.observer import WorkflowObserver

        from runsight_api.logic.observers.streaming_observer import StreamingObserver

        observer = StreamingObserver(run_id="run_proto_1")
        assert isinstance(observer, WorkflowObserver)


# ---------------------------------------------------------------------------
# 7. StreamingObserver pushes events to asyncio.Queue (B6 fix: async tests)
# ---------------------------------------------------------------------------


class TestStreamingObserver:
    @pytest.mark.asyncio
    async def test_observer_pushes_events_to_queue(self):
        """StreamingObserver.on_block_start should enqueue a node_started event."""
        from runsight_api.logic.observers.streaming_observer import StreamingObserver

        observer = StreamingObserver(run_id="run_q_1")
        observer.on_block_start("wf", "block_1", "llm")

        event = await observer.queue.get()
        assert event["event"] == "node_started"
        assert event["data"]["node_id"] == "block_1"

    @pytest.mark.asyncio
    async def test_observer_pushes_node_completed(self):
        """StreamingObserver.on_block_complete should enqueue a node_completed event."""
        from runsight_api.logic.observers.streaming_observer import StreamingObserver

        observer = StreamingObserver(run_id="run_q_2")
        mock_state = Mock()
        mock_state.total_cost_usd = 0.01
        mock_state.total_tokens = 100
        observer.on_block_complete("wf", "block_1", "llm", 1.5, mock_state)

        event = await observer.queue.get()
        assert event["event"] == "node_completed"
        assert event["data"]["node_id"] == "block_1"
        assert event["data"]["duration_s"] == 1.5

    @pytest.mark.asyncio
    async def test_observer_pushes_node_failed(self):
        """StreamingObserver.on_block_error should enqueue a node_failed event."""
        from runsight_api.logic.observers.streaming_observer import StreamingObserver

        observer = StreamingObserver(run_id="run_q_3")
        observer.on_block_error("wf", "block_1", "llm", 0.5, ValueError("bad input"))

        event = await observer.queue.get()
        assert event["event"] == "node_failed"
        assert event["data"]["node_id"] == "block_1"
        assert "bad input" in event["data"]["error"]

    @pytest.mark.asyncio
    async def test_observer_pushes_run_completed(self):
        """StreamingObserver.on_workflow_complete should enqueue run_completed."""
        from runsight_api.logic.observers.streaming_observer import StreamingObserver

        observer = StreamingObserver(run_id="run_q_4")
        mock_state = Mock()
        mock_state.total_cost_usd = 0.05
        mock_state.total_tokens = 500
        observer.on_workflow_complete("wf", mock_state, 10.0)

        event = await observer.queue.get()
        assert event["event"] == "run_completed"

    @pytest.mark.asyncio
    async def test_observer_pushes_run_failed(self):
        """StreamingObserver.on_workflow_error should enqueue run_failed."""
        from runsight_api.logic.observers.streaming_observer import StreamingObserver

        observer = StreamingObserver(run_id="run_q_5")
        observer.on_workflow_error("wf", RuntimeError("crash"), 3.0)

        event = await observer.queue.get()
        assert event["event"] == "run_failed"
        assert "crash" in event["data"]["error"]


# ---------------------------------------------------------------------------
# 8. Observer registry in ExecutionService (B7 fix: new test)
# ---------------------------------------------------------------------------


class TestObserverRegistry:
    @pytest.mark.asyncio
    async def test_execution_service_registers_observer_for_run_id(self):
        """ExecutionService should store a StreamingObserver per run_id and allow retrieval."""
        from runsight_api.logic.observers.streaming_observer import StreamingObserver
        from runsight_api.logic.services.execution_service import ExecutionService

        exec_service = ExecutionService(
            run_repo=Mock(),
            workflow_repo=Mock(),
            provider_repo=Mock(),
        )

        observer = StreamingObserver(run_id="run_reg_1")

        # Register observer for a run_id
        exec_service.register_observer("run_reg_1", observer)

        # Retrieve it back
        retrieved = exec_service.get_observer("run_reg_1")
        assert retrieved is observer

    @pytest.mark.asyncio
    async def test_execution_service_returns_none_for_unknown_run_id(self):
        """ExecutionService.get_observer should return None for unregistered run_ids."""
        from runsight_api.logic.services.execution_service import ExecutionService

        exec_service = ExecutionService(
            run_repo=Mock(),
            workflow_repo=Mock(),
            provider_repo=Mock(),
        )

        result = exec_service.get_observer("nonexistent_run")
        assert result is None

    @pytest.mark.asyncio
    async def test_execution_service_unregisters_observer(self):
        """ExecutionService should allow removing an observer after run completion."""
        from runsight_api.logic.observers.streaming_observer import StreamingObserver
        from runsight_api.logic.services.execution_service import ExecutionService

        exec_service = ExecutionService(
            run_repo=Mock(),
            workflow_repo=Mock(),
            provider_repo=Mock(),
        )

        observer = StreamingObserver(run_id="run_reg_2")
        exec_service.register_observer("run_reg_2", observer)

        # Unregister after completion
        exec_service.unregister_observer("run_reg_2")

        assert exec_service.get_observer("run_reg_2") is None


# ---------------------------------------------------------------------------
# 9. RUN-410 replay failure logging
# ---------------------------------------------------------------------------


class TestReplayFailureLogging:
    def test_replay_failure_logs_warning_and_stream_continues(self):
        """Replay DB errors should log a warning and still emit live terminal events."""
        from runsight_api.transport.routers import sse_stream

        mock_run_service = Mock()
        mock_run_service.get_run.return_value = _make_mock_run()
        mock_run_service.get_run_logs.side_effect = RuntimeError("db unavailable")

        mock_exec_service = Mock()

        async def _fake_stream(run_id):
            yield {"event": "run_completed", "data": {"run_id": run_id}}

        mock_exec_service.subscribe_stream = _fake_stream

        app.dependency_overrides[get_run_service] = lambda: mock_run_service
        app.dependency_overrides[get_execution_service] = lambda: mock_exec_service

        try:
            with patch.object(sse_stream, "logger", create=True) as mock_logger:
                with client.stream("GET", "/api/runs/run_sse_1/stream") as response:
                    body = response.read().decode()

            events = _parse_sse_events(body)

            assert response.status_code == 200
            assert events[-1]["event"] == "run_completed"
            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args
            assert call_args.args[0] == "SSE replay failed"
            assert call_args.kwargs["exc_info"] is True
        finally:
            app.dependency_overrides.clear()

    def test_sse_stream_source_has_no_bare_except_pass_in_replay_path(self):
        """The replay path must not silently swallow exceptions with except/pass."""
        source = SSE_STREAM_PATH.read_text()

        assert "except Exception:\n            pass" not in source
