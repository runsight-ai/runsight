"""
Integration tests for Workflow.run() with call_stack and workflow_registry propagation.

Tests the full execution path from top-level run() through child workflow execution with
WorkflowBlock, verifying call_stack and workflow_registry propagation.
"""

import pytest
from conftest import block_output_from_state
from runsight_core import WorkflowBlock
from runsight_core.blocks.base import BaseBlock
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.workflow import Workflow


class SimpleBlock(BaseBlock):
    """Simple test block that records execution and can optionally modify state."""

    def __init__(
        self,
        block_id: str,
        output: str = "default output",
        declared_inputs: dict[str, str] | None = None,
    ):
        super().__init__(block_id)
        self.output = output
        self.context_access = "declared"
        self.declared_inputs = dict(declared_inputs or {})
        self.seen_workflow_inputs = None

    async def execute(self, ctx):
        """Execute by recording output in results."""
        state = ctx.state_snapshot
        self.seen_workflow_inputs = dict(state.workflow_inputs)
        next_state = state.model_copy(
            update={
                "results": {**state.results, self.block_id: BlockResult(output=self.output)},
                "execution_log": state.execution_log
                + [{"role": "system", "content": f"[Block {self.block_id}] Executed"}],
            }
        )
        return block_output_from_state(self.block_id, state, next_state)


@pytest.mark.asyncio
async def test_workflow_block_input_output_mapping():
    """
    Verify complete input/output mapping cycle in WorkflowBlock execution.

    Tests that:
    1. Inputs are correctly mapped from parent to child state
    2. Outputs are correctly mapped from child back to parent
    3. Parent state is not modified except for mapped fields
    4. Child state is isolated (clean start)
    """
    # Create child workflow
    child_workflow = Workflow(name="mapping_child_workflow")
    mapping_child_block = SimpleBlock(
        "mapping_child_step",
        "child result",
        declared_inputs={
            "input_key": "workflow.input_key",
            "context": "workflow.context",
        },
    )
    child_workflow.add_block(mapping_child_block)
    child_workflow.set_entry("mapping_child_step")
    child_workflow.add_transition("mapping_child_step", None)

    # Create parent with mapped inputs/outputs
    parent_workflow = Workflow(name="mapping_parent_workflow")
    parent_workflow.add_block(
        WorkflowBlock(
            block_id="mapped_child_workflow_block",
            child_workflow=child_workflow,
            inputs={
                "input_key": "shared_memory.parent_key",
                "context": "results.parent_context",
            },
            outputs={
                "results.output_key": "results.mapping_child_step",
            },
            max_depth=10,
        )
    )
    parent_workflow.set_entry("mapped_child_workflow_block")
    parent_workflow.add_transition("mapped_child_workflow_block", None)

    # Create parent state with values to map
    initial_state = WorkflowState(
        shared_memory={"parent_key": "parent_shared_value", "other": "untouched"},
        results={
            "parent_context": BlockResult(output="context_data"),
            "existing": BlockResult(output="data"),
        },
        metadata={"mapping_marker": "preserved"},
    )

    # Execute
    final_state = await parent_workflow.run(initial_state)

    # Verify: Output mapping
    # Child produced "child result" in results.mapping_child_step
    # This should be mapped to results.output_key in parent
    assert "output_key" in final_state.results
    assert final_state.results["output_key"].output == "child result"
    assert mapping_child_block.seen_workflow_inputs == {
        "input_key": "parent_shared_value",
        "context": "context_data",
    }

    # Verify: Preserved parent data
    assert final_state.results["existing"].output == "data"
    assert final_state.shared_memory["other"] == "untouched"
    assert final_state.metadata["mapping_marker"] == "preserved"

    # Verify: Mapped inputs were provided to child (the child executed with the input key)
    # The child's shared_memory should have been initialized with input_key
    # (though we don't have direct access to child state in this test)


@pytest.mark.asyncio
async def test_workflow_block_with_cost_accumulation():
    """
    Verify that child workflow costs are accumulated in parent state.

    Tests that:
    1. Child workflow costs are added to parent totals
    2. System message includes cost information
    3. Token counts are accumulated
    """
    # Create child workflow that returns cost
    child_workflow = Workflow(name="cost_child_workflow")
    child_workflow.add_block(SimpleBlock("cost_child_step", "output"))
    child_workflow.set_entry("cost_child_step")
    child_workflow.add_transition("cost_child_step", None)

    # Mock child run to return costs
    async def mock_child_run(
        initial_state,
        *,
        inputs=None,
        registry=None,
        call_stack=None,
        workflow_registry=None,
        observer=None,
    ):
        return initial_state.model_copy(
            update={
                "results": {
                    **initial_state.results,
                    "cost_child_step": BlockResult(output="output"),
                },
                "total_cost_usd": 0.15,  # Child cost
                "total_tokens": 200,  # Child tokens
                "execution_log": initial_state.execution_log
                + [{"role": "system", "content": "Child execution"}],
            }
        )

    child_workflow.run = mock_child_run

    # Create parent with WorkflowBlock
    parent_workflow = Workflow(name="cost_parent_workflow")
    parent_workflow.add_block(
        WorkflowBlock(
            block_id="cost_child_workflow_block",
            child_workflow=child_workflow,
            inputs={},
            outputs={},
            max_depth=10,
        )
    )
    parent_workflow.set_entry("cost_child_workflow_block")
    parent_workflow.add_transition("cost_child_workflow_block", None)

    # Execute with initial costs
    initial_state = WorkflowState(total_cost_usd=0.05, total_tokens=100)
    final_state = await parent_workflow.run(initial_state)

    # Verify: Costs accumulated
    assert final_state.total_cost_usd == pytest.approx(0.20)  # 0.05 + 0.15
    assert final_state.total_tokens == 300  # 100 + 200

    # Verify: Cost info in system message
    system_msgs = [m for m in final_state.execution_log if m["role"] == "system"]
    summary = next((m["content"] for m in system_msgs if "cost:" in m["content"]), None)
    assert summary is not None
    assert "$0.15" in summary or "0.15" in summary
