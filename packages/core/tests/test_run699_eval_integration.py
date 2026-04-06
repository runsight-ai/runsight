"""Integration tests for RUN-699: Eval harness cross-module wiring.

Verifies that the three RUN-686 epic modules work together end-to-end:
  - RUN-694: EvalSectionDef / EvalCaseDef YAML schema models
  - RUN-695: run_eval(), EvalSuiteResult, EvalCaseResult eval runner
  - RUN-696: _apply_transform() / transform hooks in run_assertion / run_assertions

Scenarios:
  1 — Schema -> Runner pipeline (YAML parse -> run_eval -> structured results)
  2 — SKIPPED (EvalObserver requires apps/api + sqlmodel, unavailable in core env)
  3 — Runner assertion context construction (multi-block, per-block assertion wiring)
  4 — Threshold boundary (0.8 threshold, mixed scores -> passed=False)
  5 — Executor callback integration (with/without executor)
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
import runsight_core.assertions.deterministic  # noqa: F401  — registers all 15 types
from runsight_core.assertions.base import AssertionContext, GradingResult
from runsight_core.assertions.scoring import AssertionsResult
from runsight_core.eval.runner import EvalCaseResult, EvalSuiteResult, run_eval
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.yaml.schema import EvalCaseDef, EvalSectionDef

# ---------------------------------------------------------------------------
# Shared YAML templates
# ---------------------------------------------------------------------------

_SCENARIO_1_YAML = """\
version: "1.0"
souls:
  researcher:
    id: researcher
    model: gpt-4o
    system_prompt: "You are a research assistant."
blocks:
  analyze:
    type: llm
    soul: researcher
    prompt_template: "Analyze: {topic}"
  summarize:
    type: llm
    soul: researcher
    prompt_template: "Summarize the analysis."
workflow:
  name: research_pipeline
  entry: analyze
  transitions:
    - from: analyze
      to: summarize
    - from: summarize
      to: END
eval:
  threshold: 0.8
  cases:
    - id: case_research
      fixtures:
        analyze: "Deep research into LLM architectures and transformer models."
        summarize: "LLMs use transformer architecture for language understanding."
      expected:
        analyze:
          - type: contains
            value: "research"
        summarize:
          - type: contains
            value: "transformer"
    - id: case_summary_quality
      fixtures:
        analyze: "Analysis of neural network training methodologies."
        summarize: "Neural networks require careful training procedures."
      expected:
        analyze:
          - type: contains
            value: "neural"
        summarize:
          - type: contains
            value: "training"
"""

_SCENARIO_3_YAML = """\
version: "1.0"
souls:
  analyst:
    id: analyst
    model: gpt-4o
    system_prompt: "You are an analyst."
blocks:
  analyze:
    type: llm
    soul: analyst
    prompt_template: "Analyze: {topic}"
  summarize:
    type: llm
    soul: analyst
    prompt_template: "Summarize."
workflow:
  name: multi_block_eval
  entry: analyze
  transitions:
    - from: analyze
      to: summarize
    - from: summarize
      to: END
eval:
  threshold: 1.0
  cases:
    - id: multi_block_case
      fixtures:
        analyze: "Thorough research into LLM scaling laws."
        summarize: '{"summary": "LLMs scale well", "confidence": 0.95}'
      expected:
        analyze:
          - type: contains
            value: "research"
        summarize:
          - type: is-json
            value:
"""

_SCENARIO_4_YAML = """\
version: "1.0"
souls:
  default:
    id: default
    model: gpt-4o
    system_prompt: "You are an assistant."
blocks:
  analyze:
    type: llm
    soul: default
    prompt_template: "Analyze: {topic}"
workflow:
  name: threshold_test
  entry: analyze
  transitions:
    - from: analyze
      to: END
