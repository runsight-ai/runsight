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
async def test_dynamic_injection_with_registry():
    """Dynamic step injection uses a registered factory."""
    from runsight_core.blocks.registry import BlockRegistry

    injected_mock = MockBlock("injected_step", "Injected result")
    terminal_block = MockBlock("terminal", "Terminal output")

    class PlannerBlock(BaseBlock):
        """Simulates EngineeringManagerBlock: writes _new_steps to metadata."""

        def __init__(self) -> None:
            super().__init__("planner")

        async def execute(self, ctx: BlockContext) -> BlockOutput:
            return BlockOutput(
                output="plan generated",
                metadata_updates={
                    "planner_new_steps": [
                        {"step_id": "injected_step", "description": "Do injected work"}
                    ]
                },
                log_entries=[{"role": "system", "content": "[Block planner] PlannerBlock"}],
            )

    wf = Workflow(name="registered_injection_workflow")
    wf.add_block(PlannerBlock())
    wf.add_block(terminal_block)
    wf.add_transition("planner", "terminal")
    wf.add_transition("terminal", None)
    wf.set_entry("planner")

    # Registry with custom factory returning the injected block.
    registry = BlockRegistry()
    registry.register("injected_step", lambda sid, desc: injected_mock)

    state = WorkflowState()
    final_state = await wf.run(state, registry=registry)

    assert injected_mock.executed is True
    assert "injected_step" in final_state.results
    assert terminal_block.executed is True


@pytest.mark.asyncio
async def test_dynamic_injection_missing_registry_raises():
    """Dynamic step injection raises ValueError when registry is missing."""
    terminal_block = MockBlock("terminal", "Terminal output")

    class PlannerBlock(BaseBlock):
        def __init__(self) -> None:
            super().__init__("planner")

        async def execute(self, ctx: BlockContext) -> BlockOutput:
            return BlockOutput(
                output="plan generated",
                metadata_updates={
                    "planner_new_steps": [
                        {
                            "step_id": "injected_step",
                            "description": "Do injected work",
                        }
                    ]
                },
                log_entries=[{"role": "system", "content": "[Block planner] PlannerBlock"}],
            )

    wf = Workflow(name="missing_registry_injection_workflow")
    wf.add_block(PlannerBlock())
    wf.add_block(terminal_block)
    wf.add_transition("planner", "terminal")
    wf.add_transition("terminal", None)
    wf.set_entry("planner")

    state = WorkflowState()
    with pytest.raises(ValueError, match="No factory registered"):
        await wf.run(state, registry=None)


def test_dynamic_injection_missing_step_id():
    """Dynamic injection raises ValueError for missing step_id key."""
    import asyncio

    class BadPlannerBlock(BaseBlock):
        def __init__(self) -> None:
            super().__init__("planner")

        async def execute(self, ctx: BlockContext) -> BlockOutput:
            return BlockOutput(
                output="plan generated",
                metadata_updates={
                    "planner_new_steps": [
                        {"description": "Do injected work"}  # Missing step_id
                    ]
                },
                log_entries=[{"role": "system", "content": "[Block planner] BadPlannerBlock"}],
            )

    wf = Workflow(name="missing_step_id_injection_workflow")
    wf.add_block(BadPlannerBlock())
    wf.add_transition("planner", None)
    wf.set_entry("planner")

    async def run_test() -> None:
        state = WorkflowState()
        with pytest.raises(ValueError, match="missing 'step_id' or 'description'"):
            await wf.run(state)

    asyncio.run(run_test())


def test_dynamic_injection_missing_description():
    """Dynamic injection raises ValueError for missing description key."""
    import asyncio

    class BadPlannerBlock(BaseBlock):
        def __init__(self) -> None:
            super().__init__("planner")

        async def execute(self, ctx: BlockContext) -> BlockOutput:
            return BlockOutput(
                output="plan generated",
                metadata_updates={
                    "planner_new_steps": [
                        {"step_id": "injected_step"}  # Missing description
                    ]
                },
                log_entries=[{"role": "system", "content": "[Block planner] BadPlannerBlock"}],
            )

    wf = Workflow(name="missing_description_injection_workflow")
    wf.add_block(BadPlannerBlock())
    wf.add_transition("planner", None)
    wf.set_entry("planner")

    async def run_test() -> None:
        state = WorkflowState()
        with pytest.raises(ValueError, match="missing 'step_id' or 'description'"):
            await wf.run(state)

    asyncio.run(run_test())
