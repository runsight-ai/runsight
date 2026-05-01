"""
Integration tests for WorkflowBlock legacy block compatibility and error handling.

These tests verify that:
1. Existing blocks still work when passed **kwargs by Workflow.run()
2. Error propagation works correctly through WorkflowBlock
3. Workflows that don't use WorkflowBlock still run unchanged
4. Error messages are clear and helpful
"""

import pytest
from conftest import block_output_from_state
from runsight_core import (
    LinearBlock,
    WorkflowBlock,
)
from runsight_core.blocks.base import BaseBlock
from runsight_core.primitives import Soul
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.workflow import Workflow


class EchoBlock(BaseBlock):
    """Simple block that echoes a description to results. Used as a test stand-in."""

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


class BlockWithoutKwargs(BaseBlock):
    """Block that explicitly doesn't accept **kwargs."""

    async def execute(self, ctx):
        """Execute without **kwargs signature."""
        state = ctx.state_snapshot
        next_state = state.model_copy(
            update={
                "results": {**state.results, self.block_id: BlockResult(output="executed")},
                "execution_log": state.execution_log
                + [{"role": "system", "content": f"[Block {self.block_id}] Executed"}],
            }
        )
        return block_output_from_state(self.block_id, state, next_state)


class BlockWithKwargs(BaseBlock):
    """Block that accepts **kwargs."""

    async def execute(self, ctx, **kwargs):
        """Execute with **kwargs signature."""
        state = ctx.state_snapshot
        next_state = state.model_copy(
            update={
                "results": {
                    **state.results,
                    self.block_id: BlockResult(output="executed_with_kwargs"),
                },
                "execution_log": state.execution_log
                + [{"role": "system", "content": f"[Block {self.block_id}] Executed with kwargs"}],
            }
        )
        return block_output_from_state(self.block_id, state, next_state)


@pytest.mark.asyncio
async def test_block_execute_without_kwargs_runs_without_workflow_blocks():
    """
    Verify that blocks without **kwargs run in workflows without WorkflowBlocks.

    Tests:
    1. Workflow without WorkflowBlock can use blocks without **kwargs
    2. Execution succeeds without errors
    3. Plain workflow behavior is maintained
    """
    wf = Workflow(name="without_kwargs_block_workflow")

    block_without_kwargs = BlockWithoutKwargs("without_kwargs_step")
    wf.add_block(block_without_kwargs)

    wf.set_entry("without_kwargs_step")
    wf.add_transition("without_kwargs_step", None)

    # Execute
    initial_state = WorkflowState()
    final_state = await wf.run(initial_state)

    # Verify: Block executed successfully
    assert "without_kwargs_step" in final_state.results
    assert final_state.results["without_kwargs_step"].output == "executed"


@pytest.mark.asyncio
async def test_block_execute_with_kwargs_runs_in_plain_workflow():
    """
    Verify that blocks with **kwargs execute in a plain workflow.

    Tests:
    1. Blocks with **kwargs work in workflows without WorkflowBlocks
    2. Execution succeeds without errors
    3. Kwargs are optional for block execution
    """
    wf = Workflow(name="with_kwargs_block_workflow")

    block_with_kwargs = BlockWithKwargs("with_kwargs_step")
    wf.add_block(block_with_kwargs)

    wf.set_entry("with_kwargs_step")
    wf.add_transition("with_kwargs_step", None)

    # Execute
    initial_state = WorkflowState()
    final_state = await wf.run(initial_state)

    # Verify: Block executed successfully
    assert "with_kwargs_step" in final_state.results
    assert final_state.results["with_kwargs_step"].output == "executed_with_kwargs"


@pytest.mark.asyncio
async def test_workflow_can_mix_execute_signatures():
    """
    Verify that workflows can mix blocks with and without **kwargs.

    Tests:
    1. Both execute signatures can coexist
    2. Both execute correctly
    3. No interference between different block signatures
    """
    wf = Workflow(name="mixed_execute_signature_workflow")

    wf.add_block(BlockWithoutKwargs("without_kwargs_first_step"))

    wf.add_block(BlockWithKwargs("with_kwargs_step"))

    wf.add_block(BlockWithoutKwargs("without_kwargs_final_step"))

    wf.set_entry("without_kwargs_first_step")
    wf.add_transition("without_kwargs_first_step", "with_kwargs_step")
    wf.add_transition("with_kwargs_step", "without_kwargs_final_step")
    wf.add_transition("without_kwargs_final_step", None)

    # Execute
    initial_state = WorkflowState()
    final_state = await wf.run(initial_state)

    # Verify: All blocks executed
    assert "without_kwargs_first_step" in final_state.results
    assert "with_kwargs_step" in final_state.results
    assert "without_kwargs_final_step" in final_state.results