eval:
  threshold: 0.8
  cases:
    - id: case_1
      fixtures:
        analyze: "The LLM performed well on this task."
      expected:
        analyze:
          - type: contains
            value: "LLM"
          - type: contains
            value: "performed"
    - id: case_2
      fixtures:
        analyze: "The model showed mixed results overall."
      expected:
        analyze:
          - type: contains
            value: "model"
          - type: contains
            value: "NONEXISTENT_VALUE_FOR_FAILURE"
"""

_SCENARIO_5_NO_FIXTURES_YAML = """\
version: "1.0"
souls:
  default:
    id: default
    model: gpt-4o
    system_prompt: "You are an assistant."
blocks:
  analyze:
    type: llm
    soul: default
    prompt_template: "Analyze: {topic}"
workflow:
  name: executor_test
  entry: analyze
  transitions:
    - from: analyze
      to: END
eval:
  threshold: 0.8
  cases:
    - id: exec_case
      inputs:
        topic: "transformers"
      expected:
        analyze:
          - type: contains
            value: "transformer"
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_context(**overrides) -> AssertionContext:
    """Build a minimal AssertionContext with sensible defaults."""
    defaults = dict(
        output="",
        prompt="",
        prompt_hash="",
        soul_id="",
        soul_version="",
        block_id="block-1",
        block_type="",
        cost_usd=0.0,
        total_tokens=0,
        latency_ms=0.0,
        variables={},
        run_id="",
        workflow_id="",
    )
    defaults.update(overrides)
    return AssertionContext(**defaults)


# ===========================================================================
# Scenario 1 — Schema -> Runner pipeline
# ===========================================================================


class TestScenario1SchemaToRunnerPipeline:
    """Given valid workflow YAML with eval section containing 2 cases with
    fixtures and assertions, when passed to run_eval(), then parses eval
    section, runs both cases, returns EvalSuiteResult with 2 EvalCaseResult
    entries."""

    async def test_yaml_parses_into_eval_schema_models(self):
        """The eval section in the YAML can be parsed by RunsightWorkflowFile
        and produces EvalSectionDef with EvalCaseDef entries."""
        import yaml

        raw = yaml.safe_load(_SCENARIO_1_YAML)
        eval_section = EvalSectionDef.model_validate(raw["eval"])

        assert isinstance(eval_section, EvalSectionDef)
        assert len(eval_section.cases) == 2
        assert eval_section.threshold == 0.8
        for case in eval_section.cases:
            assert isinstance(case, EvalCaseDef)
            assert case.fixtures is not None
            assert case.expected is not None

    async def test_run_eval_returns_suite_with_two_cases(self):
        """run_eval processes 2 fixture-based cases and returns
        EvalSuiteResult with 2 EvalCaseResult entries."""
        result = await run_eval(_SCENARIO_1_YAML)

        assert isinstance(result, EvalSuiteResult)
        assert len(result.case_results) == 2
        for cr in result.case_results:
            assert isinstance(cr, EvalCaseResult)

    async def test_case_ids_match_yaml_definitions(self):
        """Case IDs in the result match those defined in the YAML."""
        result = await run_eval(_SCENARIO_1_YAML)
        case_ids = {cr.case_id for cr in result.case_results}
        assert case_ids == {"case_research", "case_summary_quality"}

    async def test_all_assertions_pass_with_matching_fixtures(self):
        """Both cases pass because fixtures contain the expected values."""
        result = await run_eval(_SCENARIO_1_YAML)

        assert result.passed is True
        assert result.score == 1.0
        for cr in result.case_results:
            assert cr.passed is True
            assert cr.score == 1.0

    async def test_block_results_populated_per_block(self):
        """Each case has block_results keyed by block_id with real
        AssertionsResult from the registry pipeline."""
        result = await run_eval(_SCENARIO_1_YAML)

        for cr in result.case_results:
            assert "analyze" in cr.block_results
            assert "summarize" in cr.block_results
            for block_id, agg in cr.block_results.items():
                assert isinstance(agg, AssertionsResult)
                assert len(agg.results) == 1  # one assertion per block
                assert agg.results[0].passed is True

    async def test_real_contains_assertion_used_not_stub(self):
        """The real ContainsAssertion (case-sensitive) is used, not a stub.
        Verify by checking the reason format in GradingResult — the real
        ContainsAssertion uses 'Output contains ...' while stubs differ."""
        result = await run_eval(_SCENARIO_1_YAML)
        cr = result.case_results[0]
        grading = cr.block_results["analyze"].results[0]
        assert isinstance(grading, GradingResult)
        # Real ContainsAssertion reason includes the check target
        assert "contains" in grading.reason.lower()


