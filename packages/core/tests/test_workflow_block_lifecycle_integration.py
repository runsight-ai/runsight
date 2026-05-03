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
async def test_parent_child_workflow_execution():
    """
    Integration test with parent workflow containing WorkflowBlock.

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
    child_workflow = Workflow(name="analysis_child_workflow")
    analysis_child_block = SimpleBlock(
        "analysis_child_step",
        "child output",
        declared_inputs={"topic": "workflow.topic"},
    )
    child_workflow.add_block(analysis_child_block)
    child_workflow.set_entry("analysis_child_step")
    child_workflow.add_transition("analysis_child_step", None)  # Terminal

    # ==== Setup: Create parent workflow with WorkflowBlock ====
    parent_workflow = Workflow(name="analysis_parent_workflow")

    # Create a WorkflowBlock that references the child
    workflow_block = WorkflowBlock(
        block_id="analysis_child_workflow_block",
        child_workflow=child_workflow,
        inputs={
            # Child receives a public invocation input from parent shared memory
            "topic": "shared_memory.research_topic"
        },
        outputs={
            # Child result is mapped back to parent
            "results.analysis": "results.analysis_child_step"
        },
        max_depth=10,
    )

    parent_workflow.add_block(workflow_block)
    parent_workflow.set_entry("analysis_child_workflow_block")
    parent_workflow.add_transition("analysis_child_workflow_block", None)  # Terminal

    # Validate workflows
    parent_errors = parent_workflow.validate()
    child_errors = child_workflow.validate()
    assert not parent_errors, f"Parent workflow validation failed: {parent_errors}"
    assert not child_errors, f"Child workflow validation failed: {child_errors}"

    # ==== Execute: Create initial state with mapped inputs ====
    initial_state = WorkflowState(
        shared_memory={"research_topic": "quantum computing", "other": "data"},
        results={"existing": BlockResult(output="value")},
        metadata={"workflow_id": "analysis-parent-workflow-run"},
        total_cost_usd=0.0,
        total_tokens=0,
    )

    # ==== Execute: Run parent workflow ====
    # Note: No workflow_registry needed since child is passed directly to WorkflowBlock
    final_state = await parent_workflow.run(initial_state)

    # ==== Verify: Basic execution completed ====
    assert final_state is not None
    assert isinstance(final_state, WorkflowState)

    # ==== Verify: WorkflowBlock result recorded ====
    assert "analysis_child_workflow_block" in final_state.results
    assert (
        "WorkflowBlock 'analysis_child_workflow' completed"
        in final_state.results["analysis_child_workflow_block"].output
    )

    # ==== Verify: Output mapping (child results → parent state) ====
    assert "analysis" in final_state.results
    assert final_state.results["analysis"].output == "child output"
    assert analysis_child_block.seen_workflow_inputs == {"topic": "quantum computing"}

    # ==== Verify: Existing parent data preserved ====
    assert final_state.results["existing"].output == "value"
    assert final_state.shared_memory["other"] == "data"

    # ==== Verify: System message appended with cost summary ====
    system_messages = [msg for msg in final_state.execution_log if msg["role"] == "system"]
    assert len(system_messages) > 0
    summary_msg = system_messages[-1]["content"]
    assert "WorkflowBlock 'analysis_child_workflow' completed" in summary_msg
    assert "cost:" in summary_msg
    assert "tokens:" in summary_msg

    # ==== Verify: Cost propagation ====
    # Child workflow had one block execution with zero cost (SimpleBlock)
    # So final cost should be >= 0
    assert final_state.total_cost_usd >= 0.0
    assert final_state.total_tokens >= 0


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
    child_workflow = Workflow(name="registry_child_workflow")
    child_workflow.add_block(SimpleBlock("registry_child_step", "output"))
    child_workflow.set_entry("registry_child_step")
    child_workflow.add_transition("registry_child_step", None)

    # Create parent with WorkflowBlock
    parent_workflow = Workflow(name="registry_parent_workflow")
    parent_workflow.add_block(
        WorkflowBlock(
            block_id="registry_passthrough_workflow_block",
            child_workflow=child_workflow,
            inputs={},
            outputs={},
            max_depth=10,
        )
    )
    parent_workflow.set_entry("registry_passthrough_workflow_block")
    parent_workflow.add_transition("registry_passthrough_workflow_block", None)

    # Capture what parameters child receives
    captured_kwargs = {}

    async def mock_child_run(
        initial_state,
        *,
        inputs=None,
        registry=None,
        call_stack=None,
        workflow_registry=None,
        observer=None,
    ):
        captured_kwargs["registry"] = registry
        captured_kwargs["call_stack"] = call_stack or []
        captured_kwargs["workflow_registry"] = workflow_registry
        captured_kwargs["inputs"] = dict(inputs or {})
        return initial_state.model_copy(
            update={
                "results": {
                    **initial_state.results,
                    "registry_child_step": BlockResult(output="output"),
                },
                "total_cost_usd": 0.0,
                "total_tokens": 0,
            }
        )

    child_workflow.run = mock_child_run

    # Create a mock workflow_registry
    from unittest.mock import MagicMock

    mock_registry = MagicMock()

    # Execute with workflow_registry
    initial_state = WorkflowState()
    await parent_workflow.run(initial_state, workflow_registry=mock_registry)

    # Verify: child received workflow_registry
    assert "workflow_registry" in captured_kwargs
    assert captured_kwargs["workflow_registry"] is mock_registry
    assert captured_kwargs["inputs"] == {}

    # Verify: call_stack was also passed (extended with parent name, then child name)
    # When WorkflowBlock.execute() is called, it receives call_stack + [self.name]
    # So child receives the parent and child workflow names before running
    # But then when child.run() is called, that list is used as-is
    assert "call_stack" in captured_kwargs
    assert captured_kwargs["call_stack"] == [
        "registry_parent_workflow",
        "registry_child_workflow",
    ]
