"""E2E tests for RUN-704: on_error=catch + error_route + output mapping combinations.

Tests three untested combinations from Epics 22 and 23:

AC1: WorkflowBlock on_error="catch" + error_route — child raises, parent catches,
     exit_handle="error", workflow routes to error handler, handler result in final state.
AC2: WorkflowBlock output mapping on success — child produces output, parent maps via
     outputs: config, mapped key in parent results, unmapped child keys absent.
AC3: depends predecessor fails -> error_route fires — downstream block with depends:
     does not execute, failed block's error_route handler runs.
"""

from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent
from types import SimpleNamespace

import pytest
from runsight_core.blocks.base import BaseBlock
from runsight_core.blocks.workflow_block import WorkflowBlock
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.workflow import Workflow
from runsight_core.yaml.parser import parse_workflow_yaml
from runsight_core.yaml.schema import (
    WorkflowInterfaceDef,
    WorkflowInterfaceInputDef,
    WorkflowInterfaceOutputDef,
)

# ---------------------------------------------------------------------------
# Helpers — block doubles (no LLM, no subprocess)
# ---------------------------------------------------------------------------


class _FailingBlock(BaseBlock):
    """Block that always raises RuntimeError."""

    def __init__(self, block_id: str, *, error_msg: str = "block failed"):
        super().__init__(block_id)
        self._error_msg = error_msg
        self.call_count = 0

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        self.call_count += 1
        raise RuntimeError(self._error_msg)


class _WriteBlock(BaseBlock):
    """Block that records its execution into results and shared_memory."""

    def __init__(self, block_id: str, *, output: str | None = None):
        super().__init__(block_id)
        self._output = output or block_id
        self.call_count = 0

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        self.call_count += 1
        return state.model_copy(
            update={
                "results": {
                    **state.results,
                    self.block_id: BlockResult(output=self._output),
                },
                "shared_memory": {
                    **state.shared_memory,
                    f"visited_{self.block_id}": self.call_count,
                },
            }
        )


class _ErrorAwareHandlerBlock(BaseBlock):
    """Handler block that snapshots routed error metadata for assertions."""

    def __init__(self, block_id: str, *, failed_block_id: str):
        super().__init__(block_id)
        self.failed_block_id = failed_block_id
        self.call_count = 0

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        self.call_count += 1
        error_info = state.shared_memory.get(f"__error__{self.failed_block_id}")
        return state.model_copy(
            update={
                "results": {
                    **state.results,
                    self.block_id: BlockResult(
                        output="handled",
                        metadata={"seen_error": error_info},
                    ),
                },
                "shared_memory": {
                    **state.shared_memory,
                    "handler_ran": True,
                },
            }
        )


class _ScriptedRunner:
    """Deterministic runner for exercising parsed LLM-backed blocks end-to-end."""

    def __init__(self, behaviors=None):
        self.behaviors = behaviors or {}
        self.model_name = "gpt-4o-mini"
        self.calls: list[tuple[str, str, str | None]] = []
        self.attempts: dict[str, int] = {}

    async def execute(self, instruction: str, context, soul, messages=None, **kwargs):
        soul_id = soul.id
        attempt = self.attempts.get(soul_id, 0) + 1
        self.attempts[soul_id] = attempt
        self.calls.append((soul_id, instruction, context))

        behavior = self.behaviors.get(soul_id)
        if behavior is None:
            output = f"{soul_id}|{instruction}|{context or ''}"
        else:
            output = behavior(attempt, instruction, soul)

        if isinstance(output, BaseException):
            raise output

        return SimpleNamespace(output=str(output), cost_usd=0.0, total_tokens=0)


def _write_workflow_file(base_dir: Path, name: str, yaml_content: str) -> str:
    workflow_file = base_dir / name
    workflow_file.write_text(dedent(yaml_content), encoding="utf-8")
    return str(workflow_file)


def _build_workflow(name: str, *blocks: BaseBlock, entry: str) -> Workflow:
    """Build a workflow from blocks, setting entry."""
    wf = Workflow(name=name)
    for block in blocks:
        wf.add_block(block)
    wf.set_entry(entry)
    return wf