# ===========================================================================
# Scenario 2 — SKIPPED (EvalObserver requires apps/api + sqlmodel)
# ===========================================================================

_SKIP_REASON = (
    "Scenario 2 requires apps/api environment (sqlmodel, RunNode, EvalObserver) "
    "which is not available in the core test environment."
)


@pytest.mark.skip(reason=_SKIP_REASON)
class TestScenario2EvalObserverLiveWiring:
    """Placeholder: EvalObserver on_block_complete with transform wiring.

    This scenario requires sqlmodel (RunNode persistence), SSE event emission,
    and apps/api observer imports. Skipped in core package tests.
    """

    async def test_eval_observer_transform_wiring(self):
        pass


# ===========================================================================
# Scenario 3 — Runner assertion context construction
# ===========================================================================


class TestScenario3AssertionContextConstruction:
    """Given workflow YAML with fixtures for 'analyze' and 'summarize',
    assertions: analyze [contains 'research'], summarize [is-json],
    when run_eval() in fixture mode, then AssertionContext built per block
    with correct block_id, assertions run on fixture output, scores
    aggregated correctly."""

    async def test_multi_block_assertions_with_different_types(self):
        """analyze uses 'contains', summarize uses 'is-json' — both pass
        against their fixture outputs using real assertion handlers."""
        result = await run_eval(_SCENARIO_3_YAML)

        assert isinstance(result, EvalSuiteResult)
        assert len(result.case_results) == 1

        cr = result.case_results[0]
        assert cr.case_id == "multi_block_case"
        assert "analyze" in cr.block_results
        assert "summarize" in cr.block_results

    async def test_contains_assertion_on_analyze_block(self):
        """The 'contains' assertion on analyze evaluates against the
        fixture text and passes."""
        result = await run_eval(_SCENARIO_3_YAML)
        cr = result.case_results[0]

        analyze_result = cr.block_results["analyze"]
        assert len(analyze_result.results) == 1
        assert analyze_result.results[0].passed is True
        assert "contains" in analyze_result.results[0].reason.lower()

    async def test_is_json_assertion_on_summarize_block(self):
        """The 'is-json' assertion on summarize evaluates the JSON fixture
        and passes."""
        result = await run_eval(_SCENARIO_3_YAML)
        cr = result.case_results[0]

        summarize_result = cr.block_results["summarize"]
        assert len(summarize_result.results) == 1
        assert summarize_result.results[0].passed is True
        assert "valid JSON" in summarize_result.results[0].reason

    async def test_scores_aggregated_across_blocks(self):
        """Both blocks pass -> case score = 1.0, suite score = 1.0."""
        result = await run_eval(_SCENARIO_3_YAML)
        cr = result.case_results[0]

        assert cr.score == 1.0
        assert cr.passed is True
        assert result.score == 1.0
        assert result.passed is True

    async def test_is_json_fails_on_non_json_fixture(self):
        """When the fixture for summarize is NOT valid JSON, the is-json
        assertion fails and the case score reflects it."""
        yaml_str = """\
version: "1.0"
souls:
  analyst:
    id: analyst
    model: gpt-4o
    system_prompt: "You are an analyst."
blocks:
  summarize:
    type: llm
    soul: analyst
    prompt_template: "Summarize."
workflow:
  name: json_fail_test
  entry: summarize
  transitions:
    - from: summarize
      to: END
eval:
  threshold: 1.0
  cases:
    - id: bad_json_case
      fixtures:
        summarize: "This is plain text, not JSON at all."
      expected:
        summarize:
          - type: is-json
            value:
"""
        result = await run_eval(yaml_str)
        cr = result.case_results[0]

        assert cr.passed is False
        assert cr.score == 0.0
        assert result.passed is False


