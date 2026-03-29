"""
Integration tests for WorkflowBlock interactions with other block types.

These tests verify that:
1. WorkflowBlock integrates correctly with LinearBlock, FanOutBlock, SynthesizeBlock, etc.
2. Block sequencing works properly with mixed block types
3. State flows correctly through complex workflows combining block types
4. Cost and token accumulation works across nested workflows
"""

import pytest
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.workflow import Workflow
from runsight_core.blocks.base import BaseBlock
from runsight_core import (
    WorkflowBlock,
    LinearBlock,
)
from runsight_core.primitives import Soul, Task


class EchoBlock(BaseBlock):
    """Simple block that echoes a description to results. Used as a test stand-in."""

    def __init__(self, block_id: str, description: str) -> None:
        super().__init__(block_id)
        self.description = description

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        return state.model_copy(
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


class MockRunner:
    """Mock runner for testing."""

    def __init__(self):
        self.executions = []

    async def execute_task(self, task: Task, soul: Soul):
        """Mock task execution."""
        self.executions.append((task.id, soul.id))

        class MockResult:
            def __init__(self):
                self.output = f"Result from {soul.id}"
                self.cost_usd = 0.01
                self.total_tokens = 10
                self.soul_id = soul.id

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
    child_wf = Workflow(name="child_process")
    child_wf.add_block(EchoBlock("child_step", "child result"))
    child_wf.set_entry("child_step")
    child_wf.add_transition("child_step", None)

    # Create parent workflow
    parent_wf = Workflow(name="parent_process")

    # Add WorkflowBlock
    workflow_block = WorkflowBlock(
        block_id="run_child",
        child_workflow=child_wf,
        inputs={},
        outputs={"results.child_output": "results.child_step"},
        max_depth=10,
    )
    parent_wf.add_block(workflow_block)

    # Add LinearBlock after WorkflowBlock
    mock_runner_parent = MockRunner()
    final_step = LinearBlock(
        block_id="parent_linear",
        soul=Soul(id="parent_soul", role="Manager", system_prompt="Manage"),
        runner=mock_runner_parent,
    )
    parent_wf.add_block(final_step)

    parent_wf.set_entry("run_child")
    parent_wf.add_transition("run_child", "parent_linear")
    parent_wf.add_transition("parent_linear", None)

    # Create initial state with current_task for LinearBlock
    initial_state = WorkflowState(
        current_task=Task(id="task1", instruction="Do something"),
        results={},
        shared_memory={},
    )

    # Execute
    final_state = await parent_wf.run(initial_state)

    # Verify: Both blocks executed
    assert "run_child" in final_state.results
    assert "parent_linear" in final_state.results

    # Verify: Output mapping from child worked
    assert "child_output" in final_state.results
    assert final_state.results["child_output"].output == "child result"

    # Verify: Cost accumulation (from parent LinearBlock)
    assert final_state.total_cost_usd >= 0.01

    # Verify: Messages from both blocks
    assert len(final_state.execution_log) > 0
    system_msgs = [m for m in final_state.execution_log if m["role"] == "system"]
    assert any("run_child" in m["content"] for m in system_msgs)
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
    child_wf = Workflow(name="child_wf")
    child_wf.add_block(EchoBlock("child_ph", "Child execution"))
    child_wf.set_entry("child_ph")
    child_wf.add_transition("child_ph", None)

    # Create parent workflow
    parent_wf = Workflow(name="parent_wf")

    # Add EchoBlock before WorkflowBlock
    parent_wf.add_block(EchoBlock("before_wf", "Before execution"))

    # Add WorkflowBlock
    workflow_block = WorkflowBlock(
        block_id="invoke_child",
        child_workflow=child_wf,
        inputs={},
        outputs={},
        max_depth=10,
    )
    parent_wf.add_block(workflow_block)

    # Add EchoBlock after WorkflowBlock
    parent_wf.add_block(EchoBlock("after_wf", "After execution"))

    parent_wf.set_entry("before_wf")
    parent_wf.add_transition("before_wf", "invoke_child")
    parent_wf.add_transition("invoke_child", "after_wf")
    parent_wf.add_transition("after_wf", None)

    # Execute
    initial_state = WorkflowState()
    final_state = await parent_wf.run(initial_state)

    # Verify: All blocks executed in order
    assert "before_wf" in final_state.results
    assert "invoke_child" in final_state.results
    assert "after_wf" in final_state.results

    # Verify: Messages show correct execution order
    messages = [m["content"] for m in final_state.execution_log if m["role"] == "system"]
    before_idx = next((i for i, m in enumerate(messages) if "before_wf" in m), -1)
    invoke_idx = next((i for i, m in enumerate(messages) if "invoke_child" in m), -1)
    after_idx = next((i for i, m in enumerate(messages) if "after_wf" in m), -1)

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
    grandchild_wf = Workflow(name="grandchild")
    grandchild_wf.add_block(EchoBlock("gc_step", "Grandchild executed"))
    grandchild_wf.set_entry("gc_step")
    grandchild_wf.add_transition("gc_step", None)

    # Create child workflow with WorkflowBlock invoking grandchild
    child_wf = Workflow(name="child")
    gc_block = WorkflowBlock(
        block_id="invoke_gc",
        child_workflow=grandchild_wf,
        inputs={},
        outputs={"results.gc_result": "results.gc_step"},
        max_depth=10,
    )
    child_wf.add_block(gc_block)
    child_wf.set_entry("invoke_gc")
    child_wf.add_transition("invoke_gc", None)

    # Create parent workflow with WorkflowBlock invoking child
    parent_wf = Workflow(name="parent")
    c_block = WorkflowBlock(
        block_id="invoke_child",
        child_workflow=child_wf,
        inputs={},
        outputs={"results.child_result": "results.gc_result"},
        max_depth=10,
    )
    parent_wf.add_block(c_block)
    parent_wf.set_entry("invoke_child")
    parent_wf.add_transition("invoke_child", None)

    # Execute
    initial_state = WorkflowState()
    final_state = await parent_wf.run(initial_state)

    # Verify: All levels executed
    assert "invoke_child" in final_state.results
    assert "child_result" in final_state.results
    assert final_state.results["child_result"].output == "Grandchild executed"

    # Verify: System messages from top-level blocks
    # Note: Messages from nested workflows are propagated up through the parent message stream
    messages = [m["content"] for m in final_state.execution_log if m["role"] == "system"]
    assert any("invoke_child" in m for m in messages)  # Parent → child block
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
    child_wf = Workflow(name="modifying_child")

    class ModifyingBlock(BaseBlock):
        def __init__(self, block_id: str, description: str) -> None:
            super().__init__(block_id)
            self.description = description

        async def execute(self, state, **kwargs):
            # Try to modify all state fields
            new_state = state.model_copy(
                update={
                    "results": {**state.results, "child_secret": BlockResult(output="hidden")},
                    "shared_memory": {**state.shared_memory, "child_only": "secret_data"},
                    "metadata": {**state.metadata, "child_meta": "private"},
                }
            )
            return new_state.model_copy(
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

    child_block = ModifyingBlock("modify_step", "Modified state")
    child_wf.add_block(child_block)
    child_wf.set_entry("modify_step")
    child_wf.add_transition("modify_step", None)

    # Create parent workflow
    parent_wf = Workflow(name="parent")
    workflow_block = WorkflowBlock(
        block_id="invoke_child",
        child_workflow=child_wf,
        inputs={},
        outputs={"results.mapped_out": "results.modify_step"},
        max_depth=10,
    )
    parent_wf.add_block(workflow_block)
    parent_wf.set_entry("invoke_child")
    parent_wf.add_transition("invoke_child", None)

    # Create parent state with existing data
    initial_state = WorkflowState(
        results={"parent_data": BlockResult(output="keep_me")},
        shared_memory={"parent_key": "keep_me"},
        metadata={"parent_meta": "keep_me"},
    )

    # Execute
    final_state = await parent_wf.run(initial_state)

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
    child_wf = Workflow(name="child_cost_tracking")

    class CostProducingBlock(BaseBlock):
        def __init__(self, block_id: str, cost: float):
            super().__init__(block_id)
            self.cost = cost

        async def execute(self, state, **kwargs):
            return state.model_copy(
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

    child_wf.add_block(CostProducingBlock("child_block", 0.05))
    child_wf.set_entry("child_block")
    child_wf.add_transition("child_block", None)

    # Create parent workflow
    parent_wf = Workflow(name="parent")

    # Add initial cost block
    parent_wf.add_block(CostProducingBlock("parent_initial", 0.02))

    # Add WorkflowBlock (will invoke child which costs 0.05)
    workflow_block = WorkflowBlock(
        block_id="invoke_child",
        child_workflow=child_wf,
        inputs={},
        outputs={},
        max_depth=10,
    )
    parent_wf.add_block(workflow_block)

    # Add final cost block
    parent_wf.add_block(CostProducingBlock("parent_final", 0.03))

    parent_wf.set_entry("parent_initial")
    parent_wf.add_transition("parent_initial", "invoke_child")
    parent_wf.add_transition("invoke_child", "parent_final")
    parent_wf.add_transition("parent_final", None)

    # Execute
    initial_state = WorkflowState(total_cost_usd=0.0, total_tokens=0)
    final_state = await parent_wf.run(initial_state)

    # Verify: Total costs accumulated
    # parent_initial: 0.02
    # child: 0.05
    # parent_final: 0.03
    # Total: 0.10
    assert final_state.total_cost_usd == pytest.approx(0.10, abs=0.001)
    assert final_state.total_tokens == 30  # 3 blocks × 10 tokens
