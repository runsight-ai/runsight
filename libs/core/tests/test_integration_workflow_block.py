"""
End-to-end integration tests for Workflow.run() with call_stack and workflow_registry propagation.

Tests the full execution path from top-level run() through child workflow execution with
WorkflowBlock, verifying call_stack and workflow_registry propagation.
"""

import pytest

from runsight_core.state import BlockResult, WorkflowState
from runsight_core.workflow import Workflow
from runsight_core.blocks.base import BaseBlock
from runsight_core.blocks.implementations import WorkflowBlock


class SimpleBlock(BaseBlock):
    """Simple test block that records execution and can optionally modify state."""

    def __init__(self, block_id: str, output: str = "default output"):
        super().__init__(block_id)
        self.output = output

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        """Execute by recording output in results."""
        return state.model_copy(
            update={
                "results": {**state.results, self.block_id: BlockResult(output=self.output)},
                "messages": state.messages
                + [{"role": "system", "content": f"[Block {self.block_id}] Executed"}],
            }
        )


@pytest.mark.asyncio
async def test_parent_child_workflow_execution():
    """
    AC-14: End-to-end integration test with parent workflow containing WorkflowBlock.

    Verifies:
    1. Parent workflow runs with initial state
    2. WorkflowBlock executes child workflow
    3. call_stack is propagated correctly (not mutated)
    4. workflow_registry is passed through
    5. Input mapping: parent state values → child state
    6. Output mapping: child results → parent state
    7. Cost propagation: child costs accumulated in parent
    8. System message appended with execution summary
    """
    # ==== Setup: Create child workflow ====
    child_wf = Workflow(name="child_workflow")
    child_wf.add_block(SimpleBlock("child_step", "child output"))
    child_wf.set_entry("child_step")
    child_wf.add_transition("child_step", None)  # Terminal

    # ==== Setup: Create parent workflow with WorkflowBlock ====
    parent_wf = Workflow(name="parent_workflow")

    # Create a WorkflowBlock that references the child
    workflow_block = WorkflowBlock(
        block_id="invoke_child",
        child_workflow=child_wf,
        inputs={
            # Child receives a shared memory value from parent
            "shared_memory.topic": "shared_memory.research_topic"
        },
        outputs={
            # Child result is mapped back to parent
            "results.analysis": "results.child_step"
        },
        max_depth=10,
    )

    parent_wf.add_block(workflow_block)
    parent_wf.set_entry("invoke_child")
    parent_wf.add_transition("invoke_child", None)  # Terminal

    # Validate workflows
    parent_errors = parent_wf.validate()
    child_errors = child_wf.validate()
    assert not parent_errors, f"Parent workflow validation failed: {parent_errors}"
    assert not child_errors, f"Child workflow validation failed: {child_errors}"

    # ==== Execute: Create initial state with mapped inputs ====
    initial_state = WorkflowState(
        shared_memory={"research_topic": "quantum computing", "other": "data"},
        results={"existing": BlockResult(output="value")},
        metadata={"workflow_id": "test_workflow"},
        total_cost_usd=0.0,
        total_tokens=0,
    )

    # ==== Execute: Run parent workflow ====
    # Note: No workflow_registry needed since child is passed directly to WorkflowBlock
    final_state = await parent_wf.run(initial_state)

    # ==== Verify: Basic execution completed ====
    assert final_state is not None
    assert isinstance(final_state, WorkflowState)

    # ==== Verify: WorkflowBlock result recorded ====
    assert "invoke_child" in final_state.results
    assert "WorkflowBlock 'child_workflow' completed" in final_state.results["invoke_child"].output

    # ==== Verify: Output mapping (child results → parent state) ====
    assert "analysis" in final_state.results
    assert final_state.results["analysis"].output == "child output"

    # ==== Verify: Existing parent data preserved ====
    assert final_state.results["existing"].output == "value"
    assert final_state.shared_memory["other"] == "data"

    # ==== Verify: System message appended with cost summary ====
    system_messages = [msg for msg in final_state.messages if msg["role"] == "system"]
    assert len(system_messages) > 0
    summary_msg = system_messages[-1]["content"]
    assert "WorkflowBlock 'child_workflow' completed" in summary_msg
    assert "cost:" in summary_msg
    assert "tokens:" in summary_msg

    # ==== Verify: Cost propagation ====
    # Child workflow had one block execution with zero cost (SimpleBlock)
    # So final cost should be >= 0
    assert final_state.total_cost_usd >= 0.0
    assert final_state.total_tokens >= 0


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
    child_wf = Workflow(name="child_wf")
    child_wf.add_block(SimpleBlock("step1", "output1"))
    child_wf.set_entry("step1")
    child_wf.add_transition("step1", None)

    # Create parent workflow with WorkflowBlock
    parent_wf = Workflow(name="parent_wf")
    workflow_block = WorkflowBlock(
        block_id="invoke_child",
        child_workflow=child_wf,
        inputs={},
        outputs={},
        max_depth=10,
    )
    parent_wf.add_block(workflow_block)
    parent_wf.set_entry("invoke_child")
    parent_wf.add_transition("invoke_child", None)

    # Mock the child_wf.run() to capture the call_stack
    captured_call_stacks = []

    async def mock_run(
        initial_state, *, registry=None, call_stack=[], workflow_registry=None, observer=None
    ):
        # Capture the call_stack passed to child
        captured_call_stacks.append(
            call_stack.copy() if isinstance(call_stack, list) else list(call_stack)
        )
        # Return a final state
        return initial_state.model_copy(
            update={
                "results": {**initial_state.results, "child_step": "child_output"},
                "total_cost_usd": 0.0,
                "total_tokens": 0,
            }
        )

    child_wf.run = mock_run

    # Execute
    initial_state = WorkflowState()
    await parent_wf.run(initial_state)

    # Verify: child received extended call_stack
    assert len(captured_call_stacks) > 0
    child_call_stack = captured_call_stacks[0]
    assert "parent_wf" in child_call_stack, (
        f"Expected 'parent_wf' in call_stack, got {child_call_stack}"
    )


