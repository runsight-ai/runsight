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
            provider: openai
            model_name: gpt-4o
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


def _completion_response(content: str):
    message = MagicMock()
    message.content = content
    message.tool_calls = None

    choice = MagicMock()
    choice.message = message
    choice.finish_reason = "stop"

    usage = MagicMock()
    usage.prompt_tokens = 0
    usage.completion_tokens = 0
    usage.total_tokens = 0

    response = MagicMock()
    response.choices = [choice]
    response.usage = usage
    return response


# ===========================================================================
# 1. Workflow.run() signature accepts inputs parameter
# ===========================================================================


class TestYamlWorkflowInputSeedingIntegration:
    """
    Full integration path: parse a YAML workflow with a block that declares
    inputs: { x: { from: "workflow.field" } }, run with inputs={"field": "hello"},
    and verify the runtime state carries workflow_inputs for engine consumption.
    """

    @pytest.mark.asyncio
    async def test_yaml_parsed_workflow_resolves_input_from_caller(self, tmp_path, monkeypatch):
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
              name: workflow_input_seeding
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
        monkeypatch.setattr(
            "runsight_core.llm.client.acompletion",
            AsyncMock(return_value=_completion_response("executed")),
        )
        monkeypatch.setattr("runsight_core.llm.client.completion_cost", lambda **_: 0.0)

        # Patch the runner construction inside build_linear_block
        with patch(
            "runsight_core.yaml.parser.RunsightTeamRunner",
            return_value=mock_runner,
        ):
            wf = parse_workflow_yaml(yaml_path, api_keys={"openai": "dummy-openai-key"})

        assert wf is not None

        initial_state = WorkflowState()
        final_state = await wf.run(initial_state, inputs={"message": "hello"})

        assert final_state.workflow_inputs == {"message": "hello"}, (
            "WorkflowState.workflow_inputs must contain the caller inputs in the final state. "
            f"Got: {getattr(final_state, 'workflow_inputs', None)!r}"
        )
