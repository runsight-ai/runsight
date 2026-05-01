"""Integration coverage for WorkflowBlock behavior inside LoopBlock."""

from __future__ import annotations

import pytest
from runsight_core.blocks.loop import LoopBlock
from runsight_core.blocks.workflow_block import WorkflowBlock
from runsight_core.state import WorkflowState
from runsight_core.workflow import Workflow
from workflow_block_integration_helpers import (
    RecordingObserver,
    ResultBlock,
    make_workflow_with_loop,
)


@pytest.mark.asyncio
async def test_workflowblock_in_loop_breaks_on_success():
    """
    LoopBlock "review_loop" (max_rounds=3, break_on_exit="completed")
    contains ["writer", "review_subworkflow"].

    "writer" is a simple ResultBlock.
    "review_subworkflow" is a WorkflowBlock calling a child workflow that
    completes successfully.

    Expected: WorkflowBlock returns exit_handle="completed" after the child
    workflow succeeds, so LoopBlock breaks after the first round.
    """
    reviewer = ResultBlock("reviewer", "review accepted")
    child_workflow = Workflow("review_child")
    child_workflow.add_block(reviewer)
    child_workflow.set_entry("reviewer")
    child_workflow.add_transition("reviewer", None)

    # Parent blocks
    writer = ResultBlock("writer", "draft text")
    review_subworkflow = WorkflowBlock(
        block_id="review_subworkflow",
        child_workflow=child_workflow,
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

    wf = make_workflow_with_loop("happy_path_workflow", loop, writer, review_subworkflow)

    state = WorkflowState()
    final_state = await wf.run(state)

    loop_meta = final_state.shared_memory["__loop__review_loop"]
    assert loop_meta["broke_early"] is True
    assert loop_meta["rounds_completed"] == 1
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
    reviewer = ResultBlock("reviewer", "review accepted")
    child_workflow = Workflow("review_child")
    child_workflow.add_block(reviewer)
    child_workflow.set_entry("reviewer")
    child_workflow.add_transition("reviewer", None)

    writer = ResultBlock("writer", "draft")
    review_subworkflow = WorkflowBlock(
        block_id="review_subworkflow",
        child_workflow=child_workflow,
        inputs={},
        outputs={},
    )

    loop = LoopBlock(
        "review_loop",
        inner_block_refs=["writer", "review_subworkflow"],
        max_rounds=3,
        break_on_exit="completed",
    )

    wf = make_workflow_with_loop("observer_workflow", loop, writer, review_subworkflow)

    observer = RecordingObserver()
    state = WorkflowState()
    await wf.run(state, observer=observer)

    # Parent workflow lifecycle
    assert ("workflow_start", "observer_workflow") in observer.events
    assert ("workflow_complete", "observer_workflow") in observer.events

    # LoopBlock lifecycle
    assert ("block_start", "observer_workflow", "review_loop", "LoopBlock") in observer.events
    assert ("block_complete", "observer_workflow", "review_loop", "LoopBlock") in observer.events

    # Inner writer block events (at least one round)
    writer_starts = [
        e for e in observer.events if e[:3] == ("block_start", "observer_workflow", "writer")
    ]
    assert len(writer_starts) >= 1

    # WorkflowBlock events (at least one round)
    wfb_starts = [
        e
        for e in observer.events
        if e[:3] == ("block_start", "observer_workflow", "review_subworkflow")
    ]
    assert len(wfb_starts) >= 1

    # Child workflow's inner block events (forwarded by ChildObserverWrapper)
    # The child observer forwards block-level events but intercepts workflow-level ones
    child_block_events = [e for e in observer.events if len(e) >= 4 and e[2] == "reviewer"]
    assert len(child_block_events) >= 1, (
        "Expected child workflow's 'reviewer' block events to be forwarded "
        "to parent observer via ChildObserverWrapper"
    )
