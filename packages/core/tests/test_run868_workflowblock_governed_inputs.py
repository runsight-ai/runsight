"""RUN-868 regressions for WorkflowBlock governed input mapping."""

from __future__ import annotations

import json
from typing import Any

import pytest
from runsight_core.block_io import build_block_context
from runsight_core.blocks.workflow_block import WorkflowBlock
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.workflow import BlockExecutionContext, execute_block
from runsight_core.yaml.schema import (
    WorkflowInterfaceDef,
    WorkflowInterfaceInputDef,
)


class CapturingWorkflow:
    """Child workflow spy that records the state WorkflowBlock passes to it."""

    def __init__(self) -> None:
        self.name = "child_workflow"
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
            "workflow": BlockResult(
                output=json.dumps(
                    {
                        "payload": {"id": "payload-1"},
                        "other": "result leak",
                    }
                )
            ),
            "draft": BlockResult(
                output=json.dumps({"summary": "draft summary", "secret": "hidden"})
            ),
            "unrelated": BlockResult(output="result leak"),
        },
        shared_memory={"unrelated": "shared leak"},
    )


def _interface(target: str) -> WorkflowInterfaceDef:
    return WorkflowInterfaceDef(
        inputs=[WorkflowInterfaceInputDef(name="value", target=target)],
        outputs=[],
    )


@pytest.mark.parametrize(
    ("parent_ref", "expected_value", "target", "target_bucket", "target_key"),
    [
        (
            "metadata.runtime.branch",
            "main",
            "metadata.branch",
            "metadata",
            "branch",
        ),
        (
            "results.workflow.payload",
            {"id": "payload-1"},
            "shared_memory.payload",
            "shared_memory",
            "payload",
        ),
        (
            "draft.summary",
            "draft summary",
            "results.summary",
            "results",
            "summary",
        ),
    ],
)
@pytest.mark.asyncio
async def test_workflowblock_interface_mapping_uses_governed_ctx_inputs(
    parent_ref: str,
    expected_value: Any,
    target: str,
    target_bucket: str,
    target_key: str,
) -> None:
    """Interface bindings must consume already-resolved ctx.inputs values."""
    child_workflow = CapturingWorkflow()
    block = WorkflowBlock(
        block_id="invoke_child",
        child_workflow=child_workflow,
        inputs={"value": parent_ref},
        outputs={},
        interface=_interface(target),
    )
    ctx = build_block_context(block, _state_with_parent_context())
    assert ctx.inputs["value"] == expected_value

    await block.execute(ctx)

    assert child_workflow.received_state is not None
    bucket = getattr(child_workflow.received_state, target_bucket)
    assert bucket[target_key] == expected_value


@pytest.mark.asyncio
async def test_workflowblock_interface_mapping_keeps_execution_plumbing_out_of_child_state() -> (
    None
):
    """Internal execution inputs must not become child workflow input data."""
    child_workflow = CapturingWorkflow()
    observer = object()
    registry = object()
    block = WorkflowBlock(
        block_id="invoke_child",
        child_workflow=child_workflow,
        inputs={"value": "metadata.runtime.branch"},
        outputs={},
        interface=_interface("metadata.branch"),
    )
    governed_ctx = build_block_context(block, _state_with_parent_context())
    ctx = governed_ctx.model_copy(
        update={
            "inputs": {
                **governed_ctx.inputs,
                "call_stack": ["parent_workflow"],
                "workflow_registry": registry,
                "observer": observer,
            }
        }
    )

    await block.execute(ctx)

    assert child_workflow.received_state is not None
    assert child_workflow.received_kwargs is not None
    assert child_workflow.received_state.metadata == {"branch": "main"}
    assert child_workflow.received_state.results == {}
    assert child_workflow.received_state.shared_memory == {}
    assert child_workflow.received_kwargs["call_stack"] == [
        "parent_workflow",
        "child_workflow",
    ]
    assert child_workflow.received_kwargs["workflow_registry"] is registry
    assert child_workflow.received_kwargs["observer"] is observer


@pytest.mark.asyncio
async def test_workflowblock_legacy_mapping_uses_governed_ctx_inputs_for_child_paths() -> None:
    """Legacy child dotted-path keys must also use resolved ctx.inputs values."""
    child_workflow = CapturingWorkflow()
    block = WorkflowBlock(
        block_id="invoke_child",
        child_workflow=child_workflow,
        inputs={
            "metadata.branch": "metadata.runtime.branch",
            "shared_memory.payload": "results.workflow.payload",
            "results.summary": "draft.summary",
        },
        outputs={},
    )
    ctx = build_block_context(block, _state_with_parent_context())
    assert ctx.inputs == {
        "metadata.branch": "main",
        "shared_memory.payload": {"id": "payload-1"},
        "results.summary": "draft summary",
        "call_stack": [],
        "workflow_registry": None,
        "observer": None,
    }

    await block.execute(ctx)

    assert child_workflow.received_state is not None
    assert child_workflow.received_state.metadata == {"branch": "main"}
    assert child_workflow.received_state.shared_memory == {"payload": {"id": "payload-1"}}
    assert child_workflow.received_state.results == {"summary": "draft summary"}


@pytest.mark.asyncio
async def test_workflowblock_legacy_mapping_keeps_execution_plumbing_out_of_child_state() -> None:
    """Legacy mode must keep execution plumbing separate from child input data."""
    child_workflow = CapturingWorkflow()
    block = WorkflowBlock(
        block_id="invoke_child",
        child_workflow=child_workflow,
        inputs={"metadata.branch": "metadata.runtime.branch"},
        outputs={},
    )
    governed_ctx = build_block_context(block, _state_with_parent_context())
    ctx = governed_ctx.model_copy(
        update={
            "inputs": {
                **governed_ctx.inputs,
                "call_stack": ["parent_workflow"],
                "workflow_registry": object(),
                "observer": object(),
            }
        }
    )

    await block.execute(ctx)

    assert child_workflow.received_state is not None
    assert child_workflow.received_state.metadata == {"branch": "main"}
    assert child_workflow.received_state.results == {}
    assert child_workflow.received_state.shared_memory == {}


@pytest.mark.asyncio
async def test_execute_block_direct_workflowblock_preserves_governed_declared_inputs() -> None:
    """Direct WorkflowBlock dispatch must not drop inputs resolved by governance."""
    child_workflow = CapturingWorkflow()
    block = WorkflowBlock(
        block_id="invoke_child",
        child_workflow=child_workflow,
        inputs={"value": "metadata.runtime.branch"},
        outputs={},
        interface=_interface("metadata.branch"),
    )
    state = _state_with_parent_context()
    exec_ctx = BlockExecutionContext(
        workflow_name="parent_workflow",
        blocks={},
        call_stack=[],
        workflow_registry=None,
        observer=None,
    )

    await execute_block(block, state, exec_ctx)

    assert child_workflow.received_state is not None
    assert child_workflow.received_state.metadata == {"branch": "main"}