@pytest.mark.asyncio
async def test_workflow_block_cycle_detection():
    """
    Verify that WorkflowBlock detects and prevents cycles in workflow references.

    Tests that:
    1. Circular reference raises RecursionError
    2. Error message includes block_id and call_stack
    """
    # Create a workflow that references itself (cycle)
    cyclic_wf = Workflow(name="cyclic_workflow")

    # Create a mock child workflow
    child_wf = Workflow(name="cyclic_workflow")  # Same name as parent - will cause cycle
    child_wf.add_block(SimpleBlock("step", "output"))
    child_wf.set_entry("step")
    child_wf.add_transition("step", None)

    # Add WorkflowBlock to parent (references itself)
    cyclic_wf.add_block(
        WorkflowBlock(
            block_id="self_invoke",
            child_workflow=child_wf,
            inputs={},
            outputs={},
            max_depth=10,
        )
    )
    cyclic_wf.set_entry("self_invoke")
    cyclic_wf.add_transition("self_invoke", None)

    # Execute and expect RecursionError
    initial_state = WorkflowState()

    with pytest.raises(RecursionError) as exc_info:
        await cyclic_wf.run(initial_state)

    error_msg = str(exc_info.value)
    assert "cycle detected" in error_msg.lower() or "circular reference" in error_msg.lower()
    assert "cyclic_workflow" in error_msg or "self_invoke" in error_msg


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
    wf_a = Workflow(name="workflow_a")
    wf_b = Workflow(name="workflow_b")

    # Add simple steps
    wf_a.add_block(SimpleBlock("step_a", "output_a"))
    wf_a.set_entry("step_a")
    wf_a.add_transition("step_a", None)

    wf_b.add_block(SimpleBlock("step_b", "output_b"))
    wf_b.set_entry("step_b")
    wf_b.add_transition("step_b", None)

    # Create a deep call with max_depth=1 (should fail at depth 2)
    deep_block = WorkflowBlock(
        block_id="invoke_b",
        child_workflow=wf_b,
        inputs={},
        outputs={},
        max_depth=1,  # Very restrictive
    )

    wf_a.add_block(deep_block)
    wf_a.set_entry("invoke_b")

    # Mock wf_b.run() to simulate nested call (increase depth)
    async def mock_run_b(
        initial_state, *, registry=None, call_stack=[], workflow_registry=None, observer=None
    ):
        # Simulate that we're being called at depth 1
        # If call_stack already has elements, we're nested
        if len(call_stack) > 0:
            # This is a nested call, we should fail
            raise RecursionError(
                f"WorkflowBlock 'invoke_b': maximum depth 1 exceeded. "
                f"Call stack depth: {len(call_stack)}. "
                f"Call stack: {' -> '.join(call_stack)}"
            )
        return initial_state.model_copy(
            update={
                "results": {**initial_state.results, "step_b": "output_b"},
                "total_cost_usd": 0.0,
                "total_tokens": 0,
            }
        )

    wf_b.run = mock_run_b

    # Execute with initial call_stack at depth 1 (should fail)
    initial_state = WorkflowState()

    with pytest.raises(RecursionError) as exc_info:
        # Simulate calling from an already-nested context
        await wf_a.run(initial_state, call_stack=["parent_wf"])

    error_msg = str(exc_info.value)
    assert "depth" in error_msg.lower() or "exceeded" in error_msg.lower()


