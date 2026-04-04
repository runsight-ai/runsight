"""RED tests for RUN-332: SSE event type constants.

Problem: SSE event types are magic strings scattered across streaming_observer.py,
execution_service.py, and frontend code. This creates a maintenance hazard where
a typo or rename in one place silently breaks the event contract.

Fix: Define SSE event type names as module-level string constants in
domain/events.py and use them in both streaming_observer and execution_service.

AC:
1. SSE event type names defined as constants (not an enum -- just string constants)
2. streaming_observer uses constants instead of string literals
3. execution_service uses constants for terminal event checks
4. All existing tests pass
"""

import ast
import inspect
import textwrap
from unittest.mock import Mock

import pytest

# ---------------------------------------------------------------------------
# AC-1: SSE event type names defined as constants in domain/events.py
# ---------------------------------------------------------------------------


class TestSSEEventConstantsExist:
    """Constants must be importable from runsight_api.domain.events."""

    def test_sse_run_started_constant_exists(self):
        from runsight_api.domain.events import SSE_RUN_STARTED

        assert SSE_RUN_STARTED == "run_started"

    def test_sse_run_completed_constant_exists(self):
        from runsight_api.domain.events import SSE_RUN_COMPLETED

        assert SSE_RUN_COMPLETED == "run_completed"

    def test_sse_run_failed_constant_exists(self):
        from runsight_api.domain.events import SSE_RUN_FAILED

        assert SSE_RUN_FAILED == "run_failed"

    def test_sse_node_started_constant_exists(self):
        from runsight_api.domain.events import SSE_NODE_STARTED

        assert SSE_NODE_STARTED == "node_started"

    def test_sse_node_completed_constant_exists(self):
        from runsight_api.domain.events import SSE_NODE_COMPLETED

        assert SSE_NODE_COMPLETED == "node_completed"

    def test_sse_node_failed_constant_exists(self):
        from runsight_api.domain.events import SSE_NODE_FAILED

        assert SSE_NODE_FAILED == "node_failed"

    def test_terminal_events_tuple_exists(self):
        """A convenience tuple of terminal event types for stream-end checks."""
        from runsight_api.domain.events import SSE_TERMINAL_EVENTS

        assert isinstance(SSE_TERMINAL_EVENTS, (tuple, frozenset))
        assert "run_completed" in SSE_TERMINAL_EVENTS
        assert "run_failed" in SSE_TERMINAL_EVENTS

    def test_constants_are_plain_strings(self):
        """Constants must be plain str -- not enum members or other wrappers."""
        from runsight_api.domain import events

        for name in (
            "SSE_RUN_STARTED",
            "SSE_RUN_COMPLETED",
            "SSE_RUN_FAILED",
            "SSE_NODE_STARTED",
            "SSE_NODE_COMPLETED",
            "SSE_NODE_FAILED",
        ):
            value = getattr(events, name)
            assert type(value) is str, f"{name} should be str, got {type(value).__name__}"


# ---------------------------------------------------------------------------
# AC-2: streaming_observer uses constants instead of string literals
# ---------------------------------------------------------------------------


class TestStreamingObserverUsesConstants:
    """streaming_observer.py must import and use the SSE constants,
    not inline string literals for event type names."""

    def test_streaming_observer_imports_from_events(self):
        """The module must import at least one SSE constant from domain.events."""
        import runsight_api.logic.observers.streaming_observer as mod

        source = inspect.getsource(mod)
        tree = ast.parse(source)

        imported_names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and "events" in node.module:
                    for alias in node.names:
                        imported_names.add(alias.name)

        sse_constants = {
            "SSE_RUN_STARTED",
            "SSE_RUN_COMPLETED",
            "SSE_RUN_FAILED",
            "SSE_NODE_STARTED",
            "SSE_NODE_COMPLETED",
            "SSE_NODE_FAILED",
        }

        found = imported_names & sse_constants
        assert len(found) >= 1, (
            f"streaming_observer.py does not import any SSE constants from "
            f"domain.events. Imported names: {imported_names}"
        )

    def test_no_hardcoded_event_strings_in_observer(self):
        """streaming_observer.py must not contain hardcoded SSE event type strings
        as values in the 'event' key of queue payloads."""
        import runsight_api.logic.observers.streaming_observer as mod

        source = inspect.getsource(mod)
        tree = ast.parse(source)

        magic_strings = {
            "run_started",
            "run_completed",
            "run_failed",
            "node_started",
            "node_completed",
            "node_failed",
        }

        # Walk AST looking for dict literals with "event": <string_literal>
        violations: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Dict):
                for key, value in zip(node.keys, node.values):
                    if (
                        isinstance(key, ast.Constant)
                        and key.value == "event"
                        and isinstance(value, ast.Constant)
                        and value.value in magic_strings
                    ):
                        violations.append(value.value)

        assert not violations, (
            f"streaming_observer.py still has hardcoded event strings: {violations}. "
            f"Replace with constants from domain.events."
        )


# ---------------------------------------------------------------------------
# AC-3: execution_service uses constants for terminal event checks
# ---------------------------------------------------------------------------


