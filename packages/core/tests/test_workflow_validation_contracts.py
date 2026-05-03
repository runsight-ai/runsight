"""Workflow validation, routing, execution, and dynamic injection tests."""

import pytest
from runsight_core.block_io import BlockContext, BlockOutput
from runsight_core.blocks.base import BaseBlock
from runsight_core.state import WorkflowState
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


def test_workflow_validation_errors():
    """Workflow detects missing entry and unknown transition targets."""
    wf = Workflow(name="validation_errors_workflow")

    # Error: No entry block set
    errors = wf.validate()
    assert len(errors) == 1
    assert "No entry block set" in errors[0]

    # Error: Entry block doesn't exist
    wf.set_entry("nonexistent")
    errors = wf.validate()
    assert any("not found" in e for e in errors)

    # Error: Transition to missing target block.
    wf.add_block(MockBlock("source"))
    wf.add_transition("source", "missing_target")
    wf.set_entry("source")
    errors = wf.validate()
    assert any("unknown block 'missing_target'" in e for e in errors)


def test_workflow_cycle_detection():
    """Workflow detects plain-transition cycles."""
    wf = Workflow(name="cyclic_workflow")
    wf.add_block(MockBlock("draft"))
    wf.add_block(MockBlock("review"))
    wf.add_block(MockBlock("publish"))

    # Create cycle through three workflow blocks.
    wf.add_transition("draft", "review")
    wf.add_transition("review", "publish")
    wf.add_transition("publish", "draft")
    wf.set_entry("draft")

    errors = wf.validate()
    assert len(errors) == 1
    assert "Cycle detected" in errors[0]


@pytest.mark.asyncio
async def test_workflow_run_validates():
    """Workflow.run() validates before execution."""
    wf = Workflow(name="invalid_workflow")
    # No blocks, no entry -> invalid

    with pytest.raises(ValueError, match="Cannot run invalid workflow"):
        await wf.run(WorkflowState())


def test_workflow_terminal_transition():
    """Terminal blocks use to_block_id=None."""
    wf = Workflow(name="terminal_workflow")
    wf.add_block(MockBlock("terminal"))
    wf.add_transition("terminal", None)

    # Verify no entry in _transitions
    assert "terminal" not in wf._transitions


def test_workflow_duplicate_block_id():
    """Workflow raises ValueError for duplicate block IDs."""
    wf = Workflow(name="duplicate_block_workflow")
    wf.add_block(MockBlock("writer"))

    with pytest.raises(ValueError, match="already exists"):
        wf.add_block(MockBlock("writer"))


def test_workflow_duplicate_transition():
    """Workflow raises ValueError for duplicate transitions (single-path only)."""
    wf = Workflow(name="duplicate_transition_workflow")
    wf.add_block(MockBlock("router"))
    wf.add_block(MockBlock("first_target"))
    wf.add_block(MockBlock("second_target"))

    wf.add_transition("router", "first_target")

    with pytest.raises(ValueError, match="already has transition"):
        wf.add_transition("router", "second_target")


def test_workflow_fluent_chain_supports_terminal_block_validation():
    """Fluent Workflow setup returns self and accepts a final block without an outgoing edge."""
    wf = Workflow(name="fluent_terminal_workflow")
    first = MockBlock("first")
    second = MockBlock("second")
    terminal = MockBlock("terminal")

    result = (
        wf.add_block(first)
        .add_block(second)
        .add_block(terminal)
        .set_entry("first")
        .add_transition("first", "second")
        .add_transition("second", "terminal")
    )

    assert result is wf
    assert wf.validate() == []
    assert "terminal" not in wf._transitions


# ============================================================================
# Conditional transition behavior
# ============================================================================
