"""Workflow error routing and output mapping behavior coverage.

The suite covers three flow-level contracts:

- WorkflowBlock on_error="catch" with error_route routes caught child failures.
- WorkflowBlock output mapping exposes selected child results to the parent state.
- A failed predecessor with an error_route skips dependent blocks and runs the handler.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest
from runsight_core.block_io import (
    BlockContext,
    BlockOutput,
    apply_block_output,
    build_block_context,
)
from runsight_core.blocks.base import BaseBlock
from runsight_core.blocks.workflow_block import WorkflowBlock
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.workflow import Workflow
from runsight_core.yaml.parser import parse_workflow_yaml


async def _exec(block, state, **extra_inputs):
    """Helper: build BlockContext, execute block, apply output to state."""
    ctx = build_block_context(block, state)
    if extra_inputs:
        ctx = ctx.model_copy(update={"inputs": {**ctx.inputs, **extra_inputs}})
    output = await block.execute(ctx)
    return apply_block_output(state, block.block_id, output)


# ---------------------------------------------------------------------------
# Helpers - block doubles with no LLM or subprocess work.
# ---------------------------------------------------------------------------


class _FailingBlock(BaseBlock):
    """Block that always raises RuntimeError."""

    def __init__(self, block_id: str, *, error_msg: str = "block failed"):
        super().__init__(block_id)
        self._error_msg = error_msg
        self.call_count = 0

    async def execute(self, ctx: BlockContext) -> BlockOutput:
        self.call_count += 1
        raise RuntimeError(self._error_msg)


class _WriteBlock(BaseBlock):
    """Block that records its execution into results and shared_memory."""

    def __init__(self, block_id: str, *, output: str | None = None):
        super().__init__(block_id)
        self._output = output or block_id
        self.call_count = 0

    async def execute(self, ctx: BlockContext) -> BlockOutput:
        self.call_count += 1
        return BlockOutput(
            output=self._output,
            shared_memory_updates={f"visited_{self.block_id}": self.call_count},
        )


class _ErrorAwareHandlerBlock(BaseBlock):
    """Handler block that snapshots routed error metadata for assertions."""

    def __init__(self, block_id: str, *, failed_block_id: str):
        super().__init__(block_id)
        self.failed_block_id = failed_block_id
        self.call_count = 0
        self.declared_inputs = {
            "routed_error": f"shared_memory.__error__{failed_block_id}",
        }

    async def execute(self, ctx: BlockContext) -> BlockOutput:
        self.call_count += 1
        error_info = ctx.inputs.get("routed_error")
        return BlockOutput(
            output="handled",
            metadata={"seen_error": error_info},
            shared_memory_updates={"handler_ran": True},
        )


def _write_workflow_file(base_dir: Path, name: str, yaml_content: str) -> str:
    content = dedent(yaml_content)
    lines = content.lstrip().splitlines()
    first_key = lines[0].split(":")[0].strip() if lines else ""
    if first_key != "id":
        content = "id: workflow-error-routing-workflow\nkind: workflow\n" + content
    workflow_file = base_dir / name
    workflow_file.write_text(content, encoding="utf-8")
    return str(workflow_file)


def _build_workflow(name: str, *blocks: BaseBlock, entry: str) -> Workflow:
    """Build a workflow from blocks, setting entry."""
    workflow = Workflow(name=name)
    for block in blocks:
        workflow.add_block(block)
    workflow.set_entry(entry)
    return workflow


@pytest.mark.asyncio
class TestWorkflowBlockOnErrorCatchWithErrorRoute:
    """WorkflowBlock on_error="catch" and error_route in the parent workflow.

    When a WorkflowBlock has on_error="catch", child failure is caught (no
    exception propagates). The BlockResult has exit_handle="error". The parent
    workflow should route to the error handler and the handler's result should
    appear in the final state.
    """

    async def test_catch_plus_error_route_runs_handler(self):
        """
        Setup: parent workflow has:
          - invoke_child (WorkflowBlock, on_error="catch", error_route -> handler)
          - handler (records its execution)
          - normal_successor (skipped because error routing takes precedence)

        Child workflow raises RuntimeError.
        Expected: handler executes, normal_successor is skipped, handler result in final state.
        """
        # Build a child workflow with a single failing block
        child_fail = _FailingBlock("child_step", error_msg="child exploded")
        child_workflow = _build_workflow("failing_child", child_fail, entry="child_step")

        wb = WorkflowBlock(
            block_id="invoke_child",
            child_workflow=child_workflow,
            inputs={"topic": "shared_memory.parent_topic"},
            outputs={},
            on_error="catch",
        )

        handler = _WriteBlock("handler", output="handled")
        normal_successor = _WriteBlock("normal_successor", output="should not run")

        # Parent workflow: invoke_child -> normal_successor (normal path)
        #                  invoke_child -error_route-> handler
        parent_workflow = _build_workflow(
            "parent_workflow",
            wb,
            handler,
            normal_successor,
            entry="invoke_child",
        )
        parent_workflow.add_transition("invoke_child", "normal_successor")
        parent_workflow.set_error_route("invoke_child", "handler")

        parent_state = WorkflowState(
            shared_memory={"parent_topic": "testing"},
        )

        final_state = await parent_workflow.run(parent_state)

        # The WorkflowBlock catches the child failure (on_error="catch")
        invoke_result = final_state.results.get("invoke_child")
        assert invoke_result is not None, "WorkflowBlock must produce a BlockResult"
        assert isinstance(invoke_result, BlockResult)
        assert invoke_result.exit_handle == "error", (
            f"exit_handle must be 'error' for caught child failure, got {invoke_result.exit_handle!r}"
        )

        # The handler must have executed through error routing.
        assert "handler" in final_state.results, (
            "error handler must execute when WorkflowBlock catches child failure "
            "and error_route is configured"
        )
        assert final_state.results["handler"].output == "handled"

        # The normal successor must be skipped.
        assert "normal_successor" not in final_state.results, (
            "normal successor must be skipped when child fails"
        )

    async def test_catch_plus_error_route_handler_result_in_final_state(self):
        """
        Verify that the handler block's result appears in the final workflow
        state with correct output and metadata.
        """
        child_fail = _FailingBlock("child_step", error_msg="timeout reached")
        child_workflow = _build_workflow("failing_child", child_fail, entry="child_step")

        wb = WorkflowBlock(
            block_id="invoke_child",
            child_workflow=child_workflow,
            inputs={"topic": "shared_memory.parent_topic"},
            outputs={},
            on_error="catch",
        )

        handler = _WriteBlock("handler", output="error recovered")

        parent_workflow = _build_workflow("parent_workflow", wb, handler, entry="invoke_child")
        parent_workflow.set_error_route("invoke_child", "handler")

        parent_state = WorkflowState(
            shared_memory={"parent_topic": "testing"},
        )

        final_state = await parent_workflow.run(parent_state)

        # Handler must have its result in the final state
        handler_result = final_state.results.get("handler")
        assert handler_result is not None, "handler result must be present in final state"
        assert handler_result.output == "error recovered"

    async def test_catch_plus_error_route_yaml_parsed_workflow(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """
        YAML-parsed child workflow with a parent error_route.

        Uses a code block as the child so no LLM mock is needed for the child.
        The parent uses a linear block for the WorkflowBlock invoker, but
        since on_error="catch" is a WorkflowBlock feature, we build the parent
        programmatically with a WorkflowBlock and wire it into a parent workflow.

        This variant tests with CodeBlock as the child (raises via code execution).
        """
        from runsight_core.blocks.code import CodeBlock

        async def _fake_child_code_run(self: CodeBlock, inputs: dict) -> tuple[bytes, bytes, int]:
            assert self.block_id == "child_step"
            return b"", b"RuntimeError: code block failure", 1

        monkeypatch.setattr(CodeBlock, "_run_subprocess", _fake_child_code_run)

        # Build child workflow from YAML (contains a code block that raises)
        child_yaml_path = _write_workflow_file(
            tmp_path,
            "child.yaml",
            """\
            version: "1.0"
            blocks:
              child_step:
                type: code
                code: |
                  def main(data):
                      raise RuntimeError("code block failure")
            workflow:
              name: failing_child
              entry: child_step
            """,
        )
        child_workflow = parse_workflow_yaml(child_yaml_path)

        wb = WorkflowBlock(
            block_id="invoke_child",
            child_workflow=child_workflow,
            inputs={},
            outputs={},
            on_error="catch",
        )

        handler = _WriteBlock("handler", output="recovered from child failure")

        parent_workflow = _build_workflow("parent_workflow", wb, handler, entry="invoke_child")
        parent_workflow.set_error_route("invoke_child", "handler")

        final_state = await parent_workflow.run(WorkflowState())

        # WorkflowBlock must catch the child error
        invoke_result = final_state.results.get("invoke_child")
        assert invoke_result is not None
        assert invoke_result.exit_handle == "error"

        # Handler must run
        assert "handler" in final_state.results
        assert final_state.results["handler"].output == "recovered from child failure"
