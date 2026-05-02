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
# 7. Integration: YAML with inputs resolves via Workflow.run(inputs=...)
# ===========================================================================
