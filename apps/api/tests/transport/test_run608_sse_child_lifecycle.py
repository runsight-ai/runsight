"""RED tests for RUN-608: child lifecycle SSE and shared transport contracts.

Problem: The current transport schemas and StreamingObserver have no concept
of parent/child run nesting. When a workflow-call block spawns a child run,
the child's ``run_completed`` event is indistinguishable from the root run's
completion — causing the SSE stream to close prematurely.

AC:
1. Parent stream stays open until root run completes.
2. Workflow-call node updates include child linkage.
3. Child completion never emits a terminal parent event.
4. No legacy SSE path remains that treats child completion as terminal for the parent.

Changes required:
- RunResponse gains ``parent_run_id``, ``root_run_id``, ``depth``.
- RunNodeResponse gains ``child_run_id``, ``exit_handle``.
- StreamingObserver becomes nesting-aware: only root completion is terminal.
"""

from unittest.mock import Mock

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_RUN_RESPONSE_BASE = dict(
    id="run_608",
    workflow_id="wf_1",
    workflow_name="wf_1",
    status="running",
    started_at=100.0,
    completed_at=None,
    duration_seconds=None,
    total_cost_usd=0.0,
    total_tokens=0,
    created_at=100.0,
    branch="main",
    source="manual",
    commit_sha=None,
    run_number=None,
    eval_pass_pct=None,
    regression_count=None,
    node_summary=None,
)

_NODE_RESPONSE_BASE = dict(
    id="run_608:step_1",
    run_id="run_608",
    node_id="step_1",
    block_type="llm",
    status="completed",
    started_at=100.0,
    completed_at=200.0,
    duration_seconds=1.0,
    cost_usd=0.05,
    tokens={"prompt": 100, "completion": 50, "total": 150},
    error=None,
    output=None,
    soul_id=None,
    model_name=None,
    eval_score=None,
    eval_passed=None,
    eval_results=None,
)


def _mock_state(cost: float = 0.0, tokens: int = 0):
    state = Mock()
    state.total_cost_usd = cost
    state.total_tokens = tokens
    return state


# ===========================================================================
# 1. Transport schema: RunResponse parent linkage fields
# ===========================================================================


class TestRunResponseParentLinkageFields:
    """RunResponse must declare parent_run_id, root_run_id, depth."""

    def test_run_response_has_parent_run_id_field(self):
        """RunResponse schema must accept and store parent_run_id."""
        from runsight_api.transport.schemas.runs import RunResponse

        resp = RunResponse(**{**_RUN_RESPONSE_BASE, "parent_run_id": "run_parent_1"})
        assert resp.parent_run_id == "run_parent_1"

    def test_run_response_has_root_run_id_field(self):
        """RunResponse schema must accept and store root_run_id."""
        from runsight_api.transport.schemas.runs import RunResponse

        resp = RunResponse(**{**_RUN_RESPONSE_BASE, "root_run_id": "run_root_1"})
        assert resp.root_run_id == "run_root_1"

    def test_run_response_has_depth_field(self):
        """RunResponse schema must accept and store depth."""
        from runsight_api.transport.schemas.runs import RunResponse

        resp = RunResponse(**{**_RUN_RESPONSE_BASE, "depth": 2})
        assert resp.depth == 2

    def test_run_response_linkage_fields_default_to_none_and_zero(self):
        """parent_run_id and root_run_id default to None; depth defaults to 0."""
        from runsight_api.transport.schemas.runs import RunResponse

        resp = RunResponse(**_RUN_RESPONSE_BASE)
        assert resp.parent_run_id is None
        assert resp.root_run_id is None
        assert resp.depth == 0