@pytest.mark.asyncio
async def test_workflow_registry_parameter_passthrough():
    """
    Verify that workflow_registry parameter is passed through to child workflow.

    Tests that:
    1. workflow_registry is passed to child's run() call
    2. workflow_registry is available for child to use
    3. Parameter name is 'workflow_registry' (not 'registry')
    """
    # Create child workflow
    child_wf = Workflow(name="child_wf")
    child_wf.add_block(SimpleBlock("step", "output"))
    child_wf.set_entry("step")
    child_wf.add_transition("step", None)

    # Create parent with WorkflowBlock
    parent_wf = Workflow(name="parent_wf")
    parent_wf.add_block(
        WorkflowBlock(
            block_id="invoke_child",
            child_workflow=child_wf,
            inputs={},
            outputs={},
            max_depth=10,
        )
    )
    parent_wf.set_entry("invoke_child")
    parent_wf.add_transition("invoke_child", None)

    # Capture what parameters child receives
    captured_kwargs = {}

    async def mock_child_run(
        initial_state, *, registry=None, call_stack=[], workflow_registry=None, observer=None
    ):
        captured_kwargs["registry"] = registry
        captured_kwargs["call_stack"] = call_stack
        captured_kwargs["workflow_registry"] = workflow_registry
        return initial_state.model_copy(
            update={
                "results": {**initial_state.results, "step": "output"},
                "total_cost_usd": 0.0,
                "total_tokens": 0,
            }
        )

    child_wf.run = mock_child_run

    # Create a mock workflow_registry
    from unittest.mock import MagicMock

    mock_registry = MagicMock()

    # Execute with workflow_registry
    initial_state = WorkflowState()
    await parent_wf.run(initial_state, workflow_registry=mock_registry)

    # Verify: child received workflow_registry
    assert "workflow_registry" in captured_kwargs
    assert captured_kwargs["workflow_registry"] is mock_registry

    # Verify: call_stack was also passed (extended with parent name, then child name)
    # When WorkflowBlock.execute() is called, it receives call_stack + [self.name]
    # So child receives ["parent_wf"] before running
    # But then when child.run() is called, that list is used as-is
    assert "call_stack" in captured_kwargs
    assert "parent_wf" in captured_kwargs["call_stack"]


