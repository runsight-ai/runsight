"""
Tests for Workflow state machine and validation.
"""

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
    """AC-9: Workflow detects validation errors."""
    wf = Workflow(name="test_wf")

    # Error: No entry block set
    errors = wf.validate()
    assert len(errors) == 1
    assert "No entry block set" in errors[0]

    # Error: Entry block doesn't exist
    wf.set_entry("nonexistent")
    errors = wf.validate()
    assert any("not found" in e for e in errors)

    # Error: Transition to nonexistent block
    wf.add_block(MockBlock("a"))
    wf.add_transition("a", "b")  # b doesn't exist
    wf.set_entry("a")
    errors = wf.validate()
    assert any("unknown block 'b'" in e for e in errors)


def test_workflow_cycle_detection():
    """AC-11: Workflow detects cycles."""
    wf = Workflow(name="cyclic_wf")
    wf.add_block(MockBlock("a"))
    wf.add_block(MockBlock("b"))
    wf.add_block(MockBlock("c"))

    # Create cycle: a -> b -> c -> a
    wf.add_transition("a", "b")
    wf.add_transition("b", "c")
    wf.add_transition("c", "a")
    wf.set_entry("a")

    errors = wf.validate()
    assert len(errors) == 1
    assert "Cycle detected" in errors[0]


@pytest.mark.asyncio
async def test_workflow_linear_execution():
    """AC-10: Workflow executes linear flow."""
    wf = Workflow(name="linear_wf")

    block_a = MockBlock("a", "Output A")
    block_b = MockBlock("b", "Output B")
    block_c = MockBlock("c", "Output C")

    wf.add_block(block_a)
    wf.add_block(block_b)
    wf.add_block(block_c)
    wf.add_transition("a", "b")
    wf.add_transition("b", "c")
    wf.add_transition("c", None)  # Terminal
    wf.set_entry("a")

    # Validate before run
    errors = wf.validate()
    assert not errors

    # Execute
    initial_state = WorkflowState()
    final_state = await wf.run(initial_state)

    # Verify execution order
    assert block_a.executed
    assert block_b.executed
    assert block_c.executed

    # Verify results accumulated (workflow seed key is always present)
    assert final_state.results["a"] == BlockResult(output="Output A")
    assert final_state.results["b"] == BlockResult(output="Output B")
    assert final_state.results["c"] == BlockResult(output="Output C")
    assert "workflow" in final_state.results

    # Verify messages appended
    assert len(final_state.execution_log) == 3


@pytest.mark.asyncio
async def test_workflow_run_validates():
    """Workflow.run() validates before execution."""
    wf = Workflow(name="invalid_wf")
    # No blocks, no entry -> invalid

    with pytest.raises(ValueError, match="Cannot run invalid workflow"):
        await wf.run(WorkflowState())


def test_workflow_terminal_transition():
    """Terminal blocks use to_block_id=None (tech lead issue #1)."""
    wf = Workflow(name="terminal_wf")
    wf.add_block(MockBlock("a"))
    wf.add_transition("a", None)  # Mark as terminal

    # Verify no entry in _transitions
    assert "a" not in wf._transitions


def test_workflow_duplicate_block_id():
    """Workflow raises ValueError for duplicate block IDs."""
    wf = Workflow(name="test_wf")
    wf.add_block(MockBlock("a"))

    with pytest.raises(ValueError, match="already exists"):
        wf.add_block(MockBlock("a"))


def test_workflow_duplicate_transition():
    """Workflow raises ValueError for duplicate transitions (single-path only)."""
    wf = Workflow(name="test_wf")
    wf.add_block(MockBlock("a"))
    wf.add_block(MockBlock("b"))
    wf.add_block(MockBlock("c"))

    wf.add_transition("a", "b")

    with pytest.raises(ValueError, match="already has transition"):
        wf.add_transition("a", "c")


# ============================================================================
# Tests for Conditional Transitions (AC-2 through AC-10)
# ============================================================================


def test_add_conditional_transition_fluent_return():
    """AC-5: add_conditional_transition() returns self for fluent chaining."""
    wf = Workflow(name="test_wf")
    wf.add_block(MockBlock("dispatch"))
    wf.add_block(MockBlock("path_a"))

    result = wf.add_conditional_transition("dispatch", {"yes": "path_a"})
    assert result is wf


def test_add_conditional_transition_conflict_with_plain():
    """AC-2: add_conditional_transition() raises ValueError when plain transition exists."""
    wf = Workflow(name="test_wf")
    wf.add_block(MockBlock("r"))
    wf.add_block(MockBlock("x"))

    # Add plain transition first
    wf.add_transition("r", "x")

    # Try to add conditional transition (should fail)
    with pytest.raises(ValueError, match="already has a plain transition"):
        wf.add_conditional_transition("r", {"yes": "x"})


