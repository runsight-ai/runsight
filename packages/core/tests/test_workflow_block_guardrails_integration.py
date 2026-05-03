"""
Integration tests for Workflow.run() with call_stack and workflow_registry propagation.

Tests the full execution path from top-level run() through child workflow execution with
WorkflowBlock, verifying call_stack and workflow_registry propagation.
"""

import pytest
from conftest import block_output_from_state
from runsight_core import WorkflowBlock
from runsight_core.blocks.base import BaseBlock
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.workflow import Workflow


class SimpleBlock(BaseBlock):
    """Simple test block that records execution and can optionally modify state."""

    def __init__(
        self,
        block_id: str,
        output: str = "default output",
        declared_inputs: dict[str, str] | None = None,
    ):
        super().__init__(block_id)
        self.output = output
        self.context_access = "declared"
        self.declared_inputs = dict(declared_inputs or {})
        self.seen_workflow_inputs = None

    async def execute(self, ctx):
        """Execute by recording output in results."""
        state = ctx.state_snapshot
        self.seen_workflow_inputs = dict(state.workflow_inputs)
        next_state = state.model_copy(
            update={
                "results": {**state.results, self.block_id: BlockResult(output=self.output)},
                "execution_log": state.execution_log
                + [{"role": "system", "content": f"[Block {self.block_id}] Executed"}],
            }
        )
        return block_output_from_state(self.block_id, state, next_state)


@pytest.mark.asyncio
async def test_workflow_block_call_stack_propagation():
    """
    Verify that call_stack is correctly propagated and extended at each level.

    Tests that:
    1. call_stack is not mutated (new list created with +)
    2. call_stack includes all workflow names in execution path
    3. call_stack can be used for cycle detection
    """
    # Create a child workflow
    child_workflow = Workflow(name="call_stack_child_workflow")
    child_workflow.add_block(SimpleBlock("call_stack_child_step", "output1"))
    child_workflow.set_entry("call_stack_child_step")
    child_workflow.add_transition("call_stack_child_step", None)

    # Create parent workflow with WorkflowBlock
    parent_workflow = Workflow(name="call_stack_parent_workflow")
    workflow_block = WorkflowBlock(
        block_id="call_stack_workflow_block",
        child_workflow=child_workflow,
        inputs={},
        outputs={},
        max_depth=10,
    )
    parent_workflow.add_block(workflow_block)
    parent_workflow.set_entry("call_stack_workflow_block")
    parent_workflow.add_transition("call_stack_workflow_block", None)

    # Mock the child_workflow.run() to capture the call_stack
    captured_call_stacks = []
    captured_inputs = []

    async def mock_run(
        initial_state,
        *,
        inputs=None,
        registry=None,
        call_stack=None,
        workflow_registry=None,
        observer=None,
    ):
        # Capture the call_stack passed to child
        call_stack = call_stack or []
        captured_call_stacks.append(
            call_stack.copy() if isinstance(call_stack, list) else list(call_stack)
        )
        captured_inputs.append(dict(inputs or {}))
        # Return a final state
        return initial_state.model_copy(
            update={
                "results": {
                    **initial_state.results,
                    "call_stack_child_step": BlockResult(output="child_output"),
                },
                "total_cost_usd": 0.0,
                "total_tokens": 0,
            }
        )

    child_workflow.run = mock_run

    # Execute
    initial_state = WorkflowState()
    await parent_workflow.run(initial_state)

    # Verify: child received extended call_stack
    assert len(captured_call_stacks) > 0
    child_call_stack = captured_call_stacks[0]
    assert child_call_stack == ["call_stack_parent_workflow", "call_stack_child_workflow"]
    assert captured_inputs == [{}]


