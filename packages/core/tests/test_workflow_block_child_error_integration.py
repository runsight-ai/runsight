"""Integration coverage for WorkflowBlock child failure handling."""

from __future__ import annotations

import pytest
from runsight_core.blocks.workflow_block import WorkflowBlock
from runsight_core.state import WorkflowState
from runsight_core.workflow import Workflow
from workflow_block_integration_helpers import (
    FailingBlock,
    RecordingObserver,
    make_single_block_workflow,
)


def _failing_child_workflow(name: str, message: str) -> Workflow:
    failing = FailingBlock("failing_step", message)
    child_workflow = Workflow(name)
    child_workflow.add_block(failing)
    child_workflow.set_entry("failing_step")
    child_workflow.add_transition("failing_step", None)
    return child_workflow


@pytest.mark.asyncio
async def test_workflowblock_child_error_propagates_to_parent_workflow():
    """Default on_error='raise' should surface child workflow failures."""
    invoke_failing = WorkflowBlock(
        block_id="invoke_failing",
        child_workflow=_failing_child_workflow("failing_child", "child workflow crashed"),
        inputs={},
        outputs={},
        on_error="raise",
    )

    workflow = make_single_block_workflow("error_workflow", invoke_failing)

    with pytest.raises(RuntimeError, match="child workflow crashed"):
        await workflow.run(WorkflowState())


@pytest.mark.asyncio
async def test_workflowblock_on_error_catch_returns_error_result():
    """on_error='catch' should convert child failure into an error BlockResult."""
    invoke_catch = WorkflowBlock(
        block_id="invoke_catch",
        child_workflow=_failing_child_workflow("catching_child", "caught failure"),
        inputs={},
        outputs={},
        on_error="catch",
    )

    workflow = make_single_block_workflow("catch_workflow", invoke_catch)
    final_state = await workflow.run(WorkflowState())

    assert "invoke_catch" in final_state.results
    invoke_result = final_state.results["invoke_catch"]
    assert invoke_result.exit_handle == "error"
    assert invoke_result.output == "WorkflowBlock 'catching_child' failed"
    assert invoke_result.metadata is not None
    assert invoke_result.metadata["child_error"] == "caught failure"


@pytest.mark.asyncio
async def test_workflowblock_child_error_notifies_parent_observer():
    """Propagated child failures should surface parent workflow error events."""
    invoke_failing = WorkflowBlock(
        block_id="invoke_failing",
        child_workflow=_failing_child_workflow("failing_child_obs", "observer error test"),
        inputs={},
        outputs={},
    )

    workflow = make_single_block_workflow("error_observer_workflow", invoke_failing)
    observer = RecordingObserver()

    with pytest.raises(RuntimeError):
        await workflow.run(WorkflowState(), observer=observer)

    assert any(event[0] == "workflow_error" for event in observer.events)
    assert any(event[0] == "block_error" for event in observer.events)
