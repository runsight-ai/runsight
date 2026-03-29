"""Red tests for RUN-128: Defensive observer wrapping in Workflow.run().

Currently, Workflow.run() calls observer methods directly without try/except.
If an observer raises, it crashes the workflow execution. RUN-128 requires that
observer errors are caught and logged, never propagating to crash the workflow.

Critical edge case: an observer error in on_block_error must NOT replace the
original block error — the original exception must still propagate.

All tests should FAIL until the implementation is done.
"""

import pytest
from runsight_core.blocks.base import BaseBlock
from runsight_core.state import WorkflowState
from runsight_core.workflow import Workflow

# ---------------------------------------------------------------------------
# Helper: a simple block that succeeds or fails on demand
# ---------------------------------------------------------------------------


class SuccessBlock(BaseBlock):
    def __init__(self, block_id: str = "ok_block"):
        super().__init__(block_id=block_id)

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        return state.model_copy(update={"results": {**state.results, self.block_id: "done"}})


class FailBlock(BaseBlock):
    def __init__(self, block_id: str = "fail_block", error_cls=RuntimeError, msg="block boom"):
        super().__init__(block_id=block_id)
        self._error_cls = error_cls
        self._msg = msg

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        raise self._error_cls(self._msg)


class CrashingObserver:
    """Observer that raises on every method call."""

    def on_workflow_start(self, workflow_name, state):
        raise RuntimeError("observer crash: workflow_start")

    def on_block_start(self, workflow_name, block_id, block_type):
        raise RuntimeError("observer crash: block_start")

    def on_block_complete(self, workflow_name, block_id, block_type, duration_s, state):
        raise RuntimeError("observer crash: block_complete")

    def on_block_error(self, workflow_name, block_id, block_type, duration_s, error):
        raise RuntimeError("observer crash: block_error")

    def on_workflow_complete(self, workflow_name, state, duration_s):
        raise RuntimeError("observer crash: workflow_complete")

    def on_workflow_error(self, workflow_name, error, duration_s):
        raise RuntimeError("observer crash: workflow_error")


# ---------------------------------------------------------------------------
# 1. Observer crash on workflow_start does not kill execution
# ---------------------------------------------------------------------------


class TestDefensiveObserverOnWorkflowStart:
    @pytest.mark.asyncio
    async def test_observer_crash_on_workflow_start_does_not_propagate(self):
        """If observer.on_workflow_start raises, workflow still executes and completes."""
        wf = Workflow("test_wf")
        wf.add_block(SuccessBlock("b1"))
        wf.set_entry("b1")
        wf.add_transition("b1", None)

        state = await wf.run(WorkflowState(), observer=CrashingObserver())
        assert "b1" in state.results
        assert state.results["b1"] == "done"


# ---------------------------------------------------------------------------
# 2. Observer crash on block_start does not kill execution
# ---------------------------------------------------------------------------


class TestDefensiveObserverOnBlockStart:
    @pytest.mark.asyncio
    async def test_observer_crash_on_block_start_does_not_propagate(self):
        """If observer.on_block_start raises, block still executes."""
        wf = Workflow("test_wf")
        wf.add_block(SuccessBlock("b1"))
        wf.set_entry("b1")
        wf.add_transition("b1", None)

        state = await wf.run(WorkflowState(), observer=CrashingObserver())
        assert "b1" in state.results


# ---------------------------------------------------------------------------
# 3. Observer crash on block_complete does not kill execution
# ---------------------------------------------------------------------------


class TestDefensiveObserverOnBlockComplete:
    @pytest.mark.asyncio
    async def test_observer_crash_on_block_complete_does_not_propagate(self):
        """If observer.on_block_complete raises, workflow continues to next block."""
        wf = Workflow("test_wf")
        wf.add_block(SuccessBlock("b1"))
        wf.add_block(SuccessBlock("b2"))
        wf.set_entry("b1")
        wf.add_transition("b1", "b2")
        wf.add_transition("b2", None)

        state = await wf.run(WorkflowState(), observer=CrashingObserver())
        assert "b1" in state.results
        assert "b2" in state.results


# ---------------------------------------------------------------------------
# 4. Observer crash on block_error does NOT replace original error
# ---------------------------------------------------------------------------