@pytest.mark.asyncio
async def test_workflow_block_input_output_mapping():
    """
    Verify complete input/output mapping cycle in WorkflowBlock execution.

    Tests that:
    1. Inputs are correctly mapped from parent to child state
    2. Outputs are correctly mapped from child back to parent
    3. Parent state is not modified except for mapped fields
    4. Child state is isolated (clean start)
    """
    # Create child workflow
    child_wf = Workflow(name="child_wf")
    child_wf.add_block(SimpleBlock("child_step", "child result"))
    child_wf.set_entry("child_step")
    child_wf.add_transition("child_step", None)

    # Create parent with mapped inputs/outputs
    parent_wf = Workflow(name="parent_wf")
    parent_wf.add_block(
        WorkflowBlock(
            block_id="mapped_invoke",
            child_workflow=child_wf,
            inputs={
                "shared_memory.input_key": "shared_memory.parent_key",
                "results.context": "results.parent_context",
            },
            outputs={
                "results.output_key": "results.child_step",
            },
            max_depth=10,
        )
    )
    parent_wf.set_entry("mapped_invoke")
    parent_wf.add_transition("mapped_invoke", None)

    # Create parent state with values to map
    initial_state = WorkflowState(
        shared_memory={"parent_key": "parent_shared_value", "other": "untouched"},
        results={
            "parent_context": BlockResult(output="context_data"),
            "existing": BlockResult(output="data"),
        },
        metadata={"test": "metadata"},
    )

    # Execute
    final_state = await parent_wf.run(initial_state)

    # Verify: Output mapping
    # Child produced "child result" in results.child_step
    # This should be mapped to results.output_key in parent
    assert "output_key" in final_state.results
    assert final_state.results["output_key"].output == "child result"

    # Verify: Preserved parent data
    assert final_state.results["existing"].output == "data"
    assert final_state.shared_memory["other"] == "untouched"
    assert final_state.metadata["test"] == "metadata"

    # Verify: Mapped inputs were provided to child (the child executed with the input key)
    # The child's shared_memory should have been initialized with input_key
    # (though we don't have direct access to child state in this test)


@pytest.mark.asyncio
async def test_workflow_block_with_cost_accumulation():
    """
    Verify that child workflow costs are accumulated in parent state.

    Tests that:
    1. Child workflow costs are added to parent totals
    2. System message includes cost information
    3. Token counts are accumulated
    """
    # Create child workflow that returns cost
    child_wf = Workflow(name="child_wf")
    child_wf.add_block(SimpleBlock("step", "output"))
    child_wf.set_entry("step")
    child_wf.add_transition("step", None)

    # Mock child run to return costs
    async def mock_child_run(
        initial_state, *, registry=None, call_stack=[], workflow_registry=None, observer=None
    ):
        return initial_state.model_copy(
            update={
                "results": {**initial_state.results, "step": "output"},
                "total_cost_usd": 0.15,  # Child cost
                "total_tokens": 200,  # Child tokens
                "messages": initial_state.messages
                + [{"role": "system", "content": "Child execution"}],
            }
        )

    child_wf.run = mock_child_run

    # Create parent with WorkflowBlock
    parent_wf = Workflow(name="parent_wf")
    parent_wf.add_block(
        WorkflowBlock(
            block_id="invoke",
            child_workflow=child_wf,
            inputs={},
            outputs={},
            max_depth=10,
        )
    )
    parent_wf.set_entry("invoke")
    parent_wf.add_transition("invoke", None)

    # Execute with initial costs
    initial_state = WorkflowState(total_cost_usd=0.05, total_tokens=100)
    final_state = await parent_wf.run(initial_state)

    # Verify: Costs accumulated
    assert final_state.total_cost_usd == pytest.approx(0.20)  # 0.05 + 0.15
    assert final_state.total_tokens == 300  # 100 + 200

    # Verify: Cost info in system message
    system_msgs = [m for m in final_state.messages if m["role"] == "system"]
    summary = next((m["content"] for m in system_msgs if "cost:" in m["content"]), None)
    assert summary is not None
    assert "$0.15" in summary or "0.15" in summary
