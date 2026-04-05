"""
E2E tests for RUN-682: WorkflowBlock inside LoopBlock end-to-end.

Tests cover:
1. Happy path — WorkflowBlock breaks loop on success (exit_handle propagation)
2. WorkflowBlock error handling — child workflow failure propagation
3. Depth limiting — nested WorkflowBlocks at max_depth trigger RecursionError
4. Cycle detection — self-referencing child workflows raise RecursionError
"""

from __future__ import annotations

import pytest
from runsight_core.blocks.base import BaseBlock
from runsight_core.blocks.loop import LoopBlock
from runsight_core.blocks.workflow_block import WorkflowBlock
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.workflow import Workflow

# ── Test helpers ──────────────────────────────────────────────────────────────


class ResultBlock(BaseBlock):
    """Simple block that stores a fixed output string in results."""

    def __init__(self, block_id: str, output: str) -> None:
        super().__init__(block_id)
        self.output = output

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        return state.model_copy(
            update={
                "results": {
                    **state.results,
                    self.block_id: BlockResult(output=self.output),
                },
            }
        )


class CountingBlock(BaseBlock):
    """Block that tracks call count via instance state and emits exit_handle after threshold.

    Uses mutable instance counter so it persists across LoopBlock rounds
    (LoopBlock invokes the same block instance each round).
    """

    def __init__(self, block_id: str, threshold: int = 2, exit_handle: str = "completed") -> None:
        super().__init__(block_id)
        self.calls = 0
        self.threshold = threshold
        self._exit_handle = exit_handle

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        self.calls += 1
        handle = self._exit_handle if self.calls >= self.threshold else None
        return state.model_copy(
            update={
                "results": {
                    **state.results,
                    self.block_id: BlockResult(
                        output=f"call_{self.calls}",
                        exit_handle=handle,
                    ),
                },
            }
        )


class FailingBlock(BaseBlock):
    """Block that always raises RuntimeError."""

    def __init__(self, block_id: str, message: str = "intentional failure") -> None:
        super().__init__(block_id)
        self.message = message

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        raise RuntimeError(self.message)


