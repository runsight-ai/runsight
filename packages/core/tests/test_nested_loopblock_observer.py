"""
RUN-683: E2E tests for nested LoopBlock with observer parity.

Scenarios:
1. Observer event counts for nested loops — verifies the observer sees the correct
   number of block_start/block_complete events when outer and inner LoopBlocks
   are composed, run through Workflow.run().
2. Inner loop break_on_exit — verifies that break_on_exit terminates the inner
   loop early on each outer-loop cycle, producing the expected total worker calls.
3. Retry on inner block in nested loop — verifies that retry_config on a flaky
   inner block inside a nested loop is handled by execute_block(), and the
   workflow completes successfully.
"""

from __future__ import annotations

from typing import Any, Optional
from unittest.mock import AsyncMock, patch

import pytest
from runsight_core.block_io import BlockContext, BlockOutput
from runsight_core.blocks.base import BaseBlock
from runsight_core.blocks.loop import LoopBlock
from runsight_core.state import WorkflowState
from runsight_core.workflow import Workflow
from runsight_core.yaml.schema import RetryConfig

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


class ResultBlock(BaseBlock):
    """Simple block that counts calls and returns a configurable output."""

    def __init__(self, block_id: str, output: str = "done"):
        super().__init__(block_id)
        self.output = output
        self.calls = 0

    async def execute(self, ctx: BlockContext) -> BlockOutput:
        self.calls += 1
        return BlockOutput(output=self.output)


class ExitHandleBlock(BaseBlock):
    """Block that returns a specific exit_handle on every call."""

    def __init__(self, block_id: str, exit_handle: str = "done", output: str = "ok"):
        super().__init__(block_id)
        self._exit_handle = exit_handle
        self._output = output
        self.calls = 0

    async def execute(self, ctx: BlockContext) -> BlockOutput:
        self.calls += 1
        return BlockOutput(output=self._output, exit_handle=self._exit_handle)


class FlakyBlock(BaseBlock):
    """Block that fails on odd-numbered calls and succeeds on even-numbered calls."""

    def __init__(self, block_id: str = "worker"):
        super().__init__(block_id)
        self.calls = 0

    async def execute(self, ctx: BlockContext) -> BlockOutput:
        self.calls += 1
        if self.calls % 2 == 1:
            raise RuntimeError("flaky!")
        return BlockOutput(output="recovered")