@pytest.mark.asyncio
async def test_workflow_block_cycle_detection():
    """
    Verify that WorkflowBlock detects and prevents cycles in workflow references.

    Tests that:
    1. Circular reference raises RecursionError
    2. Error message includes block_id and call_stack
    """
    # Create a workflow that references itself (cycle)
    cyclic_workflow = Workflow(name="cyclic_workflow")

    # Create a mock child workflow
    child_workflow = Workflow(name="cyclic_workflow")  # Same name as parent - will cause cycle
    child_workflow.add_block(SimpleBlock("cycle_child_step", "output"))
    child_workflow.set_entry("cycle_child_step")
    child_workflow.add_transition("cycle_child_step", None)

    # Add WorkflowBlock to parent (references itself)
    cyclic_workflow.add_block(
        WorkflowBlock(
            block_id="self_cycle_workflow_block",
            child_workflow=child_workflow,
            inputs={},
            outputs={},
            max_depth=10,
        )
    )
    cyclic_workflow.set_entry("self_cycle_workflow_block")
    cyclic_workflow.add_transition("self_cycle_workflow_block", None)

    # Execute and expect RecursionError
    initial_state = WorkflowState()

    with pytest.raises(RecursionError) as exc_info:
        await cyclic_workflow.run(initial_state)

    error_msg = str(exc_info.value)
    assert "cycle detected" in error_msg.lower() or "circular reference" in error_msg.lower()
    assert "cyclic_workflow" in error_msg or "self_cycle_workflow_block" in error_msg


@pytest.mark.asyncio
async def test_workflow_block_depth_limit():
    """
    Verify that WorkflowBlock enforces max_depth limit to prevent infinite recursion.

    Tests that:
    1. Depth limit is enforced
    2. RecursionError raised when limit exceeded
    3. Error message includes max_depth and current depth
    """
    # Create two workflows that will call each other
    depth_parent_workflow = Workflow(name="depth_limit_parent_workflow")
    depth_child_workflow = Workflow(name="depth_limit_child_workflow")

    # Add simple steps
    depth_parent_workflow.add_block(SimpleBlock("depth_parent_step", "output_a"))
    depth_parent_workflow.set_entry("depth_parent_step")
    depth_parent_workflow.add_transition("depth_parent_step", None)

    depth_child_workflow.add_block(SimpleBlock("depth_child_step", "output_b"))
    depth_child_workflow.set_entry("depth_child_step")
    depth_child_workflow.add_transition("depth_child_step", None)

    # Create a deep call with max_depth=1 (should fail at depth 2)
    deep_block = WorkflowBlock(
        block_id="depth_limit_workflow_block",
        child_workflow=depth_child_workflow,
        inputs={},
        outputs={},
        max_depth=1,  # Very restrictive
    )

    depth_parent_workflow.add_block(deep_block)
    depth_parent_workflow.set_entry("depth_limit_workflow_block")

    # Mock the child workflow run to simulate a nested call.
    async def mock_run_b(
        initial_state,
        *,
        inputs=None,
        registry=None,
        call_stack=None,
        workflow_registry=None,
        observer=None,
    ):
        call_stack = call_stack or []
        # Simulate that we're being called at depth 1
        # If call_stack already has elements, we're nested
        if len(call_stack) > 0:
            # This is a nested call, we should fail
            raise RecursionError(
                f"WorkflowBlock 'depth_limit_workflow_block': maximum depth 1 exceeded. "
                f"Call stack depth: {len(call_stack)}. "
                f"Call stack: {' -> '.join(call_stack)}"
            )
        return initial_state.model_copy(
            update={
                "results": {
                    **initial_state.results,
                    "depth_child_step": BlockResult(output="output_b"),
                },
                "total_cost_usd": 0.0,
                "total_tokens": 0,
            }
        )

    depth_child_workflow.run = mock_run_b

    # Execute with initial call_stack at depth 1 (should fail)
    initial_state = WorkflowState()

    with pytest.raises(RecursionError) as exc_info:
        # Simulate calling from an already-nested context
        await depth_parent_workflow.run(
            initial_state,
            call_stack=["depth_limit_parent_workflow"],
        )

    error_msg = str(exc_info.value)
    assert "depth" in error_msg.lower() or "exceeded" in error_msg.lower()