def test_add_transition_conflict_with_conditional():
    """AC-3: add_transition() raises ValueError when conditional transition exists."""
    wf = Workflow(name="test_wf")
    wf.add_block(MockBlock("r"))
    wf.add_block(MockBlock("x"))

    # Add conditional transition first
    wf.add_conditional_transition("r", {"yes": "x"})

    # Try to add plain transition (should fail)
    with pytest.raises(ValueError, match="already has a conditional transition"):
        wf.add_transition("r", "x")


def test_add_conditional_transition_duplicate():
    """AC-4: add_conditional_transition() raises ValueError if called twice for same from_step_id."""
    wf = Workflow(name="test_wf")
    wf.add_block(MockBlock("dispatch"))
    wf.add_block(MockBlock("path_a"))
    wf.add_block(MockBlock("path_b"))

    wf.add_conditional_transition("dispatch", {"yes": "path_a"})

    # Try to add another conditional transition for same source
    with pytest.raises(ValueError, match="already has a conditional transition"):
        wf.add_conditional_transition("dispatch", {"no": "path_b"})


def test_validate_conditional_target_not_registered():
    """AC-6: validate() returns error list containing unregistered target block ID string."""
    wf = Workflow(name="test_wf")
    wf.add_block(MockBlock("dispatch"))
    wf.add_conditional_transition("dispatch", {"yes": "nonexistent_block"})
    wf.set_entry("dispatch")

    errors = wf.validate()
    assert len(errors) > 0
    assert any("nonexistent_block" in e for e in errors)


def test_detect_cycle_with_conditional_transitions():
    """AC-7: _detect_cycle() traverses conditional transition targets."""
    wf = Workflow(name="cyclic_wf")
    wf.add_block(MockBlock("dispatch"))
    wf.add_block(MockBlock("action"))

    # Create cycle through conditional transition: dispatch -[yes]-> action -plain-> dispatch
    wf.add_conditional_transition("dispatch", {"yes": "action", "no": "dispatch"})
    wf.add_transition("action", "dispatch")
    wf.set_entry("dispatch")

    errors = wf.validate()
    assert any("Cycle detected" in e for e in errors)


def test_resolve_next_global_key():
    """AC-8: _resolve_next() reads exit_handle from BlockResult."""
    wf = Workflow(name="test_wf")
    wf.add_block(MockBlock("dispatch"))
    wf.add_block(MockBlock("path_a"))
    wf.add_conditional_transition("dispatch", {"approved": "path_a"})

    state = WorkflowState(
        results={"dispatch": BlockResult(output="approved", exit_handle="approved")}
    )
    next_id = wf._resolve_next("dispatch", state)
    assert next_id == "path_a"


def test_resolve_next_block_scoped_key_fallback():
    """AC-8: _resolve_next() reads exit_handle from BlockResult (block-scoped)."""
    wf = Workflow(name="test_wf")
    wf.add_block(MockBlock("dispatch"))
    wf.add_block(MockBlock("path_a"))
    wf.add_conditional_transition("dispatch", {"approved": "path_a"})

    # exit_handle set on BlockResult (replaces block-scoped metadata key)
    state = WorkflowState(
        results={"dispatch": BlockResult(output="approved", exit_handle="approved")}
    )
    next_id = wf._resolve_next("dispatch", state)
    assert next_id == "path_a"


def test_resolve_next_default_fallback():
    """AC-10: _resolve_next() uses condition_map['default'] when decision not explicit key."""
    wf = Workflow(name="test_wf")
    wf.add_block(MockBlock("dispatch"))
    wf.add_block(MockBlock("default_path"))
    wf.add_conditional_transition("dispatch", {"yes": "path_a", "default": "default_path"})

    # Unknown decision value
    state = WorkflowState(
        results={"dispatch": BlockResult(output="unknown", exit_handle="unknown")}
    )
    next_id = wf._resolve_next("dispatch", state)
    assert next_id == "default_path"


def test_resolve_next_no_default_raises_key_error():
    """AC-9: _resolve_next() raises KeyError when decision not in map and no 'default'."""
    wf = Workflow(name="test_wf")
    wf.add_block(MockBlock("dispatch"))
    wf.add_block(MockBlock("path_a"))
    wf.add_conditional_transition("dispatch", {"yes": "path_a"})

    # Unknown decision, no default
    state = WorkflowState(
        results={"dispatch": BlockResult(output="unknown", exit_handle="unknown")}
    )
    with pytest.raises(KeyError):
        wf._resolve_next("dispatch", state)


