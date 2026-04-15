"""E2E tests for RUN-702: Mixed-type block pipeline — Linear -> Code -> Gate chained workflow.

Tests the core user journey of chaining different block types in a single workflow:
  - LinearBlock (LLM-backed, mocked) produces structured output
  - CodeBlock (pure Python, no LLM) reads linear output and transforms it
  - GateBlock (LLM-backed, mocked) evaluates code output and routes to pass/fail successor

AC1: Linear -> Code -> Gate -> pass branch — all three blocks execute, final state has
     all three results, gate routes to pass successor
AC2: Linear -> Code -> Gate -> fail branch — gate routes to fail successor
AC3: State passes correctly between blocks (code block reads linear output, gate evaluates code output)
AC4: All mocked — no real API calls
"""

from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent
from types import SimpleNamespace

import pytest
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.yaml.parser import parse_workflow_yaml

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _ScriptedRunner:
    """Deterministic runner for exercising parsed LLM-backed blocks end-to-end."""

    def __init__(self, behaviors=None):
        self.behaviors = behaviors or {}
        self.model_name = "gpt-4o-mini"
        self.calls: list[tuple[str, str, str | None]] = []
        self.attempts: dict[str, int] = {}

    async def execute(self, instruction: str, context: str | None, soul, messages=None):
        soul_id = soul.id
        attempt = self.attempts.get(soul_id, 0) + 1
        self.attempts[soul_id] = attempt
        self.calls.append((soul_id, instruction, context))

        behavior = self.behaviors.get(soul_id)
        if behavior is None:
            output = f"{soul_id}|{instruction}|{context or ''}"
        else:
            output = behavior(attempt, instruction, soul, context)

        if isinstance(output, BaseException):
            raise output

        return SimpleNamespace(output=str(output), cost_usd=0.01, total_tokens=50, exit_handle=None)


def _write_workflow_file(base_dir: Path, name: str, yaml_content: str) -> str:
    workflow_file = base_dir / name
    content = dedent(yaml_content)
    lines = content.lstrip().splitlines()
    first_key = lines[0].split(":")[0].strip() if lines else ""
    if first_key != "id":
        content = "id: test-workflow\nkind: workflow\n" + content
    workflow_file.write_text(content, encoding="utf-8")
    return str(workflow_file)


# ---------------------------------------------------------------------------
# YAML workflow template — the core mixed-type pipeline
#
# linear_block (LLM) -> code_block (Python) -> quality_gate (LLM gate)
#   gate pass -> pass_handler (code)
#   gate fail -> fail_handler (code)
# ---------------------------------------------------------------------------

_MIXED_PIPELINE_YAML = """\
version: "1.0"
souls:
  writer:
    id: writer
    kind: soul
    name: Content Writer
    role: Content Writer
    system_prompt: Generate structured JSON output.
  evaluator:
    id: evaluator
    kind: soul
    name: Quality Evaluator
    role: Quality Evaluator
    system_prompt: Evaluate content quality.
blocks:
  linear_block:
    type: linear
    soul_ref: writer
  code_block:
    type: code
    code: |
      import json
      def main(data):
          linear_output = data["results"]["linear_block"]
          parsed = json.loads(linear_output)
          return {
              "transformed": True,
              "title": parsed["title"].upper(),
              "word_count": len(parsed["body"].split()),
              "source": "linear_block"
          }
  quality_gate:
    type: gate
    soul_ref: evaluator
    eval_key: code_block
    pass: pass_handler
    fail: fail_handler
  pass_handler:
    type: code
    code: |
      import json
      def main(data):
          gate_result = data["results"]["quality_gate"]
          code_result = json.loads(data["results"]["code_block"])
          return {
              "branch": "pass",
              "gate_said": gate_result,
              "title_from_code": code_result["title"]
          }
  fail_handler:
    type: code
    code: |
      import json
      def main(data):
          gate_result = data["results"]["quality_gate"]
          code_result = json.loads(data["results"]["code_block"])
          return {
              "branch": "fail",
              "gate_said": gate_result,
              "title_from_code": code_result["title"]
          }
workflow:
  name: mixed_pipeline
  entry: linear_block
  transitions:
    - from: linear_block
      to: code_block
    - from: code_block
      to: quality_gate
"""


# ===========================================================================
# AC1: Linear -> Code -> Gate -> pass branch
# ===========================================================================


