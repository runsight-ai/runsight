"""WorkflowBlock governed input mapping behavior."""

from __future__ import annotations

import json
from typing import Any

import pytest
from runsight_core.block_io import build_block_context
from runsight_core.blocks.workflow_block import WorkflowBlock
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.workflow import BlockExecutionContext, execute_block


class CapturingWorkflow:
    """Child workflow spy that records the state and kwargs WorkflowBlock passes."""

    def __init__(self) -> None:
        self.name = "governed_child_workflow"
        self.received_state: WorkflowState | None = None
        self.received_kwargs: dict[str, Any] | None = None

    async def run(self, state: WorkflowState, **kwargs: Any) -> WorkflowState:
        self.received_state = state
        self.received_kwargs = kwargs
        return WorkflowState(
            artifact_store=state.artifact_store,
            total_cost_usd=0.0,
            total_tokens=0,
        )


def _state_with_parent_context() -> WorkflowState:
    return WorkflowState(
        metadata={
            "runtime": {"branch": "main", "secret": "hidden"},
            "unrelated": "metadata leak",
        },
        results={
            "draft": BlockResult(
                output=json.dumps({"summary": "draft summary", "secret": "hidden"})
            ),
            "unrelated": BlockResult(output="result leak"),
        },
        workflow_inputs={
            "payload": {"id": "payload-1"},
        },
        shared_memory={"unrelated": "shared leak"},
    )


@pytest.mark.parametrize(
    ("public_name", "parent_ref", "expected_value"),
    [
        ("branch", "metadata.runtime.branch", "main"),
        ("payload", "workflow.payload", {"id": "payload-1"}),
        ("summary", "draft.summary", "draft summary"),
    ],
)
@pytest.mark.asyncio
async def test_workflowblock_passes_governed_ctx_inputs_as_child_invocation_inputs(
    public_name: str,
    parent_ref: str,
    expected_value: Any,
) -> None:
    child_workflow = CapturingWorkflow()
    block = WorkflowBlock(
        block_id="governed_input_workflow_block",
        child_workflow=child_workflow,
        inputs={public_name: parent_ref},
        outputs={},
    )
    ctx = build_block_context(block, _state_with_parent_context())
    assert ctx.inputs[public_name] == expected_value

    await block.execute(ctx)

    assert child_workflow.received_state is not None
    assert child_workflow.received_kwargs is not None
    assert child_workflow.received_kwargs["inputs"] == {public_name: expected_value}
    assert child_workflow.received_state.workflow_inputs == {public_name: expected_value}
    assert child_workflow.received_state.metadata == {}
    assert child_workflow.received_state.results == {}
    assert child_workflow.received_state.shared_memory == {}


@pytest.mark.asyncio
async def test_workflowblock_keeps_execution_plumbing_out_of_child_invocation_inputs() -> None:
    child_workflow = CapturingWorkflow()
    observer = object()
    registry = object()
    block = WorkflowBlock(
        block_id="plumbing_filtered_workflow_block",
        child_workflow=child_workflow,
        inputs={"branch": "metadata.runtime.branch"},
        outputs={},
    )
    governed_ctx = build_block_context(block, _state_with_parent_context())
    ctx = governed_ctx.model_copy(
        update={
            "inputs": {
                **governed_ctx.inputs,
                "call_stack": ["governed_parent_workflow"],
                "workflow_registry": registry,
                "observer": observer,
            }
        }
    )

    await block.execute(ctx)

    assert child_workflow.received_kwargs is not None
    assert child_workflow.received_kwargs["inputs"] == {"branch": "main"}
    assert child_workflow.received_kwargs["call_stack"] == [
        "governed_parent_workflow",
        "governed_child_workflow",
    ]
    assert child_workflow.received_kwargs["workflow_registry"] is registry
    assert child_workflow.received_kwargs["observer"] is observer


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "private_target", ["metadata.branch", "shared_memory.payload", "results.summary"]
)
async def test_workflowblock_rejects_private_child_state_input_targets(
    private_target: str,
) -> None:
    child_workflow = CapturingWorkflow()

    with pytest.raises(ValueError, match="private child state|child invocation input"):
        block = WorkflowBlock(
            block_id="private_input_workflow_block",
            child_workflow=child_workflow,
            inputs={private_target: "metadata.runtime.branch"},
            outputs={},
        )
        ctx = build_block_context(block, _state_with_parent_context())
        await block.execute(ctx)

    assert child_workflow.received_state is None


@pytest.mark.asyncio
async def test_execute_block_direct_workflowblock_preserves_governed_declared_inputs() -> None:
    child_workflow = CapturingWorkflow()
    block = WorkflowBlock(
        block_id="direct_execute_governed_workflow_block",
        child_workflow=child_workflow,
        inputs={"branch": "metadata.runtime.branch"},
        outputs={},
    )
    state = _state_with_parent_context()
    exec_ctx = BlockExecutionContext(
        workflow_name="governed_parent_workflow",
        blocks={},
        call_stack=[],
        workflow_registry=None,
        observer=None,
    )

    await execute_block(block, state, exec_ctx)

    assert child_workflow.received_kwargs is not None
    assert child_workflow.received_kwargs["inputs"] == {"branch": "main"}