class TestDefensiveObserverOnBlockError:
    @pytest.mark.asyncio
    async def test_observer_crash_on_block_error_preserves_original_error(self):
        """If observer.on_block_error raises, the ORIGINAL block error propagates, not the observer error."""
        wf = Workflow("test_wf")
        wf.add_block(FailBlock("b1", error_cls=ValueError, msg="original block error"))
        wf.set_entry("b1")
        wf.add_transition("b1", None)

        with pytest.raises(ValueError, match="original block error"):
            await wf.run(WorkflowState(), observer=CrashingObserver())

    @pytest.mark.asyncio
    async def test_observer_crash_on_block_error_does_not_raise_observer_error(self):
        """The observer's RuntimeError must NOT surface — only the original ValueError."""
        wf = Workflow("test_wf")
        wf.add_block(FailBlock("b1", error_cls=ValueError, msg="real error"))
        wf.set_entry("b1")
        wf.add_transition("b1", None)

        try:
            await wf.run(WorkflowState(), observer=CrashingObserver())
            pytest.fail("Should have raised ValueError")
        except ValueError as e:
            assert "real error" in str(e)
        except RuntimeError:
            pytest.fail("Observer's RuntimeError leaked — must be swallowed")


# ---------------------------------------------------------------------------
# 5. Observer crash on workflow_complete does not kill execution
# ---------------------------------------------------------------------------


class TestDefensiveObserverOnWorkflowComplete:
    @pytest.mark.asyncio
    async def test_observer_crash_on_workflow_complete_still_returns_state(self):
        """If observer.on_workflow_complete raises, workflow still returns final state."""
        wf = Workflow("test_wf")
        wf.add_block(SuccessBlock("b1"))
        wf.set_entry("b1")
        wf.add_transition("b1", None)

        state = await wf.run(WorkflowState(), observer=CrashingObserver())
        assert "b1" in state.results


# ---------------------------------------------------------------------------
# 6. Observer crash on workflow_error does NOT replace original error
# ---------------------------------------------------------------------------


class TestDefensiveObserverOnWorkflowError:
    @pytest.mark.asyncio
    async def test_observer_crash_on_workflow_error_preserves_original_error(self):
        """If observer.on_workflow_error raises, the original workflow error propagates."""
        wf = Workflow("test_wf")
        wf.add_block(FailBlock("b1", error_cls=TypeError, msg="original workflow error"))
        wf.set_entry("b1")
        wf.add_transition("b1", None)

        with pytest.raises(TypeError, match="original workflow error"):
            await wf.run(WorkflowState(), observer=CrashingObserver())


# ---------------------------------------------------------------------------
# 7. Selective observer crash — only one method fails, others succeed
# ---------------------------------------------------------------------------


class SelectiveCrashObserver:
    """Observer that only crashes on on_block_complete, all others work."""

    def __init__(self):
        self.calls = []

    def on_workflow_start(self, workflow_name, state):
        self.calls.append("workflow_start")

    def on_block_start(self, workflow_name, block_id, block_type):
        self.calls.append(f"block_start:{block_id}")

    def on_block_complete(self, workflow_name, block_id, block_type, duration_s, state):
        raise RuntimeError("observer crash: block_complete")

    def on_block_error(self, workflow_name, block_id, block_type, duration_s, error):
        self.calls.append(f"block_error:{block_id}")

    def on_workflow_complete(self, workflow_name, state, duration_s):
        self.calls.append("workflow_complete")

    def on_workflow_error(self, workflow_name, error, duration_s):
        self.calls.append("workflow_error")


class TestSelectiveObserverCrash:
    @pytest.mark.asyncio
    async def test_other_observer_methods_still_called_after_crash(self):
        """If on_block_complete crashes, subsequent observer calls (workflow_complete) still happen."""
        wf = Workflow("test_wf")
        wf.add_block(SuccessBlock("b1"))
        wf.set_entry("b1")
        wf.add_transition("b1", None)

        obs = SelectiveCrashObserver()
        state = await wf.run(WorkflowState(), observer=obs)

        assert "workflow_start" in obs.calls
        assert "block_start:b1" in obs.calls
        # on_block_complete crashed, but workflow_complete should still fire
        assert "workflow_complete" in obs.calls
        assert "b1" in state.results
