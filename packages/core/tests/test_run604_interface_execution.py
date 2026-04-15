"""
RUN-604 — Failing tests for interface-bound WorkflowBlock execution.

WorkflowBlock currently maps inputs/outputs using raw dict keys as child state
paths.  After RUN-603 the contract changed: ``inputs`` maps
``{interface_name: parent_path}`` and ``outputs`` maps
``{parent_path: interface_name}``.  The interface's ``target`` (on inputs) and
``source`` (on outputs) supply the child's internal state path.

These tests exercise the new contract and MUST fail against the current
implementation because:
  - WorkflowBlock.__init__ does not accept a ``WorkflowInterfaceDef``
  - _map_inputs writes to the interface *name* ("topic") instead of the
    interface *target* ("shared_memory.topic")
  - _map_outputs reads from the interface *name* instead of the interface
    *source*
  - BlockResult.metadata does not carry compact child-workflow metadata
  - exit_handle is not populated by WorkflowBlock.execute()
"""

from __future__ import annotations

import pytest
from runsight_core.block_io import apply_block_output, build_block_context
from runsight_core.blocks.workflow_block import WorkflowBlock
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


class _EchoBlock:
    """Minimal fake block that copies a shared_memory key into results."""

    def __init__(self, block_id: str, *, copy_key: str | None = None):
        self.block_id = block_id
        self.retry_config = None
        self.stateful = False
        self._copy_key = copy_key

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        output_value = ""
        if self._copy_key:
            output_value = str(state.shared_memory.get(self._copy_key, ""))
        return state.model_copy(
            update={
                "results": {
                    **state.results,
                    self.block_id: BlockResult(output=output_value),
                },
            }
        )


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


class _EmptyBlock:
    """Fake block that produces no results at all."""

    def __init__(self, block_id: str):
        self.block_id = block_id
        self.retry_config = None
        self.stateful = False

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        return state  # no results written


