"""
RUN-856: Failing tests for Workflow.run and execute decomposition.

AC:
1. Workflow.run decomposed into sub-methods (main loop, error routing, observer lifecycle)
2. execute decomposed (single-shot path, agentic loop, tool dispatch as separate methods)
3. Nesting ≤3 levels in all resulting functions
4. All existing tests still pass

These tests are written BEFORE the refactor — they will fail (AttributeError or
assertion failures) against the current implementations and pass only once the
Green team completes the decomposition.
"""

from __future__ import annotations

import inspect

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _count_non_blank_non_comment_lines(source: str) -> int:
    """Count lines that are neither blank nor pure comments."""
    count = 0
    for line in source.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            count += 1
    return count


# ---------------------------------------------------------------------------
# Test Group 1: Sub-method existence on Workflow
# Expected failure: AttributeError — methods do not yet exist.
# ---------------------------------------------------------------------------


class TestWorkflowSubMethodExistence:
    """Workflow must expose private sub-methods after decomposition."""

    def test_workflow_has_run_main_loop_method(self):
        """Workflow._run_main_loop must exist as a callable method."""
        from runsight_core.workflow import Workflow

        assert hasattr(Workflow, "_run_main_loop"), (
            "Workflow must have a '_run_main_loop' method after decomposition"
        )
        assert callable(getattr(Workflow, "_run_main_loop"))

    def test_workflow_has_handle_block_error_method(self):
        """Workflow._handle_block_error must exist as a callable method."""
        from runsight_core.workflow import Workflow

        assert hasattr(Workflow, "_handle_block_error"), (
            "Workflow must have a '_handle_block_error' method after decomposition"
        )
        assert callable(getattr(Workflow, "_handle_block_error"))

    def test_workflow_has_notify_observers_method(self):
        """Workflow._notify_observers must exist as a callable method."""
        from runsight_core.workflow import Workflow

        assert hasattr(Workflow, "_notify_observers"), (
            "Workflow must have a '_notify_observers' method after decomposition"
        )
        assert callable(getattr(Workflow, "_notify_observers"))


# ---------------------------------------------------------------------------
# Test Group 2: Sub-method existence on RunsightTeamRunner
# Expected failure: AttributeError — methods do not yet exist.
# ---------------------------------------------------------------------------


class TestRunnerSubMethodExistence:
    """RunsightTeamRunner must expose private sub-methods after decomposition."""

    def test_runner_has_execute_single_shot_method(self):
        """RunsightTeamRunner._execute_single_shot must exist."""
        from runsight_core.runner import RunsightTeamRunner

        assert hasattr(RunsightTeamRunner, "_execute_single_shot"), (
            "RunsightTeamRunner must have '_execute_single_shot' after decomposition"
        )
        assert callable(getattr(RunsightTeamRunner, "_execute_single_shot"))

    def test_runner_has_execute_agentic_loop_method(self):
        """RunsightTeamRunner._execute_agentic_loop must exist."""
        from runsight_core.runner import RunsightTeamRunner

        assert hasattr(RunsightTeamRunner, "_execute_agentic_loop"), (
            "RunsightTeamRunner must have '_execute_agentic_loop' after decomposition"
        )
        assert callable(getattr(RunsightTeamRunner, "_execute_agentic_loop"))

    def test_runner_has_dispatch_tool_call_method(self):
        """RunsightTeamRunner._dispatch_tool_call must exist."""
        from runsight_core.runner import RunsightTeamRunner

        assert hasattr(RunsightTeamRunner, "_dispatch_tool_call"), (
            "RunsightTeamRunner must have '_dispatch_tool_call' after decomposition"
        )
        assert callable(getattr(RunsightTeamRunner, "_dispatch_tool_call"))


# ---------------------------------------------------------------------------
# Test Group 3: Line count guards
# Expected failure: current functions are 175 and 158 lines respectively.
# ---------------------------------------------------------------------------


class TestLineCounts:
    """Orchestrator functions must shrink to ≤60 non-blank, non-comment lines."""

    def test_workflow_run_under_60_lines(self):
        """Workflow.run must be ≤60 non-blank/non-comment lines after extraction."""
        from runsight_core.workflow import Workflow

        source = inspect.getsource(Workflow.run)
        line_count = _count_non_blank_non_comment_lines(source)
        assert line_count <= 60, (
            f"Workflow.run is {line_count} non-blank/non-comment lines; "
            f"expected ≤60 after sub-method extraction"
        )

    def test_execute_under_60_lines(self):
        """execute must be ≤60 non-blank/non-comment lines after extraction."""
        from runsight_core.runner import RunsightTeamRunner

        source = inspect.getsource(RunsightTeamRunner.execute)
        line_count = _count_non_blank_non_comment_lines(source)
        assert line_count <= 60, (
            f"execute is {line_count} non-blank/non-comment lines; "
            f"expected ≤60 after sub-method extraction"
        )


# ---------------------------------------------------------------------------
# Test Group 4: Async behavioural guards
# These check that the public API remains async after decomposition.
# Expected: PASS currently (regression guards — must remain green after refactor).
# ---------------------------------------------------------------------------


class TestAsyncPreservation:
    """Public methods must remain coroutines after decomposition."""

    def test_workflow_run_still_async(self):
        """Workflow.run must still be a coroutine function after decomposition."""
        from runsight_core.workflow import Workflow

        assert inspect.iscoroutinefunction(Workflow.run), (
            "Workflow.run must remain an async method after decomposition"
        )

    def test_execute_still_async(self):
        """RunsightTeamRunner.execute must still be a coroutine function."""
        from runsight_core.runner import RunsightTeamRunner

        assert inspect.iscoroutinefunction(RunsightTeamRunner.execute), (
            "execute must remain an async method after decomposition"
        )

    def test_workflow_run_main_loop_is_async(self):
        """Workflow._run_main_loop must be an async method (it contains awaits)."""
        from runsight_core.workflow import Workflow

        assert hasattr(Workflow, "_run_main_loop"), "need _run_main_loop to exist first"
        assert inspect.iscoroutinefunction(Workflow._run_main_loop), (
            "Workflow._run_main_loop must be async"
        )

    def test_runner_execute_agentic_loop_is_async(self):
        """RunsightTeamRunner._execute_agentic_loop must be async (contains awaits)."""
        from runsight_core.runner import RunsightTeamRunner

        assert hasattr(RunsightTeamRunner, "_execute_agentic_loop"), (
            "need _execute_agentic_loop to exist first"
        )
        assert inspect.iscoroutinefunction(RunsightTeamRunner._execute_agentic_loop), (
            "RunsightTeamRunner._execute_agentic_loop must be async"
        )

    def test_runner_execute_single_shot_is_async(self):
        """RunsightTeamRunner._execute_single_shot must be async (contains awaits)."""
        from runsight_core.runner import RunsightTeamRunner

        assert hasattr(RunsightTeamRunner, "_execute_single_shot"), (
            "need _execute_single_shot to exist first"
        )
        assert inspect.iscoroutinefunction(RunsightTeamRunner._execute_single_shot), (
            "RunsightTeamRunner._execute_single_shot must be async"
        )

    def test_runner_dispatch_tool_call_is_async(self):
        """RunsightTeamRunner._dispatch_tool_call must be async (calls tool.execute)."""
        from runsight_core.runner import RunsightTeamRunner

        assert hasattr(RunsightTeamRunner, "_dispatch_tool_call"), (
            "need _dispatch_tool_call to exist first"
        )
        assert inspect.iscoroutinefunction(RunsightTeamRunner._dispatch_tool_call), (
            "RunsightTeamRunner._dispatch_tool_call must be async"
        )
