"""
Integration tests validating the Phase 1.2e merge: Workflow orchestration logic.

Tests the renamed Workflow class and its cross-feature interactions.
"""

import pytest
from runsight_core.blocks.base import BaseBlock
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.workflow import Workflow

# ===== Test Doubles =====


class MockBlock(BaseBlock):
    """Simple mock block for testing Workflow orchestration."""

    def __init__(self, block_id: str, output: str = "result"):
        super().__init__(block_id)
        self.output = output

    async def execute(self, state: WorkflowState) -> WorkflowState:
        return state.model_copy(
            update={
                "results": {**state.results, self.block_id: BlockResult(output=self.output)},
                "execution_log": state.execution_log
                + [{"role": "system", "content": f"[{self.block_id}] executed"}],
            }
        )


# ===== Workflow Class Tests =====


def test_workflow_fluent_api_chain():
    """Test that Workflow fluent API works correctly (renamed class)."""
    wf = Workflow(name="chain_test")
    block_a = MockBlock("a")
    block_b = MockBlock("b")
    block_c = MockBlock("c")

    # Fluent API should return self for chaining
    result = (
        wf.add_block(block_a)
        .add_block(block_b)
        .add_block(block_c)
        .set_entry("a")
        .add_transition("a", "b")
        .add_transition("b", "c")
    )

    assert result is wf
    assert len(wf._blocks) == 3
    assert len(wf._transitions) == 2


@pytest.mark.asyncio
async def test_workflow_execution_renamed_class():
    """Test Workflow.run() method works correctly after rename."""
    wf = Workflow(name="execution_test")
    block_a = MockBlock("a", "output_a")
    block_b = MockBlock("b", "output_b")

    wf.add_block(block_a).add_block(block_b).set_entry("a").add_transition("a", "b")

    state = WorkflowState()
    final_state = await wf.run(state)

    # Verify both blocks executed
    assert "a" in final_state.results
    assert "b" in final_state.results
    assert final_state.results["a"].output == "output_a"
    assert final_state.results["b"].output == "output_b"


def test_workflow_terminal_block_no_transition():
    """Verify terminal blocks (no outgoing transition) work in Workflow."""
    wf = Workflow(name="terminal_test")
    block_a = MockBlock("a")
    block_b = MockBlock("b")

    wf.add_block(block_a).add_block(block_b).set_entry("a").add_transition("a", "b")
    # b is terminal (no transition defined)
    errors = wf.validate()
    assert len(errors) == 0