# ===========================================================================
# Scenario 3b — Transform hooks wired through run_eval pipeline
# ===========================================================================


class TestScenario3bTransformInEvalPipeline:
    """Verify that transform hooks (RUN-696) work when wired through
    the eval runner (RUN-695), exercising the full cross-module path:
    YAML -> run_eval -> run_assertions -> _apply_transform -> assertion."""

    async def test_json_path_transform_in_eval_case(self):
        """An eval case with transform: 'json_path:$.result' extracts
        the field before running the assertion."""
        yaml_str = """\
version: "1.0"
souls:
  default:
    id: default
    model: gpt-4o
    system_prompt: "Assistant."
blocks:
  analyze:
    type: llm
    soul: default
    prompt_template: "Analyze."
workflow:
  name: transform_eval_test
  entry: analyze
  transitions:
    - from: analyze
      to: END
eval:
  threshold: 1.0
  cases:
    - id: transform_case
      fixtures:
        analyze: '{"result": "success", "extra": "data"}'
      expected:
        analyze:
          - type: equals
            value: "success"
            transform: "json_path:$.result"
"""
        result = await run_eval(yaml_str)

        assert result.passed is True
        cr = result.case_results[0]
        assert cr.passed is True
        assert cr.score == 1.0
        # The assertion evaluated against "success", not the full JSON blob
        grading = cr.block_results["analyze"].results[0]
        assert grading.passed is True

    async def test_json_path_transform_extraction_rejects_wrong_field(self):
        """Transform extracts $.result so assertion only sees 'success',
        not 'data' from $.extra — a contains check on 'data' should fail."""
        yaml_str = """\
version: "1.0"
souls:
  default:
    id: default
    model: gpt-4o
    system_prompt: "Assistant."
blocks:
  analyze:
    type: llm
    soul: default
    prompt_template: "Analyze."
workflow:
  name: transform_reject_test
  entry: analyze
  transitions:
    - from: analyze
      to: END
eval:
  threshold: 1.0
  cases:
    - id: reject_case
      fixtures:
        analyze: '{"result": "success", "extra": "secret data"}'
      expected:
        analyze:
          - type: contains
            value: "secret data"
            transform: "json_path:$.result"
"""
        result = await run_eval(yaml_str)

        assert result.passed is False
        cr = result.case_results[0]
        assert cr.passed is False

    async def test_mixed_transform_and_plain_assertions_in_eval(self):
        """A single block with both a transform assertion and a plain
        assertion — both should evaluate correctly."""
        yaml_str = """\
version: "1.0"
souls:
  default:
    id: default
    model: gpt-4o
    system_prompt: "Assistant."
blocks:
  analyze:
    type: llm
    soul: default
    prompt_template: "Analyze."
workflow:
  name: mixed_transform_test
  entry: analyze
  transitions:
    - from: analyze
      to: END
eval:
  threshold: 1.0
  cases:
    - id: mixed_case
      fixtures:
        analyze: '{"result": "success", "extra": "data"}'
      expected:
        analyze:
          - type: equals
            value: "success"
            transform: "json_path:$.result"
          - type: is-json
            value:
"""
        result = await run_eval(yaml_str)

        assert result.passed is True
        cr = result.case_results[0]
        assert cr.passed is True
        assert len(cr.block_results["analyze"].results) == 2
        assert all(g.passed for g in cr.block_results["analyze"].results)


# ===========================================================================
# Scenario 4 — Threshold boundary
# ===========================================================================