def _make_interface(
    inputs: list[dict] | None = None,
    outputs: list[dict] | None = None,
) -> WorkflowInterfaceDef:
    return WorkflowInterfaceDef(
        inputs=[WorkflowInterfaceInputDef(**i) for i in (inputs or [])],
        outputs=[WorkflowInterfaceOutputDef(**o) for o in (outputs or [])],
    )


# ===========================================================================
# AC1: WorkflowBlock on_error="catch" + error_route combination
# ===========================================================================


@pytest.mark.asyncio
class TestWorkflowBlockOnErrorCatchWithErrorRoute:
    """AC1: WorkflowBlock on_error="catch" + error_route in the parent workflow.

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
          - happy_next (should NOT execute)

        Child workflow raises RuntimeError.
        Expected: handler executes, happy_next does NOT, handler result in final state.
        """
        # Build a child workflow with a single failing block
        child_fail = _FailingBlock("child_step", error_msg="child exploded")
        child_wf = _build_workflow("failing_child", child_fail, entry="child_step")

        interface = _make_interface(
            inputs=[{"name": "topic", "target": "shared_memory.topic"}],
        )

        wb = WorkflowBlock(
            block_id="invoke_child",
            child_workflow=child_wf,
            inputs={"topic": "shared_memory.parent_topic"},
            outputs={},
            interface=interface,
            on_error="catch",
        )

        handler = _ErrorAwareHandlerBlock("handler", failed_block_id="invoke_child")
        happy_next = _WriteBlock("happy_next", output="should not run")

        # Parent workflow: invoke_child -> happy_next (normal path)
        #                  invoke_child -error_route-> handler
        parent_wf = _build_workflow("parent_wf", wb, handler, happy_next, entry="invoke_child")
        parent_wf.add_transition("invoke_child", "happy_next")
        parent_wf.set_error_route("invoke_child", "handler")

        parent_state = WorkflowState(
            shared_memory={"parent_topic": "testing"},
        )

        final_state = await parent_wf.run(parent_state)

        # The WorkflowBlock catches the child failure (on_error="catch")
        invoke_result = final_state.results.get("invoke_child")
        assert invoke_result is not None, "WorkflowBlock must produce a BlockResult"
        assert isinstance(invoke_result, BlockResult)
        assert invoke_result.exit_handle == "error", (
            f"exit_handle must be 'error' for caught child failure, got {invoke_result.exit_handle!r}"
        )

        # The handler must have executed (routed via error_route or conditional transition)
        assert "handler" in final_state.results, (
            "error handler must execute when WorkflowBlock catches child failure "
            "and error_route is configured"
        )
        assert final_state.results["handler"].output == "handled"

        # happy_next must NOT have executed (error path, not happy path)
        assert "happy_next" not in final_state.results, (
            "happy path successor must NOT execute when child fails"
        )

    async def test_catch_plus_error_route_handler_result_in_final_state(self):
        """
        Verify that the handler block's result appears in the final workflow
        state with correct output and metadata.
        """
        child_fail = _FailingBlock("child_step", error_msg="timeout reached")
        child_wf = _build_workflow("failing_child", child_fail, entry="child_step")

        interface = _make_interface(
            inputs=[{"name": "topic", "target": "shared_memory.topic"}],
        )

        wb = WorkflowBlock(
            block_id="invoke_child",
            child_workflow=child_wf,
            inputs={"topic": "shared_memory.parent_topic"},
            outputs={},
            interface=interface,
            on_error="catch",
        )

        handler = _WriteBlock("handler", output="error recovered")

        parent_wf = _build_workflow("parent_wf", wb, handler, entry="invoke_child")
        parent_wf.set_error_route("invoke_child", "handler")

        parent_state = WorkflowState(
            shared_memory={"parent_topic": "testing"},
        )

        final_state = await parent_wf.run(parent_state)

        # Handler must have its result in the final state
        handler_result = final_state.results.get("handler")
        assert handler_result is not None, "handler result must be present in final state"
        assert handler_result.output == "error recovered"

    async def test_catch_plus_error_route_yaml_parsed_workflow(self, tmp_path: Path):
        """
        End-to-end test using YAML-parsed workflow: a WorkflowBlock with
        on_error="catch" in a parent that has error_route configured.

        Uses a code block as the child so no LLM mock is needed for the child.
        The parent uses a linear block for the WorkflowBlock invoker, but
        since on_error="catch" is a WorkflowBlock feature, we build the parent
        programmatically with a WorkflowBlock and wire it into a parent workflow.

        This variant tests with CodeBlock as the child (raises via code execution).
        """
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
        child_wf = parse_workflow_yaml(child_yaml_path)

        wb = WorkflowBlock(
            block_id="invoke_child",
            child_workflow=child_wf,
            inputs={},
            outputs={},
            on_error="catch",
        )

        handler = _WriteBlock("handler", output="recovered from child failure")

        parent_wf = _build_workflow("parent_wf", wb, handler, entry="invoke_child")
        parent_wf.set_error_route("invoke_child", "handler")

        final_state = await parent_wf.run(WorkflowState())

        # WorkflowBlock must catch the child error
        invoke_result = final_state.results.get("invoke_child")
        assert invoke_result is not None
        assert invoke_result.exit_handle == "error"

        # Handler must run
        assert "handler" in final_state.results
        assert final_state.results["handler"].output == "recovered from child failure"


