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

        wf = Workflow(name="nested_loop_workflow")
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

        wf = Workflow(name="nested_loop_workflow")
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

        wf = Workflow(name="nested_loop_workflow")
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

        wf = Workflow(name="nested_loop_workflow")
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
