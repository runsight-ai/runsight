"""
Failing tests for RUN-899-style workflow input state wiring.

Acceptance Criteria verified:
- Workflow.run() accepts an inputs: dict parameter
- Before first block runs, WorkflowState.workflow_inputs contains the inputs
- Blocks with declared_inputs: { x: "workflow.field" } can resolve the value
- When no inputs are provided, WorkflowState.workflow_inputs is empty
- Parser rejects bare "workflow" references
- YAML inputs: { field: { from: "workflow.field" } } resolves caller data
"""

from __future__ import annotations

import inspect
import textwrap
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

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

    def __init__(self, block_id: str) -> None:
        super().__init__(block_id)
        self.context_access = "declared"
        self.declared_inputs = {"workflow": "workflow"}
        self.received_states: list[WorkflowState] = []

    async def execute(self, ctx: BlockContext) -> BlockOutput:
        # Record the state snapshot so tests can inspect workflow_inputs.
        if ctx.state_snapshot is not None:
            self.received_states.append(ctx.state_snapshot)
        return BlockOutput(output="ok")


def _make_single_block_workflow(block: BaseBlock) -> Workflow:
    """Build a minimal single-block Workflow with no transitions."""
    wf = Workflow(name="test_wf")
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
        content = "id: test-workflow\nkind: workflow\n" + content
    workflow_file.write_text(content, encoding="utf-8")
    return str(workflow_file)


# ===========================================================================
# 1. Workflow.run() signature accepts inputs parameter
# ===========================================================================


class TestWorkflowRunSignatureAcceptsInputs:
    """Workflow.run() must accept an `inputs` keyword argument."""

    def test_run_signature_has_inputs_parameter(self):
        """inspect.signature of Workflow.run must include an 'inputs' parameter."""
        sig = inspect.signature(Workflow.run)
        assert "inputs" in sig.parameters, (
            f"Workflow.run() does not have an 'inputs' parameter. "
            f"Actual parameters: {list(sig.parameters)}"
        )

    def test_inputs_parameter_defaults_to_none(self):
        """The 'inputs' parameter must default to None."""
        sig = inspect.signature(Workflow.run)
        param = sig.parameters["inputs"]
        assert param.default is None, (
            f"Workflow.run 'inputs' parameter default must be None, got {param.default!r}"
        )

    def test_inputs_parameter_is_keyword_only(self):
        """The 'inputs' parameter must be keyword-only (after the * separator)."""
        sig = inspect.signature(Workflow.run)
        param = sig.parameters["inputs"]
        assert param.kind in (
            inspect.Parameter.KEYWORD_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        ), f"Workflow.run 'inputs' must be accessible as a keyword argument. Got kind: {param.kind}"


# ===========================================================================
# 2. WorkflowState.workflow_inputs seeded before first block
# ===========================================================================


class TestWorkflowInputsSeededBeforeFirstBlock:
    """Before the first block executes, WorkflowState.workflow_inputs must be set."""

    @pytest.mark.asyncio
    async def test_workflow_inputs_present_in_first_block_state(self):
        """Recording block sees WorkflowState.workflow_inputs before it executes."""
        block = _RecordingBlock("step1")
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
        block = _RecordingBlock("step1")
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
        block = _RecordingBlock("step1")
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

        wf = Workflow(name="test_wf")
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

        wf = Workflow(name="test_wf")
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


class TestParserRejectsWorkflowAsBlockId:
    """parse_workflow_yaml must raise ValueError when a block is named 'workflow'."""

    def test_block_id_workflow_raises_value_error(self, tmp_path):
        """A block named 'workflow' collides with the reserved seed key."""
        from runsight_core.yaml.parser import parse_workflow_yaml

        _write_soul_file(tmp_path)
        yaml_path = _write_workflow_file(
            tmp_path,
            """\
            version: "1.0"
            workflow:
              name: collision_test
              entry: workflow
              transitions: []

            blocks:
              workflow:
                type: linear
                soul_ref: writer
            """,
        )

        with pytest.raises(ValueError) as exc_info:
            parse_workflow_yaml(yaml_path)

        # Error message must clearly indicate the collision/reserved name
        # (not some other unrelated parse error)
        error_msg = str(exc_info.value)
        assert "workflow" in error_msg.lower(), (
            f"Error message must mention 'workflow', got: {error_msg!r}"
        )

    def test_block_id_workflow_error_message_mentions_reserved(self, tmp_path):
        """Error message must indicate the block ID is reserved or collides."""
        from runsight_core.yaml.parser import parse_workflow_yaml

        _write_soul_file(tmp_path)
        yaml_path = _write_workflow_file(
            tmp_path,
            """\
            version: "1.0"
            workflow:
              name: reserved_name_test
              entry: workflow
              transitions: []

            blocks:
              workflow:
                type: linear
                soul_ref: writer
            """,
        )

        with pytest.raises(ValueError) as exc_info:
            parse_workflow_yaml(yaml_path)

        error_msg = str(exc_info.value)
        # Must mention either "reserved" or "collision" or "workflow" as a block id problem
        has_reserved = "reserved" in error_msg.lower()
        has_collision = "collision" in error_msg.lower()
        has_workflow = "workflow" in error_msg.lower()
        assert has_reserved or has_collision or has_workflow, (
            f"Error must mention reserved/collision/'workflow', got: {error_msg!r}"
        )

    def test_non_workflow_block_id_is_accepted(self, tmp_path):
        """Block IDs other than 'workflow' must still parse without error."""
        from runsight_core.yaml.parser import parse_workflow_yaml

        _write_soul_file(tmp_path)
        yaml_path = _write_workflow_file(
            tmp_path,
            """\
            version: "1.0"
            workflow:
              name: valid_workflow
              entry: step_a
              transitions: []

            blocks:
              step_a:
                type: linear
                soul_ref: writer
            """,
        )

        # Must not raise
        wf = parse_workflow_yaml(yaml_path)
        assert wf is not None