@pytest.mark.asyncio
async def test_dynamic_routing_global_decision():
    """Test conditional routing with exit_handle on BlockResult."""
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

    wf = Workflow(name="routing_test")
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
async def test_dynamic_routing_block_scoped_decision():
    """Test conditional routing with block-scoped exit_handle on BlockResult."""
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

    wf = Workflow(name="routing_test")
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
    """Test dynamic step injection with custom registry."""
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

    wf = Workflow(name="injection_test")
    wf.add_block(PlannerBlock())
    wf.add_block(terminal_block)
    wf.add_transition("planner", "terminal")
    wf.add_transition("terminal", None)
    wf.set_entry("planner")

    # Registry with custom factory returning our injected_mock
    registry = BlockRegistry()
    registry.register("injected_step", lambda sid, desc: injected_mock)

    state = WorkflowState()
    final_state = await wf.run(state, registry=registry)

    assert injected_mock.executed is True
    assert "injected_step" in final_state.results
    assert terminal_block.executed is True


@pytest.mark.asyncio
async def test_dynamic_injection_placeholder_fallback():
    """Test dynamic step injection raises ValueError when registry is None."""
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

    wf = Workflow(name="injection_test")
    wf.add_block(PlannerBlock())
    wf.add_block(terminal_block)
    wf.add_transition("planner", "terminal")
    wf.add_transition("terminal", None)
    wf.set_entry("planner")

    state = WorkflowState()
    with pytest.raises(ValueError, match="No factory registered"):
        await wf.run(state, registry=None)


def test_dynamic_injection_missing_step_id():
    """Test dynamic injection raises ValueError for missing 'step_id' key."""
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

    wf = Workflow(name="injection_test")
    wf.add_block(BadPlannerBlock())
    wf.add_transition("planner", None)
    wf.set_entry("planner")

    async def run_test() -> None:
        state = WorkflowState()
        with pytest.raises(ValueError, match="missing 'step_id' or 'description'"):
            await wf.run(state)

    asyncio.run(run_test())


def test_dynamic_injection_missing_description():
    """Test dynamic injection raises ValueError for missing 'description' key."""
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

    wf = Workflow(name="injection_test")
    wf.add_block(BadPlannerBlock())
    wf.add_transition("planner", None)
    wf.set_entry("planner")

    async def run_test() -> None:
        state = WorkflowState()
        with pytest.raises(ValueError, match="missing 'step_id' or 'description'"):
            await wf.run(state)

    asyncio.run(run_test())


@pytest.mark.asyncio
async def test_run_backward_compatible_without_registry():
    """AC-11: run(state) without registry parameter continues to work."""
    wf = Workflow(name="simple_wf")
    block_a = MockBlock("a", "Output A")
    block_b = MockBlock("b", "Output B")

    wf.add_block(block_a)
    wf.add_block(block_b)
    wf.add_transition("a", "b")
    wf.add_transition("b", None)
    wf.set_entry("a")

    # Call without registry parameter (backward compatible)
    initial_state = WorkflowState()
    final_state = await wf.run(initial_state)

    assert block_a.executed
    assert block_b.executed
    assert final_state.results["a"] == BlockResult(output="Output A")
    assert final_state.results["b"] == BlockResult(output="Output B")
    assert "workflow" in final_state.results


