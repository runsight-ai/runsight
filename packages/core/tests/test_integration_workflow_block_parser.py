"""Smoke coverage for WorkflowBlock parser/schema and runtime wiring."""

from unittest.mock import AsyncMock

import pytest
from pydantic import TypeAdapter
from runsight_core import WorkflowBlock
from runsight_core.block_io import apply_block_output, build_block_context
from runsight_core.blocks._registry import BLOCK_BUILDER_REGISTRY
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.yaml.registry import WorkflowRegistry
from runsight_core.yaml.schema import BlockDef, RunsightWorkflowFile


async def _exec(block, state, **extra_inputs):
    ctx = build_block_context(block, state)
    if extra_inputs:
        ctx = ctx.model_copy(update={"inputs": {**ctx.inputs, **extra_inputs}})
    output = await block.execute(ctx)
    return apply_block_output(state, block.block_id, output)


def test_workflow_block_schema_and_registry_smoke():
    assert "workflow" in BLOCK_BUILDER_REGISTRY

    block_def = TypeAdapter(BlockDef).validate_python(
        {
            "type": "workflow",
            "workflow_ref": "child_analysis",
            "inputs": {"topic": "shared_memory.research_topic"},
            "outputs": {"results.analysis": "results.final"},
            "max_depth": 5,
        }
    )
    assert block_def.workflow_ref == "child_analysis"
    assert block_def.inputs == {"topic": "shared_memory.research_topic"}

    registry = WorkflowRegistry()
    registry.register(
        "child_analysis",
        RunsightWorkflowFile.model_validate(
            {
                "version": "1.0",
                "id": "child_analysis",
                "kind": "workflow",
                "workflow": {
                    "id": "child_analysis",
                    "kind": "workflow",
                    "name": "child_analysis",
                    "entry": "analyze",
                },
                "blocks": {"analyze": {"type": "linear", "soul_ref": "researcher"}},
                "transitions": [{"from": "analyze", "to": None}],
            }
        ),
    )
    assert registry.get("child_analysis").workflow.name == "child_analysis"


@pytest.mark.asyncio
async def test_workflow_block_isolates_child_state_and_maps_outputs_with_registry():
    child_workflow = AsyncMock()
    child_workflow.name = "child_analysis"
    child_workflow.run = AsyncMock(
        return_value=WorkflowState(
            results={"final": BlockResult(output="child output")},
            total_cost_usd=0.05,
            total_tokens=50,
        )
    )
    block = WorkflowBlock(
        block_id="child_invocation",
        child_workflow=child_workflow,
        inputs={"topic": "shared_memory.topic"},
        outputs={"results.analysis": "results.final"},
    )
    parent_state = WorkflowState(
        shared_memory={"topic": "integration wiring"},
        results={"existing": BlockResult(output="keep")},
        total_cost_usd=0.10,
        total_tokens=100,
    )
    registry = WorkflowRegistry()

    result = await _exec(block, parent_state, workflow_registry=registry)

    child_state = child_workflow.run.call_args.args[0]
    call_kwargs = child_workflow.run.call_args.kwargs
    assert child_state.results == {}
    assert call_kwargs["inputs"] == {"topic": "integration wiring"}
    assert call_kwargs["workflow_registry"] is registry
    assert call_kwargs["call_stack"] == ["child_analysis"]
    assert result.results["existing"] == BlockResult(output="keep")
    assert result.results["analysis"] == BlockResult(output="child output")
    assert result.total_cost_usd == pytest.approx(0.15)
    assert result.total_tokens == 150