@pytest.mark.asyncio
class TestMixedPipelinePassPath:
    """When the gate evaluates positively, the workflow routes to pass_handler."""

    async def test_pass_path_all_three_blocks_execute(self, tmp_path: Path):
        """All three core blocks (linear, code, gate) execute and produce results."""
        workflow_path = _write_workflow_file(tmp_path, "pass_pipeline.yaml", _MIXED_PIPELINE_YAML)

        linear_output = json.dumps(
            {"title": "Good Article", "body": "This is well written content"}
        )
        runner = _ScriptedRunner(
            {
                "writer": lambda attempt, instruction, soul, context=None: linear_output,
                "evaluator": lambda attempt, instruction, soul, context=None: "PASS",
            }
        )
        workflow = parse_workflow_yaml(workflow_path, runner=runner)

        final_state = await workflow.run(WorkflowState())

        # All three core blocks must have results
        assert "linear_block" in final_state.results
        assert "code_block" in final_state.results
        assert "quality_gate" in final_state.results

    async def test_pass_path_gate_routes_to_pass_handler(self, tmp_path: Path):
        """Gate with PASS exit_handle routes to pass_handler, not fail_handler."""
        workflow_path = _write_workflow_file(tmp_path, "pass_route.yaml", _MIXED_PIPELINE_YAML)

        linear_output = json.dumps({"title": "Good Article", "body": "Well written content here"})
        runner = _ScriptedRunner(
            {
                "writer": lambda attempt, instruction, soul, context=None: linear_output,
                "evaluator": lambda attempt, instruction, soul, context=None: "PASS",
            }
        )
        workflow = parse_workflow_yaml(workflow_path, runner=runner)

        final_state = await workflow.run(WorkflowState())

        # Pass handler executed, fail handler did NOT execute
        assert "pass_handler" in final_state.results
        assert "fail_handler" not in final_state.results

    async def test_pass_path_gate_exit_handle_is_pass(self, tmp_path: Path):
        """The gate block result has exit_handle='pass'."""
        workflow_path = _write_workflow_file(tmp_path, "pass_exit.yaml", _MIXED_PIPELINE_YAML)

        linear_output = json.dumps({"title": "Good Article", "body": "Quality content here"})
        runner = _ScriptedRunner(
            {
                "writer": lambda attempt, instruction, soul, context=None: linear_output,
                "evaluator": lambda attempt, instruction, soul, context=None: "PASS",
            }
        )
        workflow = parse_workflow_yaml(workflow_path, runner=runner)

        final_state = await workflow.run(WorkflowState())

        assert final_state.results["quality_gate"].exit_handle == "pass"

    async def test_pass_path_final_state_has_four_block_results(self, tmp_path: Path):
        """Final state has results for all four blocks: linear, code, gate, pass_handler."""
        workflow_path = _write_workflow_file(tmp_path, "pass_all.yaml", _MIXED_PIPELINE_YAML)

        linear_output = json.dumps({"title": "Good Article", "body": "Content here today"})
        runner = _ScriptedRunner(
            {
                "writer": lambda attempt, instruction, soul, context=None: linear_output,
                "evaluator": lambda attempt, instruction, soul, context=None: "PASS",
            }
        )
        workflow = parse_workflow_yaml(workflow_path, runner=runner)

        final_state = await workflow.run(WorkflowState())

        expected_blocks = {"linear_block", "code_block", "quality_gate", "pass_handler"}
        assert expected_blocks <= set(final_state.results.keys())

    async def test_pass_handler_receives_gate_and_code_results(self, tmp_path: Path):
        """The pass_handler code block can read both gate and code results from state."""
        workflow_path = _write_workflow_file(tmp_path, "pass_data.yaml", _MIXED_PIPELINE_YAML)

        linear_output = json.dumps({"title": "Good Article", "body": "Content here today"})
        runner = _ScriptedRunner(
            {
                "writer": lambda attempt, instruction, soul, context=None: linear_output,
                "evaluator": lambda attempt, instruction, soul, context=None: "PASS",
            }
        )
        workflow = parse_workflow_yaml(workflow_path, runner=runner)

        final_state = await workflow.run(WorkflowState())

        handler_output = json.loads(final_state.results["pass_handler"].output)
        assert handler_output["branch"] == "pass"
        assert handler_output["title_from_code"] == "GOOD ARTICLE"


# ===========================================================================
# AC2: Linear -> Code -> Gate -> fail branch
# ===========================================================================


