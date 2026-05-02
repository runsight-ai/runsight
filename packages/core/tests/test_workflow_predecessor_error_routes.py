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
from runsight_core.state import WorkflowState
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