@pytest.mark.asyncio
async def test_error_in_workflow_block_propagates():
    """
    Verify that errors in child workflow propagate correctly to parent.

    Tests:
    1. Exception in child workflow raises to parent
    2. Error message includes details
    3. Execution stops at the error
    """

    class FailingBlock(BaseBlock):
        async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
            raise ValueError("Intentional failure in child")

    # Create child workflow that fails
    error_child_workflow = Workflow(name="error_propagation_child_workflow")
    error_child_workflow.add_block(FailingBlock("workflow_error_step"))
    error_child_workflow.set_entry("workflow_error_step")
    error_child_workflow.add_transition("workflow_error_step", None)

    # Create parent with WorkflowBlock
    error_parent_workflow = Workflow(name="error_propagation_parent_workflow")
    workflow_block = WorkflowBlock(
        block_id="error_child_workflow_block",
        child_workflow=error_child_workflow,
        inputs={},
        outputs={},
        max_depth=10,
    )
    error_parent_workflow.add_block(workflow_block)
    error_parent_workflow.set_entry("error_child_workflow_block")
    error_parent_workflow.add_transition("error_child_workflow_block", None)

    # Execute and expect error
    initial_state = WorkflowState()

    with pytest.raises(ValueError) as exc_info:
        await error_parent_workflow.run(initial_state)

    assert "Intentional failure" in str(exc_info.value)


@pytest.mark.asyncio
async def test_invalid_input_mapping_raises_clear_error():
    """
    Verify that invalid input mapping raises clear error.

    Tests:
    1. Referencing non-existent parent key raises KeyError
    2. Error message is clear and helpful
    3. Error includes block_id and path
    """
    # Create child workflow
    input_mapping_child_workflow = Workflow(name="input_mapping_child_workflow")
    input_mapping_child_workflow.add_block(EchoBlock("input_mapping_child_step", "output"))
    input_mapping_child_workflow.set_entry("input_mapping_child_step")
    input_mapping_child_workflow.add_transition("input_mapping_child_step", None)

    # Create parent with invalid input mapping
    input_mapping_parent_workflow = Workflow(name="invalid_input_mapping_parent_workflow")
    workflow_block = WorkflowBlock(
        block_id="invalid_input_mapping_workflow_block",
        child_workflow=input_mapping_child_workflow,
        inputs={
            "input": "shared_memory.nonexistent_key",  # Key doesn't exist
        },
        outputs={},
        max_depth=10,
    )
    input_mapping_parent_workflow.add_block(workflow_block)
    input_mapping_parent_workflow.set_entry("invalid_input_mapping_workflow_block")
    input_mapping_parent_workflow.add_transition("invalid_input_mapping_workflow_block", None)

    # Execute with state that doesn't have the key
    initial_state = WorkflowState(shared_memory={"other_key": "value"})

    with pytest.raises(KeyError) as exc_info:
        await input_mapping_parent_workflow.run(initial_state)

    error_msg = str(exc_info.value)
    assert "nonexistent_key" in error_msg or "not found" in error_msg.lower()


@pytest.mark.asyncio
async def test_invalid_output_mapping_raises_clear_error():
    """
    Verify that invalid output mapping raises clear error.

    Tests:
    1. Referencing non-existent child key raises KeyError
    2. Error message is clear
    3. Error includes block_id and path
    """
    # Create child workflow that produces limited output
    output_mapping_child_workflow = Workflow(name="output_mapping_child_workflow")
    output_mapping_child_workflow.add_block(EchoBlock("output_mapping_child_step", "output"))
    output_mapping_child_workflow.set_entry("output_mapping_child_step")
    output_mapping_child_workflow.add_transition("output_mapping_child_step", None)

    # Create parent with invalid output mapping
    output_mapping_parent_workflow = Workflow(name="invalid_output_mapping_parent_workflow")
    workflow_block = WorkflowBlock(
        block_id="invalid_output_mapping_workflow_block",
        child_workflow=output_mapping_child_workflow,
        inputs={},
        outputs={
            "results.mapped": "results.nonexistent",  # Child doesn't produce this
        },
        max_depth=10,
    )
    output_mapping_parent_workflow.add_block(workflow_block)
    output_mapping_parent_workflow.set_entry("invalid_output_mapping_workflow_block")
    output_mapping_parent_workflow.add_transition("invalid_output_mapping_workflow_block", None)

    # Execute
    initial_state = WorkflowState()

    with pytest.raises(KeyError) as exc_info:
        await output_mapping_parent_workflow.run(initial_state)

    error_msg = str(exc_info.value)
    assert "nonexistent" in error_msg or "not found" in error_msg.lower()