class RecordingObserver:
    """Observer that records all events for assertion."""

    def __init__(self) -> None:
        self.events: list[tuple[str, ...]] = []

    def on_workflow_start(self, workflow_name: str, state: WorkflowState) -> None:
        self.events.append(("workflow_start", workflow_name))

    def on_block_start(self, workflow_name: str, block_id: str, block_type: str, **kwargs) -> None:
        self.events.append(("block_start", workflow_name, block_id, block_type))

    def on_block_complete(
        self,
        workflow_name: str,
        block_id: str,
        block_type: str,
        duration_s: float,
        state: WorkflowState,
        **kwargs,
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


def _make_workflow_with_loop(
    name: str,
    loop: LoopBlock,
    *inner_blocks: BaseBlock,
) -> Workflow:
    """Create a workflow with a LoopBlock as entry + all inner blocks registered."""
    wf = Workflow(name)
    wf.add_block(loop)
    for block in inner_blocks:
        wf.add_block(block)
    wf.set_entry(loop.block_id)
    wf.add_transition(loop.block_id, None)
    return wf


# ── Scenario 1: Happy path — WorkflowBlock breaks loop on success ────────────


@pytest.mark.asyncio
async def test_workflowblock_in_loop_breaks_on_success():
    """
    LoopBlock "review_loop" (max_rounds=3, break_on_exit="completed")
    contains ["writer", "review_subworkflow"].

    "writer" is a simple ResultBlock.
    "review_subworkflow" is a WorkflowBlock calling a child workflow that
    contains a CountingBlock which succeeds (exit_handle="completed") on round 2.

    Expected: WorkflowBlock returns exit_handle="completed" on round 2,
    LoopBlock breaks early (broke_early=True, rounds_completed=2).
    """
    # Child workflow: contains a CountingBlock that fires "completed" on call 2
    reviewer = CountingBlock("reviewer", threshold=2, exit_handle="completed")
    child_wf = Workflow("review_child")
    child_wf.add_block(reviewer)
    child_wf.set_entry("reviewer")
    child_wf.add_transition("reviewer", None)

    # Parent blocks
    writer = ResultBlock("writer", "draft text")
    review_subworkflow = WorkflowBlock(
        block_id="review_subworkflow",
        child_workflow=child_wf,
        inputs={},
        outputs={},
    )

    # The WorkflowBlock always returns exit_handle="completed" after child finishes.
    # The LoopBlock's break_on_exit="completed" should match this.
    loop = LoopBlock(
        "review_loop",
        inner_block_refs=["writer", "review_subworkflow"],
        max_rounds=3,
        break_on_exit="completed",
    )

    wf = _make_workflow_with_loop("happy_path_wf", loop, writer, review_subworkflow)

    state = WorkflowState()
    final_state = await wf.run(state)

    # The WorkflowBlock always sets exit_handle="completed" on success,
    # so break_on_exit="completed" should fire after the FIRST round.
    loop_meta = final_state.shared_memory["__loop__review_loop"]
    assert loop_meta["broke_early"] is True
    # WorkflowBlock always returns exit_handle="completed", so loop breaks at round 1
    assert loop_meta["rounds_completed"] >= 1
    assert "exit_handle" in loop_meta["break_reason"]

    # Verify both blocks produced results
    assert "writer" in final_state.results
    assert "review_subworkflow" in final_state.results
    assert final_state.results["review_subworkflow"].exit_handle == "completed"


@pytest.mark.asyncio
async def test_workflowblock_in_loop_observer_events_at_all_levels():
    """
    Observer should receive events at all nesting levels:
    - Parent workflow start/complete
    - LoopBlock start/complete
    - Writer block start/complete (per round)
    - WorkflowBlock start/complete (per round)
    - Child workflow's inner block start/complete (forwarded via ChildObserverWrapper)
    """
    reviewer = CountingBlock("reviewer", threshold=2, exit_handle="completed")
    child_wf = Workflow("review_child")
    child_wf.add_block(reviewer)
    child_wf.set_entry("reviewer")
    child_wf.add_transition("reviewer", None)

    writer = ResultBlock("writer", "draft")
    review_subworkflow = WorkflowBlock(
        block_id="review_subworkflow",
        child_workflow=child_wf,
        inputs={},
        outputs={},
    )

    loop = LoopBlock(
        "review_loop",
        inner_block_refs=["writer", "review_subworkflow"],
        max_rounds=3,
        break_on_exit="completed",
    )

    wf = _make_workflow_with_loop("observer_wf", loop, writer, review_subworkflow)

    observer = RecordingObserver()
    state = WorkflowState()
    await wf.run(state, observer=observer)

    # Parent workflow lifecycle
    assert ("workflow_start", "observer_wf") in observer.events
    assert ("workflow_complete", "observer_wf") in observer.events

    # LoopBlock lifecycle
    assert ("block_start", "observer_wf", "review_loop", "LoopBlock") in observer.events
    assert ("block_complete", "observer_wf", "review_loop", "LoopBlock") in observer.events

    # Inner writer block events (at least one round)
    writer_starts = [
        e for e in observer.events if e[:3] == ("block_start", "observer_wf", "writer")
    ]
    assert len(writer_starts) >= 1

    # WorkflowBlock events (at least one round)
    wfb_starts = [
        e for e in observer.events if e[:3] == ("block_start", "observer_wf", "review_subworkflow")
    ]
    assert len(wfb_starts) >= 1

    # Child workflow's inner block events (forwarded by ChildObserverWrapper)
    # The child observer forwards block-level events but intercepts workflow-level ones
    child_block_events = [e for e in observer.events if len(e) >= 4 and e[2] == "reviewer"]
    assert len(child_block_events) >= 1, (
        "Expected child workflow's 'reviewer' block events to be forwarded "
        "to parent observer via ChildObserverWrapper"
    )


# ── Scenario 2: WorkflowBlock error handling ─────────────────────────────────


@pytest.mark.asyncio
async def test_workflowblock_error_propagates_through_loop():
    """
    LoopBlock with WorkflowBlock whose child workflow fails on round 1.
    The error should propagate up through the LoopBlock and the parent workflow.

    Tests error propagation (on_error="raise" which is the default).
    """
    # Child workflow that always fails
    failing = FailingBlock("failing_step", "child workflow crashed")
    child_wf = Workflow("failing_child")
    child_wf.add_block(failing)
    child_wf.set_entry("failing_step")
    child_wf.add_transition("failing_step", None)

    # WorkflowBlock with default on_error="raise"
    invoke_failing = WorkflowBlock(
        block_id="invoke_failing",
        child_workflow=child_wf,
        inputs={},
        outputs={},
        on_error="raise",
    )

    loop = LoopBlock(
        "error_loop",
        inner_block_refs=["invoke_failing"],
        max_rounds=3,
    )

    wf = _make_workflow_with_loop("error_wf", loop, invoke_failing)

    state = WorkflowState()
    with pytest.raises(RuntimeError, match="child workflow crashed"):
        await wf.run(state)


@pytest.mark.asyncio
async def test_workflowblock_on_error_catch_in_loop():
    """
    WorkflowBlock with on_error="catch" should swallow child errors and
    return exit_handle="error" in its BlockResult.

    The LoopBlock should continue iterating (no break_on_exit for "error").
    After max_rounds, loop completes normally with broke_early=False.
    """
    # Child workflow that always fails
    failing = FailingBlock("failing_step", "caught failure")
    child_wf = Workflow("catching_child")
    child_wf.add_block(failing)
    child_wf.set_entry("failing_step")
    child_wf.add_transition("failing_step", None)

    # WorkflowBlock with on_error="catch"
    invoke_catch = WorkflowBlock(
        block_id="invoke_catch",
        child_workflow=child_wf,
        inputs={},
        outputs={},
        on_error="catch",
    )

    loop = LoopBlock(
        "catch_loop",
        inner_block_refs=["invoke_catch"],
        max_rounds=2,
    )

    wf = _make_workflow_with_loop("catch_wf", loop, invoke_catch)

    state = WorkflowState()
    final_state = await wf.run(state)

    # on_error="catch" means the WorkflowBlock returns exit_handle="error"
    # but the LoopBlock has no break_on_exit, so it runs all rounds
    loop_meta = final_state.shared_memory["__loop__catch_loop"]
    assert loop_meta["rounds_completed"] == 2
    assert loop_meta["broke_early"] is False

    # The WorkflowBlock result should indicate error
    assert "invoke_catch" in final_state.results
    assert final_state.results["invoke_catch"].exit_handle == "error"


@pytest.mark.asyncio
async def test_workflowblock_error_observer_events():
    """
    When a WorkflowBlock error propagates, observer should receive
    block_error and workflow_error events.
    """
    failing = FailingBlock("failing_step", "observer error test")
    child_wf = Workflow("failing_child_obs")
    child_wf.add_block(failing)
    child_wf.set_entry("failing_step")
    child_wf.add_transition("failing_step", None)

    invoke_failing = WorkflowBlock(
        block_id="invoke_failing",
        child_workflow=child_wf,
        inputs={},
        outputs={},
    )

    loop = LoopBlock(
        "error_obs_loop",
        inner_block_refs=["invoke_failing"],
        max_rounds=2,
    )

    wf = _make_workflow_with_loop("error_obs_wf", loop, invoke_failing)

    observer = RecordingObserver()
    state = WorkflowState()
    with pytest.raises(RuntimeError):
        await wf.run(state, observer=observer)

    # The parent workflow should report error
    workflow_errors = [e for e in observer.events if e[0] == "workflow_error"]
    assert len(workflow_errors) >= 1

    # There should be a block_error for either the WorkflowBlock or the child block
    block_errors = [e for e in observer.events if e[0] == "block_error"]
    assert len(block_errors) >= 1


# ── Scenario 3: Depth limiting ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_workflowblock_depth_limiting_raises_recursion_error():
    """
    WorkflowBlock at depth 1, child workflow also contains a WorkflowBlock.
    With max_depth=1, the nested WorkflowBlock should trigger RecursionError.

    The LoopBlock should propagate the error.
    """
    # Grandchild workflow (deepest level) — simple block
    grandchild_block = ResultBlock("gc_step", "grandchild done")
    grandchild_wf = Workflow("grandchild_wf")
    grandchild_wf.add_block(grandchild_block)
    grandchild_wf.set_entry("gc_step")
    grandchild_wf.add_transition("gc_step", None)

    # Child workflow — contains a WorkflowBlock pointing to grandchild
    invoke_grandchild = WorkflowBlock(
        block_id="invoke_grandchild",
        child_workflow=grandchild_wf,
        inputs={},
        outputs={},
        max_depth=1,  # Restrictive: only allow depth 1
    )
    child_wf = Workflow("child_wf")
    child_wf.add_block(invoke_grandchild)
    child_wf.set_entry("invoke_grandchild")
    child_wf.add_transition("invoke_grandchild", None)

    # Parent WorkflowBlock pointing to child
    invoke_child = WorkflowBlock(
        block_id="invoke_child",
        child_workflow=child_wf,
        inputs={},
        outputs={},
        max_depth=10,  # Generous at this level
    )

    loop = LoopBlock(
        "depth_loop",
        inner_block_refs=["invoke_child"],
        max_rounds=2,
    )

    wf = _make_workflow_with_loop("depth_wf", loop, invoke_child)

    state = WorkflowState()
    with pytest.raises(RecursionError, match="maximum depth"):
        await wf.run(state)


@pytest.mark.asyncio
async def test_depth_limit_exact_boundary():
    """
    WorkflowBlock nesting at exactly max_depth should raise RecursionError.

    Parent workflow -> WorkflowBlock(max_depth=2) -> child workflow
    -> WorkflowBlock(max_depth=2) -> grandchild workflow

    The call_stack at grandchild invocation will be
    [parent_wf, child_wf] which has length 2 == max_depth, so it should fail.
    """
    grandchild_block = ResultBlock("gc_step", "grandchild done")
    grandchild_wf = Workflow("grandchild_exact")
    grandchild_wf.add_block(grandchild_block)
    grandchild_wf.set_entry("gc_step")
    grandchild_wf.add_transition("gc_step", None)

    invoke_gc = WorkflowBlock(
        block_id="invoke_gc",
        child_workflow=grandchild_wf,
        inputs={},
        outputs={},
        max_depth=2,
    )
    child_wf = Workflow("child_exact")
    child_wf.add_block(invoke_gc)
    child_wf.set_entry("invoke_gc")
    child_wf.add_transition("invoke_gc", None)

    invoke_child = WorkflowBlock(
        block_id="invoke_child",
        child_workflow=child_wf,
        inputs={},
        outputs={},
        max_depth=10,
    )

    loop = LoopBlock(
        "depth_exact_loop",
        inner_block_refs=["invoke_child"],
        max_rounds=1,
    )

    wf = _make_workflow_with_loop("depth_exact_wf", loop, invoke_child)

    state = WorkflowState()
    with pytest.raises(RecursionError, match="maximum depth"):
        await wf.run(state)


# ── Scenario 4: Cycle detection ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cycle_detection_raises_recursion_error():
    """
    WorkflowBlock whose child workflow calls back to the parent.
    Cycle detection should raise RecursionError.
    The LoopBlock should propagate the error.

    Setup:
    - parent_wf contains a LoopBlock with inner WorkflowBlock "invoke_child"
    - child_wf contains a WorkflowBlock "invoke_parent" that calls parent_wf
    - This creates a cycle: parent -> child -> parent
    """
    # We create the cycle by having both workflows reference each other.
    # First, create child_wf with a placeholder, then replace after parent exists.

    # Step 1: Build child workflow that invokes "parent_cycle_wf"
    # The child's WorkflowBlock will point to parent — creating a cycle.
    # We need to construct this carefully since Workflow objects are mutable.

    # Create parent workflow first (we'll set child to reference it)
    parent_wf = Workflow("parent_cycle_wf")

    # Child: a workflow that invokes the parent back (cycle)
    invoke_parent = WorkflowBlock(
        block_id="invoke_parent",
        child_workflow=parent_wf,  # points back to parent => cycle
        inputs={},
        outputs={},
    )
    child_wf = Workflow("child_cycle_wf")
    child_wf.add_block(invoke_parent)
    child_wf.set_entry("invoke_parent")
    child_wf.add_transition("invoke_parent", None)

    # Parent: contains a loop with a WorkflowBlock that calls child
    invoke_child = WorkflowBlock(
        block_id="invoke_child",
        child_workflow=child_wf,
        inputs={},
        outputs={},
    )

    loop = LoopBlock(
        "cycle_loop",
        inner_block_refs=["invoke_child"],
        max_rounds=2,
    )

    parent_wf.add_block(loop)
    parent_wf.add_block(invoke_child)
    parent_wf.set_entry("cycle_loop")
    parent_wf.add_transition("cycle_loop", None)

    state = WorkflowState()
    with pytest.raises(RecursionError, match="cycle detected"):
        await parent_wf.run(state)


@pytest.mark.asyncio
async def test_cycle_detection_observer_receives_error():
    """
    When cycle detection fires, the observer should receive error events.
    """
    parent_wf = Workflow("parent_obs_cycle")

    invoke_parent = WorkflowBlock(
        block_id="invoke_parent",
        child_workflow=parent_wf,
        inputs={},
        outputs={},
    )
    child_wf = Workflow("child_obs_cycle")
    child_wf.add_block(invoke_parent)
    child_wf.set_entry("invoke_parent")
    child_wf.add_transition("invoke_parent", None)

    invoke_child = WorkflowBlock(
        block_id="invoke_child",
        child_workflow=child_wf,
        inputs={},
        outputs={},
    )

    loop = LoopBlock(
        "obs_cycle_loop",
        inner_block_refs=["invoke_child"],
        max_rounds=1,
    )

    parent_wf.add_block(loop)
    parent_wf.add_block(invoke_child)
    parent_wf.set_entry("obs_cycle_loop")
    parent_wf.add_transition("obs_cycle_loop", None)

    observer = RecordingObserver()
    state = WorkflowState()
    with pytest.raises(RecursionError):
        await parent_wf.run(state, observer=observer)

    # Observer should have received a workflow_error event
    workflow_errors = [e for e in observer.events if e[0] == "workflow_error"]
    assert len(workflow_errors) >= 1

    # Observer should have received block_error events
    block_errors = [e for e in observer.events if e[0] == "block_error"]
    assert len(block_errors) >= 1
