"""
RUN-701 — Additional state isolation verification tests.

Strengthens coverage for WorkflowBlock child→parent state isolation:
- Verifies mapped output VALUE (not just key presence)
- Verifies raw child block IDs don't leak as unmapped results
- Tests empty output mapping (nothing should leak)
- Enumerates parent results to ensure only expected keys exist
"""

import pytest
from conftest import block_output_from_state
from runsight_core import WorkflowBlock
from runsight_core.blocks.base import BaseBlock
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.workflow import Workflow


class ChildBlock(BaseBlock):
    """A child block that creates multiple result keys."""

    def __init__(self, block_id: str, output_text: str) -> None:
        super().__init__(block_id)
        self.output_text = output_text

    async def execute(self, ctx):
        state = ctx.state_snapshot
        next_state = state.model_copy(
            update={
                "results": {
                    **state.results,
                    self.block_id: BlockResult(output=self.output_text),
                    "internal_temp": BlockResult(output="scratch_value"),
                    "another_child_key": BlockResult(output="should_not_leak"),
                },
                "execution_log": state.execution_log
                + [
                    {
                        "role": "system",
                        "content": f"[Block {self.block_id}] ChildBlock executed",
                    }
                ],
            }
        )
        return block_output_from_state(self.block_id, state, next_state)


def _make_child_workflow(block_id: str = "child_step", output_text: str = "child_output"):
    """Helper: create a single-block child workflow."""
    wf = Workflow(name="child_wf")
    block = ChildBlock(block_id, output_text)
    wf.add_block(block)
    wf.set_entry(block_id)
    wf.add_transition(block_id, None)
    return wf


def _make_parent_workflow(child_wf, outputs, block_id="invoke_child"):
    """Helper: wrap a child workflow in a parent WorkflowBlock."""
    parent_wf = Workflow(name="parent_wf")
    wb = WorkflowBlock(
        block_id=block_id,
        child_workflow=child_wf,
        inputs={},
        outputs=outputs,
        max_depth=10,
    )
    parent_wf.add_block(wb)
    parent_wf.set_entry(block_id)
    parent_wf.add_transition(block_id, None)
    return parent_wf


@pytest.mark.asyncio
async def test_mapped_output_has_correct_value():
    """AC3: Mapped output should carry the correct value from the child, not just exist as a key."""
    child_wf = _make_child_workflow("child_step", "expected_output_value")
    parent_wf = _make_parent_workflow(
        child_wf,
        outputs={"results.my_output": "results.child_step"},
    )

    initial_state = WorkflowState(
        results={"pre_existing": BlockResult(output="original")},
    )

    final_state = await parent_wf.run(initial_state)

    # The mapped output must exist AND have the correct value
    assert "my_output" in final_state.results, "Mapped output key should be present"
    assert final_state.results["my_output"].output == "expected_output_value", (
        "Mapped output should carry the child block's actual output value"
    )


@pytest.mark.asyncio
async def test_unmapped_child_block_id_not_in_parent():
    """AC2: The raw child block ID (e.g. 'child_step') must NOT appear in parent results."""
    child_wf = _make_child_workflow("child_step", "some_value")
    parent_wf = _make_parent_workflow(
        child_wf,
        outputs={"results.mapped": "results.child_step"},
    )

    initial_state = WorkflowState()

    final_state = await parent_wf.run(initial_state)

    # 'child_step' is the child's block ID — it should NOT leak to parent
    assert "child_step" not in final_state.results, (
        "Raw child block ID should not appear in parent results"
    )
    # Other internal child keys should also not leak
    assert "internal_temp" not in final_state.results, (
        "Internal child result keys should not leak to parent"
    )
    assert "another_child_key" not in final_state.results, (
        "Unmapped child result keys should not leak to parent"
    )


@pytest.mark.asyncio
async def test_empty_outputs_mapping_leaks_nothing():
    """AC2: When outputs={}, NO child results should appear in parent (only the WorkflowBlock's own result)."""
    child_wf = _make_child_workflow("child_step", "invisible_output")
    parent_wf = _make_parent_workflow(
        child_wf,
        outputs={},  # No mappings at all
        block_id="wb_block",
    )

    initial_state = WorkflowState(
        results={"original": BlockResult(output="stays")},
    )

    final_state = await parent_wf.run(initial_state)

    # Only the parent's original data + the WorkflowBlock's own summary should be present.
    # "workflow" is a sentinel key seeded by Workflow.run() itself and is expected.
    expected_keys = {"original", "wb_block", "workflow"}
    actual_keys = set(final_state.results.keys())
    unexpected = actual_keys - expected_keys
    assert not unexpected, (
        f"Unexpected child results leaked to parent: {unexpected}. "
        f"With empty outputs mapping, only parent originals + WorkflowBlock "
        f"summary should exist."
    )


@pytest.mark.asyncio
async def test_parent_results_contain_only_expected_keys():
    """AC2+AC3: Exhaustively verify parent results contain ONLY expected keys after execution."""
    child_wf = _make_child_workflow("child_step", "mapped_value")
    parent_wf = _make_parent_workflow(
        child_wf,
        outputs={"results.out": "results.child_step"},
        block_id="invoke_child",
    )

    initial_state = WorkflowState(
        results={"parent_original": BlockResult(output="keep")},
    )

    final_state = await parent_wf.run(initial_state)

    # Exactly these keys should be present:
    # - parent_original: pre-existing parent data
    # - out: the mapped output
    # - invoke_child: the WorkflowBlock's own summary result
    # - workflow: sentinel key seeded by Workflow.run() itself
    expected_keys = {"parent_original", "out", "invoke_child", "workflow"}
    actual_keys = set(final_state.results.keys())
    unexpected = actual_keys - expected_keys
    missing = expected_keys - actual_keys

    assert not unexpected, f"Unexpected keys leaked from child to parent: {unexpected}"
    assert not missing, f"Expected keys missing from parent results: {missing}"
