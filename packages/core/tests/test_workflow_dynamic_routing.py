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


@pytest.mark.asyncio
async def test_dynamic_routing_approved_exit_handle():
    """Workflow routing follows an approved exit_handle."""
    approved_block = MockBlock("approve_path", "Approved output")
    rejected_block = MockBlock("reject_path", "Rejected output")

    class DispatchMock(BaseBlock):
        def __init__(self) -> None:
            super().__init__("dispatch")

        async def execute(self, ctx: BlockContext) -> BlockOutput:
            return BlockOutput(
                output="approved",
                exit_handle="approved",
                log_entries=[{"role": "system", "content": "[Block dispatch] DispatchMock"}],
            )

    wf = Workflow(name="approved_routing_workflow")
    wf.add_block(DispatchMock())
    wf.add_block(approved_block)
    wf.add_block(rejected_block)
    wf.add_conditional_transition(
        "dispatch",
        {"approved": "approve_path", "rejected": "reject_path", "default": "reject_path"},
    )
    wf.add_transition("approve_path", None)
    wf.add_transition("reject_path", None)
    wf.set_entry("dispatch")

    errors = wf.validate()
    assert not errors

    state = WorkflowState()
    await wf.run(state)

    assert approved_block.executed is True
    assert rejected_block.executed is False


@pytest.mark.asyncio
async def test_dynamic_routing_rejected_exit_handle():
    """Workflow routing follows a rejected exit_handle."""
    approved_block = MockBlock("approve_path", "Approved output")
    rejected_block = MockBlock("reject_path", "Rejected output")

    class DispatchMock(BaseBlock):
        def __init__(self) -> None:
            super().__init__("dispatch")

        async def execute(self, ctx: BlockContext) -> BlockOutput:
            return BlockOutput(
                output="rejected",
                exit_handle="rejected",
                log_entries=[{"role": "system", "content": "[Block dispatch] DispatchMock"}],
            )

    wf = Workflow(name="rejected_routing_workflow")
    wf.add_block(DispatchMock())
    wf.add_block(approved_block)
    wf.add_block(rejected_block)
    wf.add_conditional_transition(
        "dispatch",
        {"approved": "approve_path", "rejected": "reject_path", "default": "approve_path"},
    )
    wf.add_transition("approve_path", None)
    wf.add_transition("reject_path", None)
    wf.set_entry("dispatch")

    state = WorkflowState()
    await wf.run(state)

    assert rejected_block.executed is True


@pytest.mark.asyncio
async def test_dynamic_routing_uses_default_target_for_unknown_exit_handle():
    """Workflow.run() routes unknown exit handles through the default target."""
    default_target = MockBlock("default_path", "Default output")
    unknown_path = MockBlock("unknown_path", "Unexpected output")

    class DispatchMockUnknown(BaseBlock):
        def __init__(self) -> None:
            super().__init__("dispatch")

        async def execute(self, ctx: BlockContext) -> BlockOutput:
            return BlockOutput(
                output="unknown_decision",
                exit_handle="unknown_decision",
                log_entries=[{"role": "system", "content": "[Block dispatch] DispatchMockUnknown"}],
            )

    wf = Workflow(name="default_routing_workflow")
    wf.add_block(DispatchMockUnknown())
    wf.add_block(default_target)
    wf.add_block(unknown_path)
    wf.add_conditional_transition(
        "dispatch",
        {"known": "unknown_path", "default": "default_path"},
    )
    wf.add_transition("default_path", None)
    wf.add_transition("unknown_path", None)
    wf.set_entry("dispatch")

    await wf.run(WorkflowState())

    assert default_target.executed is True
    assert unknown_path.executed is False


@pytest.mark.asyncio
async def test_dynamic_routing_raises_key_error_without_default_target():
    """Workflow.run() raises KeyError when a decision has no matching target."""

    class DispatchMockNoDefault(BaseBlock):
        def __init__(self) -> None:
            super().__init__("dispatch")

        async def execute(self, ctx: BlockContext) -> BlockOutput:
            return BlockOutput(
                output="missing",
                exit_handle="missing",
                log_entries=[
                    {"role": "system", "content": "[Block dispatch] DispatchMockNoDefault"}
                ],
            )

    fallback_block = MockBlock("fallback", "Fallback output")

    wf = Workflow(name="missing_default_routing_workflow")
    wf.add_block(DispatchMockNoDefault())
    wf.add_block(fallback_block)
    wf.add_conditional_transition("dispatch", {"only_key": "fallback"})
    wf.add_transition("fallback", None)
    wf.set_entry("dispatch")

    with pytest.raises(KeyError):
        await wf.run(WorkflowState())