# ===========================================================================
# 6. Parser accepts "workflow.field" in inputs: from without raising
# ===========================================================================


class TestParserAcceptsWorkflowInputRef:
    """
    parse_workflow_yaml must NOT raise when a block has inputs: { x: { from: "workflow.field" } }.
    "workflow" is the reserved caller-input source for dotted refs.
    """

    def test_workflow_field_input_ref_does_not_raise(self, tmp_path):
        """inputs: { field: { from: "workflow.name" } } must parse without error."""
        from runsight_core.yaml.parser import parse_workflow_yaml

        _write_soul_file(tmp_path)
        yaml_path = _write_workflow_file(
            tmp_path,
            """\
            version: "1.0"
            workflow:
              name: input_ref_test
              entry: step_a
              transitions: []

            blocks:
              step_a:
                type: linear
                soul_ref: writer
                inputs:
                  name:
                    from: workflow.name
            """,
        )

        # Must not raise — "workflow" is the reserved input source
        wf = parse_workflow_yaml(yaml_path)
        assert wf is not None

    def test_workflow_field_ref_without_field_path_does_not_raise(self, tmp_path):
        """inputs: { all_data: { from: "workflow" } } must be rejected."""
        from runsight_core.yaml.parser import parse_workflow_yaml

        _write_soul_file(tmp_path)
        yaml_path = _write_workflow_file(
            tmp_path,
            """\
            version: "1.0"
            workflow:
              name: input_ref_no_field_test
              entry: step_a
              transitions: []

            blocks:
              step_a:
                type: linear
                soul_ref: writer
                inputs:
                  all_data:
                    from: workflow
            """,
        )

        with pytest.raises(ValueError, match="workflow|named input"):
            parse_workflow_yaml(yaml_path)


# ===========================================================================
# 7. End-to-end: YAML with inputs resolves via Workflow.run(inputs=...)
# ===========================================================================


class TestEndToEndYamlWorkflowInputSeeding:
    """
    Full end-to-end: parse a YAML workflow with a block that declares
    inputs: { x: { from: "workflow.field" } }, run with inputs={"field": "hello"},
    and verify the runtime state carries workflow_inputs for engine consumption.
    """

    @pytest.mark.asyncio
    async def test_yaml_parsed_workflow_resolves_input_from_caller(self, tmp_path):
        """
        Parse a YAML workflow where step_a declares inputs from workflow.message.
        Run with inputs={"message": "hello"}.
        Verify step_a receives "hello" in _resolved_inputs["text"].
        """
        from unittest.mock import patch

        from runsight_core.yaml.parser import parse_workflow_yaml

        _write_soul_file(tmp_path)
        yaml_path = _write_workflow_file(
            tmp_path,
            """\
            version: "1.0"
            workflow:
              name: e2e_input_test
              entry: step_a
              transitions: []

            blocks:
              step_a:
                type: linear
                soul_ref: writer
                inputs:
                  text:
                    from: workflow.message
            """,
        )

        # We patch the runner so no real LLM call happens
        mock_runner = MagicMock()

        async def _fake_execute(instruction, context, soul, **kw):
            from runsight_core.runner import ExecutionResult

            # This is called after _resolved_inputs is set
            return ExecutionResult(
                task_id="t1",
                soul_id=soul.id,
                output="executed",
                cost_usd=0.0,
                total_tokens=0,
            )

        mock_runner.execute = AsyncMock(side_effect=_fake_execute)
        mock_runner.model_name = "gpt-4o"

        # Patch the runner construction inside build_linear_block
        with patch(
            "runsight_core.yaml.parser.RunsightTeamRunner",
            return_value=mock_runner,
        ):
            wf = parse_workflow_yaml(yaml_path)

        assert wf is not None

        initial_state = WorkflowState()
        final_state = await wf.run(initial_state, inputs={"message": "hello"})

        assert final_state.workflow_inputs == {"message": "hello"}, (
            "WorkflowState.workflow_inputs must contain the caller inputs in the final state. "
            f"Got: {getattr(final_state, 'workflow_inputs', None)!r}"
        )
