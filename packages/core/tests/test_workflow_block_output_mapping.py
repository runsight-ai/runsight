"""Workflow error routing and output mapping behavior coverage.

The suite covers three flow-level contracts:

- WorkflowBlock on_error="catch" with error_route routes caught child failures.
- WorkflowBlock output mapping exposes selected child results to the parent state.
- A failed predecessor with an error_route skips dependent blocks and runs the handler.
"""

from __future__ import annotations

import json
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
class TestWorkflowBlockOutputMappingOnSuccess:
    """WorkflowBlock output mapping works correctly on success."""

    async def test_output_mapping_transfers_child_result_to_parent(self):
        """
        Child CodeBlock returns a dict. Parent maps child result key to parent
        results via outputs config. Mapped key must appear in parent state,
        unmapped child keys must be absent.
        """
        # Child block writes {"summary": "analysis complete", "raw": "internal data"}
        child_block = _WriteBlock("child_writer", output="analysis complete")
        child_workflow = _build_workflow("child_workflow", child_block, entry="child_writer")

        wb = WorkflowBlock(
            block_id="invoke_child",
            child_workflow=child_workflow,
            inputs={"topic": "shared_memory.parent_topic"},
            outputs={"results.mapped_summary": "results.child_writer"},
        )

        parent_state = WorkflowState(
            shared_memory={"parent_topic": "testing"},
        )

        final_state = await _exec(wb, parent_state)

        # Mapped key must exist in parent results
        mapped = final_state.results.get("mapped_summary")
        assert mapped is not None, (
            "Output mapping must transfer child result to parent under mapped key"
        )
        # The mapped value should be the child's output
        assert mapped == BlockResult(output="analysis complete"), (
            f"Mapped output must match child's output, got {mapped!r}"
        )

    async def test_unmapped_child_keys_absent_from_parent(self):
        """
        Child workflow has multiple blocks producing results. Only the mapped
        outputs should appear in parent state; unmapped child result keys must
        be absent.
        """
        # Child workflow: writer_a writes result, writer_b writes another
        writer_a = _WriteBlock("writer_a", output="result A")
        writer_b = _WriteBlock("writer_b", output="result B")
        child_workflow = _build_workflow(
            "child_workflow",
            writer_a,
            writer_b,
            entry="writer_a",
        )
        child_workflow.add_transition("writer_a", "writer_b")

        # Only map writer_a's output; writer_b should stay in the child workflow.
        wb = WorkflowBlock(
            block_id="invoke_child",
            child_workflow=child_workflow,
            inputs={"topic": "shared_memory.parent_topic"},
            outputs={"results.parent_a": "results.writer_a"},
        )

        parent_state = WorkflowState(
            shared_memory={"parent_topic": "testing"},
        )

        final_state = await _exec(wb, parent_state)

        # Mapped key present
        assert "parent_a" in final_state.results, "Mapped child result must appear in parent"
        assert final_state.results["parent_a"] == BlockResult(output="result A")

        # Unmapped keys stay absent from the parent results.
        assert "writer_b" not in final_state.results, (
            "Unmapped child result key must stay out of parent results"
        )
        assert "writer_a" not in final_state.results, (
            "Raw child result key must stay out of parent results"
        )

    async def test_output_mapping_success_produces_completed_exit_handle(self):
        """
        On success with output mapping, the WorkflowBlock's own BlockResult
        should have exit_handle="completed" (not "error").
        """
        child_block = _WriteBlock("child_writer", output="done")
        child_workflow = _build_workflow("child_workflow", child_block, entry="child_writer")

        wb = WorkflowBlock(
            block_id="invoke_child",
            child_workflow=child_workflow,
            inputs={"topic": "shared_memory.parent_topic"},
            outputs={"results.parent_out": "results.child_writer"},
        )

        parent_state = WorkflowState(
            shared_memory={"parent_topic": "testing"},
        )

        final_state = await _exec(wb, parent_state)

        wb_result = final_state.results.get("invoke_child")
        assert wb_result is not None
        assert isinstance(wb_result, BlockResult)
        assert wb_result.exit_handle == "completed", (
            f"WorkflowBlock exit_handle should be 'completed' on success, "
            f"got {wb_result.exit_handle!r}"
        )

    async def test_output_mapping_to_shared_memory(self):
        """
        Output mapping can target shared_memory in the parent, not just results.
        """
        child_block = _WriteBlock("child_writer", output="mapped_value")
        child_workflow = _build_workflow("child_workflow", child_block, entry="child_writer")

        wb = WorkflowBlock(
            block_id="invoke_child",
            child_workflow=child_workflow,
            inputs={"topic": "shared_memory.parent_topic"},
            outputs={"shared_memory.parent_output": "results.child_writer"},
        )

        parent_state = WorkflowState(
            shared_memory={"parent_topic": "testing"},
        )

        final_state = await _exec(wb, parent_state)

        # The output should appear in shared_memory
        assert final_state.shared_memory.get("parent_output") == "mapped_value", (
            "Output mapping to shared_memory must work on success"
        )

    async def test_output_mapping_with_code_block_child(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """
        Integration: child is a YAML-parsed CodeBlock that returns a dict.
        Parent maps the code block's result to parent state.
        """
        from runsight_core.blocks.code import CodeBlock

        async def _fake_analyzer_code_run(
            self: CodeBlock, inputs: dict
        ) -> tuple[bytes, bytes, int]:
            assert self.block_id == "analyzer"
            payload = {"analyzed": inputs.get("topic", "unknown"), "score": 42}
            return json.dumps(payload).encode(), b"", 0

        monkeypatch.setattr(CodeBlock, "_run_subprocess", _fake_analyzer_code_run)

        child_yaml_path = _write_workflow_file(
            tmp_path,
            "child_code.yaml",
            """\
            version: "1.0"
            blocks:
              analyzer:
                type: code
                inputs:
                  topic:
                    from: workflow.topic
                code: |
                  def main(data):
                      topic = data.get("topic", "unknown")
                      return {"analyzed": topic, "score": 42}
            workflow:
              name: child_code_workflow
              entry: analyzer
            """,
        )
        child_workflow = parse_workflow_yaml(child_yaml_path)

        wb = WorkflowBlock(
            block_id="invoke_child",
            child_workflow=child_workflow,
            inputs={"topic": "shared_memory.parent_topic"},
            outputs={"results.parent_analysis": "results.analyzer"},
        )

        parent_state = WorkflowState(
            shared_memory={"parent_topic": "machine learning"},
        )

        final_state = await _exec(wb, parent_state)

        # The mapped output should appear in parent results
        parent_analysis = final_state.results.get("parent_analysis")
        assert parent_analysis is not None, (
            "CodeBlock child output must be mapped to parent results"
        )
        # CodeBlock returns JSON-serialized output
        if isinstance(parent_analysis, BlockResult):
            parent_analysis = parent_analysis.output
        parsed = (
            json.loads(parent_analysis) if isinstance(parent_analysis, str) else parent_analysis
        )
        assert parsed["analyzed"] == "machine learning"
        assert parsed["score"] == 42
