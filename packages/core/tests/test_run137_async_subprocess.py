"""
Tests for RUN-137: CodeBlock async subprocess migration.

CodeBlock.execute() must use asyncio.create_subprocess_exec() instead of
synchronous subprocess.run(), so the event loop is never blocked.

These tests are RED — they will fail against the current implementation
that uses subprocess.run().
"""

import asyncio
import json
import textwrap
import time
from unittest.mock import AsyncMock, patch

import pytest
from conftest import execute_block_for_test
from runsight_core import CodeBlock
from runsight_core.state import WorkflowState

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(**overrides) -> WorkflowState:
    defaults = {
        "results": {},
        "metadata": {},
        "shared_memory": {},
        "execution_log": [],
    }
    defaults.update(overrides)
    return WorkflowState(**defaults)


SIMPLE_CODE = textwrap.dedent("""\
def main(data):
    return {"value": 42}
""")

SLOW_CODE = textwrap.dedent("""\
import time
def main(data):
    time.sleep(0.5)
    return {"done": True}
""")


# ---------------------------------------------------------------------------
# 1. Uses asyncio subprocess, not subprocess.run()
# ---------------------------------------------------------------------------


class TestAsyncSubprocessUsed:
    """CodeBlock.execute() must call asyncio.create_subprocess_exec, not subprocess.run."""

    @pytest.mark.asyncio
    async def test_no_subprocess_run_call(self):
        """subprocess.run must NOT be called during execute()."""
        block = CodeBlock("cb1", SIMPLE_CODE)
        state = _make_state()

        with patch(
            "subprocess.run", side_effect=AssertionError("subprocess.run was called")
        ) as mock_run:
            await execute_block_for_test(block, state)

        # If we get here without AssertionError, subprocess.run was not called.
        mock_run.assert_not_called()

    @pytest.mark.asyncio
    async def test_asyncio_create_subprocess_exec_called(self):
        """asyncio.create_subprocess_exec must be called during execute()."""
        block = CodeBlock("cb1", SIMPLE_CODE)
        state = _make_state()

        with patch(
            "runsight_core.blocks.code.asyncio.create_subprocess_exec",
            new_callable=AsyncMock,
        ) as mock_create:
            # Set up mock process
            mock_proc = AsyncMock()
            mock_proc.communicate = AsyncMock(
                return_value=(json.dumps({"value": 42}).encode(), b"")
            )
            mock_proc.returncode = 0
            mock_create.return_value = mock_proc

            await execute_block_for_test(block, state)

        mock_create.assert_called_once()


# ---------------------------------------------------------------------------
# 2. Event loop is not blocked
# ---------------------------------------------------------------------------


class TestEventLoopNotBlocked:
    """Execution must not block the event loop — other coroutines must run concurrently."""

    @pytest.mark.asyncio
    async def test_concurrent_coroutines_run_during_execute(self):
        """
        While CodeBlock.execute() runs a slow subprocess, a concurrent
        coroutine must be able to make progress. With synchronous subprocess.run(),
        the event loop is blocked and the sentinel never runs.
        """
        block = CodeBlock("cb_slow", SLOW_CODE, timeout_seconds=5)
        state = _make_state()

        sentinel_ran = False

        async def sentinel():
            nonlocal sentinel_ran
            await asyncio.sleep(0.05)
            sentinel_ran = True

        # Run both concurrently
        execute_task = asyncio.create_task(execute_block_for_test(block, state))
        sentinel_task = asyncio.create_task(sentinel())

        await asyncio.gather(execute_task, sentinel_task)

        assert sentinel_ran, (
            "Sentinel coroutine did not run — event loop was blocked "
            "(subprocess.run is synchronous)"
        )

    @pytest.mark.asyncio
    async def test_execute_yields_to_event_loop(self):
        """
        Measure that another coroutine can complete *before* execute() finishes.
        If subprocess.run blocks, the fast coroutine only runs after the slow one.
        """
        block = CodeBlock("cb_slow2", SLOW_CODE, timeout_seconds=5)
        state = _make_state()

        timestamps = []

        async def record_timestamp(label):
            await asyncio.sleep(0.01)
            timestamps.append((label, time.monotonic()))

        start = time.monotonic()
        task_exec = asyncio.create_task(execute_block_for_test(block, state))
        task_fast = asyncio.create_task(record_timestamp("fast"))

        await asyncio.gather(task_exec, task_fast)

        # The fast task should complete well before the execute task.
        # With subprocess.run, both complete at essentially the same time (after blocking).
        assert len(timestamps) == 1
        fast_time = timestamps[0][1] - start
        # fast coroutine should complete in <0.1s, while execute takes ~0.5s
        assert fast_time < 0.2, (
            f"Fast coroutine took {fast_time:.3f}s — event loop was likely blocked"
        )


# ---------------------------------------------------------------------------
# 3. Timeout uses asyncio.wait_for (not subprocess timeout)
# ---------------------------------------------------------------------------