@pytest.mark.asyncio
async def test_workflow_without_workflow_blocks_runs_without_workflow_block_parameters():
    """
    Verify complete legacy compatibility: workflows without WorkflowBlock run unchanged.

    Tests:
    1. Complex workflow without any WorkflowBlocks works
    2. All existing block types work
    3. No WorkflowBlock-specific parameters are required
    """

    class MockRunner:
        model_name = None

        async def execute(self, instruction, context, soul, messages=None, **kwargs):
            class Result:
                def __init__(self):
                    self.output = "mocked output"
                    self.cost_usd = 0.01
                    self.total_tokens = 10
                    self.soul_id = soul.id
                    self.exit_handle = None

            return Result()

    # Create a comprehensive workflow with various blocks
    wf = Workflow(name="legacy_linear_echo_workflow")

    runner = MockRunner()
    soul = Soul(
        id="legacy_linear_soul",
        kind="soul",
        name="Legacy Linear Soul",
        role="Fixture runner",
        system_prompt="Run the legacy linear step",
    )

    # Add LinearBlock
    linear_block = LinearBlock(
        block_id="legacy_linear_step",
        soul=soul,
        runner=runner,
    )
    wf.add_block(linear_block)

    # Add EchoBlock
    wf.add_block(EchoBlock("echo_step", "echo output"))

    wf.set_entry("legacy_linear_step")
    wf.add_transition("legacy_linear_step", "echo_step")
    wf.add_transition("echo_step", None)

    # Execute without any WorkflowRegistry or special parameters
    initial_state = WorkflowState()
    final_state = await wf.run(initial_state)

    # Verify: Execution successful
    assert "legacy_linear_step" in final_state.results
    assert "echo_step" in final_state.results


@pytest.mark.asyncio
async def test_workflow_block_with_kwargs_in_chain():
    """
    Verify WorkflowBlock works correctly when it receives **kwargs from parent.

    Tests:
    1. WorkflowBlock.execute() accepts **kwargs
    2. It correctly passes call_stack and workflow_registry to child
    3. Child receives correct parameters
    """
    # Create child workflow
    call_stack_child_workflow = Workflow(name="call_stack_child_workflow")
    call_stack_child_workflow.add_block(EchoBlock("call_stack_child_step", "child_out"))
    call_stack_child_workflow.set_entry("call_stack_child_step")
    call_stack_child_workflow.add_transition("call_stack_child_step", None)

    # Create parent with WorkflowBlock
    call_stack_parent_workflow = Workflow(name="call_stack_parent_workflow")
    workflow_block = WorkflowBlock(
        block_id="call_stack_workflow_block",
        child_workflow=call_stack_child_workflow,
        inputs={},
        outputs={},
        max_depth=10,
    )
    call_stack_parent_workflow.add_block(workflow_block)
    call_stack_parent_workflow.set_entry("call_stack_workflow_block")
    call_stack_parent_workflow.add_transition("call_stack_workflow_block", None)

    # Capture what the child receives
    captured_call_stack = []
    original_run = call_stack_child_workflow.run

    async def mock_run(
        state,
        *,
        inputs=None,
        registry=None,
        call_stack=None,
        workflow_registry=None,
        observer=None,
    ):
        captured_call_stack.append(call_stack if call_stack is not None else [])
        return await original_run(
            state,
            registry=registry,
            call_stack=call_stack,
            workflow_registry=workflow_registry,
            observer=observer,
        )

    call_stack_child_workflow.run = mock_run

    # Execute with explicit call_stack
    initial_state = WorkflowState()
    initial_call_stack = ["root_call_stack_workflow"]

    await call_stack_parent_workflow.run(initial_state, call_stack=initial_call_stack)

    # Verify: call_stack was passed and extended
    assert len(captured_call_stack) > 0
    received_stack = captured_call_stack[0]
    assert received_stack == [
        "root_call_stack_workflow",
        "call_stack_parent_workflow",
        "call_stack_child_workflow",
    ]


