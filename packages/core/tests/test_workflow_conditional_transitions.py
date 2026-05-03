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


def test_add_conditional_transition_fluent_return():
    """add_conditional_transition() returns self for fluent chaining."""
    wf = Workflow(name="conditional_transition_workflow")
    wf.add_block(MockBlock("dispatch"))
    wf.add_block(MockBlock("approved_path"))

    result = wf.add_conditional_transition("dispatch", {"approved": "approved_path"})
    assert result is wf


def test_add_conditional_transition_conflict_with_plain():
    """add_conditional_transition() raises ValueError when plain transition exists."""
    wf = Workflow(name="plain_transition_conflict_workflow")
    wf.add_block(MockBlock("router"))
    wf.add_block(MockBlock("target"))

    wf.add_transition("router", "target")

    with pytest.raises(ValueError, match="already has a plain transition"):
        wf.add_conditional_transition("router", {"approved": "target"})


def test_add_transition_conflict_with_conditional():
    """add_transition() raises ValueError when conditional transition exists."""
    wf = Workflow(name="conditional_transition_conflict_workflow")
    wf.add_block(MockBlock("router"))
    wf.add_block(MockBlock("target"))

    wf.add_conditional_transition("router", {"approved": "target"})

    with pytest.raises(ValueError, match="already has a conditional transition"):
        wf.add_transition("router", "target")


def test_add_conditional_transition_duplicate():
    """add_conditional_transition() raises ValueError if called twice for a source."""
    wf = Workflow(name="duplicate_conditional_transition_workflow")
    wf.add_block(MockBlock("dispatch"))
    wf.add_block(MockBlock("approved_path"))
    wf.add_block(MockBlock("rejected_path"))

    wf.add_conditional_transition("dispatch", {"approved": "approved_path"})

    with pytest.raises(ValueError, match="already has a conditional transition"):
        wf.add_conditional_transition("dispatch", {"rejected": "rejected_path"})


def test_validate_conditional_target_not_registered():
    """validate() returns errors containing unregistered conditional targets."""
    wf = Workflow(name="unregistered_conditional_target_workflow")
    wf.add_block(MockBlock("dispatch"))
    wf.add_conditional_transition("dispatch", {"approved": "nonexistent_block"})
    wf.set_entry("dispatch")

    errors = wf.validate()
    assert len(errors) > 0
    assert any("nonexistent_block" in e for e in errors)


def test_detect_cycle_with_conditional_transitions():
    """_detect_cycle() traverses conditional transition targets."""
    wf = Workflow(name="conditional_cycle_workflow")
    wf.add_block(MockBlock("dispatch"))
    wf.add_block(MockBlock("action"))

    # Create a cycle through a conditional target and a plain transition.
    wf.add_conditional_transition("dispatch", {"approved": "action", "rejected": "dispatch"})
    wf.add_transition("action", "dispatch")
    wf.set_entry("dispatch")

    errors = wf.validate()
    assert any("Cycle detected" in e for e in errors)


def test_resolve_next_uses_block_result_exit_handle():
    """_resolve_next() reads exit_handle from BlockResult."""
    wf = Workflow(name="resolve_exit_handle_workflow")
    wf.add_block(MockBlock("dispatch"))
    wf.add_block(MockBlock("approved_path"))
    wf.add_conditional_transition("dispatch", {"approved": "approved_path"})

    state = WorkflowState(
        results={"dispatch": BlockResult(output="approved", exit_handle="approved")}
    )
    next_id = wf._resolve_next("dispatch", state)
    assert next_id == "approved_path"


def test_resolve_next_default_fallback():
    """_resolve_next() uses condition_map['default'] when decision is not explicit."""
    wf = Workflow(name="resolve_default_fallback_workflow")
    wf.add_block(MockBlock("dispatch"))
    wf.add_block(MockBlock("default_path"))
    wf.add_conditional_transition(
        "dispatch", {"approved": "approved_path", "default": "default_path"}
    )

    # Unknown decision value
    state = WorkflowState(
        results={"dispatch": BlockResult(output="unknown", exit_handle="unknown")}
    )
    next_id = wf._resolve_next("dispatch", state)
    assert next_id == "default_path"


def test_resolve_next_no_default_raises_key_error():
    """_resolve_next() raises KeyError when decision has no default target."""
    wf = Workflow(name="resolve_missing_default_workflow")
    wf.add_block(MockBlock("dispatch"))
    wf.add_block(MockBlock("approved_path"))
    wf.add_conditional_transition("dispatch", {"approved": "approved_path"})

    # Unknown decision, no default
    state = WorkflowState(
        results={"dispatch": BlockResult(output="unknown", exit_handle="unknown")}
    )
    with pytest.raises(KeyError):
        wf._resolve_next("dispatch", state)
