"""Tests for RUN-695: Offline eval runner for workflow test cases.

Covers:
  AC1 -- Executor mode: 2 cases, no fixtures, executor callback called, assertions fire,
         structured result returned with per-case and aggregate scores.
  AC2 -- Fixture mode: case with fixtures for all blocks -> no executor called,
         assertions run against fixture outputs.
  AC3 -- Threshold/pass-fail: aggregate score vs eval.threshold drives result.passed.
  Edge cases -- no executor + no fixtures -> error; multiple blocks; empty expected.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from runsight_core.assertions.base import AssertionContext, GradingResult
from runsight_core.assertions.registry import register_assertion
from runsight_core.assertions.scoring import AssertionsResult

# This import WILL FAIL until Green implements the module -- expected Red failure.
from runsight_core.eval.runner import EvalCaseResult, EvalSuiteResult, run_eval
from runsight_core.state import BlockResult, WorkflowState

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# A minimal workflow YAML used as template across tests.
# One block "analyze" with a "contains" assertion.
_TWO_CASE_WORKFLOW_YAML = """\
version: "1.0"
souls:
  default_soul:
    id: default_soul
    model: gpt-4o
    system_prompt: "You are a research assistant."
blocks:
  analyze:
    type: llm
    soul: default_soul
    prompt_template: "Analyze: {task_instruction}"
workflow:
  name: test_workflow
  entry: analyze
  transitions:
    - from: analyze
      to: END
eval:
  threshold: 0.8
  cases:
    - id: case_1
      inputs:
        task_instruction: "Research LLMs"
      expected:
        analyze:
          - type: contains
            value: "LLM"
    - id: case_2
      inputs:
        task_instruction: "Research transformers"
      expected:
        analyze:
          - type: contains
            value: "transformer"
"""

_FIXTURE_CASE_YAML = """\
version: "1.0"
souls:
  default_soul:
    id: default_soul
    model: gpt-4o
    system_prompt: "You are a research assistant."
blocks:
  analyze:
    type: llm
    soul: default_soul
    prompt_template: "Analyze: {task_instruction}"
workflow:
  name: test_workflow
  entry: analyze
  transitions:
    - from: analyze
      to: END
eval:
  threshold: 0.8
  cases:
    - id: fixture_case
      inputs:
        task_instruction: "Research LLMs"
      fixtures:
        analyze: "LLMs have transformed software development significantly."
      expected:
        analyze:
          - type: contains
            value: "LLM"
"""

_LOW_THRESHOLD_YAML = """\
version: "1.0"
souls:
  default_soul:
    id: default_soul
    model: gpt-4o
    system_prompt: "You are a research assistant."
blocks:
  analyze:
    type: llm
    soul: default_soul
    prompt_template: "Analyze: {task_instruction}"
workflow:
  name: test_workflow
  entry: analyze
  transitions:
    - from: analyze
      to: END
eval:
  threshold: 0.3
  cases:
    - id: easy_case
      inputs:
        task_instruction: "Say hello"
      expected:
        analyze:
          - type: contains
            value: "hello"
"""

_TWO_BLOCK_YAML = """\
version: "1.0"
souls:
  default_soul:
    id: default_soul
    model: gpt-4o
    system_prompt: "You are a research assistant."
blocks:
  analyze:
    type: llm
    soul: default_soul
    prompt_template: "Analyze: {task_instruction}"
  summarize:
    type: llm
    soul: default_soul
    prompt_template: "Summarize the analysis."
workflow:
  name: test_workflow
  entry: analyze
  transitions:
    - from: analyze
      to: summarize
    - from: summarize
      to: END
eval:
  threshold: 0.8
  cases:
    - id: multi_block_case
      inputs:
        task_instruction: "Research LLMs"
      fixtures:
        analyze: "LLMs have revolutionized NLP tasks."
        summarize: "Summary: LLMs are transformative."
      expected:
        analyze:
          - type: contains
            value: "LLM"
        summarize:
          - type: contains
            value: "Summary"
"""

_NO_EXPECTED_CASE_YAML = """\
version: "1.0"
souls:
  default_soul:
    id: default_soul
    model: gpt-4o
    system_prompt: "You are a research assistant."
blocks:
  analyze:
    type: llm
    soul: default_soul
    prompt_template: "Analyze: {task_instruction}"
workflow:
  name: test_workflow
  entry: analyze
  transitions:
    - from: analyze
      to: END
eval:
  threshold: 0.5
  cases:
    - id: no_assertions_case
      fixtures:
        analyze: "Some output."
      expected: {}
