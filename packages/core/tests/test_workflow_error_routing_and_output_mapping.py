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
        content = "id: test-workflow\nkind: workflow\n" + content
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
        End-to-end: child is a YAML-parsed CodeBlock that returns a dict.
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
              name: child_code_wf
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


@pytest.mark.asyncio
class TestDependsPredecessorFailsErrorRouteRuns:
    """Failed predecessors with error_route skip dependent blocks.

    When fetch fails and has an error_route, analyze depends on fetch:
      - fetch's error_route handler runs
      - analyze is skipped
    """

    async def test_depends_block_not_executed_when_predecessor_fails(self):
        """
        Workflow: entry=fetch -> analyze (depends: fetch)
                  fetch has error_route -> handler

        fetch fails -> handler runs, analyze is skipped.
        """
        fetch = _FailingBlock("fetch", error_msg="fetch crashed")
        analyze = _WriteBlock("analyze", output="should not run")
        handler = _ErrorAwareHandlerBlock("handler", failed_block_id="fetch")

        workflow = _build_workflow("depends_fail", fetch, analyze, handler, entry="fetch")
        # depends: fetch on analyze means add_transition("fetch", "analyze")
        workflow.add_transition("fetch", "analyze")
        workflow.set_error_route("fetch", "handler")

        final_state = await workflow.run(WorkflowState())

        # fetch should have an error result
        assert "fetch" in final_state.results
        assert final_state.results["fetch"].exit_handle == "error"

        # handler should have executed
        assert "handler" in final_state.results, (
            "error_route handler must execute when predecessor fails"
        )
        assert final_state.results["handler"].output == "handled"

        # analyze should be skipped after the predecessor failure.
        assert "analyze" not in final_state.results, (
            "Block with depends on failed predecessor must be skipped when error_route fires"
        )

    async def test_depends_block_skipped_handler_continues_chain(self):
        """
        Workflow: entry=fetch -> analyze (depends: fetch)
                  fetch error_route -> handler -> cleanup

        fetch fails -> handler runs -> cleanup runs, analyze is skipped.
        """
        fetch = _FailingBlock("fetch", error_msg="network error")
        analyze = _WriteBlock("analyze", output="should not run")
        handler = _WriteBlock("handler", output="error handled")
        cleanup = _WriteBlock("cleanup", output="cleanup done")

        workflow = _build_workflow(
            "depends_chain",
            fetch,
            analyze,
            handler,
            cleanup,
            entry="fetch",
        )
        workflow.add_transition("fetch", "analyze")
        workflow.set_error_route("fetch", "handler")
        workflow.add_transition("handler", "cleanup")

        final_state = await workflow.run(WorkflowState())

        # Error path: fetch (fail) -> handler -> cleanup
        assert "handler" in final_state.results
        assert final_state.results["handler"].output == "error handled"
        assert "cleanup" in final_state.results
        assert final_state.results["cleanup"].output == "cleanup done"

        # Normal path should be skipped
        assert "analyze" not in final_state.results, (
            "Downstream depends block must be skipped when predecessor fails"
        )

    async def test_depends_error_metadata_available_to_handler(self):
        """
        When predecessor fails, the error info should be available in
        shared_memory for the error handler to inspect.
        """
        fetch = _FailingBlock("fetch", error_msg="connection refused")
        analyze = _WriteBlock("analyze", output="should not run")
        handler = _ErrorAwareHandlerBlock("handler", failed_block_id="fetch")

        workflow = _build_workflow("depends_meta", fetch, analyze, handler, entry="fetch")
        workflow.add_transition("fetch", "analyze")
        workflow.set_error_route("fetch", "handler")

        final_state = await workflow.run(WorkflowState())

        # Error metadata should be in shared_memory
        error_info = final_state.shared_memory.get("__error__fetch")
        assert error_info is not None, "Error info must be stored in shared_memory for handler"
        assert error_info["type"] == "RuntimeError"
        assert error_info["message"] == "connection refused"

        # Handler should have seen the error
        handler_result = final_state.results["handler"]
        assert handler_result.metadata["seen_error"] == {
            "type": "RuntimeError",
            "message": "connection refused",
        }

    async def test_depends_predecessor_error_route_yaml_parsed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """
        YAML-parsed test: fetch exits through error_route to handler,
        analyze has depends: fetch.

        fetch fails -> handler runs, analyze is skipped.
        """
        from runsight_core.blocks.code import CodeBlock

        code_calls: list[str] = []

        async def _fake_code_run(self: CodeBlock, inputs: dict) -> tuple[bytes, bytes, int]:
            code_calls.append(self.block_id)
            if self.block_id == "fetch":
                return (
                    json.dumps({"exit_handle": "error", "reason": "fetch failed"}).encode(),
                    b"",
                    0,
                )
            if self.block_id == "handler":
                return (json.dumps({"handled": True}).encode(), b"", 0)
            raise AssertionError(f"{self.block_id} should be skipped")

        monkeypatch.setattr(CodeBlock, "_run_subprocess", _fake_code_run)

        workflow_path = _write_workflow_file(
            tmp_path,
            "depends_error.yaml",
            """\
            version: "1.0"
            blocks:
              fetch:
                type: code
                error_route: handler
                code: |
                  def main(data):
                      return {"exit_handle": "error", "reason": "fetch failed"}
              analyze:
                type: code
                depends: fetch
                code: |
                  def main(data):
                      return {"analyzed": True}
              handler:
                type: code
                code: |
                  def main(data):
                      return {"handled": True}
            workflow:
              name: depends_error_route
              entry: fetch
            """,
        )

        workflow = parse_workflow_yaml(workflow_path)

        final_state = await workflow.run(WorkflowState())

        # fetch should have failed with error result
        assert final_state.results["fetch"].exit_handle == "error"

        # handler should have run
        assert "handler" in final_state.results
        handler_output = json.loads(final_state.results["handler"].output)
        assert handler_output["handled"] is True

        # analyze should be skipped because it depends on failed fetch.
        assert "analyze" not in final_state.results, (
            "Block with depends: on failed predecessor must not execute"
        )
        assert code_calls == ["fetch", "handler"]

    async def test_depends_successor_runs_after_predecessor_yaml_parsed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """YAML depends wiring runs the successor after its predecessor completes."""
        from runsight_core.blocks.code import CodeBlock

        code_calls: list[str] = []

        async def _fake_code_run(self: CodeBlock, inputs: dict) -> tuple[bytes, bytes, int]:
            code_calls.append(self.block_id)
            if self.block_id == "fetch":
                return (json.dumps({"fetched": True}).encode(), b"", 0)
            if self.block_id == "analyze":
                return (json.dumps({"analyzed": inputs.get("upstream")}).encode(), b"", 0)
            raise AssertionError("handler should be skipped")

        monkeypatch.setattr(CodeBlock, "_run_subprocess", _fake_code_run)

        workflow_path = _write_workflow_file(
            tmp_path,
            "depends_success.yaml",
            """\
            version: "1.0"
            blocks:
              fetch:
                type: code
                error_route: handler
                code: |
                  def main(data):
                      return {"fetched": True}
              analyze:
                type: code
                depends: fetch
                inputs:
                  upstream:
                    from: results.fetch
                code: |
                  def main(data):
                      return {"analyzed": data.get("upstream")}
              handler:
                type: code
                code: |
                  def main(data):
                      return {"handled": True}
            workflow:
              name: depends_success_route
              entry: fetch
            """,
        )

        workflow = parse_workflow_yaml(workflow_path)

        final_state = await workflow.run(WorkflowState())

        assert code_calls == ["fetch", "analyze"]
        assert "handler" not in final_state.results
        assert "analyze" in final_state.results
        analyzer_output = json.loads(final_state.results["analyze"].output)
        assert json.loads(analyzer_output["analyzed"]) == {"fetched": True}