class TestScenario4ThresholdBoundary:
    """Given threshold 0.8, case_1 scores 1.0, case_2 scores 0.5,
    when run_eval() completes, then score is 0.75, passed is False."""

    async def test_mixed_scores_below_threshold_fails(self):
        """case_1: both assertions pass (1.0), case_2: one passes one fails
        (0.5). Average = 0.75 < 0.8 threshold -> suite fails."""
        result = await run_eval(_SCENARIO_4_YAML)

        assert isinstance(result, EvalSuiteResult)
        assert result.threshold == 0.8

        case_1 = next(cr for cr in result.case_results if cr.case_id == "case_1")
        case_2 = next(cr for cr in result.case_results if cr.case_id == "case_2")

        assert case_1.score == 1.0
        assert case_1.passed is True

        assert case_2.score == 0.5
        assert case_2.passed is False

        assert result.score == 0.75
        assert result.passed is False

    async def test_exact_threshold_boundary_passes(self):
        """Score exactly equal to threshold -> passed is True."""
        yaml_str = """\
version: "1.0"
souls:
  default:
    id: default
    model: gpt-4o
    system_prompt: "Assistant."
blocks:
  analyze:
    type: llm
    soul: default
    prompt_template: "Analyze."
workflow:
  name: boundary_test
  entry: analyze
  transitions:
    - from: analyze
      to: END
eval:
  threshold: 0.5
  cases:
    - id: pass_case
      fixtures:
        analyze: "The LLM is great."
      expected:
        analyze:
          - type: contains
            value: "LLM"
    - id: fail_case
      fixtures:
        analyze: "Something completely unrelated."
      expected:
        analyze:
          - type: contains
            value: "XYZNONEXISTENT"
"""
        result = await run_eval(yaml_str)

        assert result.score == 0.5
        assert result.threshold == 0.5
        assert result.passed is True

    async def test_all_cases_fail_zero_score(self):
        """When all cases fail, score is 0.0 and suite fails."""
        yaml_str = """\
version: "1.0"
souls:
  default:
    id: default
    model: gpt-4o
    system_prompt: "Assistant."
blocks:
  analyze:
    type: llm
    soul: default
    prompt_template: "Analyze."
workflow:
  name: all_fail_test
  entry: analyze
  transitions:
    - from: analyze
      to: END
eval:
  threshold: 0.1
  cases:
    - id: fail_a
      fixtures:
        analyze: "No match here."
      expected:
        analyze:
          - type: contains
            value: "XYZNONEXISTENT"
    - id: fail_b
      fixtures:
        analyze: "Also no match."
      expected:
        analyze:
          - type: contains
            value: "ABCNONEXISTENT"
"""
        result = await run_eval(yaml_str)

        assert result.score == 0.0
        assert result.passed is False


# ===========================================================================
# Scenario 5 — Executor callback integration
# ===========================================================================


