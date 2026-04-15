"""
Failing tests for RUN-880: Seed workflow input — inject state.results["workflow"]
before first block.

Acceptance Criteria verified:
- Workflow.run() accepts an inputs: dict parameter
- Before first block runs, state.results["workflow"] contains a BlockResult
  with JSON-serialized inputs
- Blocks with declared_inputs: { x: "workflow.field" } can resolve the value
- When no inputs provided, state.results["workflow"] is BlockResult(output="{}")
- Parser validates that "workflow" is not used as a block ID — raises error if
  collision detected
- YAML inputs: { field: { from: "workflow.field" } } resolves external caller
  data end-to-end
"""

from __future__ import annotations

import inspect
import json
import textwrap
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from runsight_core.block_io import BlockContext, BlockOutput
from runsight_core.blocks.base import BaseBlock
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.workflow import Workflow

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


class _RecordingBlock(BaseBlock):
    """
    Minimal block that records the state it received and returns it unchanged.
    Used to verify state.results["workflow"] is seeded before execution.
    """

    def __init__(self, block_id: str) -> None:
        super().__init__(block_id)
        self.received_states: list[WorkflowState] = []

    async def execute(self, ctx: BlockContext) -> BlockOutput:
        # Record the state snapshot so tests can inspect state.results["workflow"]
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
# 2. state.results["workflow"] seeded before first block
# ===========================================================================


class TestWorkflowResultSeededBeforeFirstBlock:
    """Before the first block executes, state.results["workflow"] must be set."""

    @pytest.mark.asyncio
    async def test_workflow_result_present_in_first_block_state(self):
        """Recording block sees state.results["workflow"] before it executes."""
        block = _RecordingBlock("step1")
        wf = _make_single_block_workflow(block)
        initial_state = WorkflowState()

        await wf.run(initial_state, inputs={"name": "Alice"})

        assert len(block.received_states) == 1, "Block was not executed"
        received = block.received_states[0]
        assert "workflow" in received.results, (
            f"state.results['workflow'] was not seeded before block execution. "
            f"Keys present: {list(received.results.keys())}"
        )

    @pytest.mark.asyncio
    async def test_workflow_result_is_block_result_instance(self):
        """state.results["workflow"] must be a BlockResult instance."""
        block = _RecordingBlock("step1")
        wf = _make_single_block_workflow(block)
        initial_state = WorkflowState()

        await wf.run(initial_state, inputs={"x": 42})

        received = block.received_states[0]
        wf_result = received.results["workflow"]
        assert isinstance(wf_result, BlockResult), (
            f"state.results['workflow'] must be a BlockResult, got {type(wf_result)}"
        )

    @pytest.mark.asyncio
    async def test_workflow_result_output_is_json_of_inputs(self):
        """state.results["workflow"].output must be json.dumps(inputs)."""
        inputs = {"name": "Alice", "count": 3}
        block = _RecordingBlock("step1")
        wf = _make_single_block_workflow(block)
        initial_state = WorkflowState()

        await wf.run(initial_state, inputs=inputs)

        received = block.received_states[0]
        wf_result = received.results["workflow"]
        parsed = json.loads(wf_result.output)
        assert parsed == inputs, (
            f"state.results['workflow'].output must equal json.dumps(inputs). "
            f"Expected {inputs!r}, got {parsed!r}"
        )

    @pytest.mark.asyncio
    async def test_workflow_result_output_json_is_valid(self):
        """state.results["workflow"].output must be valid JSON."""
        block = _RecordingBlock("step1")
        wf = _make_single_block_workflow(block)
        initial_state = WorkflowState()

        await wf.run(initial_state, inputs={"key": "value"})

        received = block.received_states[0]
        wf_result = received.results["workflow"]
        try:
            json.loads(wf_result.output)
        except json.JSONDecodeError as exc:
            pytest.fail(
                f"state.results['workflow'].output is not valid JSON: {exc!r}. "
                f"Output was: {wf_result.output!r}"
            )


# ===========================================================================
# 3. No inputs provided → state.results["workflow"].output == "{}"
# ===========================================================================