"""

_NO_FIXTURES_NO_EXECUTOR_YAML = """\
version: "1.0"
souls:
  default_soul:
    id: default_soul
    model: gpt-4o
    system_prompt: "You are a research assistant."
blocks:
  analyze:
    type: llm
    soul: default_soul
    prompt_template: "Analyze: {task_instruction}"
workflow:
  name: test_workflow
  entry: analyze
  transitions:
    - from: analyze
      to: END
eval:
  threshold: 0.8
  cases:
    - id: needs_executor
      inputs:
        task_instruction: "Research LLMs"
      expected:
        analyze:
          - type: contains
            value: "LLM"
"""


class _ContainsAssertion:
    """Stub assertion: checks if ``value`` is contained in output."""

    type: str = "contains"

    def __init__(self, value: str = ""):
        self._value = value

    def evaluate(self, output: str, context: AssertionContext) -> GradingResult:
        passed = self._value.lower() in output.lower()
        return GradingResult(
            passed=passed,
            score=1.0 if passed else 0.0,
            reason=f"'contains' check for '{self._value}'",
            assertion_type="contains",
        )


@pytest.fixture(autouse=True)
def _register_stubs():
    """Ensure stub assertion handlers are registered before every test."""
    register_assertion("contains", _ContainsAssertion)


def _make_executor_returning(results_by_case: dict[str, dict[str, str]]) -> AsyncMock:
    """Create an async mock executor that returns WorkflowState with the given results.

    ``results_by_case`` maps case inputs (as a deterministic key) to block_id -> output
    mappings.  The mock returns different results based on the inputs it receives.
    """
    call_count = {"n": 0}
    ordered_results = list(results_by_case.values())

    async def _executor(workflow, inputs):
        idx = call_count["n"]
        call_count["n"] += 1
        block_outputs = ordered_results[idx]
        state = WorkflowState()
        for block_id, output_text in block_outputs.items():
            state.results[block_id] = BlockResult(output=output_text)
        return state

    mock = AsyncMock(side_effect=_executor)
    return mock


# ===========================================================================
# AC1 -- Executor mode (no fixtures, executor provided)
# ===========================================================================


class TestEvalRunnerExecutorMode:
    """AC1: Given a workflow with eval section containing 2 test cases and no fixtures,
    when eval runner executes, then both cases run via executor callback, assertions fire,
    and structured result is returned with per-case and aggregate scores."""

    @pytest.mark.asyncio
    async def test_run_eval_returns_eval_suite_result(self):
        """run_eval returns an EvalSuiteResult instance."""
        executor = _make_executor_returning(
            {
                "case_1": {"analyze": "LLM research findings"},
                "case_2": {"analyze": "transformer architecture details"},
            }
        )
        result = await run_eval(_TWO_CASE_WORKFLOW_YAML, executor=executor)
        assert isinstance(result, EvalSuiteResult)

    @pytest.mark.asyncio
    async def test_executor_called_for_each_case(self):
        """Executor is called once per case (2 cases -> 2 calls)."""
        executor = _make_executor_returning(
            {
                "case_1": {"analyze": "LLM research findings"},
                "case_2": {"analyze": "transformer architecture details"},
            }
        )
        await run_eval(_TWO_CASE_WORKFLOW_YAML, executor=executor)
        assert executor.call_count == 2

    @pytest.mark.asyncio
    async def test_case_results_list_has_correct_length(self):
        """EvalSuiteResult.case_results has one entry per eval case."""
        executor = _make_executor_returning(
            {
                "case_1": {"analyze": "LLM research findings"},
                "case_2": {"analyze": "transformer architecture details"},
            }
        )
        result = await run_eval(_TWO_CASE_WORKFLOW_YAML, executor=executor)
        assert len(result.case_results) == 2

    @pytest.mark.asyncio
    async def test_case_result_ids_match_yaml(self):
        """Each EvalCaseResult has the correct case_id from the YAML."""
        executor = _make_executor_returning(
            {
                "case_1": {"analyze": "LLM research findings"},
                "case_2": {"analyze": "transformer architecture details"},
            }
        )
        result = await run_eval(_TWO_CASE_WORKFLOW_YAML, executor=executor)
        case_ids = [cr.case_id for cr in result.case_results]
        assert "case_1" in case_ids
        assert "case_2" in case_ids

    @pytest.mark.asyncio
    async def test_case_results_are_eval_case_result_instances(self):
        """Each entry in case_results is an EvalCaseResult instance."""
        executor = _make_executor_returning(
            {
                "case_1": {"analyze": "LLM research findings"},
                "case_2": {"analyze": "transformer architecture details"},
            }
        )
        result = await run_eval(_TWO_CASE_WORKFLOW_YAML, executor=executor)
        for cr in result.case_results:
            assert isinstance(cr, EvalCaseResult)

    @pytest.mark.asyncio
    async def test_assertions_run_per_block(self):
        """Each case result has block_results keyed by block_id with AssertionsResult."""
        executor = _make_executor_returning(
            {
                "case_1": {"analyze": "LLM research findings"},
                "case_2": {"analyze": "transformer architecture details"},
            }
        )
        result = await run_eval(_TWO_CASE_WORKFLOW_YAML, executor=executor)
        for cr in result.case_results:
            assert "analyze" in cr.block_results
            assert isinstance(cr.block_results["analyze"], AssertionsResult)

    @pytest.mark.asyncio
    async def test_passing_case_has_score_one(self):
        """When the executor output contains the expected value, case score is 1.0."""
        executor = _make_executor_returning(
            {
                "case_1": {"analyze": "LLM research findings"},
                "case_2": {"analyze": "transformer architecture details"},
            }
        )
        result = await run_eval(_TWO_CASE_WORKFLOW_YAML, executor=executor)
        case_1 = next(cr for cr in result.case_results if cr.case_id == "case_1")
        assert case_1.score == 1.0
        assert case_1.passed is True

    @pytest.mark.asyncio
    async def test_aggregate_score_is_average_of_cases(self):
        """EvalSuiteResult.score is the average of all case scores."""
        executor = _make_executor_returning(
            {
                "case_1": {"analyze": "LLM research findings"},
                "case_2": {"analyze": "transformer architecture details"},
            }
        )
        result = await run_eval(_TWO_CASE_WORKFLOW_YAML, executor=executor)
        # Both cases should pass -> average = 1.0
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_suite_threshold_from_yaml(self):
        """EvalSuiteResult.threshold matches the eval.threshold from YAML."""
        executor = _make_executor_returning(
            {
                "case_1": {"analyze": "LLM research findings"},
                "case_2": {"analyze": "transformer architecture details"},
            }
        )
        result = await run_eval(_TWO_CASE_WORKFLOW_YAML, executor=executor)
        assert result.threshold == 0.8

    @pytest.mark.asyncio
    async def test_executor_receives_correct_inputs(self):
        """The executor is called with workflow and the case's inputs dict."""
        calls = []

        async def tracking_executor(workflow, inputs):
            calls.append(inputs)
            state = WorkflowState()
            state.results["analyze"] = BlockResult(output="LLM transformer output")
            return state

        await run_eval(_TWO_CASE_WORKFLOW_YAML, executor=tracking_executor)
        assert len(calls) == 2
        # The inputs from case_1 and case_2
        input_values = [c.get("task_instruction") for c in calls]
        assert "Research LLMs" in input_values
        assert "Research transformers" in input_values