@pytest.mark.asyncio
async def test_nested_workflow_block_extends_explicit_call_stack():
    """
    Verify that nested WorkflowBlock execution extends an explicit call stack.

    Tests:
    1. Explicit root call stack is preserved
    2. Parent and child workflow names are appended before child workflow execution
    3. Nested workflow execution still succeeds
    """
    nested_call_stack_child_workflow = Workflow(name="nested_call_stack_child_workflow")
    nested_call_stack_child_workflow.add_block(
        EchoBlock("nested_call_stack_child_step", "nested child executed")
    )
    nested_call_stack_child_workflow.set_entry("nested_call_stack_child_step")
    nested_call_stack_child_workflow.add_transition("nested_call_stack_child_step", None)

    captured_call_stacks = []
    original_run = nested_call_stack_child_workflow.run

    async def capture_child_run(
        state,
        *,
        inputs=None,
        registry=None,
        call_stack=None,
        workflow_registry=None,
        observer=None,
    ):
        captured_call_stacks.append(list(call_stack or []))
        return await original_run(
            state,
            inputs=inputs,
            registry=registry,
            call_stack=call_stack,
            workflow_registry=workflow_registry,
            observer=observer,
        )

    nested_call_stack_child_workflow.run = capture_child_run

    # Create parent with WorkflowBlock
    nested_call_stack_parent_workflow = Workflow(name="nested_call_stack_parent_workflow")
    workflow_block = WorkflowBlock(
        block_id="nested_call_stack_workflow_block",
        child_workflow=nested_call_stack_child_workflow,
        inputs={},
        outputs={},
        max_depth=10,
    )
    nested_call_stack_parent_workflow.add_block(workflow_block)
    nested_call_stack_parent_workflow.set_entry("nested_call_stack_workflow_block")
    nested_call_stack_parent_workflow.add_transition("nested_call_stack_workflow_block", None)

    final_state = await nested_call_stack_parent_workflow.run(
        WorkflowState(),
        call_stack=["root_call_stack_workflow"],
    )

    assert "nested_call_stack_workflow_block" in final_state.results
    assert captured_call_stacks == [
        [
            "root_call_stack_workflow",
            "nested_call_stack_parent_workflow",
            "nested_call_stack_child_workflow",
        ]
    ]


@pytest.mark.asyncio
async def test_parent_and_child_cost_steps_run_until_child_error():
    """
    Verify that cost-producing steps execute up to the failing child step.

    Tests:
    1. Parent cost step runs before invoking the child workflow
    2. Child workflow runs its first cost step before the failing step
    3. Child error propagates to the parent workflow
    """
    executed_blocks = []

    class CostTrackingBlock(BaseBlock):
        def __init__(self, block_id: str, cost: float, fail: bool = False):
            super().__init__(block_id)
            self.cost = cost
            self.fail = fail

        async def execute(self, ctx):
            state = ctx.state_snapshot
            executed_blocks.append(self.block_id)
            new_state = state.model_copy(
                update={
                    "total_cost_usd": state.total_cost_usd + self.cost,
                    "total_tokens": state.total_tokens + 10,
                    "results": {**state.results, self.block_id: BlockResult(output="completed")},
                }
            )
            if self.fail:
                raise RuntimeError(f"Block {self.block_id} failed")
            return block_output_from_state(self.block_id, state, new_state)

    # Create child with two blocks: first succeeds, second fails
    partial_cost_child_workflow = Workflow(name="partial_cost_child_workflow")
    partial_cost_child_workflow.add_block(CostTrackingBlock("child_cost_first_step", 0.05))
    partial_cost_child_workflow.add_block(
        CostTrackingBlock("child_cost_failure_step", 0.03, fail=True)
    )
    partial_cost_child_workflow.set_entry("child_cost_first_step")
    partial_cost_child_workflow.add_transition(
        "child_cost_first_step",
        "child_cost_failure_step",
    )
    partial_cost_child_workflow.add_transition("child_cost_failure_step", None)

    # Create parent
    cost_error_parent_workflow = Workflow(name="cost_error_parent_workflow")
    cost_error_parent_workflow.add_block(CostTrackingBlock("parent_cost_step", 0.02))
    workflow_block = WorkflowBlock(
        block_id="cost_error_workflow_block",
        child_workflow=partial_cost_child_workflow,
        inputs={},
        outputs={},
        max_depth=10,
    )
    cost_error_parent_workflow.add_block(workflow_block)
    cost_error_parent_workflow.set_entry("parent_cost_step")
    cost_error_parent_workflow.add_transition("parent_cost_step", "cost_error_workflow_block")
    cost_error_parent_workflow.add_transition("cost_error_workflow_block", None)

    # Execute
    initial_state = WorkflowState()

    with pytest.raises(RuntimeError, match="child_cost_failure_step"):
        await cost_error_parent_workflow.run(initial_state)

    assert executed_blocks == [
        "parent_cost_step",
        "child_cost_first_step",
        "child_cost_failure_step",
    ]
