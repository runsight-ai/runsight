"""
RUN-605 — Failing tests for on_error modes on sub-workflow nodes.

WorkflowBlock currently does NOT accept an ``on_error`` parameter and
WorkflowBlockDef does NOT have an ``on_error`` field.  These tests exercise
the new contract and MUST fail against the current implementation because:

  - WorkflowBlock.__init__ does not accept ``on_error``
  - WorkflowBlockDef does not have an ``on_error`` field
  - WorkflowBlock.execute() never catches child exceptions to produce an
    ``exit_handle="error"`` result
  - No child_status="failed" or child_error metadata is ever produced

AC:
  1. ``raise`` preserves current behavior (child exception propagates)
  2. ``catch`` produces a normal BlockResult with exit_handle="error"
  3. Parent status and child status remain distinguishable in monitoring
  4. No alternate/legacy error-routing path for callable sub-workflows
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from runsight_core.block_io import apply_block_output, build_block_context
from runsight_core.blocks.workflow_block import WorkflowBlock, WorkflowBlockDef
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.workflow import Workflow
from runsight_core.yaml.schema import (
    WorkflowInterfaceDef,
    WorkflowInterfaceInputDef,
    WorkflowInterfaceOutputDef,
)


async def _exec(block, state, **extra_inputs):
    """Helper: build BlockContext, execute block, apply output to state."""
    ctx = build_block_context(block, state)
    if extra_inputs:
        ctx = ctx.model_copy(update={"inputs": {**ctx.inputs, **extra_inputs}})
    output = await block.execute(ctx)
    return apply_block_output(state, block.block_id, output)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FailingBlock:
    """Fake block that always raises during execute."""

    def __init__(self, block_id: str, *, error_msg: str = "child block failed"):
        self.block_id = block_id
        self.retry_config = None
        self.stateful = False
        self._error_msg = error_msg

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        raise RuntimeError(self._error_msg)


class _WriterBlock:
    """Fake block that writes a hard-coded value into results."""

    def __init__(self, block_id: str, *, value: str = "written"):
        self.block_id = block_id
        self.retry_config = None
        self.stateful = False
        self._value = value

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        return state.model_copy(
            update={
                "results": {
                    **state.results,
                    self.block_id: BlockResult(output=self._value),
                },
            }
        )


def _build_child_workflow(name: str, block: object) -> Workflow:
    """Build a single-block child workflow for testing."""
    wf = Workflow(name=name)
    wf.add_block(block)
    wf.set_entry(block.block_id)
    return wf


def _make_interface(
    inputs: list[dict] | None = None,
    outputs: list[dict] | None = None,
) -> WorkflowInterfaceDef:
    return WorkflowInterfaceDef(
        inputs=[WorkflowInterfaceInputDef(**i) for i in (inputs or [])],
        outputs=[WorkflowInterfaceOutputDef(**o) for o in (outputs or [])],
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestOnErrorModes:
    """All tests target the new on_error parameter for WorkflowBlock."""

    async def test_on_error_raise_propagates_child_exception(self) -> None:
        """
        AC1: With on_error="raise" (explicit), the child exception must
        propagate to the caller unchanged.
        """
        interface = _make_interface(
            inputs=[{"name": "topic", "target": "shared_memory.topic"}],
        )

        child_block = _FailingBlock("fail_block", error_msg="kaboom")
        child_wf = _build_child_workflow("child_wf", child_block)

        wb = WorkflowBlock(
            block_id="invoke_child",
            child_workflow=child_wf,
            inputs={"topic": "shared_memory.parent_topic"},
            outputs={},
            interface=interface,
            on_error="raise",
        )

        parent_state = WorkflowState(
            shared_memory={"parent_topic": "testing"},
        )

        with pytest.raises(RuntimeError, match="kaboom"):
            await _exec(wb, parent_state)

    async def test_on_error_catch_returns_error_exit_handle(self) -> None:
        """
        AC2: With on_error="catch", child failure must NOT propagate.
        Instead, execute() returns a WorkflowState where the BlockResult
        for this block has exit_handle="error".
        """
        interface = _make_interface(
            inputs=[{"name": "topic", "target": "shared_memory.topic"}],
        )

        child_block = _FailingBlock("fail_block", error_msg="child exploded")
        child_wf = _build_child_workflow("child_wf", child_block)

        wb = WorkflowBlock(
            block_id="invoke_child",
            child_workflow=child_wf,
            inputs={"topic": "shared_memory.parent_topic"},
            outputs={},
            interface=interface,
            on_error="catch",
        )

        parent_state = WorkflowState(
            shared_memory={"parent_topic": "testing"},
        )

        # Must NOT raise — the error is caught
        result_state = await _exec(wb, parent_state)

        br = result_state.results.get("invoke_child")
        assert br is not None, "WorkflowBlock must store its own BlockResult even on catch"
        assert isinstance(br, BlockResult)
        assert br.exit_handle == "error", (
            f"exit_handle must be 'error' for caught child failure, got '{br.exit_handle}'"
        )

    async def test_on_error_catch_metadata_includes_child_status_failed(self) -> None:
        """
        AC3: With on_error="catch", the BlockResult.metadata must include
        child_status="failed" so parent and child status are distinguishable.
        """
        interface = _make_interface(
            inputs=[{"name": "topic", "target": "shared_memory.topic"}],
        )

        child_block = _FailingBlock("fail_block")
        child_wf = _build_child_workflow("child_wf", child_block)

        wb = WorkflowBlock(
            block_id="invoke_child",
            child_workflow=child_wf,
            inputs={"topic": "shared_memory.parent_topic"},
            outputs={},
            interface=interface,
            on_error="catch",
        )

        parent_state = WorkflowState(
            shared_memory={"parent_topic": "testing"},
        )

        result_state = await _exec(wb, parent_state)

        br = result_state.results["invoke_child"]
        assert br.metadata is not None, "metadata must be populated on catch"
        assert br.metadata.get("child_status") == "failed", (
            f"child_status must be 'failed', got '{br.metadata.get('child_status')}'"
        )

    async def test_on_error_catch_metadata_includes_error_message(self) -> None:
        """
        AC3 (extended): metadata should include the error message so the
        parent workflow can inspect what went wrong without re-raising.
        """
        interface = _make_interface(
            inputs=[{"name": "topic", "target": "shared_memory.topic"}],
        )

        child_block = _FailingBlock("fail_block", error_msg="timeout reached")
        child_wf = _build_child_workflow("child_wf", child_block)

        wb = WorkflowBlock(
            block_id="invoke_child",
            child_workflow=child_wf,
            inputs={"topic": "shared_memory.parent_topic"},
            outputs={},
            interface=interface,
            on_error="catch",
        )

        parent_state = WorkflowState(
            shared_memory={"parent_topic": "testing"},
        )

        result_state = await _exec(wb, parent_state)

        br = result_state.results["invoke_child"]
        assert br.metadata is not None
        assert "child_error" in br.metadata, "metadata must include 'child_error' key"
        assert "timeout reached" in br.metadata["child_error"], (
            f"child_error must contain the exception message, got '{br.metadata.get('child_error')}'"
        )

    async def test_on_error_catch_does_not_map_outputs(self) -> None:
        """
        When on_error="catch" and the child fails, output mapping must NOT
        happen (child state is incomplete/absent). The parent state should
        remain unchanged except for the WorkflowBlock's own BlockResult.
        """
        interface = _make_interface(
            inputs=[{"name": "topic", "target": "shared_memory.topic"}],
            outputs=[{"name": "summary", "source": "results.writer"}],
        )

        child_block = _FailingBlock("writer", error_msg="writer crashed")
        child_wf = _build_child_workflow("child_wf", child_block)

        wb = WorkflowBlock(
            block_id="invoke_child",
            child_workflow=child_wf,
            inputs={"topic": "shared_memory.parent_topic"},
            outputs={"results.analysis": "summary"},
            interface=interface,
            on_error="catch",
        )

        parent_state = WorkflowState(
            shared_memory={"parent_topic": "testing"},
        )

        result_state = await _exec(wb, parent_state)

        # The child crashed, so "results.analysis" should NOT exist in parent
        assert "analysis" not in result_state.results, (
            "Output mapping must be skipped when child fails under on_error='catch'"
        )

        # But the WorkflowBlock's own result must exist
        br = result_state.results.get("invoke_child")
        assert br is not None
        assert br.exit_handle == "error"

    async def test_on_error_default_is_raise(self) -> None:
        """
        When on_error is NOT specified, the default behavior must be
        identical to on_error="raise" — the child exception propagates.
        """
        interface = _make_interface(
            inputs=[{"name": "topic", "target": "shared_memory.topic"}],
        )

        child_block = _FailingBlock("fail_block", error_msg="default should raise")
        child_wf = _build_child_workflow("child_wf", child_block)

        # on_error not passed — should default to "raise"
        wb = WorkflowBlock(
            block_id="invoke_child",
            child_workflow=child_wf,
            inputs={"topic": "shared_memory.parent_topic"},
            outputs={},
            interface=interface,
            on_error="raise",
        )

        parent_state = WorkflowState(
            shared_memory={"parent_topic": "testing"},
        )

        with pytest.raises(RuntimeError, match="default should raise"):
            await _exec(wb, parent_state)


class TestWorkflowBlockDefOnErrorField:
    """Schema tests for the on_error field on WorkflowBlockDef."""

    def test_workflow_block_def_accepts_on_error_raise(self) -> None:
        """WorkflowBlockDef must accept on_error='raise'."""
        block_def = WorkflowBlockDef(
            type="workflow",
            workflow_ref="child_wf",
            on_error="raise",
        )
        assert block_def.on_error == "raise"

    def test_workflow_block_def_accepts_on_error_catch(self) -> None:
        """WorkflowBlockDef must accept on_error='catch'."""
        block_def = WorkflowBlockDef(
            type="workflow",
            workflow_ref="child_wf",
            on_error="catch",
        )
        assert block_def.on_error == "catch"

    def test_workflow_block_def_default_on_error_is_raise(self) -> None:
        """When on_error is not specified, the default must be 'raise'."""
        block_def = WorkflowBlockDef(
            type="workflow",
            workflow_ref="child_wf",
        )
        assert block_def.on_error == "raise"

    def test_workflow_block_def_rejects_invalid_on_error(self) -> None:
        """Invalid on_error values must be rejected by Pydantic.

        The field must exist and accept valid Literal values. An invalid
        value like "ignore" must be rejected with a validation error that
        mentions the allowed values, NOT rejected as an unknown extra field.
        """
        # First, confirm valid values are accepted (field exists)
        valid = WorkflowBlockDef(
            type="workflow",
            workflow_ref="child_wf",
            on_error="raise",
        )
        assert valid.on_error == "raise"

        # Then confirm invalid value is rejected
        with pytest.raises(ValidationError, match="raise|catch"):
            WorkflowBlockDef(
                type="workflow",
                workflow_ref="child_wf",
                on_error="ignore",
            )