def _build_child_workflow(
    name: str,
    block: object,
) -> Workflow:
    """Build a single-block child workflow for testing."""
    wf = Workflow(name=name)
    wf.add_block(block)
    wf.set_entry(block.block_id)
    # terminal — no transitions needed
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
class TestInterfaceBoundExecution:
    """All tests target the new interface-mediated input/output mapping."""

    async def test_workflow_block_maps_inputs_through_interface_targets(self) -> None:
        """
        Parent binds ``inputs: {"topic": "shared_memory.parent_topic"}``.
        Interface declares ``{name: "topic", target: "shared_memory.topic"}``.
        The child MUST receive the value at ``shared_memory.topic``, not at the
        raw interface name "topic".
        """
        interface = _make_interface(
            inputs=[{"name": "topic", "target": "shared_memory.topic"}],
            outputs=[{"name": "echo_result", "source": "results.echo"}],
        )

        child_block = _EchoBlock("echo", copy_key="topic")
        child_wf = _build_child_workflow("child_wf", child_block)

        # --- The constructor must accept interface; this will fail today ---
        wb = WorkflowBlock(
            block_id="invoke_child",
            child_workflow=child_wf,
            inputs={"topic": "shared_memory.parent_topic"},
            outputs={"results.echo": "echo_result"},
            interface=interface,
        )

        parent_state = WorkflowState(
            shared_memory={"parent_topic": "climate change"},
        )

        result_state = await _exec(wb, parent_state)

        # The child should have received the value at shared_memory.topic
        # (the interface target), NOT at "topic" (the raw interface name).
        # Interface output mapping unwraps BlockResult to .output (a string).
        child_echo = result_state.results.get("echo")
        assert child_echo is not None
        assert child_echo == "climate change"

    async def test_workflow_block_maps_outputs_through_interface_sources(self) -> None:
        """
        Interface declares ``{name: "summary", source: "results.writer"}``.
        Parent binds ``outputs: {"results.analysis": "summary"}``.
        After execution the parent state must have ``results.analysis`` populated
        from ``results.writer`` in the child's final state.
        """
        interface = _make_interface(
            inputs=[{"name": "topic", "target": "shared_memory.topic"}],
            outputs=[{"name": "summary", "source": "results.writer"}],
        )

        child_block = _WriterBlock("writer", value="child analysis output")
        child_wf = _build_child_workflow("child_wf", child_block)

        wb = WorkflowBlock(
            block_id="invoke_child",
            child_workflow=child_wf,
            inputs={"topic": "shared_memory.parent_topic"},
            outputs={"results.analysis": "summary"},
            interface=interface,
        )

        parent_state = WorkflowState(
            shared_memory={"parent_topic": "climate"},
        )

        result_state = await _exec(wb, parent_state)

        # Parent must see the child's results.writer value at results.analysis
        analysis = result_state.results.get("analysis")
        assert analysis is not None
        assert str(analysis) == "child analysis output"

    async def test_workflow_block_unwraps_parent_block_results_for_interface_inputs(self) -> None:
        """
        Interface input bindings may point at ``results.some_block`` on the parent.
        The child must receive the BlockResult.output string, not the BlockResult object.
        """
        interface = _make_interface(
            inputs=[{"name": "topic", "target": "shared_memory.topic"}],
            outputs=[{"name": "summary", "source": "results.echo"}],
        )

        child_block = _EchoBlock("echo", copy_key="topic")
        child_wf = _build_child_workflow("child_wf", child_block)

        wb = WorkflowBlock(
            block_id="invoke_child",
            child_workflow=child_wf,
            inputs={"topic": "results.prepare_input"},
            outputs={"results.analysis": "summary"},
            interface=interface,
        )

        parent_state = WorkflowState(
            results={"prepare_input": BlockResult(output="climate change")},
        )

        result_state = await _exec(wb, parent_state)

        analysis = result_state.results.get("analysis")
        assert analysis is not None
        assert str(analysis) == "climate change"

    async def test_workflow_block_returns_compact_metadata(self) -> None:
        """
        After execution ``BlockResult.metadata`` MUST contain:
        - child_status
        - child_cost_usd
        - child_tokens
        - child_duration_s

        It MUST NOT contain raw child block outputs or full child result maps.
        """
        interface = _make_interface(
            inputs=[{"name": "topic", "target": "shared_memory.topic"}],
        )

        child_block = _WriterBlock("writer", value="done")
        child_wf = _build_child_workflow("child_wf", child_block)

        wb = WorkflowBlock(
            block_id="invoke_child",
            child_workflow=child_wf,
            inputs={"topic": "shared_memory.parent_topic"},
            outputs={},
            interface=interface,
        )

        parent_state = WorkflowState(
            shared_memory={"parent_topic": "testing"},
        )

        result_state = await _exec(wb, parent_state)

        br = result_state.results.get("invoke_child")
        assert br is not None, "WorkflowBlock must store its own BlockResult"
        assert isinstance(br, BlockResult)

        # Required metadata keys
        assert br.metadata is not None, "metadata must be populated"
        assert "child_status" in br.metadata
        assert "child_cost_usd" in br.metadata
        assert "child_tokens" in br.metadata
        assert "child_duration_s" in br.metadata
        assert "child_run_id" in br.metadata

        # Must NOT leak raw child results
        assert "writer" not in br.metadata
        assert "results" not in br.metadata

    async def test_workflow_block_returns_exit_handle(self) -> None:
        """
        For a successful child execution the BlockResult should carry an
        ``exit_handle`` that a parent conditional transition can consume
        (e.g. "completed").
        """
        interface = _make_interface(
            inputs=[{"name": "topic", "target": "shared_memory.topic"}],
        )

        child_block = _WriterBlock("writer", value="ok")
        child_wf = _build_child_workflow("child_wf", child_block)

        wb = WorkflowBlock(
            block_id="invoke_child",
            child_workflow=child_wf,
            inputs={"topic": "shared_memory.parent_topic"},
            outputs={},
            interface=interface,
        )

        parent_state = WorkflowState(
            shared_memory={"parent_topic": "test"},
        )

        result_state = await _exec(wb, parent_state)

        br = result_state.results.get("invoke_child")
        assert br is not None
        assert br.exit_handle is not None, "exit_handle must be set for routing"
        assert br.exit_handle == "completed"

    async def test_workflow_block_missing_output_source_at_runtime(self) -> None:
        """
        Interface declares ``{name: "summary", source: "results.nonexistent"}``.
        The child workflow never produces ``results.nonexistent``.
        A clear error MUST be raised at output-mapping time.
        """
        interface = _make_interface(
            inputs=[{"name": "topic", "target": "shared_memory.topic"}],
            outputs=[{"name": "summary", "source": "results.nonexistent"}],
        )

        child_block = _WriterBlock("writer", value="some output")
        child_wf = _build_child_workflow("child_wf", child_block)

        wb = WorkflowBlock(
            block_id="invoke_child",
            child_workflow=child_wf,
            inputs={"topic": "shared_memory.parent_topic"},
            outputs={"results.parent_summary": "summary"},
            interface=interface,
        )

        parent_state = WorkflowState(
            shared_memory={"parent_topic": "test"},
        )

        with pytest.raises((KeyError, ValueError)):
            await _exec(wb, parent_state)

    async def test_workflow_block_repeated_invocation(self) -> None:
        """
        Two sequential invocations of the same WorkflowBlock with different
        parent state must produce independent results.  No child state should
        leak between runs.
        """
        interface = _make_interface(
            inputs=[{"name": "topic", "target": "shared_memory.topic"}],
            outputs=[{"name": "summary", "source": "results.writer"}],
        )

        child_block = _EchoBlock("writer", copy_key="topic")
        child_wf = _build_child_workflow("child_wf", child_block)

        wb = WorkflowBlock(
            block_id="invoke_child",
            child_workflow=child_wf,
            inputs={"topic": "shared_memory.parent_topic"},
            outputs={"results.analysis": "summary"},
            interface=interface,
        )

        # First invocation
        state_a = WorkflowState(shared_memory={"parent_topic": "alpha"})
        result_a = await _exec(wb, state_a)

        # Second invocation with different data
        state_b = WorkflowState(shared_memory={"parent_topic": "beta"})
        result_b = await _exec(wb, state_b)

        # Each invocation must reflect its own input — no leakage
        analysis_a = result_a.results.get("analysis")
        analysis_b = result_b.results.get("analysis")
        assert analysis_a is not None and str(analysis_a) == "alpha"
        assert analysis_b is not None and str(analysis_b) == "beta"

    async def test_workflow_block_child_no_primary_output(self) -> None:
        """
        Child workflow produces no results at all but the interface declares
        outputs.  An appropriate error or graceful handling MUST occur when
        trying to map the missing output.
        """
        interface = _make_interface(
            inputs=[{"name": "topic", "target": "shared_memory.topic"}],
            outputs=[{"name": "summary", "source": "results.writer"}],
        )

        child_block = _EmptyBlock("writer")  # produces nothing
        child_wf = _build_child_workflow("child_wf", child_block)

        wb = WorkflowBlock(
            block_id="invoke_child",
            child_workflow=child_wf,
            inputs={"topic": "shared_memory.parent_topic"},
            outputs={"results.parent_summary": "summary"},
            interface=interface,
        )

        parent_state = WorkflowState(
            shared_memory={"parent_topic": "test"},
        )

        with pytest.raises((KeyError, ValueError)):
            await _exec(wb, parent_state)

    async def test_workflow_block_rejects_dotted_path_input_bindings(self) -> None:
        """
        AC4: Callable sub-workflows cannot be invoked via raw child dotted-path
        bindings.  Inputs keyed by dotted child paths must be rejected at
        construction time.

        The error must be a ValueError explicitly about the dotted key, not a
        generic TypeError from a missing parameter.
        """
        interface = _make_interface(
            inputs=[{"name": "topic", "target": "shared_memory.topic"}],
        )

        child_block = _EchoBlock("echo", copy_key="topic")
        child_wf = _build_child_workflow("child_wf", child_block)

        with pytest.raises(ValueError, match=r"[Dd]otted|\."):
            WorkflowBlock(
                block_id="invoke_child",
                child_workflow=child_wf,
                inputs={"shared_memory.topic": "shared_memory.parent_topic"},
                outputs={},
                interface=interface,
            )