class RecordingObserver:
    """Observer that records all events for assertion."""

    def __init__(self):
        self.events: list[tuple] = []

    def on_workflow_start(self, workflow_name: str, state: WorkflowState) -> None:
        self.events.append(("workflow_start", workflow_name))

    def on_block_start(
        self,
        workflow_name: str,
        block_id: str,
        block_type: str,
        *,
        soul: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        self.events.append(("block_start", workflow_name, block_id, block_type))

    def on_block_complete(
        self,
        workflow_name: str,
        block_id: str,
        block_type: str,
        duration_s: float,
        state: WorkflowState,
        *,
        soul: Optional[Any] = None,
    ) -> None:
        self.events.append(("block_complete", workflow_name, block_id, block_type))

    def on_block_error(
        self,
        workflow_name: str,
        block_id: str,
        block_type: str,
        duration_s: float,
        error: Exception,
    ) -> None:
        self.events.append(("block_error", workflow_name, block_id, block_type, str(error)))

    def on_workflow_complete(
        self, workflow_name: str, state: WorkflowState, duration_s: float
    ) -> None:
        self.events.append(("workflow_complete", workflow_name))

    def on_workflow_error(self, workflow_name: str, error: Exception, duration_s: float) -> None:
        self.events.append(("workflow_error", workflow_name, str(error)))


def _count_events(observer: RecordingObserver, event_type: str, block_id: str) -> int:
    """Count observer events matching event_type and block_id."""
    return sum(1 for e in observer.events if e[0] == event_type and len(e) > 2 and e[2] == block_id)


# ===========================================================================
# Scenario 1: Observer event counts for nested loops
# ===========================================================================


class TestNestedLoopObserverEventCounts:
    """Outer LoopBlock (max_rounds=2) -> Inner LoopBlock (max_rounds=2) -> worker.

    Expected observer events through Workflow.run():
      - workflow_start x1
      - outer block_start x1, block_complete x1
      - inner_loop block_start x2 (once per outer round), block_complete x2
      - worker block_start x4 (2 inner rounds x 2 outer rounds), block_complete x4
      - workflow_complete x1
    Worker.execute() called 4 times total.
    """

    @pytest.mark.asyncio
    async def test_observer_event_counts(self) -> None:
        worker = ResultBlock("worker", output="result")
        inner_loop = LoopBlock("inner_loop", inner_block_refs=["worker"], max_rounds=2)
        outer_loop = LoopBlock("outer", inner_block_refs=["inner_loop"], max_rounds=2)

        wf = Workflow(name="nested_loop_wf")
        wf.add_block(worker)
        wf.add_block(inner_loop)
        wf.add_block(outer_loop)
        wf.add_transition("outer", None)
        wf.set_entry("outer")

        observer = RecordingObserver()
        state = WorkflowState()
        await wf.run(state, observer=observer)

        # Worker called 4 times total (2 inner x 2 outer)
        assert worker.calls == 4, f"Expected 4 worker calls, got {worker.calls}"

        # Verify observer event counts
        assert _count_events(observer, "block_start", "outer") == 1
        assert _count_events(observer, "block_complete", "outer") == 1
        assert _count_events(observer, "block_start", "inner_loop") == 2
        assert _count_events(observer, "block_complete", "inner_loop") == 2
        assert _count_events(observer, "block_start", "worker") == 4
        assert _count_events(observer, "block_complete", "worker") == 4

    @pytest.mark.asyncio
    async def test_workflow_lifecycle_events(self) -> None:
        """Verify workflow_start and workflow_complete fire exactly once."""
        worker = ResultBlock("worker", output="result")
        inner_loop = LoopBlock("inner_loop", inner_block_refs=["worker"], max_rounds=2)
        outer_loop = LoopBlock("outer", inner_block_refs=["inner_loop"], max_rounds=2)

        wf = Workflow(name="nested_loop_wf")
        wf.add_block(worker)
        wf.add_block(inner_loop)
        wf.add_block(outer_loop)
        wf.add_transition("outer", None)
        wf.set_entry("outer")

        observer = RecordingObserver()
        state = WorkflowState()
        await wf.run(state, observer=observer)

        workflow_starts = [e for e in observer.events if e[0] == "workflow_start"]
        workflow_completes = [e for e in observer.events if e[0] == "workflow_complete"]
        assert len(workflow_starts) == 1
        assert len(workflow_completes) == 1

    @pytest.mark.asyncio
    async def test_every_block_start_has_matching_complete(self) -> None:
        """Every block_start event must have a corresponding block_complete event."""
        worker = ResultBlock("worker", output="result")
        inner_loop = LoopBlock("inner_loop", inner_block_refs=["worker"], max_rounds=2)
        outer_loop = LoopBlock("outer", inner_block_refs=["inner_loop"], max_rounds=2)

        wf = Workflow(name="nested_loop_wf")
        wf.add_block(worker)
        wf.add_block(inner_loop)
        wf.add_block(outer_loop)
        wf.add_transition("outer", None)
        wf.set_entry("outer")

        observer = RecordingObserver()
        state = WorkflowState()
        await wf.run(state, observer=observer)

        starts = [e for e in observer.events if e[0] == "block_start"]
        completes = [e for e in observer.events if e[0] == "block_complete"]
        assert len(starts) == len(completes), (
            f"Mismatch: {len(starts)} starts vs {len(completes)} completes"
        )

        # Each block_id must have equal start and complete counts
        for block_id in ("outer", "inner_loop", "worker"):
            s = _count_events(observer, "block_start", block_id)
            c = _count_events(observer, "block_complete", block_id)
            assert s == c, f"Block '{block_id}': {s} starts vs {c} completes"

    @pytest.mark.asyncio
    async def test_event_ordering_starts_before_completes(self) -> None:
        """For each block execution, block_start must appear before block_complete."""
        worker = ResultBlock("worker", output="result")
        inner_loop = LoopBlock("inner_loop", inner_block_refs=["worker"], max_rounds=2)
        outer_loop = LoopBlock("outer", inner_block_refs=["inner_loop"], max_rounds=2)

        wf = Workflow(name="nested_loop_wf")
        wf.add_block(worker)
        wf.add_block(inner_loop)
        wf.add_block(outer_loop)
        wf.add_transition("outer", None)
        wf.set_entry("outer")

        observer = RecordingObserver()
        state = WorkflowState()
        await wf.run(state, observer=observer)

        # The first event for "outer" must be block_start
        outer_events = [e for e in observer.events if len(e) > 2 and e[2] == "outer"]
        assert outer_events[0][0] == "block_start"
        assert outer_events[-1][0] == "block_complete"

        # workflow_start must be the very first event
        assert observer.events[0][0] == "workflow_start"
        # workflow_complete must be the very last event
        assert observer.events[-1][0] == "workflow_complete"


# ===========================================================================
# Scenario 2: Inner loop break_on_exit
# ===========================================================================


class TestInnerLoopBreakOnExit:
    """Outer LoopBlock (max_rounds=3) -> Inner LoopBlock (max_rounds=5, break_on_exit="done")
    -> worker that always returns exit_handle="done".

    Since worker returns "done" immediately, inner loop breaks after 1 round each time.
    Outer runs all 3 rounds.
    Worker executes 3 times total (3 outer rounds x 1 inner round).
    """

    @pytest.mark.asyncio
    async def test_break_on_exit_limits_inner_rounds(self) -> None:
        worker = ExitHandleBlock("worker", exit_handle="done")
        inner_loop = LoopBlock(
            "inner_loop",
            inner_block_refs=["worker"],
            max_rounds=5,
            break_on_exit="done",
        )
        outer_loop = LoopBlock("outer", inner_block_refs=["inner_loop"], max_rounds=3)

        wf = Workflow(name="break_exit_wf")
        wf.add_block(worker)
        wf.add_block(inner_loop)
        wf.add_block(outer_loop)
        wf.add_transition("outer", None)
        wf.set_entry("outer")

        observer = RecordingObserver()
        state = WorkflowState()
        await wf.run(state, observer=observer)

        # Worker called 3 times (1 per outer round, inner breaks immediately)
        assert worker.calls == 3, f"Expected 3 worker calls, got {worker.calls}"

        # Observer sees worker start 3 times
        assert _count_events(observer, "block_start", "worker") == 3
        assert _count_events(observer, "block_complete", "worker") == 3

        # Inner loop ran 3 times (once per outer round)
        assert _count_events(observer, "block_start", "inner_loop") == 3
        assert _count_events(observer, "block_complete", "inner_loop") == 3

        # Outer loop ran once
        assert _count_events(observer, "block_start", "outer") == 1
        assert _count_events(observer, "block_complete", "outer") == 1

    @pytest.mark.asyncio
    async def test_break_on_exit_loop_metadata(self) -> None:
        """Inner loop metadata should reflect early break due to exit_handle."""
        worker = ExitHandleBlock("worker", exit_handle="done")
        inner_loop = LoopBlock(
            "inner_loop",
            inner_block_refs=["worker"],
            max_rounds=5,
            break_on_exit="done",
        )
        outer_loop = LoopBlock("outer", inner_block_refs=["inner_loop"], max_rounds=3)

        wf = Workflow(name="break_exit_wf")
        wf.add_block(worker)
        wf.add_block(inner_loop)
        wf.add_block(outer_loop)
        wf.add_transition("outer", None)
        wf.set_entry("outer")

        state = WorkflowState()
        final_state = await wf.run(state)

        # Inner loop metadata should show broke_early
        inner_meta = final_state.shared_memory.get("__loop__inner_loop")
        assert inner_meta is not None, "Inner loop metadata missing"
        assert inner_meta["broke_early"] is True
        assert inner_meta["rounds_completed"] == 1

        # Outer loop should complete all rounds (no break condition)
        outer_meta = final_state.shared_memory.get("__loop__outer")
        assert outer_meta is not None, "Outer loop metadata missing"
        assert outer_meta["rounds_completed"] == 3
        assert outer_meta["broke_early"] is False

    @pytest.mark.asyncio
    async def test_break_on_exit_non_matching_handle_runs_all_rounds(self) -> None:
        """When exit_handle does not match break_on_exit, inner loop runs all rounds."""
        worker = ExitHandleBlock("worker", exit_handle="continue")
        inner_loop = LoopBlock(
            "inner_loop",
            inner_block_refs=["worker"],
            max_rounds=3,
            break_on_exit="done",  # "continue" != "done", no break
        )
        outer_loop = LoopBlock("outer", inner_block_refs=["inner_loop"], max_rounds=2)

        wf = Workflow(name="no_break_wf")
        wf.add_block(worker)
        wf.add_block(inner_loop)
        wf.add_block(outer_loop)
        wf.add_transition("outer", None)
        wf.set_entry("outer")

        state = WorkflowState()
        final_state = await wf.run(state)

        # Worker called 6 times (3 inner rounds x 2 outer rounds)
        assert worker.calls == 6, f"Expected 6 worker calls, got {worker.calls}"

        inner_meta = final_state.shared_memory.get("__loop__inner_loop")
        assert inner_meta["broke_early"] is False
        assert inner_meta["rounds_completed"] == 3


# ===========================================================================
# Scenario 3: Retry on inner block in nested loop
# ===========================================================================


class TestRetryInNestedLoop:
    """Outer LoopBlock (max_rounds=2) -> Inner LoopBlock (max_rounds=2)
    -> FlakyBlock with retry_config(max_attempts=2).

    FlakyBlock fails on odd calls, succeeds on even calls.
    With retry (max_attempts=2), each execution attempt pair is:
      attempt 1: fails (odd call), attempt 2: succeeds (even call).
    Total execute_block dispatches: 2 outer x 2 inner = 4.
    Each dispatch retries once, so FlakyBlock.calls = 4 x 2 = 8.
    Workflow completes successfully.
    """

    @pytest.mark.asyncio
    async def test_retry_completes_nested_loop(self) -> None:
        worker = FlakyBlock("worker")
        worker.retry_config = RetryConfig(max_attempts=2, backoff="fixed", backoff_base_seconds=0.1)

        inner_loop = LoopBlock("inner_loop", inner_block_refs=["worker"], max_rounds=2)
        outer_loop = LoopBlock("outer", inner_block_refs=["inner_loop"], max_rounds=2)

        wf = Workflow(name="retry_nested_wf")
        wf.add_block(worker)
        wf.add_block(inner_loop)
        wf.add_block(outer_loop)
        wf.add_transition("outer", None)
        wf.set_entry("outer")

        observer = RecordingObserver()
        state = WorkflowState()

        with patch("asyncio.sleep", new_callable=AsyncMock):
            await wf.run(state, observer=observer)

        # FlakyBlock: fails on odd calls, succeeds on even.
        # 4 dispatches x 2 attempts each = 8 total calls
        assert worker.calls == 8, f"Expected 8 flaky calls, got {worker.calls}"

        # Worker block_start fires once per execute_block dispatch (4 times),
        # and block_complete fires 4 times (retry is internal to execute_block)
        assert _count_events(observer, "block_start", "worker") == 4
        assert _count_events(observer, "block_complete", "worker") == 4

        # No block_error events since retries succeeded
        worker_errors = [e for e in observer.events if e[0] == "block_error" and e[2] == "worker"]
        assert len(worker_errors) == 0, (
            f"Expected no block_error for worker (retries succeeded), got {len(worker_errors)}"
        )

        # Workflow completed successfully
        workflow_completes = [e for e in observer.events if e[0] == "workflow_complete"]
        assert len(workflow_completes) == 1

    @pytest.mark.asyncio
    async def test_retry_exhausted_raises_in_nested_loop(self) -> None:
        """When retry is exhausted, the error should propagate and
        the observer should see block_error and workflow_error events.
        """

        class AlwaysFailBlock(BaseBlock):
            def __init__(self, block_id: str = "worker"):
                super().__init__(block_id)
                self.calls = 0

            async def execute(self, ctx: BlockContext) -> BlockOutput:
                self.calls += 1
                raise RuntimeError("always fails")

        worker = AlwaysFailBlock("worker")
        worker.retry_config = RetryConfig(max_attempts=2, backoff="fixed", backoff_base_seconds=0.1)

        inner_loop = LoopBlock("inner_loop", inner_block_refs=["worker"], max_rounds=2)
        outer_loop = LoopBlock("outer", inner_block_refs=["inner_loop"], max_rounds=2)

        wf = Workflow(name="retry_exhausted_wf")
        wf.add_block(worker)
        wf.add_block(inner_loop)
        wf.add_block(outer_loop)
        wf.add_transition("outer", None)
        wf.set_entry("outer")

        observer = RecordingObserver()
        state = WorkflowState()

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(RuntimeError, match="always fails"):
                await wf.run(state, observer=observer)

        # Worker was called 2 times (max_attempts=2), then error propagated
        assert worker.calls == 2

        # Observer sees block_error for worker (after retry exhaustion)
        worker_errors = [e for e in observer.events if e[0] == "block_error" and e[2] == "worker"]
        assert len(worker_errors) == 1

        # Observer sees workflow_error
        workflow_errors = [e for e in observer.events if e[0] == "workflow_error"]
        assert len(workflow_errors) == 1

    @pytest.mark.asyncio
    async def test_retry_metadata_in_shared_memory(self) -> None:
        """After successful retry, shared_memory should contain retry metadata."""
        worker = FlakyBlock("worker")
        worker.retry_config = RetryConfig(max_attempts=2, backoff="fixed", backoff_base_seconds=0.1)

        inner_loop = LoopBlock("inner_loop", inner_block_refs=["worker"], max_rounds=1)
        outer_loop = LoopBlock("outer", inner_block_refs=["inner_loop"], max_rounds=1)

        wf = Workflow(name="retry_meta_wf")
        wf.add_block(worker)
        wf.add_block(inner_loop)
        wf.add_block(outer_loop)
        wf.add_transition("outer", None)
        wf.set_entry("outer")

        state = WorkflowState()

        with patch("asyncio.sleep", new_callable=AsyncMock):
            final_state = await wf.run(state)

        # Retry metadata should be in shared_memory
        retry_meta = final_state.shared_memory.get("__retry__worker")
        assert retry_meta is not None, "Retry metadata missing from shared_memory"
        assert retry_meta["attempt"] == 2
        assert retry_meta["max_attempts"] == 2
        assert retry_meta["total_retries"] == 1