class TestScenario5ExecutorCallbackIntegration:
    """Given eval case with NO fixtures and executor callback,
    when run_eval() called with executor -> executor called, assertions run.
    When run_eval() called WITHOUT executor -> raises error."""

    async def test_executor_called_and_assertions_run(self):
        """Executor provides WorkflowState, assertions run against its output."""

        async def mock_executor(workflow, inputs):
            state = WorkflowState()
            state.results["analyze"] = BlockResult(
                output="The transformer architecture is powerful."
            )
            return state

        result = await run_eval(_SCENARIO_5_NO_FIXTURES_YAML, executor=mock_executor)

        assert isinstance(result, EvalSuiteResult)
        assert len(result.case_results) == 1
        cr = result.case_results[0]
        assert cr.case_id == "exec_case"
        assert cr.passed is True
        assert cr.score == 1.0

    async def test_executor_called_once_per_case(self):
        """Executor is called exactly once for the single case."""
        executor = AsyncMock()

        async def _side_effect(workflow, inputs):
            state = WorkflowState()
            state.results["analyze"] = BlockResult(output="transformer details")
            return state

        executor.side_effect = _side_effect

        await run_eval(_SCENARIO_5_NO_FIXTURES_YAML, executor=executor)
        assert executor.call_count == 1

    async def test_no_executor_raises_error(self):
        """No fixtures + no executor -> RuntimeError."""
        with pytest.raises(RuntimeError, match="requires an executor"):
            await run_eval(_SCENARIO_5_NO_FIXTURES_YAML, executor=None)

    async def test_no_executor_kwarg_raises_error(self):
        """No fixtures + executor kwarg omitted -> RuntimeError."""
        with pytest.raises(RuntimeError, match="requires an executor"):
            await run_eval(_SCENARIO_5_NO_FIXTURES_YAML)

    async def test_executor_receives_inputs_from_yaml(self):
        """Executor receives the inputs dict from the YAML case definition."""
        received_inputs = []

        async def tracking_executor(workflow, inputs):
            received_inputs.append(inputs)
            state = WorkflowState()
            state.results["analyze"] = BlockResult(output="transformer output")
            return state

        await run_eval(_SCENARIO_5_NO_FIXTURES_YAML, executor=tracking_executor)

        assert len(received_inputs) == 1
        assert received_inputs[0] == {"topic": "transformers"}

    async def test_executor_multi_case_called_per_case(self):
        """With multiple no-fixture cases, executor is called once per case."""
        yaml_str = """\
version: "1.0"
souls:
  default:
    id: default
    model: gpt-4o
    system_prompt: "Assistant."
blocks:
  analyze:
    type: llm
    soul: default
    prompt_template: "Analyze: {topic}"
workflow:
  name: multi_exec_test
  entry: analyze
  transitions:
    - from: analyze
      to: END
eval:
  threshold: 0.5
  cases:
    - id: exec_a
      inputs:
        topic: "LLMs"
      expected:
        analyze:
          - type: contains
            value: "LLM"
    - id: exec_b
      inputs:
        topic: "transformers"
      expected:
        analyze:
          - type: contains
            value: "transformer"
"""
        call_count = {"n": 0}
        outputs = ["LLM scaling laws", "transformer architecture"]

        async def counting_executor(workflow, inputs):
            idx = call_count["n"]
            call_count["n"] += 1
            state = WorkflowState()
            state.results["analyze"] = BlockResult(output=outputs[idx])
            return state

        result = await run_eval(yaml_str, executor=counting_executor)

        assert call_count["n"] == 2
        assert len(result.case_results) == 2
        assert result.passed is True

    async def test_mixed_fixture_and_executor_cases(self):
        """A workflow with one fixture case and one executor case: executor
        is called only for the non-fixture case."""
        yaml_str = """\
version: "1.0"
souls:
  default:
    id: default
    model: gpt-4o
    system_prompt: "Assistant."
blocks:
  analyze:
    type: llm
    soul: default
    prompt_template: "Analyze."
workflow:
  name: mixed_test
  entry: analyze
  transitions:
    - from: analyze
      to: END
eval:
  threshold: 0.8
  cases:
    - id: fixture_case
      fixtures:
        analyze: "The LLM results are promising."
      expected:
        analyze:
          - type: contains
            value: "LLM"
    - id: executor_case
      inputs:
        topic: "transformers"
      expected:
        analyze:
          - type: contains
            value: "transformer"
"""
        executor = AsyncMock()

        async def _side_effect(workflow, inputs):
            state = WorkflowState()
            state.results["analyze"] = BlockResult(output="transformer results")
            return state

        executor.side_effect = _side_effect

        result = await run_eval(yaml_str, executor=executor)

        # Executor called only for the non-fixture case
        assert executor.call_count == 1
        assert len(result.case_results) == 2

        fixture_cr = next(cr for cr in result.case_results if cr.case_id == "fixture_case")
        executor_cr = next(cr for cr in result.case_results if cr.case_id == "executor_case")
        assert fixture_cr.passed is True
        assert executor_cr.passed is True
        assert result.passed is True