@pytest.mark.asyncio
class TestMixedPipelineFailPath:
    """When the gate evaluates negatively, the workflow routes to fail_handler."""

    async def test_fail_path_gate_routes_to_fail_handler(self, tmp_path: Path):
        """Gate with FAIL exit_handle routes to fail_handler, not pass_handler."""
        workflow_path = _write_workflow_file(tmp_path, "fail_route.yaml", _MIXED_PIPELINE_YAML)

        linear_output = json.dumps({"title": "Bad Article", "body": "Poor quality"})
        runner = _ScriptedRunner(
            {
                "writer": lambda attempt, instruction, soul, context=None: linear_output,
                "evaluator": lambda attempt,
                instruction,
                soul,
                context=None: "FAIL: content is low quality",
            }
        )
        workflow = parse_workflow_yaml(workflow_path, runner=runner)

        final_state = await workflow.run(WorkflowState())

        # Fail handler executed, pass handler did NOT execute
        assert "fail_handler" in final_state.results
        assert "pass_handler" not in final_state.results

    async def test_fail_path_gate_exit_handle_is_fail(self, tmp_path: Path):
        """The gate block result has exit_handle='fail'."""
        workflow_path = _write_workflow_file(tmp_path, "fail_exit.yaml", _MIXED_PIPELINE_YAML)

        linear_output = json.dumps({"title": "Bad Article", "body": "Poor quality"})
        runner = _ScriptedRunner(
            {
                "writer": lambda attempt, instruction, soul, context=None: linear_output,
                "evaluator": lambda attempt,
                instruction,
                soul,
                context=None: "FAIL: needs improvement",
            }
        )
        workflow = parse_workflow_yaml(workflow_path, runner=runner)

        final_state = await workflow.run(WorkflowState())

        assert final_state.results["quality_gate"].exit_handle == "fail"

    async def test_fail_path_final_state_has_four_block_results(self, tmp_path: Path):
        """Final state has results for linear, code, gate, and fail_handler (not pass_handler)."""
        workflow_path = _write_workflow_file(tmp_path, "fail_all.yaml", _MIXED_PIPELINE_YAML)

        linear_output = json.dumps({"title": "Bad Article", "body": "Poor quality"})
        runner = _ScriptedRunner(
            {
                "writer": lambda attempt, instruction, soul, context=None: linear_output,
                "evaluator": lambda attempt, instruction, soul, context=None: "FAIL: rejected",
            }
        )
        workflow = parse_workflow_yaml(workflow_path, runner=runner)

        final_state = await workflow.run(WorkflowState())

        expected_blocks = {"linear_block", "code_block", "quality_gate", "fail_handler"}
        assert expected_blocks <= set(final_state.results.keys())

    async def test_fail_handler_receives_gate_and_code_results(self, tmp_path: Path):
        """The fail_handler code block can read both gate and code results from state."""
        workflow_path = _write_workflow_file(tmp_path, "fail_data.yaml", _MIXED_PIPELINE_YAML)

        linear_output = json.dumps({"title": "Bad Article", "body": "Poor quality"})
        runner = _ScriptedRunner(
            {
                "writer": lambda attempt, instruction, soul, context=None: linear_output,
                "evaluator": lambda attempt,
                instruction,
                soul,
                context=None: "FAIL: low quality content",
            }
        )
        workflow = parse_workflow_yaml(workflow_path, runner=runner)

        final_state = await workflow.run(WorkflowState())

        handler_output = json.loads(final_state.results["fail_handler"].output)
        assert handler_output["branch"] == "fail"
        assert handler_output["title_from_code"] == "BAD ARTICLE"


# ===========================================================================
# AC3: State passes correctly between blocks
# ===========================================================================


