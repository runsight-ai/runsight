"""E2E tests for RUN-707: StreamingObserver -> SSE queue -> HTTP chunk pipeline.

Gap being closed: SSE streaming path has structural coverage at both ends but
the middle is untested:
- StreamingObserver pushes events to an in-memory queue when a block completes
- SSE endpoint reads from that queue and streams chunks to the client
- No test verifies this queue-to-HTTP-chunk path end-to-end

These tests exercise the FULL streaming pipeline:
    ExecutionService._run_workflow  ->  StreamingObserver enqueues events
        ->  ExecutionService.subscribe_stream yields events concurrently

The LLM mock uses an asyncio.Event gate to hold execution until the stream
consumer is connected, ensuring we capture all events.

All mocked — no real API calls. Only LiteLLMClient.achat is mocked.
"""

import asyncio
import json
import tempfile
from pathlib import Path
from typing import Any, Dict
from unittest.mock import Mock, patch

import pytest
from sqlmodel import Session, SQLModel, create_engine

from runsight_api.domain.entities.run import Run, RunStatus
from runsight_api.domain.events import (
    SSE_NODE_COMPLETED,
    SSE_NODE_STARTED,
    SSE_TERMINAL_EVENTS,
)


# ---------------------------------------------------------------------------
# Workflow YAML definitions
# ---------------------------------------------------------------------------

SINGLE_BLOCK_YAML = """\
id: single-block
kind: workflow
version: "1.0"
config:
  model_name: gpt-4o
souls:
  analyst:
    id: analyst
    kind: soul
    name: Analyst
    role: Analyst
    system_prompt: You are a careful analyst.
    provider: openai
    model_name: gpt-4o
blocks:
  analyze:
    type: linear
    soul_ref: analyst
workflow:
  name: single_block_sse_test
  entry: analyze
  transitions:
    - from: analyze
      to: null
"""

TWO_BLOCK_YAML = """\
id: two-block
kind: workflow
version: "1.0"
config:
  model_name: gpt-4o
souls:
  writer:
    id: writer
    kind: soul
    name: Writer
    role: Writer
    system_prompt: You are a writer.
    provider: openai
    model_name: gpt-4o
blocks:
  step_a:
    type: linear
    soul_ref: writer
  step_b:
    type: linear
    soul_ref: writer
workflow:
  name: two_block_sse_test
  entry: step_a
  transitions:
    - from: step_a
      to: step_b
    - from: step_b
      to: null
"""

PARENT_WORKFLOW_YAML = """\
id: parent-workflow
kind: workflow
version: "1.0"
config:
  model_name: gpt-4o
souls:
  planner:
    id: planner
    kind: soul
    name: Planner
    role: Planner
    system_prompt: You are a planner.
    provider: openai
    model_name: gpt-4o
blocks:
  plan:
    type: linear
    soul_ref: planner
  delegate:
    type: workflow
    workflow_ref: child-workflow
workflow:
  name: parent_sse_test
  entry: plan
  transitions:
    - from: plan
      to: delegate
    - from: delegate
      to: null
"""

