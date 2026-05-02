"""Service-level SSE event behavior for workflow execution streams."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

from runsight_api.domain.events import (
    SSE_NODE_COMPLETED,
    SSE_NODE_STARTED,
    SSE_TERMINAL_EVENTS,
)
from tests.logic import sse_event_helpers as sse_helpers

base_dir = sse_helpers.base_dir
db_engine = sse_helpers.db_engine
execution_service = sse_helpers.execution_service


class TestSSEStreamProducesBlockEvents:
    """ExecutionService._run_workflow pushes events to StreamingObserver queue;
    subscribe_stream yields those events."""

    @pytest.mark.asyncio
    async def test_single_block_produces_node_started_and_node_completed(
        self, execution_service, db_engine
    ):
        """A single-block workflow must produce at least one node_started and
        one node_completed event through the subscribe_stream pipeline."""
        run_id = "run_sse_single"
        sse_helpers._seed_run(db_engine, run_id, "single_block_sse_test")
        wf = sse_helpers.parse_workflow_fixture("single-block")
        gate = asyncio.Event()

        events = await sse_helpers._run_and_collect(
            execution_service,
            run_id,
            wf,
            {"instruction": "Analyze"},
            gate,
            sse_helpers._mock_provider(),
        )

        event_types = [e["event"] for e in events]

        assert SSE_NODE_STARTED in event_types, (
            f"Stream must contain a {SSE_NODE_STARTED} event. Got: {event_types}"
        )
        assert SSE_NODE_COMPLETED in event_types, (
            f"Stream must contain a {SSE_NODE_COMPLETED} event. Got: {event_types}"
        )

    @pytest.mark.asyncio
    async def test_two_block_workflow_produces_events_for_both_blocks(
        self, execution_service, db_engine
    ):
        """A two-block sequential workflow must emit node_started and
        node_completed for BOTH blocks (draft_stream_block and publish_stream_block)."""
        run_id = "run_sse_two"
        sse_helpers._seed_run(db_engine, run_id, "two_block_sse_test")
        wf = sse_helpers.parse_workflow_fixture("two-block")
        gate = asyncio.Event()

        events = await sse_helpers._run_and_collect(
            execution_service,
            run_id,
            wf,
            {"instruction": "Write"},
            gate,
            sse_helpers._mock_provider(),
        )

        started_events = [e for e in events if e["event"] == SSE_NODE_STARTED]
        completed_events = [e for e in events if e["event"] == SSE_NODE_COMPLETED]

        assert len(started_events) >= 2, (
            f"Two-block workflow must emit at least 2 {SSE_NODE_STARTED} events. "
            f"Got {len(started_events)}: {[e['data'] for e in started_events]}"
        )
        assert len(completed_events) >= 2, (
            f"Two-block workflow must emit at least 2 {SSE_NODE_COMPLETED} events. "
            f"Got {len(completed_events)}: {[e['data'] for e in completed_events]}"
        )

        started_ids = {e["data"]["node_id"] for e in started_events}
        completed_ids = {e["data"]["node_id"] for e in completed_events}

        assert "draft_stream_block" in started_ids, (
            f"draft_stream_block missing from started: {started_ids}"
        )
        assert "publish_stream_block" in started_ids, (
            f"publish_stream_block missing from started: {started_ids}"
        )
        assert "draft_stream_block" in completed_ids, (
            f"draft_stream_block missing from completed: {completed_ids}"
        )
        assert "publish_stream_block" in completed_ids, (
            f"publish_stream_block missing from completed: {completed_ids}"
        )


class TestSSEStreamContainsChildSummaryOnly:
    """The parent stream should surface child completion summary only.

    Raw child node lifecycle traffic belongs on the child run stream.
    """

    @pytest.mark.asyncio
    async def test_child_workflow_block_events_appear_in_stream(
        self, execution_service, db_engine, base_dir
    ):
        """The parent stream must not expose raw child node lifecycle events."""
        from runsight_core.yaml.parser import parse_workflow_yaml

        import yaml

        run_id = "run_sse_child"
        sse_helpers._seed_run(db_engine, run_id, "parent_sse_test")

        parent_workflow_text = sse_helpers.workflow_fixture_text("parent-workflow")
        raw = yaml.safe_load(parent_workflow_text)
        workflow_registry = execution_service.workflow_repo.build_runnable_workflow_registry(
            "parent-workflow",
            parent_workflow_text,
        )
        wf = parse_workflow_yaml(raw, workflow_registry=workflow_registry)

        gate = asyncio.Event()

        events = await sse_helpers._run_and_collect(
            execution_service,
            run_id,
            wf,
            {"instruction": "Plan and delegate"},
            gate,
            sse_helpers._mock_provider(),
        )

        started_node_ids = {
            e["data"]["node_id"]
            for e in events
            if e["event"] == SSE_NODE_STARTED and "node_id" in e.get("data", {})
        }
        event_types = [e["event"] for e in events]

        assert "do_work" not in started_node_ids, (
            "Parent stream must not include raw child block events. Got node_ids: "
            f"{started_node_ids}"
        )
        assert "plan" in started_node_ids, (
            f"Parent block 'plan' must appear in SSE stream. Got: {started_node_ids}"
        )
        assert "child_run_completed" in event_types, (
            f"Parent stream must surface a child summary event. Got: {event_types}"
        )


class TestSSEEventPayloadMetadata:
    """Every block lifecycle event must contain the required metadata fields."""

    @pytest.mark.asyncio
    async def test_node_started_contains_node_id_and_block_type(self, execution_service, db_engine):
        """node_started events must contain node_id and block_type."""
        run_id = "run_sse_meta_start"
        sse_helpers._seed_run(db_engine, run_id, "single_block_sse_test")
        wf = sse_helpers.parse_workflow_fixture("single-block")
        gate = asyncio.Event()

        events = await sse_helpers._run_and_collect(
            execution_service,
            run_id,
            wf,
            {"instruction": "Go"},
            gate,
            sse_helpers._mock_provider(),
        )

        started = [e for e in events if e["event"] == SSE_NODE_STARTED]
        assert len(started) >= 1, f"Must have at least one {SSE_NODE_STARTED}"

        for event in started:
            assert "node_id" in event["data"], (
                f"{SSE_NODE_STARTED} must contain 'node_id'. Got: {event['data']}"
            )
            assert "block_type" in event["data"], (
                f"{SSE_NODE_STARTED} must contain 'block_type'. Got: {event['data']}"
            )

    @pytest.mark.asyncio
    async def test_node_completed_contains_node_id_and_block_type(
        self, execution_service, db_engine
    ):
        """node_completed events must contain node_id and block_type."""
        run_id = "run_sse_meta_comp"
        sse_helpers._seed_run(db_engine, run_id, "single_block_sse_test")
        wf = sse_helpers.parse_workflow_fixture("single-block")
        gate = asyncio.Event()

        events = await sse_helpers._run_and_collect(
            execution_service,
            run_id,
            wf,
            {"instruction": "Go"},
            gate,
            sse_helpers._mock_provider(),
        )

        completed = [e for e in events if e["event"] == SSE_NODE_COMPLETED]
        assert len(completed) >= 1, f"Must have at least one {SSE_NODE_COMPLETED}"

        for event in completed:
            assert "node_id" in event["data"], (
                f"{SSE_NODE_COMPLETED} must contain 'node_id'. Got: {event['data']}"
            )
            assert "block_type" in event["data"], (
                f"{SSE_NODE_COMPLETED} must contain 'block_type'. Got: {event['data']}"
            )

    @pytest.mark.asyncio
    async def test_run_completed_contains_run_id(self, execution_service, db_engine):
        """The terminal run_completed event must contain run_id."""
        run_id = "run_sse_meta_term"
        sse_helpers._seed_run(db_engine, run_id, "single_block_sse_test")
        wf = sse_helpers.parse_workflow_fixture("single-block")
        gate = asyncio.Event()

        events = await sse_helpers._run_and_collect(
            execution_service,
            run_id,
            wf,
            {"instruction": "Go"},
            gate,
            sse_helpers._mock_provider(),
        )

        terminal = [e for e in events if e["event"] in SSE_TERMINAL_EVENTS]
        assert len(terminal) >= 1, (
            f"Must have a terminal event. Got: {[e['event'] for e in events]}"
        )

        for event in terminal:
            assert "run_id" in event["data"], (
                f"Terminal '{event['event']}' must contain 'run_id'. Got: {event['data']}"
            )
            assert event["data"]["run_id"] == run_id, (
                f"run_id mismatch: expected '{run_id}', got '{event['data']['run_id']}'"
            )


class TestRunCompletedIsLastEvent:
    """run_completed must be the LAST event in the stream."""

    @pytest.mark.asyncio
    async def test_run_completed_is_final_event_single_block(self, execution_service, db_engine):
        """For a single-block workflow, run_completed must be the final event."""
        run_id = "run_sse_order_single"
        sse_helpers._seed_run(db_engine, run_id, "single_block_sse_test")
        wf = sse_helpers.parse_workflow_fixture("single-block")
        gate = asyncio.Event()

        events = await sse_helpers._run_and_collect(
            execution_service,
            run_id,
            wf,
            {"instruction": "Go"},
            gate,
            sse_helpers._mock_provider(),
        )

        assert len(events) >= 1, "Stream must contain at least one event"

        last = events[-1]
        assert last["event"] in SSE_TERMINAL_EVENTS, (
            f"Last event must be terminal. Got: '{last['event']}'"
        )

        block_types = {SSE_NODE_STARTED, SSE_NODE_COMPLETED, "node_failed"}
        seen_terminal = False
        for event in events:
            if event["event"] in SSE_TERMINAL_EVENTS:
                seen_terminal = True
            elif seen_terminal and event["event"] in block_types:
                pytest.fail(
                    f"Block event '{event['event']}' after terminal. "
                    f"Sequence: {[e['event'] for e in events]}"
                )

    @pytest.mark.asyncio
    async def test_all_node_completed_precede_run_completed_two_blocks(
        self, execution_service, db_engine
    ):
        """Both draft_stream_block and publish_stream_block must have node_completed events BEFORE
        run_completed."""
        run_id = "run_sse_order_two"
        sse_helpers._seed_run(db_engine, run_id, "two_block_sse_test")
        wf = sse_helpers.parse_workflow_fixture("two-block")
        gate = asyncio.Event()

        events = await sse_helpers._run_and_collect(
            execution_service,
            run_id,
            wf,
            {"instruction": "Write"},
            gate,
            sse_helpers._mock_provider(),
        )

        event_types = [e["event"] for e in events]

        terminal_idx = next(
            (i for i, et in enumerate(event_types) if et in SSE_TERMINAL_EVENTS),
            None,
        )
        assert terminal_idx is not None, f"Must have terminal event. Got: {event_types}"

        completed_before = {
            e["data"]["node_id"]
            for i, e in enumerate(events)
            if e["event"] == SSE_NODE_COMPLETED and i < terminal_idx
        }

        assert "draft_stream_block" in completed_before, (
            f"draft_stream_block must complete before terminal. Got: {completed_before}"
        )
        assert "publish_stream_block" in completed_before, (
            f"publish_stream_block must complete before terminal. Got: {completed_before}"
        )


class TestNoExternalAPICalls:
    """The entire pipeline must work without external LLM API keys."""

    @pytest.mark.asyncio
    async def test_pipeline_works_without_external_api_keys(self, execution_service, db_engine):
        """The full streaming pipeline must succeed with no external API keys."""
        import os

        run_id = "run_sse_no_keys"
        sse_helpers._seed_run(db_engine, run_id, "single_block_sse_test")
        wf = sse_helpers.parse_workflow_fixture("single-block")
        gate = asyncio.Event()

        with patch.dict(os.environ, {"OPENAI_API_KEY": "", "ANTHROPIC_API_KEY": ""}):
            events = await sse_helpers._run_and_collect(
                execution_service,
                run_id,
                wf,
                {"instruction": "Test without keys"},
                gate,
                sse_helpers._mock_provider(),
            )

        event_types = [e["event"] for e in events]

        assert len(events) >= 3, (
            f"Stream must contain at least 3 events. Got {len(events)}: {event_types}"
        )

        last = events[-1]
        assert last["event"] in SSE_TERMINAL_EVENTS, (
            f"Stream must end with terminal event. Got: '{last['event']}'"
        )
