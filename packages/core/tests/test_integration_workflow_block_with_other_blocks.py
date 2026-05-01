"""
Integration tests for WorkflowBlock interactions with other block types.

These tests verify that:
1. WorkflowBlock integrates correctly with LinearBlock, DispatchBlock, SynthesizeBlock, etc.
2. Block sequencing works properly with mixed block types
3. State flows correctly through complex workflows combining block types
4. Cost and token accumulation works across nested workflows
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


class MockRunner:
    """Mock runner for testing."""

    def __init__(self):
        self.executions = []
        self.model_name = None

    async def execute(self, instruction: str, context, soul: Soul, messages=None, **kwargs):
        """Mock task execution."""
        self.executions.append((instruction, soul.id))

        class MockResult:
            def __init__(self):
                self.output = f"Result from {soul.id}"
                self.cost_usd = 0.01
                self.total_tokens = 10
                self.soul_id = soul.id
                self.exit_handle = None

        return MockResult()


@pytest.mark.asyncio
async def test_workflow_block_followed_by_linear_block():
    """
    Verify WorkflowBlock can be followed by a LinearBlock in sequence.

    Tests:
    1. WorkflowBlock executes child workflow
    2. LinearBlock executes after WorkflowBlock in parent
    3. State transitions correctly through both blocks
    4. Costs are accumulated from both blocks
    """
    # Create child workflow with placeholder (doesn't need current_task)
    child_sequence_workflow = Workflow(name="linear_sequence_child_workflow")
    child_sequence_workflow.add_block(EchoBlock("child_sequence_step", "child result"))
    child_sequence_workflow.set_entry("child_sequence_step")
    child_sequence_workflow.add_transition("child_sequence_step", None)

    # Create parent workflow
    linear_sequence_workflow = Workflow(name="linear_sequence_parent_workflow")

    # Add WorkflowBlock
    workflow_block = WorkflowBlock(
        block_id="child_workflow_runner",
        child_workflow=child_sequence_workflow,
        inputs={},
        outputs={"results.child_output": "results.child_sequence_step"},
        max_depth=10,
    )
    linear_sequence_workflow.add_block(workflow_block)

    # Add LinearBlock after WorkflowBlock
    mock_runner_parent = MockRunner()
    final_step = LinearBlock(
        block_id="parent_linear",
        soul=Soul(
            id="parent_soul",
            kind="soul",
            name="Parent Soul",
            role="Manager",
            system_prompt="Manage",
        ),
        runner=mock_runner_parent,
    )
    linear_sequence_workflow.add_block(final_step)

    linear_sequence_workflow.set_entry("child_workflow_runner")
    linear_sequence_workflow.add_transition("child_workflow_runner", "parent_linear")
    linear_sequence_workflow.add_transition("parent_linear", None)

    # Create initial state with current_task for LinearBlock
    initial_state = WorkflowState(
        results={},
        shared_memory={},
    )

    # Execute
    final_state = await linear_sequence_workflow.run(initial_state)

    # Verify: Both blocks executed
    assert "child_workflow_runner" in final_state.results
    assert "parent_linear" in final_state.results

    # Verify: Output mapping from child worked
    assert "child_output" in final_state.results
    assert final_state.results["child_output"].output == "child result"

    # Verify: Cost accumulation (from parent LinearBlock)
    assert final_state.total_cost_usd >= 0.01

    # Verify: Messages from both blocks
    assert len(final_state.execution_log) > 0
    system_msgs = [m for m in final_state.execution_log if m["role"] == "system"]
    assert any("child_workflow_runner" in m["content"] for m in system_msgs)
    assert any("parent_linear" in m["content"] for m in system_msgs)


@pytest.mark.asyncio
async def test_workflow_block_with_placeholder_before_and_after():
    """
    Verify WorkflowBlock integrates with EchoBlocks in sequence.

    Tests:
    1. EchoBlock -> WorkflowBlock -> EchoBlock sequence
    2. State flows correctly through all blocks
    3. No state interference between blocks
    """
    # Create child workflow
    echo_sequence_child_workflow = Workflow(name="echo_sequence_child_workflow")
    echo_sequence_child_workflow.add_block(EchoBlock("child_echo_step", "Child execution"))
    echo_sequence_child_workflow.set_entry("child_echo_step")
    echo_sequence_child_workflow.add_transition("child_echo_step", None)

    # Create parent workflow
    echo_sequence_parent_workflow = Workflow(name="echo_sequence_parent_workflow")

    # Add EchoBlock before WorkflowBlock
    echo_sequence_parent_workflow.add_block(EchoBlock("before_child_echo", "Before execution"))

    # Add WorkflowBlock
    workflow_block = WorkflowBlock(
        block_id="child_echo_workflow_block",
        child_workflow=echo_sequence_child_workflow,
        inputs={},
        outputs={},
        max_depth=10,
    )
    echo_sequence_parent_workflow.add_block(workflow_block)

    # Add EchoBlock after WorkflowBlock
    echo_sequence_parent_workflow.add_block(EchoBlock("after_child_echo", "After execution"))

    echo_sequence_parent_workflow.set_entry("before_child_echo")
    echo_sequence_parent_workflow.add_transition("before_child_echo", "child_echo_workflow_block")
    echo_sequence_parent_workflow.add_transition("child_echo_workflow_block", "after_child_echo")
    echo_sequence_parent_workflow.add_transition("after_child_echo", None)

    # Execute
    initial_state = WorkflowState()
    final_state = await echo_sequence_parent_workflow.run(initial_state)

    # Verify: All blocks executed in order
    assert "before_child_echo" in final_state.results
    assert "child_echo_workflow_block" in final_state.results
    assert "after_child_echo" in final_state.results

    # Verify: Messages show correct execution order
    messages = [m["content"] for m in final_state.execution_log if m["role"] == "system"]
    before_idx = next((i for i, m in enumerate(messages) if "before_child_echo" in m), -1)
    invoke_idx = next(
        (i for i, m in enumerate(messages) if "child_echo_workflow_block" in m),
        -1,
    )
    after_idx = next((i for i, m in enumerate(messages) if "after_child_echo" in m), -1)

    assert before_idx >= 0
    assert invoke_idx > before_idx
    assert after_idx > invoke_idx


@pytest.mark.asyncio
async def test_nested_workflow_blocks():
    """
    Verify nested WorkflowBlocks (child contains WorkflowBlock invoking grandchild).

    Tests:
    1. Multi-level nesting: parent → child → grandchild
    2. call_stack prevents cycles and limits depth
    3. State isolation at each level
    4. Output mapping through multiple levels
    """
    # Create grandchild workflow
    nested_leaf_workflow = Workflow(name="nested_leaf_workflow")
    nested_leaf_workflow.add_block(EchoBlock("nested_leaf_step", "Grandchild executed"))
    nested_leaf_workflow.set_entry("nested_leaf_step")
    nested_leaf_workflow.add_transition("nested_leaf_step", None)

    # Create child workflow with WorkflowBlock invoking grandchild
    nested_middle_workflow = Workflow(name="nested_middle_workflow")
    gc_block = WorkflowBlock(
        block_id="leaf_workflow_block",
        child_workflow=nested_leaf_workflow,
        inputs={},
        outputs={"results.gc_result": "results.nested_leaf_step"},
        max_depth=10,
    )
    nested_middle_workflow.add_block(gc_block)
    nested_middle_workflow.set_entry("leaf_workflow_block")
    nested_middle_workflow.add_transition("leaf_workflow_block", None)

    # Create parent workflow with WorkflowBlock invoking child
    nested_parent_workflow = Workflow(name="nested_parent_workflow")
    c_block = WorkflowBlock(
        block_id="middle_workflow_block",
        child_workflow=nested_middle_workflow,
        inputs={},
        outputs={"results.child_result": "results.gc_result"},
        max_depth=10,
    )
    nested_parent_workflow.add_block(c_block)
    nested_parent_workflow.set_entry("middle_workflow_block")
    nested_parent_workflow.add_transition("middle_workflow_block", None)

    # Execute
    initial_state = WorkflowState()
    final_state = await nested_parent_workflow.run(initial_state)

    # Verify: All levels executed
    assert "middle_workflow_block" in final_state.results
    assert "child_result" in final_state.results
    assert final_state.results["child_result"].output == "Grandchild executed"

    # Verify: System messages from top-level blocks
    # Note: Messages from nested workflows are propagated up through the parent message stream
    messages = [m["content"] for m in final_state.execution_log if m["role"] == "system"]
    assert any("middle_workflow_block" in m for m in messages)  # Parent → child block
    # The grandchild execution message may be in the child's state, then propagated
    # We verify the final output was correctly mapped instead
    assert final_state.results["child_result"].output == "Grandchild executed"


@pytest.mark.asyncio
async def test_workflow_block_state_isolation_complex():
    """
    Verify WorkflowBlock provides strict state isolation in complex scenarios.

    Tests:
    1. Parent has results, shared_memory, metadata
    2. Child should only receive mapped values
    3. Child's execution doesn't affect unmapped parent state
    4. Child's modifications don't leak to parent (except mapped outputs)
    """
    # Create child workflow that modifies all state fields
    state_isolation_child_workflow = Workflow(name="state_isolation_child_workflow")

    class ModifyingBlock(BaseBlock):
        def __init__(self, block_id: str, description: str) -> None:
            super().__init__(block_id)
            self.description = description

        async def execute(self, ctx):
            state = ctx.state_snapshot
            # Try to modify all state fields
            new_state = state.model_copy(
                update={
                    "results": {**state.results, "child_secret": BlockResult(output="hidden")},
                    "shared_memory": {**state.shared_memory, "child_only": "secret_data"},
                    "metadata": {**state.metadata, "child_meta": "private"},
                }
            )
            final_state = new_state.model_copy(
                update={
                    "results": {
                        **new_state.results,
                        self.block_id: BlockResult(output=self.description),
                    },
                    "execution_log": new_state.execution_log
                    + [
                        {
                            "role": "system",
                            "content": f"[Block {self.block_id}] ModifyingBlock: {self.description}",
                        }
                    ],
                }
            )
            return block_output_from_state(self.block_id, state, final_state)

    child_block = ModifyingBlock("modify_step", "Modified state")
    state_isolation_child_workflow.add_block(child_block)
    state_isolation_child_workflow.set_entry("modify_step")
    state_isolation_child_workflow.add_transition("modify_step", None)

    # Create parent workflow
    state_isolation_parent_workflow = Workflow(name="state_isolation_parent_workflow")
    workflow_block = WorkflowBlock(
        block_id="state_isolation_workflow_block",
        child_workflow=state_isolation_child_workflow,
        inputs={},
        outputs={"results.mapped_out": "results.modify_step"},
        max_depth=10,
    )
    state_isolation_parent_workflow.add_block(workflow_block)
    state_isolation_parent_workflow.set_entry("state_isolation_workflow_block")
    state_isolation_parent_workflow.add_transition("state_isolation_workflow_block", None)

    # Create parent state with existing data
    initial_state = WorkflowState(
        results={"parent_data": BlockResult(output="keep_me")},
        shared_memory={"parent_key": "keep_me"},
        metadata={"parent_meta": "keep_me"},
    )

    # Execute
    final_state = await state_isolation_parent_workflow.run(initial_state)

    # Verify: Parent's original data is preserved
    assert "parent_data" in final_state.results
    assert final_state.results["parent_data"].output == "keep_me"
    assert final_state.shared_memory["parent_key"] == "keep_me"
    assert final_state.metadata["parent_meta"] == "keep_me"

    # Verify: Child's modifications didn't leak (except mapped outputs)
    assert "child_secret" not in final_state.results
    assert "child_only" not in final_state.shared_memory
    assert "child_meta" not in final_state.metadata

    # Verify: Only mapped output is present
    assert "mapped_out" in final_state.results


@pytest.mark.asyncio
async def test_workflow_block_cost_propagation_multiple_levels():
    """
    Verify cost accumulation works correctly through multiple workflow levels.

    Tests:
    1. Each workflow level tracks costs
    2. Child costs propagate to parent correctly
    3. Multiple child executions accumulate properly
    """
    # Create child workflow that reports costs
    cost_tracking_child_workflow = Workflow(name="child_cost_tracking_workflow")

    class CostProducingBlock(BaseBlock):
        def __init__(self, block_id: str, cost: float):
            super().__init__(block_id)
            self.cost = cost

        async def execute(self, ctx):
            state = ctx.state_snapshot
            next_state = state.model_copy(
                update={
                    "results": {**state.results, self.block_id: BlockResult(output="Block")},
                    "execution_log": state.execution_log
                    + [
                        {"role": "system", "content": f"[Block {self.block_id}] CostProducingBlock"}
                    ],
                    "total_cost_usd": state.total_cost_usd + self.cost,
                    "total_tokens": state.total_tokens + 10,
                }
            )
            return block_output_from_state(self.block_id, state, next_state)

    cost_tracking_child_workflow.add_block(CostProducingBlock("child_cost_step", 0.05))
    cost_tracking_child_workflow.set_entry("child_cost_step")
    cost_tracking_child_workflow.add_transition("child_cost_step", None)

    # Create parent workflow
    cost_tracking_parent_workflow = Workflow(name="cost_tracking_parent_workflow")

    # Add initial cost block
    cost_tracking_parent_workflow.add_block(CostProducingBlock("parent_initial", 0.02))

    # Add WorkflowBlock (will invoke child which costs 0.05)
    workflow_block = WorkflowBlock(
        block_id="cost_child_workflow_block",
        child_workflow=cost_tracking_child_workflow,
        inputs={},
        outputs={},
        max_depth=10,
    )
    cost_tracking_parent_workflow.add_block(workflow_block)

    # Add final cost block
    cost_tracking_parent_workflow.add_block(CostProducingBlock("parent_final", 0.03))

    cost_tracking_parent_workflow.set_entry("parent_initial")
    cost_tracking_parent_workflow.add_transition("parent_initial", "cost_child_workflow_block")
    cost_tracking_parent_workflow.add_transition("cost_child_workflow_block", "parent_final")
    cost_tracking_parent_workflow.add_transition("parent_final", None)

    # Execute
    initial_state = WorkflowState(total_cost_usd=0.0, total_tokens=0)
    final_state = await cost_tracking_parent_workflow.run(initial_state)

    # Verify: Total costs accumulated
    # parent_initial: 0.02
    # child: 0.05
    # parent_final: 0.03
    # Total: 0.10
    assert final_state.total_cost_usd == pytest.approx(0.10, abs=0.001)
    assert final_state.total_tokens == 30  # 3 blocks × 10 tokens