CHILD_WORKFLOW_YAML = """\
id: child-workflow
kind: workflow
version: "1.0"
interface:
  inputs: []
  outputs: []
config:
  model_name: gpt-4o
souls:
  worker:
    id: worker
    kind: soul
    name: Worker
    role: Worker
    system_prompt: You are a worker.
    provider: openai
    model_name: gpt-4o
blocks:
  do_work:
    type: linear
    soul_ref: worker
workflow:
  name: child_sse_test
  entry: do_work
  transitions:
    - from: do_work
      to: null
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_workflow_file(base_dir: Path, workflow_id: str, content: str) -> None:
    wf_dir = base_dir / "custom" / "workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)
    canvas_dir = wf_dir / ".canvas"
    canvas_dir.mkdir(parents=True, exist_ok=True)
    (wf_dir / f"{workflow_id}.yaml").write_text(content, encoding="utf-8")


def _make_achat_response(content: str, cost_usd: float = 0.001, total_tokens: int = 100):
    return {
        "content": content,
        "cost_usd": cost_usd,
        "prompt_tokens": 50,
        "completion_tokens": 50,
        "total_tokens": total_tokens,
        "tool_calls": None,
        "finish_reason": "stop",
        "raw_message": {"role": "assistant", "content": content},
    }


def _seed_run(engine, run_id: str, workflow_name: str) -> None:
    with Session(engine) as session:
        session.add(
            Run(
                id=run_id,
                workflow_id="wf_test",
                workflow_name=workflow_name,
                status=RunStatus.pending,
                task_json="{}",
            )
        )
        session.commit()


def _mock_provider():
    mock = Mock()
    mock.id = "openai"
    mock.type = "openai"
    mock.api_key = "sk-test"
    mock.is_active = True
    mock.models = ["gpt-4o"]
    return mock


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


def _gated_achat(gate: asyncio.Event, content: str = "Done."):
    """Create an async mock for LiteLLMClient.achat that waits on a gate.

    The mock blocks on the gate event, giving the test time to connect to
    the stream before the workflow completes. The gate is set by the test
    after it starts consuming the stream.
    """

    async def _achat(*args, **kwargs):
        await gate.wait()
        return _make_achat_response(content)

    return _achat


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_engine():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(eng)
    return eng


@pytest.fixture
def base_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        _write_workflow_file(base, "single-block", SINGLE_BLOCK_YAML)
        _write_workflow_file(base, "two-block", TWO_BLOCK_YAML)
        _write_workflow_file(base, "parent-workflow", PARENT_WORKFLOW_YAML)
        _write_workflow_file(base, "child-workflow", CHILD_WORKFLOW_YAML)
        yield base


@pytest.fixture
def execution_service(db_engine, base_dir):
    """Build a real ExecutionService backed by in-memory DB and temp filesystem."""
    from runsight_api.data.filesystem.provider_repo import FileSystemProviderRepo
    from runsight_api.data.filesystem.workflow_repo import WorkflowRepository
    from runsight_api.logic.services.execution_service import ExecutionService

    workflow_repo = WorkflowRepository(str(base_dir))
    provider_repo = FileSystemProviderRepo(base_path=str(base_dir))

    mock_secrets = Mock()
    mock_secrets.resolve = Mock(return_value="sk-fake-test-key-for-e2e")

    return ExecutionService(
        run_repo=None,
        workflow_repo=workflow_repo,
        provider_repo=provider_repo,
        engine=db_engine,
        secrets=mock_secrets,
        settings_repo=None,
    )


def _parse_workflow(yaml_content: str):
    """Parse a workflow YAML string into a runnable Workflow object."""
    from runsight_core.yaml.parser import parse_workflow_yaml

    import yaml

    raw = yaml.safe_load(yaml_content)
    return parse_workflow_yaml(raw)


async def _wait_for_observer(execution_service, run_id: str, timeout: float = 5.0):
    """Wait until the observer for run_id is registered."""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        if execution_service.get_observer(run_id) is not None:
            return
        await asyncio.sleep(0.005)
    raise TimeoutError(f"Observer for {run_id} was never registered")


async def _collect_stream_events(
    execution_service, run_id: str, timeout: float = 10.0
) -> list[dict]:
    """Collect all events from subscribe_stream until a terminal event or timeout."""
    events: list[dict] = []
    deadline = asyncio.get_event_loop().time() + timeout

    async for event in execution_service.subscribe_stream(run_id):
        events.append(event)
        if event["event"] in SSE_TERMINAL_EVENTS:
            break
        if asyncio.get_event_loop().time() > deadline:
            break

    return events


async def _run_and_collect(
    execution_service,
    run_id: str,
    wf,
    task_data: Dict[str, Any],
    gate: asyncio.Event,
    mock_provider,
) -> list[dict]:
    """Run workflow and collect stream events concurrently.

    Uses a gated LLM mock: the gate holds the LLM call until the stream
    consumer is connected, then releases it to let the workflow complete.
    """
    with (
        patch(
            "runsight_core.llm.client.LiteLLMClient.achat",
            side_effect=_gated_achat(gate),
        ),
        patch.object(
            execution_service.provider_repo,
            "list_all",
            return_value=[mock_provider],
        ),
    ):
        # Start workflow in background (blocked on gate inside LLM mock)
        run_task = asyncio.create_task(execution_service._run_workflow(run_id, wf, task_data))

        # Wait for observer registration (happens before LLM call)
        await _wait_for_observer(execution_service, run_id)

        # Start collecting events in a task (this will subscribe to the queue)
        collect_task = asyncio.create_task(_collect_stream_events(execution_service, run_id))

        # Release the gate — LLM calls proceed, workflow completes
        gate.set()

        # Wait for both tasks
        events = await collect_task
        await run_task

    return events


# ===========================================================================
# AC1 — Run workflow -> SSE stream produces block_started and block_completed
#        events for each block
# ===========================================================================


class TestSSEStreamProducesBlockEvents:
    """ExecutionService._run_workflow pushes events to StreamingObserver queue;
    subscribe_stream yields those events."""

    @pytest.mark.asyncio
    async def test_single_block_produces_node_started_and_node_completed(
        self, execution_service, db_engine
    ):
        """A single-block workflow must produce at least one node_started and
        one node_completed event through the subscribe_stream pipeline."""
        run_id = "run_707_single"
        _seed_run(db_engine, run_id, "single_block_sse_test")
        wf = _parse_workflow(SINGLE_BLOCK_YAML)
        gate = asyncio.Event()

        events = await _run_and_collect(
            execution_service,
            run_id,
            wf,
            {"instruction": "Analyze"},
            gate,
            _mock_provider(),
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
        node_completed for BOTH blocks (step_a and step_b)."""
        run_id = "run_707_two"
        _seed_run(db_engine, run_id, "two_block_sse_test")
        wf = _parse_workflow(TWO_BLOCK_YAML)
        gate = asyncio.Event()

        events = await _run_and_collect(
            execution_service,
            run_id,
            wf,
            {"instruction": "Write"},
            gate,
            _mock_provider(),
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

        assert "step_a" in started_ids, f"step_a missing from started: {started_ids}"
        assert "step_b" in started_ids, f"step_b missing from started: {started_ids}"
        assert "step_a" in completed_ids, f"step_a missing from completed: {completed_ids}"
        assert "step_b" in completed_ids, f"step_b missing from completed: {completed_ids}"


# ===========================================================================
# AC2 — Child WorkflowBlock -> SSE stream contains child block events
# ===========================================================================


class TestSSEStreamContainsChildBlockEvents:
    """When a parent workflow contains a workflow-call block that spawns a child
    workflow, the SSE stream must contain events for the child workflow's blocks."""

    @pytest.mark.asyncio
    async def test_child_workflow_block_events_appear_in_stream(
        self, execution_service, db_engine, base_dir
    ):
        """The stream for a parent run must include node events from the child
        workflow's blocks (e.g. do_work), not just the parent's blocks."""
        from runsight_core.yaml.parser import parse_workflow_yaml

        import yaml

        run_id = "run_707_child"
        _seed_run(db_engine, run_id, "parent_sse_test")

        raw = yaml.safe_load(PARENT_WORKFLOW_YAML)
        workflow_registry = execution_service.workflow_repo.build_runnable_workflow_registry(
            "parent-workflow",
            PARENT_WORKFLOW_YAML,
        )
        wf = parse_workflow_yaml(raw, workflow_registry=workflow_registry)

        gate = asyncio.Event()

        events = await _run_and_collect(
            execution_service,
            run_id,
            wf,
            {"instruction": "Plan and delegate"},
            gate,
            _mock_provider(),
        )

        started_node_ids = {
            e["data"]["node_id"]
            for e in events
            if e["event"] == SSE_NODE_STARTED and "node_id" in e.get("data", {})
        }

        assert "do_work" in started_node_ids, (
            f"Child workflow's block 'do_work' must appear in the parent's SSE "
            f"stream. Got node_ids: {started_node_ids}"
        )
        assert "plan" in started_node_ids, (
            f"Parent block 'plan' must appear in SSE stream. Got: {started_node_ids}"
        )


# ===========================================================================
# AC3 — Event payloads contain run_id, node_id, block type
# ===========================================================================


class TestSSEEventPayloadMetadata:
    """Every block lifecycle event must contain the required metadata fields."""

    @pytest.mark.asyncio
    async def test_node_started_contains_node_id_and_block_type(self, execution_service, db_engine):
        """node_started events must contain node_id and block_type."""
        run_id = "run_707_meta_start"
        _seed_run(db_engine, run_id, "single_block_sse_test")
        wf = _parse_workflow(SINGLE_BLOCK_YAML)
        gate = asyncio.Event()

        events = await _run_and_collect(
            execution_service,
            run_id,
            wf,
            {"instruction": "Go"},
            gate,
            _mock_provider(),
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
        run_id = "run_707_meta_comp"
        _seed_run(db_engine, run_id, "single_block_sse_test")
        wf = _parse_workflow(SINGLE_BLOCK_YAML)
        gate = asyncio.Event()

        events = await _run_and_collect(
            execution_service,
            run_id,
            wf,
            {"instruction": "Go"},
            gate,
            _mock_provider(),
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
        run_id = "run_707_meta_term"
        _seed_run(db_engine, run_id, "single_block_sse_test")
        wf = _parse_workflow(SINGLE_BLOCK_YAML)
        gate = asyncio.Event()

        events = await _run_and_collect(
            execution_service,
            run_id,
            wf,
            {"instruction": "Go"},
            gate,
            _mock_provider(),
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


# ===========================================================================
# AC4 — No RUN_COMPLETED event fires before all blocks complete
# ===========================================================================


class TestRunCompletedIsLastEvent:
    """run_completed must be the LAST event in the stream."""

    @pytest.mark.asyncio
    async def test_run_completed_is_final_event_single_block(self, execution_service, db_engine):
        """For a single-block workflow, run_completed must be the final event."""
        run_id = "run_707_order_s"
        _seed_run(db_engine, run_id, "single_block_sse_test")
        wf = _parse_workflow(SINGLE_BLOCK_YAML)
        gate = asyncio.Event()

        events = await _run_and_collect(
            execution_service,
            run_id,
            wf,
            {"instruction": "Go"},
            gate,
            _mock_provider(),
        )

        assert len(events) >= 1, "Stream must contain at least one event"

        last = events[-1]
        assert last["event"] in SSE_TERMINAL_EVENTS, (
            f"Last event must be terminal. Got: '{last['event']}'"
        )

        # No block events after terminal
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
        """Both step_a and step_b must have node_completed events BEFORE
        run_completed."""
        run_id = "run_707_order_t"
        _seed_run(db_engine, run_id, "two_block_sse_test")
        wf = _parse_workflow(TWO_BLOCK_YAML)
        gate = asyncio.Event()

        events = await _run_and_collect(
            execution_service,
            run_id,
            wf,
            {"instruction": "Write"},
            gate,
            _mock_provider(),
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

        assert "step_a" in completed_before, (
            f"step_a must complete before terminal. Got: {completed_before}"
        )
        assert "step_b" in completed_before, (
            f"step_b must complete before terminal. Got: {completed_before}"
        )


# ===========================================================================
# AC5 — All mocked: no real API calls
# ===========================================================================


class TestNoRealAPICalls:
    """The entire pipeline must work without real LLM API keys."""

    @pytest.mark.asyncio
    async def test_pipeline_works_without_real_api_keys(self, execution_service, db_engine):
        """The full streaming pipeline must succeed with no real API keys."""
        import os

        run_id = "run_707_nokeys"
        _seed_run(db_engine, run_id, "single_block_sse_test")
        wf = _parse_workflow(SINGLE_BLOCK_YAML)
        gate = asyncio.Event()

        with patch.dict(os.environ, {"OPENAI_API_KEY": "", "ANTHROPIC_API_KEY": ""}):
            events = await _run_and_collect(
                execution_service,
                run_id,
                wf,
                {"instruction": "Test without keys"},
                gate,
                _mock_provider(),
            )

        event_types = [e["event"] for e in events]

        assert len(events) >= 3, (
            f"Stream must contain at least 3 events. Got {len(events)}: {event_types}"
        )

        last = events[-1]
        assert last["event"] in SSE_TERMINAL_EVENTS, (
            f"Stream must end with terminal event. Got: '{last['event']}'"
        )


# ===========================================================================
# HTTP Layer — SSE endpoint delivers events as HTTP chunks
# ===========================================================================


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
        mock_provider = _mock_provider()

        async with AsyncClient(
            transport=ASGITransport(app=app_with_sse),
            base_url="http://test",
        ) as client:
            with (
                patch(
                    "runsight_core.llm.client.LiteLLMClient.achat",
                    side_effect=_gated_achat(gate),
                ),
                patch.object(
                    execution_service.provider_repo,
                    "list_all",
                    return_value=[mock_provider],
                ),
            ):
                # Start the run (execution blocked on gate inside LLM mock)
                post_resp = await client.post(
                    "/api/runs",
                    json={
                        "workflow_id": "single-block",
                        "inputs": {"instruction": "Analyze"},
                    },
                )
                assert post_resp.status_code == 200
                run_id = post_resp.json()["id"]

                # Wait for observer registration
                await _wait_for_observer(execution_service, run_id)

                # Open the gate so execution can proceed
                gate.set()

                # Stream SSE events via HTTP
                chunks = []
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

        raw_sse = "".join(chunks)
        events = _parse_sse_events(raw_sse)
        event_types = [e["event"] for e in events]

        # Must contain live block events delivered as SSE chunks
        has_node_events = SSE_NODE_STARTED in event_types or SSE_NODE_COMPLETED in event_types
        has_replay_events = "replay" in event_types

        assert has_node_events or has_replay_events, (
            f"SSE HTTP stream must contain node events (live or replay). Got: {event_types}"
        )

    @pytest.mark.asyncio
    async def test_sse_http_events_contain_valid_json_data(
        self, app_with_sse, execution_service, db_engine
    ):
        """Each SSE chunk must have valid JSON in the data field."""
        from httpx import ASGITransport, AsyncClient

        gate = asyncio.Event()
        mock_provider = _mock_provider()

        async with AsyncClient(
            transport=ASGITransport(app=app_with_sse),
            base_url="http://test",
        ) as client:
            with (
                patch(
                    "runsight_core.llm.client.LiteLLMClient.achat",
                    side_effect=_gated_achat(gate),
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
                        "inputs": {"instruction": "Analyze"},
                    },
                )
                run_id = post_resp.json()["id"]

                await _wait_for_observer(execution_service, run_id)
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
        events = _parse_sse_events(raw_sse)

        assert len(events) >= 1, "Must receive at least one SSE event"

        for event in events:
            assert isinstance(event["data"], dict), (
                f"SSE event data must be valid JSON. Event '{event['event']}' has: {event['data']}"
            )
