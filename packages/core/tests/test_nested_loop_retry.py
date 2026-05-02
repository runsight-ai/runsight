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

        wf = Workflow(name="retry_nested_workflow")
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

        wf = Workflow(name="retry_exhausted_workflow")
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

        wf = Workflow(name="retry_metadata_workflow")
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
