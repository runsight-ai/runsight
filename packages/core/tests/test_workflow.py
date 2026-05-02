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