class TestRunResponseSerializesParentLinkage:
    """RunResponse serialization must include the parent linkage fields."""

    def test_run_response_serializes_parent_linkage(self):
        """Create a RunResponse with parent linkage, serialize to dict, verify fields present."""
        from runsight_api.transport.schemas.runs import RunResponse

        resp = RunResponse(
            **{
                **_RUN_RESPONSE_BASE,
                "parent_run_id": "run_parent_1",
                "root_run_id": "run_root_1",
                "depth": 1,
            }
        )
        data = resp.model_dump()
        assert data["parent_run_id"] == "run_parent_1"
        assert data["root_run_id"] == "run_root_1"
        assert data["depth"] == 1


# ===========================================================================
# 2. Transport schema: RunNodeResponse child linkage fields
# ===========================================================================


class TestRunNodeResponseChildLinkageFields:
    """RunNodeResponse must declare child_run_id and exit_handle."""

    def test_run_node_response_has_child_run_id_field(self):
        """RunNodeResponse schema must accept and store child_run_id."""
        from runsight_api.transport.schemas.runs import RunNodeResponse

        resp = RunNodeResponse(**{**_NODE_RESPONSE_BASE, "child_run_id": "run_child_1"})
        assert resp.child_run_id == "run_child_1"

    def test_run_node_response_has_exit_handle_field(self):
        """RunNodeResponse schema must accept and store exit_handle."""
        from runsight_api.transport.schemas.runs import RunNodeResponse

        resp = RunNodeResponse(**{**_NODE_RESPONSE_BASE, "exit_handle": "success"})
        assert resp.exit_handle == "success"

    def test_run_node_response_child_fields_default_to_none(self):
        """child_run_id and exit_handle default to None."""
        from runsight_api.transport.schemas.runs import RunNodeResponse

        resp = RunNodeResponse(**_NODE_RESPONSE_BASE)
        assert resp.child_run_id is None
        assert resp.exit_handle is None


class TestRunNodeResponseSerializesChildLinkage:
    """RunNodeResponse serialization must include the child linkage fields."""

    def test_run_node_response_serializes_child_run_id(self):
        """Create a RunNodeResponse with child_run_id set, serialize, verify."""
        from runsight_api.transport.schemas.runs import RunNodeResponse

        resp = RunNodeResponse(
            **{
                **_NODE_RESPONSE_BASE,
                "child_run_id": "run_child_1",
                "exit_handle": "success",
            }
        )
        data = resp.model_dump()
        assert data["child_run_id"] == "run_child_1"
        assert data["exit_handle"] == "success"


# ===========================================================================
# 3. StreamingObserver: child completion must NOT be terminal
# ===========================================================================


class TestStreamingObserverChildNonTerminal:
    """When StreamingObserver receives on_workflow_complete for a child run
    (parent_run_id is set), it must NOT set is_done or emit a terminal event
    that would close the parent SSE stream."""

    @pytest.mark.asyncio
    async def test_streaming_observer_child_complete_is_non_terminal(self):
        """Child run completion must not mark the observer as done."""
        from runsight_api.logic.observers.streaming_observer import StreamingObserver

        # Observer for a child run (has parent_run_id context)
        obs = StreamingObserver(run_id="run_child_1", parent_run_id="run_parent_1")
        obs.on_workflow_complete("child_wf", _mock_state(), 2.0)

        # The observer must NOT be done — only root completion is terminal
        assert obs.is_done is False

        # The emitted event must NOT be a terminal event type
        event = obs.queue.get_nowait()
        assert event["event"] != "run_completed", (
            "Child completion must not emit run_completed (terminal). "
            "Use a non-terminal event like 'child_run_completed'."
        )

    @pytest.mark.asyncio
    async def test_streaming_observer_child_complete_emits_child_linkage(self):
        """Child completion event must include child_run_id in the data payload."""
        from runsight_api.logic.observers.streaming_observer import StreamingObserver

        obs = StreamingObserver(run_id="run_child_1", parent_run_id="run_parent_1")
        obs.on_workflow_complete("child_wf", _mock_state(cost=0.01, tokens=50), 2.0)

        event = obs.queue.get_nowait()
        assert "child_run_id" in event["data"] or "parent_run_id" in event["data"], (
            "Child completion event must include linkage fields (child_run_id or parent_run_id)"
        )


