"""Smoke coverage for WorkflowBlock sequencing with another block type."""

import pytest
from conftest import block_output_from_state
from runsight_core import LinearBlock, WorkflowBlock
from runsight_core.blocks.base import BaseBlock
from runsight_core.primitives import Soul
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.workflow import Workflow


class EchoBlock(BaseBlock):
    def __init__(self, block_id: str, description: str) -> None:
        super().__init__(block_id)
        self.description = description

    async def execute(self, ctx):
        state = ctx.state_snapshot
        next_state = state.model_copy(
            update={
                "results": {**state.results, self.block_id: BlockResult(output=self.description)},
                "execution_log": state.execution_log
                + [
                    {
                        "role": "system",
                        "content": f"[Block {self.block_id}] EchoBlock: {self.description}",
                    }
                ],
            }
        )
        return block_output_from_state(self.block_id, state, next_state)


class MockRunner:
    def __init__(self):
        self.executions = []
        self.model_name = None

    async def execute(self, instruction: str, context, soul: Soul, messages=None, **kwargs):
        self.executions.append((instruction, soul.id))

        class MockResult:
            output = f"Result from {soul.id}"
            cost_usd = 0.01
            total_tokens = 10
            soul_id = soul.id
            exit_handle = None

        return MockResult()


@pytest.mark.asyncio
async def test_workflow_block_can_sequence_into_linear_block():
    child_workflow = Workflow(name="linear_sequence_child_workflow")
    child_workflow.add_block(EchoBlock("analysis_sequence_step", "analysis result"))
    child_workflow.set_entry("analysis_sequence_step")
    child_workflow.add_transition("analysis_sequence_step", None)

    parent_workflow = Workflow(name="linear_sequence_parent_workflow")
    workflow_block = WorkflowBlock(
        block_id="analysis_workflow_block",
        child_workflow=child_workflow,
        inputs={},
        outputs={"results.analysis_output": "results.analysis_sequence_step"},
        max_depth=10,
    )
    runner = MockRunner()
    final_step = LinearBlock(
        block_id="final_linear_step",
        soul=Soul(
            id="sequence_manager_soul",
            kind="soul",
            name="Sequence Manager Soul",
            role="Manager",
            system_prompt="Manage",
        ),
        runner=runner,
    )
    parent_workflow.add_block(workflow_block).add_block(final_step)
    parent_workflow.set_entry("analysis_workflow_block")
    parent_workflow.add_transition("analysis_workflow_block", "final_linear_step")
    parent_workflow.add_transition("final_linear_step", None)

    final_state = await parent_workflow.run(WorkflowState())

    assert final_state.results["analysis_output"].output == "analysis result"
    assert final_state.results["analysis_workflow_block"].exit_handle == "completed"
    assert final_state.results["final_linear_step"].output == "Result from sequence_manager_soul"
    assert final_state.total_cost_usd >= 0.01
    assert runner.executions == [("", "sequence_manager_soul")]