# ===========================================================================
# AC2 -- Fixture mode (fixtures provided, no executor needed)
# ===========================================================================


class TestEvalRunnerFixtureMode:
    """AC2: Given a workflow with eval section where one case has fixtures for all
    blocks in expected, when eval runner executes that case, then no LLM calls made
    (executor not called), assertions run against fixture outputs."""

    @pytest.mark.asyncio
    async def test_fixture_case_does_not_call_executor(self):
        """When all blocks in expected have fixtures, executor is NOT called."""
        executor = AsyncMock()
        await run_eval(_FIXTURE_CASE_YAML, executor=executor)
        executor.assert_not_called()

    @pytest.mark.asyncio
    async def test_fixture_case_without_executor_succeeds(self):
        """Fixture-only case works fine with no executor provided (None)."""
        result = await run_eval(_FIXTURE_CASE_YAML, executor=None)
        assert isinstance(result, EvalSuiteResult)

    @pytest.mark.asyncio
    async def test_fixture_case_without_executor_kwarg_succeeds(self):
        """Fixture-only case works fine when executor kwarg is omitted entirely."""
        result = await run_eval(_FIXTURE_CASE_YAML)
        assert isinstance(result, EvalSuiteResult)

    @pytest.mark.asyncio
    async def test_fixture_values_used_for_assertions(self):
        """Assertions evaluate against the fixture output, not real execution."""
        # The fixture output for "analyze" contains "LLM" -> contains assertion passes
        result = await run_eval(_FIXTURE_CASE_YAML)
        case = result.case_results[0]
        assert case.passed is True
        assert case.score == 1.0

    @pytest.mark.asyncio
    async def test_fixture_case_has_correct_case_id(self):
        """The case result has the correct case_id from YAML."""
        result = await run_eval(_FIXTURE_CASE_YAML)
        assert result.case_results[0].case_id == "fixture_case"

    @pytest.mark.asyncio
    async def test_fixture_case_block_results_populated(self):
        """Fixture case still populates block_results with AssertionsResult."""
        result = await run_eval(_FIXTURE_CASE_YAML)
        assert "analyze" in result.case_results[0].block_results
        assert isinstance(result.case_results[0].block_results["analyze"], AssertionsResult)

    @pytest.mark.asyncio
    async def test_fixture_assertion_failure_reflected_in_score(self):
        """When fixture output does NOT match the assertion, score reflects failure."""
        # YAML with fixture that won't match the assertion
        yaml_str = """\
version: "1.0"
souls:
  default_soul:
    id: default_soul
    model: gpt-4o
    system_prompt: "You are a research assistant."
blocks:
  analyze:
    type: llm
    soul: default_soul
    prompt_template: "Analyze: {task_instruction}"
workflow:
  name: test_workflow
  entry: analyze
  transitions:
    - from: analyze
      to: END
eval:
  threshold: 0.8
  cases:
    - id: failing_fixture
      fixtures:
        analyze: "This output mentions nothing about the expected topic."
      expected:
        analyze:
          - type: contains
            value: "quantum computing"
"""
        result = await run_eval(yaml_str)
        case = result.case_results[0]
        assert case.passed is False
        assert case.score == 0.0


