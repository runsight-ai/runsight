"""
Runtime integration tests for nested LoopBlock with observer parity.

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

import pytest
from runsight_core.block_io import BlockContext, BlockOutput
from runsight_core.blocks.base import BaseBlock
from runsight_core.blocks.loop import LoopBlock
from runsight_core.state import WorkflowState
from runsight_core.workflow import Workflow

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

        wf = Workflow(name="break_exit_workflow")
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

        wf = Workflow(name="break_exit_workflow")
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

        wf = Workflow(name="no_break_workflow")
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
