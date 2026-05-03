"""
Tests for workflow input state wiring.

Verified behavior:
- Workflow.run() accepts an inputs: dict parameter
- Before first block runs, WorkflowState.workflow_inputs contains the inputs
- Blocks with declared_inputs: { x: "workflow.field" } can resolve the value
- When no inputs are provided, WorkflowState.workflow_inputs is empty
- Parser rejects bare "workflow" references
- YAML inputs: { field: { from: "workflow.field" } } resolves caller data
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from runsight_core.block_io import BlockContext, BlockOutput
from runsight_core.blocks.base import BaseBlock
from runsight_core.state import WorkflowState
from runsight_core.workflow import Workflow

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


class _RecordingBlock(BaseBlock):
    """
    Minimal block that records the state it received and returns it unchanged.
    Used to verify WorkflowState.workflow_inputs is available before execution.
    """

    def __init__(
        self,
        block_id: str,
        declared_inputs: dict[str, str] | None = None,
    ) -> None:
        super().__init__(block_id)
        self.context_access = "declared"
        self.declared_inputs = dict(declared_inputs or {})
        self.received_states: list[WorkflowState] = []

    async def execute(self, ctx: BlockContext) -> BlockOutput:
        # Record the state snapshot so tests can inspect workflow_inputs.
        if ctx.state_snapshot is not None:
            self.received_states.append(ctx.state_snapshot)
        return BlockOutput(output="ok")


def _make_single_block_workflow(block: BaseBlock) -> Workflow:
    """Build a minimal single-block Workflow with no transitions."""
    wf = Workflow(name="workflow-input-seeding-workflow")
    wf.add_block(block)
    wf.set_entry(block.block_id)
    return wf


def _write_soul_file(base_dir: Path, name: str = "writer") -> None:
    souls_dir = base_dir / "custom" / "souls"
    souls_dir.mkdir(parents=True, exist_ok=True)
    (souls_dir / f"{name}.yaml").write_text(
        textwrap.dedent(
            """\
            id: writer
            kind: soul
            name: Writer
            role: Writer
            system_prompt: Write carefully.
            """
        ),
        encoding="utf-8",
    )


def _write_workflow_file(base_dir: Path, yaml_content: str) -> str:
    workflow_file = base_dir / "workflow.yaml"
    content = textwrap.dedent(yaml_content)
    if "id: " not in content:
        content = "id: workflow-input-seeding\nkind: workflow\n" + content
    workflow_file.write_text(content, encoding="utf-8")
    return str(workflow_file)


# ===========================================================================
# 1. Workflow.run() signature accepts inputs parameter
# ===========================================================================


class TestWorkflowInputsSeededBeforeFirstBlock:
    """Before the first block executes, WorkflowState.workflow_inputs must be set."""

    @pytest.mark.asyncio
    async def test_workflow_inputs_present_in_first_block_state(self):
        """Recording block sees WorkflowState.workflow_inputs before it executes."""
        block = _RecordingBlock("step1", declared_inputs={"name": "workflow.name"})
        wf = _make_single_block_workflow(block)
        initial_state = WorkflowState()

        await wf.run(initial_state, inputs={"name": "Alice"})

        assert len(block.received_states) == 1, "Block was not executed"
        received = block.received_states[0]
        assert received.workflow_inputs == {"name": "Alice"}, (
            "WorkflowState.workflow_inputs was not seeded before block execution. "
            f"Got: {getattr(received, 'workflow_inputs', None)!r}"
        )

    @pytest.mark.asyncio
    async def test_workflow_inputs_are_plain_dict(self):
        """WorkflowState.workflow_inputs must be a plain dict."""
        block = _RecordingBlock("step1", declared_inputs={"x": "workflow.x"})
        wf = _make_single_block_workflow(block)
        initial_state = WorkflowState()

        await wf.run(initial_state, inputs={"x": 42})

        received = block.received_states[0]
        assert received.workflow_inputs == {"x": 42}, (
            f"WorkflowState.workflow_inputs must equal the caller inputs, "
            f"got: {getattr(received, 'workflow_inputs', None)!r}"
        )

    @pytest.mark.asyncio
    async def test_workflow_inputs_preserve_nested_structures(self):
        """WorkflowState.workflow_inputs must preserve structured caller inputs."""
        inputs = {"name": "Alice", "count": 3, "filters": {"topic": "ml"}}
        block = _RecordingBlock(
            "step1",
            declared_inputs={
                "name": "workflow.name",
                "count": "workflow.count",
                "filters": "workflow.filters",
            },
        )
        wf = _make_single_block_workflow(block)
        initial_state = WorkflowState()

        await wf.run(initial_state, inputs=inputs)

        received = block.received_states[0]
        assert received.workflow_inputs == inputs, (
            "WorkflowState.workflow_inputs must preserve structured caller inputs. "
            f"Got: {getattr(received, 'workflow_inputs', None)!r}"
        )


# ===========================================================================
# 3. No inputs provided → WorkflowState.workflow_inputs == {}
# ===========================================================================


class TestNoInputsProducesEmptyJsonObject:
    """When no inputs are given, WorkflowState.workflow_inputs must be '{}'."""

    @pytest.mark.asyncio
    async def test_no_inputs_kwarg_produces_empty_dict(self):
        """Calling run() without inputs= seeds WorkflowState.workflow_inputs with '{}'."""
        block = _RecordingBlock("step1")
        wf = _make_single_block_workflow(block)
        initial_state = WorkflowState()

        await wf.run(initial_state)

        received = block.received_states[0]
        assert received.workflow_inputs == {}, (
            "WorkflowState.workflow_inputs must be seeded even when no inputs are passed"
        )

    @pytest.mark.asyncio
    async def test_inputs_none_explicitly_produces_empty_dict(self):
        """Calling run(inputs=None) seeds WorkflowState.workflow_inputs with '{}'."""
        block = _RecordingBlock("step1")
        wf = _make_single_block_workflow(block)
        initial_state = WorkflowState()

        await wf.run(initial_state, inputs=None)

        received = block.received_states[0]
        assert received.workflow_inputs == {}, (
            "WorkflowState.workflow_inputs must be seeded even when inputs=None"
        )

    @pytest.mark.asyncio
    async def test_empty_inputs_dict_produces_empty_dict(self):
        """Calling run(inputs={}) seeds WorkflowState.workflow_inputs with '{}'."""
        block = _RecordingBlock("step1")
        wf = _make_single_block_workflow(block)
        initial_state = WorkflowState()

        await wf.run(initial_state, inputs={})

        received = block.received_states[0]
        assert received.workflow_inputs == {}, (
            f"Expected '{{}}', got {getattr(received, 'workflow_inputs', None)!r}"
        )


# ===========================================================================
# 4. declared_inputs from "workflow.field" resolves seeded value
# ===========================================================================


class TestDeclaredInputsResolvesWorkflowField:
    """
    A Step wrapped block with declared_inputs={ x: "workflow.field" } must
    receive the seeded value from WorkflowState.workflow_inputs.
    """

    @pytest.mark.asyncio
    async def test_declared_input_resolves_workflow_field(self):
        """
        Step with declared_inputs={"x": "workflow.name"} resolves "name" from
        WorkflowState.workflow_inputs.
        """
        from runsight_core.block_io import BlockOutput
        from runsight_core.primitives import Step

        captured_inputs: list[dict] = []
        received_states: list[WorkflowState] = []

        class _CapturingBlock(BaseBlock):
            async def execute(self, ctx: BlockContext) -> BlockOutput:
                captured_inputs.append(dict(ctx.inputs))
                if ctx.state_snapshot is not None:
                    received_states.append(ctx.state_snapshot)
                return BlockOutput(output="ok")

        inner = _CapturingBlock("step1")
        step = Step(block=inner, declared_inputs={"x": "workflow.name"})

        wf = Workflow(name="workflow-input-seeding-workflow")
        wf.add_block(step)
        wf.set_entry(step.block_id)
        initial_state = WorkflowState()

        await wf.run(initial_state, inputs={"name": "Alice"})

        assert len(captured_inputs) == 1, "Block was not executed"
        resolved = captured_inputs[0]
        assert "x" in resolved, (
            f"_resolved_inputs must contain key 'x', got keys: {list(resolved.keys())}"
        )
        assert resolved["x"] == "Alice", (
            f"declared_input 'x' from 'workflow.name' must resolve to 'Alice', "
            f"got {resolved['x']!r}"
        )
        assert received_states[0].workflow_inputs == {"name": "Alice"}, (
            "WorkflowState.workflow_inputs must be visible to the block state snapshot. "
            f"Got: {getattr(received_states[0], 'workflow_inputs', None)!r}"
        )

    @pytest.mark.asyncio
    async def test_declared_input_workflow_field_missing_returns_none_or_empty(self):
        """
        Step with declared_inputs={"x": "workflow.nonexistent"} when inputs
        does not contain "nonexistent" — must not crash (field missing in JSON).
        The resolved value can be None or absent, but must not raise.
        """
        from runsight_core.block_io import BlockOutput
        from runsight_core.primitives import Step

        class _NoOpBlock(BaseBlock):
            async def execute(self, ctx: BlockContext) -> BlockOutput:
                return BlockOutput(output="ok")

        inner = _NoOpBlock("step1")
        step = Step(block=inner, declared_inputs={"x": "workflow.nonexistent"})

        wf = Workflow(name="workflow-input-seeding-workflow")
        wf.add_block(step)
        wf.set_entry(step.block_id)
        initial_state = WorkflowState()

        with pytest.raises(ValueError, match="field path missing"):
            await wf.run(initial_state, inputs={"name": "Alice"})

    @pytest.mark.asyncio
    async def test_declared_input_whole_workflow_object_without_field(self):
        """
        Step with declared_inputs={"all": "workflow"} (no field path) is invalid
        and must be rejected.
        """
        from runsight_core import context_governance as cg

        with pytest.raises((ValueError, cg.ContextReadDeniedError), match="workflow|named input"):
            cg.parse_context_ref("workflow")


# ===========================================================================
# 5. Parser rejects block_id == "workflow"
# ===========================================================================
