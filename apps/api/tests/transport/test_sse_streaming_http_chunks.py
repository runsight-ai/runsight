"""HTTP transport behavior for SSE streaming chunks."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest
from sqlmodel import Session

from runsight_api.domain.events import (
    SSE_NODE_COMPLETED,
    SSE_NODE_STARTED,
    SSE_TERMINAL_EVENTS,
)
from tests import sse_streaming_helpers as sse_helpers

base_dir = sse_helpers.base_dir
db_engine = sse_helpers.db_engine
execution_service = sse_helpers.execution_service


class TestSSEEndpointHTTPChunks:
    """Full HTTP path: POST to start, GET SSE stream, verify SSE-formatted chunks."""

    @pytest.fixture
    def app_with_sse(self, db_engine, base_dir, execution_service):
        """FastAPI app with both runs router and SSE stream router."""
        from fastapi import FastAPI

        from runsight_api.data.filesystem.workflow_repo import WorkflowRepository
        from runsight_api.data.repositories.run_repo import RunRepository
        from runsight_api.logic.services.eval_service import EvalService
        from runsight_api.logic.services.run_service import RunService
        from runsight_api.transport.deps import (
            get_eval_service,
            get_execution_service,
            get_run_service,
        )
        from runsight_api.transport.routers import runs, sse_stream

        app = FastAPI()
        app.include_router(runs.router, prefix="/api")
        app.include_router(sse_stream.router, prefix="/api")

        workflow_repo = WorkflowRepository(str(base_dir))
        app.state.execution_service = execution_service

        def _get_run_service():
            session = Session(db_engine)
            run_repo = RunRepository(session)
            return RunService(run_repo, workflow_repo)

        def _get_execution_service(request=None):
            return execution_service

        def _get_eval_service():
            session = Session(db_engine)
            run_repo = RunRepository(session)
            return EvalService(run_repo)

        app.dependency_overrides[get_run_service] = _get_run_service
        app.dependency_overrides[get_execution_service] = _get_execution_service
        app.dependency_overrides[get_eval_service] = _get_eval_service

        yield app

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_sse_endpoint_streams_block_events_as_http_chunks(
        self, app_with_sse, execution_service, db_engine
    ):
        """The SSE HTTP endpoint must deliver block lifecycle events as properly
        formatted SSE chunks when a run is executing.

        Uses a gated LLM mock: POST creates the run and starts execution
        (blocked on gate), then streaming GET connects and captures events,
        then the gate opens to let execution complete.
        """
        from httpx import ASGITransport, AsyncClient

        gate = asyncio.Event()
        mock_provider = sse_helpers._mock_provider()

        async with AsyncClient(
            transport=ASGITransport(app=app_with_sse),
            base_url="http://localhost",
        ) as client:
            with (
                patch(
                    "runsight_core.llm.client.LiteLLMClient.achat",
                    side_effect=sse_helpers._gated_achat(gate),
                ),
                patch.object(
                    execution_service.provider_repo,
                    "list_all",
                    return_value=[mock_provider],
                ),
            ):
                post_resp = await client.post(
                    "/api/runs",
                    json={
                        "workflow_id": "single-block",
                        "branch": "main",
                        "inputs": {"instruction": "Analyze"},
                    },
                )
                assert post_resp.status_code == 200
                run_id = post_resp.json()["id"]

                await sse_helpers._wait_for_observer(execution_service, run_id)

                chunks = []
                subscribed = asyncio.Event()
                original_subscribe_stream = execution_service.subscribe_stream

                async def subscribe_stream_with_signal(*args, **kwargs):
                    subscribed.set()
                    async for event in original_subscribe_stream(*args, **kwargs):
                        yield event

                async def consume_stream() -> None:
                    async with client.stream(
                        "GET",
                        f"/api/runs/{run_id}/stream",
                        headers={"Accept": "text/event-stream"},
                    ) as stream:
                        assert stream.status_code == 200
                        assert "text/event-stream" in stream.headers.get("content-type", "")
                        async for chunk in stream.aiter_text():
                            chunks.append(chunk)
                            if any(t in chunk for t in SSE_TERMINAL_EVENTS):
                                break

                with patch.object(
                    execution_service,
                    "subscribe_stream",
                    side_effect=subscribe_stream_with_signal,
                ):
                    stream_task = asyncio.create_task(consume_stream())
                    await asyncio.wait_for(subscribed.wait(), timeout=2)
                    gate.set()
                    await asyncio.wait_for(stream_task, timeout=10)

        raw_sse = "".join(chunks)
        events = sse_helpers._parse_sse_events(raw_sse)
        event_types = [e["event"] for e in events]
        replay_payloads = [
            event.get("data")
            for event in events
            if event.get("event") == "replay" and isinstance(event.get("data"), dict)
        ]

        has_node_events = SSE_NODE_STARTED in event_types or SSE_NODE_COMPLETED in event_types
        has_replay_progress = any(
            payload.get("event")
            in {"workflow_start", "block_start", "block_complete", "workflow_complete"}
            for payload in replay_payloads
            if isinstance(payload, dict)
        )
        has_terminal_event = any(
            event_type in SSE_TERMINAL_EVENTS for event_type in event_types
        ) or any(
            payload.get("event") in {"workflow_complete", "workflow_error"}
            for payload in replay_payloads
            if isinstance(payload, dict)
        )

        assert has_node_events, (
            "SSE HTTP stream must contain live node events before falling back to replay. "
            f"Got top-level events: {event_types}"
        )
        assert has_replay_progress or has_terminal_event, (
            "SSE HTTP stream must surface replayable progress or a terminal contract. "
            f"Got top-level events: {event_types}"
        )
        assert has_terminal_event, (
            f"SSE HTTP stream must terminate with a terminal event. Got: {event_types}"
        )

    @pytest.mark.asyncio
    async def test_sse_http_events_contain_valid_json_data(
        self, app_with_sse, execution_service, db_engine
    ):
        """Each SSE chunk must have valid JSON in the data field."""
        from httpx import ASGITransport, AsyncClient

        gate = asyncio.Event()
        mock_provider = sse_helpers._mock_provider()

        async with AsyncClient(
            transport=ASGITransport(app=app_with_sse),
            base_url="http://localhost",
        ) as client:
            with (
                patch(
                    "runsight_core.llm.client.LiteLLMClient.achat",
                    side_effect=sse_helpers._gated_achat(gate),
                ),
                patch.object(
                    execution_service.provider_repo,
                    "list_all",
                    return_value=[mock_provider],
                ),
            ):
                post_resp = await client.post(
                    "/api/runs",
                    json={
                        "workflow_id": "single-block",
                        "branch": "main",
                        "inputs": {"instruction": "Analyze"},
                    },
                )
                run_id = post_resp.json()["id"]

                await sse_helpers._wait_for_observer(execution_service, run_id)
                gate.set()

                chunks = []
                async with client.stream(
                    "GET",
                    f"/api/runs/{run_id}/stream",
                    headers={"Accept": "text/event-stream"},
                ) as stream:
                    async for chunk in stream.aiter_text():
                        chunks.append(chunk)
                        if any(t in chunk for t in SSE_TERMINAL_EVENTS):
                            break

        raw_sse = "".join(chunks)
        events = sse_helpers._parse_sse_events(raw_sse)

        assert len(events) >= 1, "Must receive at least one SSE event"

        for event in events:
            assert isinstance(event["data"], dict), (
                f"SSE event data must be valid JSON. Event '{event['event']}' has: {event['data']}"
            )
