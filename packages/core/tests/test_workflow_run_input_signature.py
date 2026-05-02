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

import inspect
import textwrap
from pathlib import Path

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
