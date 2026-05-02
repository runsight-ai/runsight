"""Workflow validation, routing, execution, and dynamic injection tests."""

import pytest
from runsight_core.block_io import BlockContext, BlockOutput
from runsight_core.blocks.base import BaseBlock
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.workflow import Workflow


class MockBlock(BaseBlock):
    """Test double for BaseBlock."""

    def __init__(self, block_id: str, output: str = "mock output"):
        super().__init__(block_id)
        self.output = output
        self.executed = False

    async def execute(self, ctx: BlockContext) -> BlockOutput:
        self.executed = True
        return BlockOutput(
            output=self.output,
            log_entries=[{"role": "system", "content": f"[Block {self.block_id}] Executed"}],
        )


@pytest.mark.asyncio
async def test_workflow_linear_execution():
    """Workflow executes a linear flow and records block results."""
    wf = Workflow(name="linear_workflow")

    first_block = MockBlock("first", "Output A")
    second_block = MockBlock("second", "Output B")
    third_block = MockBlock("third", "Output C")

    wf.add_block(first_block)
    wf.add_block(second_block)
    wf.add_block(third_block)
    wf.add_transition("first", "second")
    wf.add_transition("second", "third")
    wf.add_transition("third", None)
    wf.set_entry("first")

    # Validate before run
    errors = wf.validate()
    assert not errors

    # Execute
    initial_state = WorkflowState()
    final_state = await wf.run(initial_state)

    # Verify execution order
    assert first_block.executed
    assert second_block.executed
    assert third_block.executed

    # Verify results accumulated without synthetic workflow input material.
    assert final_state.results["first"] == BlockResult(output="Output A")
    assert final_state.results["second"] == BlockResult(output="Output B")
    assert final_state.results["third"] == BlockResult(output="Output C")
    assert "workflow" not in final_state.results

    # Verify messages appended
    assert len(final_state.execution_log) == 3


@pytest.mark.asyncio
async def test_run_without_registry_executes_static_workflow():
    """run(state) without a registry executes static workflows."""
    wf = Workflow(name="static_workflow_without_registry")
    first_block = MockBlock("first", "Output A")
    second_block = MockBlock("second", "Output B")

    wf.add_block(first_block)
    wf.add_block(second_block)
    wf.add_transition("first", "second")
    wf.add_transition("second", None)
    wf.set_entry("first")

    initial_state = WorkflowState()
    final_state = await wf.run(initial_state)

    assert first_block.executed
    assert second_block.executed
    assert final_state.results["first"] == BlockResult(output="Output A")
    assert final_state.results["second"] == BlockResult(output="Output B")
    assert "workflow" not in final_state.results