@pytest.mark.asyncio
async def test_dynamic_routing():
    """AC-3: Conditional routing branches on BlockResult.exit_handle."""
    # ── Scenario 1: exit_handle = "approved" ───────────────
    approved_block = MockBlock("approve_path", "Approved output")
    rejected_block = MockBlock("reject_path", "Rejected output")

    # Router mock: sets exit_handle on BlockResult
    class DispatchMock(BaseBlock):
        def __init__(self) -> None:
            super().__init__("dispatch")

        async def execute(self, ctx: BlockContext) -> BlockOutput:
            return BlockOutput(
                output="approved",
                exit_handle="approved",
                log_entries=[{"role": "system", "content": "[Block dispatch] DispatchMock"}],
            )

    wf = Workflow(name="routing_test")
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
    _ = await wf.run(state)

    assert approved_block.executed is True
    assert rejected_block.executed is False

    # ── Scenario 2: Block-scoped exit_handle ─────────────────────
    approved_block2 = MockBlock("approve_path2", "Approved2")
    rejected_block2 = MockBlock("reject_path2", "Rejected2")

    class DispatchMockScoped(BaseBlock):
        def __init__(self) -> None:
            super().__init__("dispatch2")

        async def execute(self, ctx: BlockContext) -> BlockOutput:
            return BlockOutput(
                output="rejected",
                exit_handle="rejected",
                log_entries=[{"role": "system", "content": "[Block dispatch2] DispatchMockScoped"}],
            )

    wf2 = Workflow(name="routing_test2")
    wf2.add_block(DispatchMockScoped())
    wf2.add_block(approved_block2)
    wf2.add_block(rejected_block2)
    wf2.add_conditional_transition(
        "dispatch2",
        {"approved": "approve_path2", "rejected": "reject_path2", "default": "approve_path2"},
    )
    wf2.add_transition("approve_path2", None)
    wf2.add_transition("reject_path2", None)
    wf2.set_entry("dispatch2")

    state2 = WorkflowState()
    _ = await wf2.run(state2)

    assert rejected_block2.executed is True

    # ── Scenario 3: Default fallback (unknown decision) ────────────────
    default_target = MockBlock("default_path", "Default output")
    unknown_path = MockBlock("unknown_path", "Should not run")

    class DispatchMockUnknown(BaseBlock):
        def __init__(self) -> None:
            super().__init__("dispatch3")

        async def execute(self, ctx: BlockContext) -> BlockOutput:
            return BlockOutput(
                output="unknown_decision",
                exit_handle="unknown_decision",
                log_entries=[
                    {"role": "system", "content": "[Block dispatch3] DispatchMockUnknown"}
                ],
            )

    wf3 = Workflow(name="routing_test3")
    wf3.add_block(DispatchMockUnknown())
    wf3.add_block(default_target)
    wf3.add_block(unknown_path)
    wf3.add_conditional_transition(
        "dispatch3",
        {"known": "unknown_path", "default": "default_path"},
    )
    wf3.add_transition("default_path", None)
    wf3.add_transition("unknown_path", None)
    wf3.set_entry("dispatch3")

    state3 = WorkflowState()
    _ = await wf3.run(state3)

    assert default_target.executed is True
    assert unknown_path.executed is False

    # ── Scenario 4: KeyError when no matching key and no default ───────
    class DispatchMockNoDefault(BaseBlock):
        def __init__(self) -> None:
            super().__init__("dispatch4")

        async def execute(self, ctx: BlockContext) -> BlockOutput:
            return BlockOutput(
                output="missing",
                exit_handle="missing",
                log_entries=[
                    {"role": "system", "content": "[Block dispatch4] DispatchMockNoDefault"}
                ],
            )

    fallback_block = MockBlock("fallback", "Fallback output")

    wf4 = Workflow(name="routing_test4")
    wf4.add_block(DispatchMockNoDefault())
    wf4.add_block(fallback_block)
    wf4.add_conditional_transition("dispatch4", {"only_key": "fallback"})
    wf4.add_transition("fallback", None)
    wf4.set_entry("dispatch4")

    state4 = WorkflowState()
    with pytest.raises(KeyError):
        await wf4.run(state4)


@pytest.mark.asyncio
async def test_dynamic_injection():
    """AC-4: Dynamic step injection splices blocks into live queue."""
    from runsight_core.blocks.registry import BlockRegistry

    # ── Scenario 1: Registry path (custom factory) ─────────────────────
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

    wf = Workflow(name="injection_test")
    wf.add_block(PlannerBlock())
    wf.add_block(terminal_block)
    wf.add_transition("planner", "terminal")
    wf.add_transition("terminal", None)
    wf.set_entry("planner")

    # Registry with custom factory returning our injected_mock
    registry = BlockRegistry()
    registry.register("injected_step", lambda sid, desc: injected_mock)

    state = WorkflowState()
    final_state = await wf.run(state, registry=registry)

    assert injected_mock.executed is True
    assert "injected_step" in final_state.results
    assert terminal_block.executed is True

    # ── Scenario 2: No registry raises ValueError ─────────────────────
    terminal_block2 = MockBlock("terminal2", "Terminal2 output")

    class PlannerBlock2(BaseBlock):
        def __init__(self) -> None:
            super().__init__("planner2")

        async def execute(self, ctx: BlockContext) -> BlockOutput:
            return BlockOutput(
                output="plan2 generated",
                metadata_updates={
                    "planner2_new_steps": [
                        {"step_id": "injected_step", "description": "Do injected work"}
                    ]
                },
                log_entries=[{"role": "system", "content": "[Block planner2] PlannerBlock2"}],
            )

    wf2 = Workflow(name="injection_test2")
    wf2.add_block(PlannerBlock2())
    wf2.add_block(terminal_block2)
    wf2.add_transition("planner2", "terminal2")
    wf2.add_transition("terminal2", None)
    wf2.set_entry("planner2")

    state2 = WorkflowState()
    with pytest.raises(ValueError, match="No factory registered"):
        await wf2.run(state2, registry=None)