@pytest.mark.asyncio
class TestStateFlowsBetweenBlocks:
    """Verify data flows correctly: code block reads linear output, gate evaluates code output."""

    async def test_code_block_transforms_linear_output(self, tmp_path: Path):
        """The code block reads linear_block output and produces a transformed result."""
        workflow_path = _write_workflow_file(tmp_path, "state_flow.yaml", _MIXED_PIPELINE_YAML)

        linear_output = json.dumps({"title": "My Title", "body": "one two three four five"})
        runner = _ScriptedRunner(
            {
                "writer": lambda attempt, instruction, soul, context=None: linear_output,
                "evaluator": lambda attempt, instruction, soul, context=None: "PASS",
            }
        )
        workflow = parse_workflow_yaml(workflow_path, runner=runner)

        final_state = await workflow.run(WorkflowState())

        code_output = json.loads(final_state.results["code_block"].output)
        assert code_output["transformed"] is True
        assert code_output["title"] == "MY TITLE"
        assert code_output["word_count"] == 5
        assert code_output["source"] == "linear_block"

    async def test_gate_evaluates_code_block_output(self, tmp_path: Path):
        """The gate block receives the code_block output as its eval content (via eval_key)."""
        workflow_path = _write_workflow_file(tmp_path, "gate_eval.yaml", _MIXED_PIPELINE_YAML)

        linear_output = json.dumps({"title": "Article", "body": "Some content here"})
        call_contexts = []

        def evaluator_behavior(attempt, instruction, soul, context=None):
            # Capture what the gate sends to the evaluator (gate puts content in context)
            call_contexts.append(context)
            return "PASS"

        runner = _ScriptedRunner(
            {
                "writer": lambda attempt, instruction, soul, context=None: linear_output,
                "evaluator": evaluator_behavior,
            }
        )
        workflow = parse_workflow_yaml(workflow_path, runner=runner)

        await workflow.run(WorkflowState())

        # The evaluator received the code_block output as context
        assert len(call_contexts) == 1
        gate_context = call_contexts[0]
        # The gate passes the code_block's output (JSON string) as context to the evaluator
        # Verify the gate context contains content from the code block's output
        assert "transformed" in gate_context
        assert "ARTICLE" in gate_context

    async def test_linear_block_output_is_raw_llm_response(self, tmp_path: Path):
        """The linear block stores the raw LLM response (mocked JSON string)."""
        workflow_path = _write_workflow_file(tmp_path, "linear_raw.yaml", _MIXED_PIPELINE_YAML)

        linear_output = json.dumps({"title": "Test Title", "body": "Test body content"})
        runner = _ScriptedRunner(
            {
                "writer": lambda attempt, instruction, soul, context=None: linear_output,
                "evaluator": lambda attempt, instruction, soul, context=None: "PASS",
            }
        )
        workflow = parse_workflow_yaml(workflow_path, runner=runner)

        final_state = await workflow.run(WorkflowState())

        # Linear block output is the raw mocked response
        assert isinstance(final_state.results["linear_block"], BlockResult)
        parsed = json.loads(final_state.results["linear_block"].output)
        assert parsed["title"] == "Test Title"
        assert parsed["body"] == "Test body content"


# ===========================================================================
# AC4: All mocked — no real API calls
# ===========================================================================


@pytest.mark.asyncio
class TestNoRealAPICalls:
    """Verify all LLM interactions are mocked via _ScriptedRunner — no real API calls."""

    async def test_runner_captures_all_llm_calls(self, tmp_path: Path):
        """The _ScriptedRunner captures exactly two LLM calls: writer + evaluator."""
        workflow_path = _write_workflow_file(tmp_path, "mock_verify.yaml", _MIXED_PIPELINE_YAML)

        linear_output = json.dumps({"title": "Article", "body": "Content here"})
        runner = _ScriptedRunner(
            {
                "writer": lambda attempt, instruction, soul, context=None: linear_output,
                "evaluator": lambda attempt, instruction, soul, context=None: "PASS",
            }
        )
        workflow = parse_workflow_yaml(workflow_path, runner=runner)

        await workflow.run(WorkflowState())

        # Exactly two LLM calls: one for linear_block (writer), one for quality_gate (evaluator)
        soul_ids_called = [call[0] for call in runner.calls]
        assert "writer" in soul_ids_called
        assert "evaluator" in soul_ids_called
        assert len(runner.calls) == 2

    async def test_code_block_makes_no_llm_calls(self, tmp_path: Path):
        """The code block executes pure Python — it does not invoke the runner."""
        workflow_path = _write_workflow_file(tmp_path, "code_no_llm.yaml", _MIXED_PIPELINE_YAML)

        linear_output = json.dumps({"title": "Article", "body": "Content here"})
        runner = _ScriptedRunner(
            {
                "writer": lambda attempt, instruction, soul, context=None: linear_output,
                "evaluator": lambda attempt, instruction, soul, context=None: "PASS",
            }
        )
        workflow = parse_workflow_yaml(workflow_path, runner=runner)

        await workflow.run(WorkflowState())

        # No soul called "code_block" — code blocks don't use LLM
        soul_ids_called = [call[0] for call in runner.calls]
        assert "code_block" not in soul_ids_called