class TestAsyncTimeout:
    """Timeout must be enforced via asyncio.wait_for, not subprocess.TimeoutExpired."""

    @pytest.mark.asyncio
    async def test_timeout_still_raises_timeout_error(self):
        """Infinite-loop code must still raise TimeoutError."""
        code = textwrap.dedent("""\
def main(data):
    while True:
        pass
""")
        block = CodeBlock("cb_timeout", code, timeout_seconds=1)
        state = _make_state()

        with pytest.raises(TimeoutError, match="timed out"):
            await execute_block_for_test(block, state)

    @pytest.mark.asyncio
    async def test_timeout_does_not_use_subprocess_timeout_expired(self):
        """
        The implementation must NOT raise subprocess.TimeoutExpired internally.
        We patch subprocess.run so that if it's called, the old path is exercised
        and the test fails.
        """
        code = textwrap.dedent("""\
def main(data):
    while True:
        pass
""")
        block = CodeBlock("cb_timeout2", code, timeout_seconds=1)
        state = _make_state()

        # If the code still uses subprocess.run, it would catch subprocess.TimeoutExpired.
        # We want to ensure asyncio.wait_for is used instead.

        with patch(
            "subprocess.run", side_effect=AssertionError("subprocess.run should not be called")
        ):
            with pytest.raises(TimeoutError, match="timed out"):
                await execute_block_for_test(block, state)

    @pytest.mark.asyncio
    async def test_timeout_does_not_block_event_loop(self):
        """Even when timing out, the event loop must remain responsive."""
        code = textwrap.dedent("""\
def main(data):
    while True:
        pass
""")
        block = CodeBlock("cb_timeout3", code, timeout_seconds=1)
        state = _make_state()

        sentinel_ran = False

        async def sentinel():
            nonlocal sentinel_ran
            await asyncio.sleep(0.05)
            sentinel_ran = True

        async def run_execute():
            with pytest.raises(TimeoutError):
                await execute_block_for_test(block, state)

        await asyncio.gather(run_execute(), sentinel())

        assert sentinel_ran, "Event loop was blocked during timeout"


# ---------------------------------------------------------------------------
# 4. macOS env var handling — env={} must include minimal required vars
# ---------------------------------------------------------------------------


class TestMacOSEnvVars:
    """
    On macOS, env={} strips DYLD_LIBRARY_PATH and similar vars needed by the
    system Python. The implementation must pass at least a minimal set of env
    vars so the subprocess can actually start.
    """

    @pytest.mark.asyncio
    async def test_subprocess_env_not_empty(self):
        """
        The subprocess must be launched with env that is NOT an empty dict.
        An empty env can cause Python to fail on macOS.

        We intercept asyncio.create_subprocess_exec to inspect the env argument.
        After the fix, env should contain minimal required vars.
        """
        block = CodeBlock("cb_env", SIMPLE_CODE)
        state = _make_state()

        captured_env = None

        original_create = asyncio.create_subprocess_exec

        async def spy_create(*args, **kwargs):
            nonlocal captured_env
            captured_env = kwargs.get("env")
            return await original_create(*args, **kwargs)

        with patch(
            "runsight_core.blocks.code.asyncio.create_subprocess_exec",
            side_effect=spy_create,
        ):
            await execute_block_for_test(block, state)

        assert captured_env is not None, "env was not passed to subprocess"
        assert len(captured_env) > 0, (
            "env is empty dict — will fail on macOS (missing DYLD_LIBRARY_PATH etc.)"
        )

    @pytest.mark.asyncio
    async def test_subprocess_env_contains_path(self):
        """The subprocess env must include PATH so that the Python binary can be found."""
        block = CodeBlock("cb_env2", SIMPLE_CODE)
        state = _make_state()

        captured_env = None
        original_create = asyncio.create_subprocess_exec

        async def spy_create(*args, **kwargs):
            nonlocal captured_env
            captured_env = kwargs.get("env")
            return await original_create(*args, **kwargs)

        with patch(
            "runsight_core.blocks.code.asyncio.create_subprocess_exec",
            side_effect=spy_create,
        ):
            await execute_block_for_test(block, state)

        assert captured_env is not None, "env kwarg not passed"
        assert "PATH" in captured_env, "PATH missing from subprocess env"

    @pytest.mark.asyncio
    async def test_simple_code_runs_successfully_on_platform(self):
        """
        Integration sanity: a simple CodeBlock actually executes without
        crashing due to missing env vars. This catches the env={} bug on macOS
        where the subprocess can't even start.
        """
        block = CodeBlock("cb_platform", SIMPLE_CODE)
        state = _make_state()
        result = await execute_block_for_test(block, state)

        assert "cb_platform" in result.results
        # Should NOT be an error — should be successful
        assert "Error" not in result.results["cb_platform"].output, (
            f"CodeBlock failed (likely env issue): {result.results['cb_platform']}"
        )
        parsed = json.loads(result.results["cb_platform"].output)
        assert parsed["value"] == 42