# ===========================================================================
# 4. StreamingObserver: root completion IS terminal
# ===========================================================================


class TestStreamingObserverRootTerminal:
    """Root run completion (no parent_run_id) MUST emit a terminal event
    and set is_done = True, preserving existing behavior."""

    @pytest.mark.asyncio
    async def test_streaming_observer_root_complete_is_terminal(self):
        """Root run completion (no parent) sets is_done and emits run_completed."""
        from runsight_api.domain.events import SSE_RUN_COMPLETED
        from runsight_api.logic.observers.streaming_observer import StreamingObserver

        obs = StreamingObserver(run_id="run_root_1")
        obs.on_workflow_complete("root_wf", _mock_state(), 5.0)

        assert obs.is_done is True
        event = obs.queue.get_nowait()
        assert event["event"] == SSE_RUN_COMPLETED

    @pytest.mark.asyncio
    async def test_streaming_observer_root_with_explicit_no_parent_is_terminal(self):
        """Root run with parent_run_id=None is explicitly terminal."""
        from runsight_api.domain.events import SSE_RUN_COMPLETED
        from runsight_api.logic.observers.streaming_observer import StreamingObserver

        obs = StreamingObserver(run_id="run_root_2", parent_run_id=None)
        obs.on_workflow_complete("root_wf", _mock_state(), 5.0)

        assert obs.is_done is True
        event = obs.queue.get_nowait()
        assert event["event"] == SSE_RUN_COMPLETED


# ===========================================================================
# 5. StreamingObserver: child run started event includes child_run_id
# ===========================================================================


class TestStreamingObserverChildRunStartedEvent:
    """When a workflow-call block starts (spawning a child run),
    the observer should emit a node event that includes child_run_id."""

    @pytest.mark.asyncio
    async def test_streaming_observer_emits_child_run_started_event(self):
        """on_block_start for a workflow block should include child_run_id in the event data."""
        from runsight_api.logic.observers.streaming_observer import StreamingObserver

        obs = StreamingObserver(run_id="run_parent_1")
        # The observer must accept child_run_id when a workflow-call block starts
        obs.on_block_start("wf", "step_wf_call", "workflow", child_run_id="run_child_1")

        event = obs.queue.get_nowait()
        assert event["data"]["child_run_id"] == "run_child_1", (
            "node_started event for a workflow-call block must include child_run_id"
        )


# ===========================================================================
# 6. SSE endpoint: no legacy path treats child completion as terminal
# ===========================================================================


class TestNoLegacyTerminalChildPath:
    """The SSE endpoint must use SSE_TERMINAL_EVENTS constant (not hardcoded
    strings) and the terminal check must be nesting-aware."""

    def test_sse_endpoint_uses_terminal_events_constant(self):
        """sse_stream.py must import and use SSE_TERMINAL_EVENTS, not hardcoded strings."""
        import ast
        import inspect

        from runsight_api.transport.routers import sse_stream

        source = inspect.getsource(sse_stream)
        tree = ast.parse(source)

        # Check that the hardcoded terminal check strings are not present
        # The current code has: if event_type in ("run_completed", "run_failed"):
        # This must be replaced with the constant
        for node in ast.walk(tree):
            if isinstance(node, ast.Compare):
                for comparator in node.comparators:
                    if isinstance(comparator, ast.Tuple):
                        values = [
                            elt.value for elt in comparator.elts if isinstance(elt, ast.Constant)
                        ]
                        if "run_completed" in values and "run_failed" in values:
                            pytest.fail(
                                "sse_stream.py still has hardcoded terminal event strings "
                                '("run_completed", "run_failed"). Replace with '
                                "SSE_TERMINAL_EVENTS from domain.events."
                            )
