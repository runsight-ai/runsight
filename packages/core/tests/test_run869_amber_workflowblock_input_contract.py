"""RUN-869 Amber regressions for WorkflowBlock child input contracts."""

from __future__ import annotations

from typing import Any

import pytest
from runsight_core.block_io import build_block_context
from runsight_core.blocks.workflow_block import WorkflowBlock
from runsight_core.state import WorkflowState
from runsight_core.yaml.schema import WorkflowInputDef


class ChildWorkflowSpy:
    def __init__(self, input_schema: dict[str, WorkflowInputDef]) -> None:
        self.name = "run869_child"
        self.input_schema = input_schema
        self.received_state: WorkflowState | None = None
        self.received_kwargs: dict[str, Any] | None = None

    async def run(self, state: WorkflowState, **kwargs: Any) -> WorkflowState:
        self.received_state = state
        self.received_kwargs = kwargs
        return state


def _parent_state() -> WorkflowState:
    return WorkflowState(
        shared_memory={
            "query": "climate brief",
            "limit": "not-a-number",
        }
    )


@pytest.mark.asyncio
async def test_workflowblock_rejects_unknown_child_input_name_before_child_execution() -> None:
    child = ChildWorkflowSpy(
        {
            "query": WorkflowInputDef(type="string"),
        }
    )
    block = WorkflowBlock(
        block_id="invoke_child",
        child_workflow=child,
        inputs={"typo_query": "shared_memory.query"},
        outputs={},
    )
    ctx = build_block_context(block, _parent_state())

    with pytest.raises(ValueError, match="typo_query|not declared|unknown"):
        await block.execute(ctx)

    assert child.received_state is None
    assert child.received_kwargs is None


@pytest.mark.asyncio
async def test_workflowblock_rejects_missing_required_child_input_before_child_execution() -> None:
    child = ChildWorkflowSpy(
        {
            "query": WorkflowInputDef(type="string", required=True),
        }
    )
    block = WorkflowBlock(
        block_id="invoke_child",
        child_workflow=child,
        inputs={},
        outputs={},
    )
    ctx = build_block_context(block, _parent_state())

    with pytest.raises(ValueError, match="query|required|missing"):
        await block.execute(ctx)

    assert child.received_state is None
    assert child.received_kwargs is None


@pytest.mark.asyncio
async def test_workflowblock_rejects_child_input_type_mismatch_before_child_execution() -> None:
    child = ChildWorkflowSpy(
        {
            "limit": WorkflowInputDef(type="number", required=True),
        }
    )
    block = WorkflowBlock(
        block_id="invoke_child",
        child_workflow=child,
        inputs={"limit": "shared_memory.limit"},
        outputs={},
    )
    ctx = build_block_context(block, _parent_state())

    with pytest.raises(ValueError, match="limit|number|type"):
        await block.execute(ctx)

    assert child.received_state is None
    assert child.received_kwargs is None


@pytest.mark.asyncio
async def test_workflowblock_applies_child_defaults_to_valid_invocation_inputs() -> None:
    child = ChildWorkflowSpy(
        {
            "query": WorkflowInputDef(type="string", required=True),
            "mode": WorkflowInputDef(type="string", required=False, default="summary"),
        }
    )
    block = WorkflowBlock(
        block_id="invoke_child",
        child_workflow=child,
        inputs={"query": "shared_memory.query"},
        outputs={},
    )
    ctx = build_block_context(block, _parent_state())

    await block.execute(ctx)

    assert child.received_state is not None
    assert child.received_state.workflow_inputs == {
        "query": "climate brief",
        "mode": "summary",
    }
    assert child.received_kwargs is not None
    assert child.received_kwargs["inputs"] == {
        "query": "climate brief",
        "mode": "summary",
    }
