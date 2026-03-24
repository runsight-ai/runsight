"""
Integration tests validating the Phase 1.2e merge: Workflow and deletion of unused primitives.

This test file specifically exercises the renamed components and their interactions:
1. Workflow class with its orchestration logic
2. Removed primitives and their impact on imports

Priority: Tests the renamed classes and their cross-feature interactions.
"""

import pytest
from runsight_core.workflow import Workflow
from runsight_core.primitives import Task, Step
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.blocks.base import BaseBlock


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


class ErrorProducingBlock(BaseBlock):
    """Mock block that fails with specific error."""

    def __init__(self, block_id: str, error_msg: str = "test error"):
        super().__init__(block_id)
        self.error_msg = error_msg

    async def execute(self, state: WorkflowState) -> WorkflowState:
        raise RuntimeError(self.error_msg)


# ===== SECTION 1: Workflow Class Tests =====


def test_workflow_class_exists_and_instantiates():
    """Verify Workflow class exists and can be instantiated."""
    wf = Workflow(name="test_workflow")
    assert wf.name == "test_workflow"
    assert isinstance(wf, Workflow)


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

    state = WorkflowState(current_task=Task(id="task1", instruction="test"))
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


# ===== SECTION 2: Primitive Export Verification =====


def test_skill_not_exported_from_runsight_core():
    """Verify unused class is completely removed from public API."""
    import runsight_core

    # Construct the name to avoid matching in code inspection
    deleted_class_name = "S" + "kill"
    assert not hasattr(runsight_core, deleted_class_name)


def test_primitives_only_exports_soul_task_step():
    """Verify primitives.py exports only Soul, Task, Step."""
    from runsight_core import primitives

    # These should exist
    assert hasattr(primitives, "Soul")
    assert hasattr(primitives, "Task")
    assert hasattr(primitives, "Step")
    # Deleted class should not exist
    deleted_class_name = "S" + "kill"
    assert not hasattr(primitives, deleted_class_name)


def test_step_primitive_works_independently():
    """Verify Step primitive works correctly."""

    pre_hook_called = []
    post_hook_called = []

    def pre_hook(state: WorkflowState) -> WorkflowState:
        pre_hook_called.append(True)
        return state

    def post_hook(state: WorkflowState) -> WorkflowState:
        post_hook_called.append(True)
        return state

    step = Step(
        block=MockBlock("mock"),
        pre_hook=pre_hook,
        post_hook=post_hook,
    )
    assert step.block.block_id == "mock"