# ===========================================================================
# AC3 -- Threshold/pass-fail behavior
# ===========================================================================


class TestEvalRunnerThreshold:
    """AC3: Given aggregate score below eval.threshold, the runner reports overall
    failure with per-case breakdown."""

    @pytest.mark.asyncio
    async def test_above_threshold_passes(self):
        """Aggregate score >= threshold -> result.passed is True."""
        executor = _make_executor_returning(
            {
                "case_1": {"analyze": "LLM research findings"},
                "case_2": {"analyze": "transformer architecture details"},
            }
        )
        result = await run_eval(_TWO_CASE_WORKFLOW_YAML, executor=executor)
        # Both pass -> score=1.0 >= threshold=0.8
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_below_threshold_fails(self):
        """Aggregate score < threshold -> result.passed is False."""
        # One case passes, one fails -> average = 0.5 < threshold 0.8
        executor = _make_executor_returning(
            {
                "case_1": {"analyze": "LLM research findings"},
                "case_2": {"analyze": "unrelated output with no mention"},
            }
        )
        result = await run_eval(_TWO_CASE_WORKFLOW_YAML, executor=executor)
        assert result.passed is False
        assert result.score < 0.8

    @pytest.mark.asyncio
    async def test_per_case_breakdown_available(self):
        """Per-case breakdown is available even when suite fails."""
        executor = _make_executor_returning(
            {
                "case_1": {"analyze": "LLM research findings"},
                "case_2": {"analyze": "unrelated output with no mention"},
            }
        )
        result = await run_eval(_TWO_CASE_WORKFLOW_YAML, executor=executor)
        # case_1 passes (contains "LLM"), case_2 fails (no "transformer")
        case_1 = next(cr for cr in result.case_results if cr.case_id == "case_1")
        case_2 = next(cr for cr in result.case_results if cr.case_id == "case_2")
        assert case_1.passed is True
        assert case_1.score == 1.0
        assert case_2.passed is False
        assert case_2.score == 0.0

    @pytest.mark.asyncio
    async def test_low_threshold_allows_partial_pass(self):
        """A low threshold allows suite to pass even with some failed cases."""
        # threshold=0.3, one case output doesn't contain "hello" -> score=0.0
        # but threshold is low enough for partial score
        executor = _make_executor_returning({"easy_case": {"analyze": "hello world"}})
        result = await run_eval(_LOW_THRESHOLD_YAML, executor=executor)
        assert result.threshold == 0.3
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_exact_threshold_boundary_passes(self):
        """Aggregate score exactly equal to threshold -> result.passed is True."""
        # Build a YAML where threshold == expected aggregate score
        yaml_str = """\
version: "1.0"
souls:
  default_soul:
    id: default_soul
    model: gpt-4o
    system_prompt: "You are a research assistant."
blocks:
  analyze:
    type: llm
    soul: default_soul
    prompt_template: "Analyze: {task_instruction}"
workflow:
  name: test_workflow
  entry: analyze
  transitions:
    - from: analyze
      to: END
eval:
  threshold: 0.5
  cases:
    - id: pass_case
      inputs:
        task_instruction: "Test"
      expected:
        analyze:
          - type: contains
            value: "yes"
    - id: fail_case
      inputs:
        task_instruction: "Test 2"
      expected:
        analyze:
          - type: contains
            value: "no"
"""
        # pass_case passes (score=1.0), fail_case fails (score=0.0)
        # average = 0.5 == threshold=0.5 -> passed=True
        executor = _make_executor_returning(
            {
                "pass_case": {"analyze": "yes indeed"},
                "fail_case": {"analyze": "yes indeed"},
            }
        )
        result = await run_eval(yaml_str, executor=executor)
        assert result.score == 0.5
        assert result.passed is True