# ===========================================================================
# AC2: WorkflowBlock output mapping on success
# ===========================================================================


@pytest.mark.asyncio
class TestWorkflowBlockOutputMappingOnSuccess:
    """AC2: WorkflowBlock output mapping works correctly on success.

    test_run605_on_error_modes.py tests that output mapping is SKIPPED on catch,
    but no test verifies output mapping WORKS correctly on success.
    """

    async def test_output_mapping_transfers_child_result_to_parent(self):
        """
        Child CodeBlock returns a dict. Parent maps child result key to parent
        results via outputs config. Mapped key must appear in parent state,
        unmapped child keys must be absent.
        """
        # Child block writes {"summary": "analysis complete", "raw": "internal data"}
        child_block = _WriteBlock("child_writer", output="analysis complete")
        child_wf = _build_workflow("child_wf", child_block, entry="child_writer")

        interface = _make_interface(
            inputs=[{"name": "topic", "target": "shared_memory.topic"}],
            outputs=[{"name": "summary", "source": "results.child_writer"}],
        )

        wb = WorkflowBlock(
            block_id="invoke_child",
            child_workflow=child_wf,
            inputs={"topic": "shared_memory.parent_topic"},
            outputs={"results.mapped_summary": "summary"},
            interface=interface,
        )

        parent_state = WorkflowState(
            shared_memory={"parent_topic": "testing"},
        )

        final_state = await wb.execute(parent_state)

        # Mapped key must exist in parent results
        mapped = final_state.results.get("mapped_summary")
        assert mapped is not None, (
            "Output mapping must transfer child result to parent under mapped key"
        )
        # The mapped value should be the child's output
        assert mapped == "analysis complete", (
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
        child_wf = _build_workflow("child_wf", writer_a, writer_b, entry="writer_a")
        child_wf.add_transition("writer_a", "writer_b")

        interface = _make_interface(
            inputs=[{"name": "topic", "target": "shared_memory.topic"}],
            outputs=[{"name": "output_a", "source": "results.writer_a"}],
        )

        # Only map writer_a's output; writer_b should NOT leak to parent
        wb = WorkflowBlock(
            block_id="invoke_child",
            child_workflow=child_wf,
            inputs={"topic": "shared_memory.parent_topic"},
            outputs={"results.parent_a": "output_a"},
            interface=interface,
        )

        parent_state = WorkflowState(
            shared_memory={"parent_topic": "testing"},
        )

        final_state = await wb.execute(parent_state)

        # Mapped key present
        assert "parent_a" in final_state.results, "Mapped child result must appear in parent"
        assert final_state.results["parent_a"] == "result A"

        # Unmapped keys absent — writer_b's result should NOT leak
        assert "writer_b" not in final_state.results, (
            "Unmapped child result key must NOT appear in parent results"
        )
        assert "writer_a" not in final_state.results, (
            "Raw child result key must NOT appear in parent results (only mapped key)"
        )

    async def test_output_mapping_success_produces_completed_exit_handle(self):
        """
        On success with output mapping, the WorkflowBlock's own BlockResult
        should have exit_handle="completed" (not "error").
        """
        child_block = _WriteBlock("child_writer", output="done")
        child_wf = _build_workflow("child_wf", child_block, entry="child_writer")

        interface = _make_interface(
            inputs=[{"name": "topic", "target": "shared_memory.topic"}],
            outputs=[{"name": "out", "source": "results.child_writer"}],
        )

        wb = WorkflowBlock(
            block_id="invoke_child",
            child_workflow=child_wf,
            inputs={"topic": "shared_memory.parent_topic"},
            outputs={"results.parent_out": "out"},
            interface=interface,
        )

        parent_state = WorkflowState(
            shared_memory={"parent_topic": "testing"},
        )

        final_state = await wb.execute(parent_state)

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
        child_wf = _build_workflow("child_wf", child_block, entry="child_writer")

        interface = _make_interface(
            inputs=[{"name": "topic", "target": "shared_memory.topic"}],
            outputs=[{"name": "out", "source": "results.child_writer"}],
        )

        wb = WorkflowBlock(
            block_id="invoke_child",
            child_workflow=child_wf,
            inputs={"topic": "shared_memory.parent_topic"},
            outputs={"shared_memory.parent_output": "out"},
            interface=interface,
        )

        parent_state = WorkflowState(
            shared_memory={"parent_topic": "testing"},
        )

        final_state = await wb.execute(parent_state)

        # The output should appear in shared_memory
        assert final_state.shared_memory.get("parent_output") == "mapped_value", (
            "Output mapping to shared_memory must work on success"
        )

    async def test_output_mapping_with_code_block_child(self, tmp_path: Path):
        """
        End-to-end: child is a YAML-parsed CodeBlock that returns a dict.
        Parent maps the code block's result to parent state.
        """
        child_yaml_path = _write_workflow_file(
            tmp_path,
            "child_code.yaml",
            """\
            version: "1.0"
            interface:
              inputs:
                - name: topic
                  target: shared_memory.topic
              outputs:
                - name: analysis
                  source: results.analyzer
            blocks:
              analyzer:
                type: code
                code: |
                  def main(data):
                      topic = data["shared_memory"].get("topic", "unknown")
                      return {"analyzed": topic, "score": 42}
            workflow:
              name: child_code_wf
              entry: analyzer
            """,
        )
        child_wf = parse_workflow_yaml(child_yaml_path)

        # Build interface manually (Workflow object doesn't store it;
        # the parser reads it from RunsightWorkflowFile.interface)
        child_interface = _make_interface(
            inputs=[{"name": "topic", "target": "shared_memory.topic"}],
            outputs=[{"name": "analysis", "source": "results.analyzer"}],
        )

        wb = WorkflowBlock(
            block_id="invoke_child",
            child_workflow=child_wf,
            inputs={"topic": "shared_memory.parent_topic"},
            outputs={"results.parent_analysis": "analysis"},
            interface=child_interface,
        )

        parent_state = WorkflowState(
            shared_memory={"parent_topic": "machine learning"},
        )

        final_state = await wb.execute(parent_state)

        # The mapped output should appear in parent results
        parent_analysis = final_state.results.get("parent_analysis")
        assert parent_analysis is not None, (
            "CodeBlock child output must be mapped to parent results"
        )
        # CodeBlock returns JSON-serialized output
        parsed = (
            json.loads(parent_analysis) if isinstance(parent_analysis, str) else parent_analysis
        )
        assert parsed["analyzed"] == "machine learning"
        assert parsed["score"] == 42


# ===========================================================================
# AC3: depends predecessor fails -> error_route fires, dependent skipped
# ===========================================================================


@pytest.mark.asyncio
class TestDependsPredecessorFailsErrorRouteRuns:
    """AC3: When block B fails and has an error_route, and block A has
    depends: B, then:
      - B's error_route handler runs
      - A does NOT execute (queue.clear() wipes it)
    """

    async def test_depends_block_not_executed_when_predecessor_fails(self):
        """
        Workflow: entry=fetch -> analyze (depends: fetch)
                  fetch has error_route -> handler

        fetch fails -> handler runs, analyze does NOT run.
        """
        fetch = _FailingBlock("fetch", error_msg="fetch crashed")
        analyze = _WriteBlock("analyze", output="should not run")
        handler = _ErrorAwareHandlerBlock("handler", failed_block_id="fetch")

        wf = _build_workflow("depends_fail", fetch, analyze, handler, entry="fetch")
        # depends: fetch on analyze means add_transition("fetch", "analyze")
        wf.add_transition("fetch", "analyze")
        wf.set_error_route("fetch", "handler")

        final_state = await wf.run(WorkflowState())

        # fetch should have an error result
        assert "fetch" in final_state.results
        assert final_state.results["fetch"].exit_handle == "error"

        # handler should have executed
        assert "handler" in final_state.results, (
            "error_route handler must execute when predecessor fails"
        )
        assert final_state.results["handler"].output == "handled"

        # analyze should NOT have executed (queue.clear() removes it)
        assert "analyze" not in final_state.results, (
            "Block with depends on failed predecessor must NOT execute "
            "when error_route fires (queue.clear() removes all downstream)"
        )

    async def test_depends_block_skipped_handler_continues_chain(self):
        """
        Workflow: entry=fetch -> analyze (depends: fetch)
                  fetch error_route -> handler -> cleanup

        fetch fails -> handler runs -> cleanup runs, analyze does NOT run.
        """
        fetch = _FailingBlock("fetch", error_msg="network error")
        analyze = _WriteBlock("analyze", output="should not run")
        handler = _WriteBlock("handler", output="error handled")
        cleanup = _WriteBlock("cleanup", output="cleanup done")

        wf = _build_workflow("depends_chain", fetch, analyze, handler, cleanup, entry="fetch")
        wf.add_transition("fetch", "analyze")
        wf.set_error_route("fetch", "handler")
        wf.add_transition("handler", "cleanup")

        final_state = await wf.run(WorkflowState())

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

        wf = _build_workflow("depends_meta", fetch, analyze, handler, entry="fetch")
        wf.add_transition("fetch", "analyze")
        wf.set_error_route("fetch", "handler")

        final_state = await wf.run(WorkflowState())

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

    async def test_depends_predecessor_fails_yaml_parsed(self, tmp_path: Path):
        """
        End-to-end YAML-parsed test: fetch (linear, raises) has error_route
        to handler (code), analyze has depends: fetch.

        fetch fails -> handler runs, analyze skipped.
        """
        workflow_path = _write_workflow_file(
            tmp_path,
            "depends_error.yaml",
            """\
            version: "1.0"
            souls:
              fetcher:
                id: fetcher
                role: Fetcher
                system_prompt: Fetch data.
            blocks:
              fetch:
                type: linear
                soul_ref: fetcher
                error_route: handler
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
                      err = data["shared_memory"].get("__error__fetch", {})
                      return {"handled": True, "error_type": err.get("type", "unknown")}
            workflow:
              name: depends_error_route
              entry: fetch
            """,
        )

        runner = _ScriptedRunner(
            {"fetcher": lambda attempt, task, soul: RuntimeError("API timeout")}
        )
        workflow = parse_workflow_yaml(workflow_path, runner=runner)

        final_state = await workflow.run(WorkflowState())

        # fetch should have failed with error result
        assert final_state.results["fetch"].exit_handle == "error"

        # handler should have run
        assert "handler" in final_state.results
        handler_output = json.loads(final_state.results["handler"].output)
        assert handler_output["handled"] is True
        assert handler_output["error_type"] == "RuntimeError"

        # analyze should NOT have run (depends on failed fetch, queue.clear'd)
        assert "analyze" not in final_state.results, (
            "Block with depends: on failed predecessor must not execute"
        )