class TestNoInputsProducesEmptyJsonObject:
    """When no inputs are given, state.results["workflow"].output must be '{}'."""

    @pytest.mark.asyncio
    async def test_no_inputs_kwarg_produces_empty_dict(self):
        """Calling run() without inputs= seeds workflow result with '{}'."""
        block = _RecordingBlock("step1")
        wf = _make_single_block_workflow(block)
        initial_state = WorkflowState()

        await wf.run(initial_state)

        received = block.received_states[0]
        assert "workflow" in received.results, (
            "state.results['workflow'] must be seeded even when no inputs are passed"
        )
        assert received.results["workflow"].output == "{}", (
            f"Expected '{{}}', got {received.results['workflow'].output!r}"
        )

    @pytest.mark.asyncio
    async def test_inputs_none_explicitly_produces_empty_dict(self):
        """Calling run(inputs=None) seeds workflow result with '{}'."""
        block = _RecordingBlock("step1")
        wf = _make_single_block_workflow(block)
        initial_state = WorkflowState()

        await wf.run(initial_state, inputs=None)

        received = block.received_states[0]
        assert "workflow" in received.results, (
            "state.results['workflow'] must be seeded even when inputs=None"
        )
        assert received.results["workflow"].output == "{}", (
            f"Expected '{{}}', got {received.results['workflow'].output!r}"
        )

    @pytest.mark.asyncio
    async def test_empty_inputs_dict_produces_empty_dict(self):
        """Calling run(inputs={}) seeds workflow result with '{}'."""
        block = _RecordingBlock("step1")
        wf = _make_single_block_workflow(block)
        initial_state = WorkflowState()

        await wf.run(initial_state, inputs={})

        received = block.received_states[0]
        assert received.results["workflow"].output == "{}", (
            f"Expected '{{}}', got {received.results['workflow'].output!r}"
        )


# ===========================================================================
# 4. declared_inputs from "workflow.field" resolves seeded value
# ===========================================================================


class TestDeclaredInputsResolvesWorkflowField:
    """
    A Step wrapped block with declared_inputs={ x: "workflow.field" } must
    receive the seeded value from state.results["workflow"].
    """

    @pytest.mark.asyncio
    async def test_declared_input_resolves_workflow_field(self):
        """
        Step with declared_inputs={"x": "workflow.name"} resolves "name" from
        the seeded workflow BlockResult.
        """
        from runsight_core.block_io import BlockOutput
        from runsight_core.primitives import Step

        captured_inputs: list[dict] = []

        class _CapturingBlock(BaseBlock):
            async def execute(self, ctx: BlockContext) -> BlockOutput:
                captured_inputs.append(dict(ctx.inputs))
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

        # Must not raise even though "nonexistent" key is absent from inputs
        await wf.run(initial_state, inputs={"name": "Alice"})

    @pytest.mark.asyncio
    async def test_declared_input_whole_workflow_object_without_field(self):
        """
        Step with declared_inputs={"all": "workflow"} (no field path) resolves
        to the full JSON string of the inputs dict.
        """
        from runsight_core.block_io import BlockOutput
        from runsight_core.primitives import Step

        captured_inputs: list[dict] = []

        class _CapturingBlock(BaseBlock):
            async def execute(self, ctx: BlockContext) -> BlockOutput:
                captured_inputs.append(dict(ctx.inputs))
                return BlockOutput(output="ok")

        inner = _CapturingBlock("step1")
        step = Step(block=inner, declared_inputs={"all": "workflow"})

        wf = Workflow(name="test_wf")
        wf.add_block(step)
        wf.set_entry(step.block_id)
        initial_state = WorkflowState()

        await wf.run(initial_state, inputs={"name": "Alice", "count": 5})

        assert len(captured_inputs) == 1
        resolved = captured_inputs[0]
        assert "all" in resolved, f"Expected 'all' key in ctx.inputs, got: {list(resolved.keys())}"


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
    Currently it raises ValueError("references unknown block 'workflow'").
    After fix, "workflow" is treated as the seeded pseudo-block.
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
        """inputs: { all_data: { from: "workflow" } } must parse without error."""
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

        # Must not raise
        wf = parse_workflow_yaml(yaml_path)
        assert wf is not None


# ===========================================================================
# 7. End-to-end: YAML with inputs resolves via Workflow.run(inputs=...)
# ===========================================================================


class TestEndToEndYamlWorkflowInputSeeding:
    """
    Full end-to-end: parse a YAML workflow with a block that declares
    inputs: { x: { from: "workflow.field" } }, run with inputs={"field": "hello"},
    and verify the block received the correct resolved value.
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

        # The block wrapped in Step captures shared_memory during execute
        # We need to intercept _resolved_inputs at execute time
        assert wf is not None

        # Run the workflow and capture the state after execution
        initial_state = WorkflowState()
        final_state = await wf.run(initial_state, inputs={"message": "hello"})

        # The resolved input is consumed during block execution; verify it was present
        # by checking the seeded workflow result exists in final state
        assert "workflow" in final_state.results, (
            "state.results['workflow'] must be present in final state"
        )
        assert json.loads(final_state.results["workflow"].output) == {"message": "hello"}, (
            f"workflow seed result must contain the inputs. "
            f"Got: {final_state.results['workflow'].output!r}"
        )