class TestExecutionServiceUsesConstants:
    """execution_service.py must use SSE_TERMINAL_EVENTS (or individual constants)
    for the terminal-event check in subscribe_stream, not inline string literals."""

    def test_execution_service_imports_from_events(self):
        """The module must import terminal-event constants from domain.events."""
        import runsight_api.logic.services.execution_service as mod

        source = inspect.getsource(mod)
        tree = ast.parse(source)

        imported_names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and "events" in node.module:
                    for alias in node.names:
                        imported_names.add(alias.name)

        acceptable = {
            "SSE_TERMINAL_EVENTS",
            "SSE_RUN_COMPLETED",
            "SSE_RUN_FAILED",
        }

        found = imported_names & acceptable
        assert len(found) >= 1, (
            f"execution_service.py does not import any SSE terminal constants "
            f"from domain.events. Imported names: {imported_names}"
        )

    def test_no_hardcoded_terminal_strings_in_subscribe_stream(self):
        """subscribe_stream must not contain inline
        'run_completed' / 'run_failed' strings."""
        import runsight_api.logic.services.execution_service as mod

        source = inspect.getsource(mod)
        tree = ast.parse(source)

        # Find the subscribe_stream method
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "subscribe_stream":
                method_source = ast.get_source_segment(source, node)
                method_tree = ast.parse(textwrap.dedent(method_source))

                magic_strings = {"run_completed", "run_failed"}
                violations: list[str] = []

                for inner_node in ast.walk(method_tree):
                    if isinstance(inner_node, ast.Constant) and inner_node.value in magic_strings:
                        violations.append(inner_node.value)

                assert not violations, (
                    f"subscribe_stream still has hardcoded terminal event strings: "
                    f"{violations}. Replace with SSE_TERMINAL_EVENTS or "
                    f"individual constants."
                )
                return

        pytest.fail("subscribe_stream method not found in execution_service.py")


# ---------------------------------------------------------------------------
# AC-4: Behavioral contract -- observer events still match constant values
# ---------------------------------------------------------------------------


class TestBehavioralContract:
    """After refactoring, the observer must still emit events matching the
    constant values. This is a smoke test ensuring the wiring is correct."""

    @pytest.mark.asyncio
    async def test_observer_emits_run_started_matching_constant(self):
        from runsight_api.domain.events import SSE_RUN_STARTED
        from runsight_api.logic.observers.streaming_observer import StreamingObserver

        obs = StreamingObserver(run_id="r1")
        obs.on_workflow_start("wf", Mock())
        event = obs.queue.get_nowait()
        assert event["event"] == SSE_RUN_STARTED

    @pytest.mark.asyncio
    async def test_observer_emits_node_started_matching_constant(self):
        from runsight_api.domain.events import SSE_NODE_STARTED
        from runsight_api.logic.observers.streaming_observer import StreamingObserver

        obs = StreamingObserver(run_id="r1")
        obs.on_block_start("wf", "b1", "llm")
        event = obs.queue.get_nowait()
        assert event["event"] == SSE_NODE_STARTED

    @pytest.mark.asyncio
    async def test_observer_emits_node_completed_matching_constant(self):
        from runsight_api.domain.events import SSE_NODE_COMPLETED
        from runsight_api.logic.observers.streaming_observer import StreamingObserver

        state = Mock()
        state.total_cost_usd = 0.0
        state.total_tokens = 0

        obs = StreamingObserver(run_id="r1")
        obs.on_block_complete("wf", "b1", "llm", 1.0, state)
        event = obs.queue.get_nowait()
        assert event["event"] == SSE_NODE_COMPLETED

    @pytest.mark.asyncio
    async def test_observer_emits_node_failed_matching_constant(self):
        from runsight_api.domain.events import SSE_NODE_FAILED
        from runsight_api.logic.observers.streaming_observer import StreamingObserver

        obs = StreamingObserver(run_id="r1")
        obs.on_block_error("wf", "b1", "llm", 0.5, ValueError("x"))
        event = obs.queue.get_nowait()
        assert event["event"] == SSE_NODE_FAILED

    @pytest.mark.asyncio
    async def test_observer_emits_run_completed_matching_constant(self):
        from runsight_api.domain.events import SSE_RUN_COMPLETED
        from runsight_api.logic.observers.streaming_observer import StreamingObserver

        state = Mock()
        state.total_cost_usd = 0.0
        state.total_tokens = 0

        obs = StreamingObserver(run_id="r1")
        obs.on_workflow_complete("wf", state, 1.0)
        event = obs.queue.get_nowait()
        assert event["event"] == SSE_RUN_COMPLETED

    @pytest.mark.asyncio
    async def test_observer_emits_run_failed_matching_constant(self):
        from runsight_api.domain.events import SSE_RUN_FAILED
        from runsight_api.logic.observers.streaming_observer import StreamingObserver

        obs = StreamingObserver(run_id="r1")
        obs.on_workflow_error("wf", RuntimeError("boom"), 1.0)
        event = obs.queue.get_nowait()
        assert event["event"] == SSE_RUN_FAILED