# ===========================================================================
# Edge cases
# ===========================================================================


class TestEvalRunnerEdgeCases:
    """Edge cases for the eval runner."""

    @pytest.mark.asyncio
    async def test_no_executor_no_fixtures_raises_error(self):
        """A case without fixtures and no executor provided -> clear error."""
        with pytest.raises((RuntimeError, ValueError)):
            await run_eval(_NO_FIXTURES_NO_EXECUTOR_YAML, executor=None)

    @pytest.mark.asyncio
    async def test_no_executor_kwarg_no_fixtures_raises_error(self):
        """A case without fixtures and executor kwarg omitted -> clear error."""
        with pytest.raises((RuntimeError, ValueError)):
            await run_eval(_NO_FIXTURES_NO_EXECUTOR_YAML)

    @pytest.mark.asyncio
    async def test_multiple_blocks_in_expected(self):
        """Case with assertions on multiple blocks evaluates all of them."""
        result = await run_eval(_TWO_BLOCK_YAML)
        case = result.case_results[0]
        assert "analyze" in case.block_results
        assert "summarize" in case.block_results
        # Both fixture outputs match their assertions
        assert case.passed is True

    @pytest.mark.asyncio
    async def test_case_with_empty_expected(self):
        """A case with expected: {} still appears in results (no assertions to run)."""
        result = await run_eval(_NO_EXPECTED_CASE_YAML)
        assert len(result.case_results) == 1
        case = result.case_results[0]
        assert case.case_id == "no_assertions_case"
        # No assertions -> block_results should be empty dict
        assert case.block_results == {}

    @pytest.mark.asyncio
    async def test_mixed_fixture_and_executor_cases(self):
        """Workflow with both fixture and non-fixture cases: executor called only
        for the non-fixture case."""
        yaml_str = """\
version: "1.0"
souls:
  default_soul:
    id: default_soul
    model: gpt-4o
    system_prompt: "You are a research assistant."
blocks:
  analyze:
    type: llm
    soul: default_soul
    prompt_template: "Analyze: {task_instruction}"
workflow:
  name: test_workflow
  entry: analyze
  transitions:
    - from: analyze
      to: END
eval:
  threshold: 0.5
  cases:
    - id: fixture_case
      fixtures:
        analyze: "LLMs are powerful language models."
      expected:
        analyze:
          - type: contains
            value: "LLM"
    - id: executor_case
      inputs:
        task_instruction: "Research transformers"
      expected:
        analyze:
          - type: contains
            value: "transformer"
"""
        executor = AsyncMock()

        async def _exec_side_effect(workflow, inputs):
            state = WorkflowState()
            state.results["analyze"] = BlockResult(output="transformer model details")
            return state

        executor.side_effect = _exec_side_effect

        result = await run_eval(yaml_str, executor=executor)

        # Executor called only for the non-fixture case
        assert executor.call_count == 1
        assert len(result.case_results) == 2

        # Both cases should pass
        fixture_cr = next(cr for cr in result.case_results if cr.case_id == "fixture_case")
        executor_cr = next(cr for cr in result.case_results if cr.case_id == "executor_case")
        assert fixture_cr.passed is True
        assert executor_cr.passed is True

    @pytest.mark.asyncio
    async def test_eval_case_result_has_expected_fields(self):
        """EvalCaseResult has case_id, passed, score, and block_results fields."""
        result = await run_eval(_FIXTURE_CASE_YAML)
        case = result.case_results[0]
        # Verify all required fields exist and have correct types
        assert isinstance(case.case_id, str)
        assert isinstance(case.passed, bool)
        assert isinstance(case.score, float)
        assert isinstance(case.block_results, dict)

    @pytest.mark.asyncio
    async def test_eval_suite_result_has_expected_fields(self):
        """EvalSuiteResult has passed, score, threshold, and case_results fields."""
        result = await run_eval(_FIXTURE_CASE_YAML)
        assert isinstance(result.passed, bool)
        assert isinstance(result.score, float)
        assert isinstance(result.threshold, float)
        assert isinstance(result.case_results, list)
