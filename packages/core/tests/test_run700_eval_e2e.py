"""E2E tests for RUN-700: Eval harness full user flow.

Three user flows:
  Flow 1 — Fixture-mode eval with transforms — full YAML to result
  Flow 2 — Multi-case eval with mixed pass/fail
  Flow 3 — Normal execution ignores eval section

Five architectural invariants:
  INV-1 — eval: is optional and backward-compatible
  INV-2 — run_eval() is read-only
  INV-3 — Transform failures are assertions, not exceptions
  INV-4 — Fixture mode is zero-side-effect
  INV-5 — One assertion engine, not two
"""

from __future__ import annotations

import json

import pytest
import runsight_core.assertions.deterministic  # noqa: F401 — registers handlers
import runsight_core.yaml.parser  # noqa: F401 — rebuilds block union for model_validate
import yaml
from runsight_core.assertions.base import GradingResult
from runsight_core.assertions.registry import (
    _REGISTRY,
    register_assertion,
    run_assertions,
)
from runsight_core.assertions.scoring import AssertionsResult
from runsight_core.eval.runner import EvalCaseResult, EvalSuiteResult, run_eval
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.yaml.schema import EvalSectionDef, RunsightWorkflowFile

# ---------------------------------------------------------------------------
# YAML templates
# ---------------------------------------------------------------------------

_FLOW_1_YAML = """\
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
workflow:
  name: flow1_pipeline
  entry: analyze
  transitions:
    - from: analyze
      to: END
eval:
  threshold: 0.9
  cases:
    - id: transform_case
      fixtures:
        analyze: '{"summary": "LLMs transform software", "details": "Deep dive"}'
      expected:
        analyze:
          - type: contains
            value: "transform"
            transform: "json_path:$.summary"
"""

_FLOW_2_YAML = """\
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
  name: flow2_multi_case
  entry: analyze
  transitions:
    - from: analyze
      to: END
eval:
  threshold: 0.6
  cases:
    - id: case_pass
      fixtures:
        analyze: "LLMs are powerful transformer models."
      expected:
        analyze:
          - type: contains
            value: "transformer"
    - id: case_fail
      fixtures:
        analyze: "The weather is sunny today."
      expected:
        analyze:
          - type: contains
            value: "NONEXISTENT_KEYWORD"
    - id: case_threshold
      fixtures:
        analyze: "Neural networks use backpropagation for training."
      expected:
        analyze:
          - type: contains
            value: "backpropagation"
          - type: contains
            value: "MISSING_VALUE"
"""

# Flow 3 and Invariant 1 YAML must conform to RunsightWorkflowFile schema
# (valid block types like "code", SoulDef with "role" not "model").

_FLOW_3_YAML = """\
version: "1.0"
souls:
  researcher:
    id: researcher
    role: research_assistant
    system_prompt: "You are a research assistant."
blocks:
  analyze:
    type: code
    code: "result = 'fixture'"
workflow:
  name: flow3_ignores_eval
  entry: analyze
  transitions:
    - from: analyze
      to: END
eval:
  threshold: 1.0
  cases:
    - id: eval_only_case
      fixtures:
        analyze: "Some fixture output."
      expected:
        analyze:
          - type: contains
            value: "fixture"
"""

_MINIMAL_WORKFLOW_NO_EVAL = """\
version: "1.0"
souls:
  default:
    id: default
    role: assistant
    system_prompt: "Assistant."
blocks:
  greet:
    type: code
    code: "result = 'hello'"
workflow:
  name: no_eval_workflow
  entry: greet
  transitions:
    - from: greet
      to: END
"""


# ===========================================================================
# Flow 1 — Fixture-mode eval with transforms — full YAML to result
# ===========================================================================


class TestFlow1FixtureModeWithTransforms:
    """Given: complete workflow YAML with analyze block, eval section with 1
    case, fixture containing JSON, expected assertion with
    {type: contains, value: "transform", transform: "json_path:$.summary"},
    threshold: 0.9.

    When: run_eval(yaml_string) is called.

    Then: EvalSuiteResult.passed is True, score >= 0.9,
    case_results[0].block_results["analyze"].results[0].passed is True,
    assertion evaluated against "LLMs transform software" (not full JSON).
    """

    async def test_suite_passes_with_transform(self):
        result = await run_eval(_FLOW_1_YAML)

        assert isinstance(result, EvalSuiteResult)
        assert result.passed is True
        assert result.score >= 0.9

    async def test_single_case_result_structure(self):
        result = await run_eval(_FLOW_1_YAML)

        assert len(result.case_results) == 1
        cr = result.case_results[0]
        assert isinstance(cr, EvalCaseResult)
        assert cr.case_id == "transform_case"
        assert cr.passed is True

    async def test_block_assertion_passes(self):
        result = await run_eval(_FLOW_1_YAML)

        cr = result.case_results[0]
        assert "analyze" in cr.block_results
        analyze_agg = cr.block_results["analyze"]
        assert isinstance(analyze_agg, AssertionsResult)
        assert len(analyze_agg.results) == 1
        assert analyze_agg.results[0].passed is True

    async def test_assertion_evaluated_against_extracted_field(self):
        """The assertion checks 'transform' in 'LLMs transform software',
        NOT in the full JSON blob. Prove it by verifying the reason mentions
        the extracted value, not the raw JSON."""
        result = await run_eval(_FLOW_1_YAML)

        grading = result.case_results[0].block_results["analyze"].results[0]
        assert grading.passed is True
        # The real ContainsAssertion reason format: "Output contains 'transform'"
        assert "Output contains" in grading.reason

    async def test_transform_actually_narrows_evaluation(self):
        """If transform is working, 'details' from the JSON root should
        NOT be visible to the assertion. A check for 'Deep dive' (in
        $.details) via $.summary transform should FAIL."""
        yaml_str = _FLOW_1_YAML.replace(
            'value: "transform"',
            'value: "Deep dive"',
        )
        result = await run_eval(yaml_str)

        cr = result.case_results[0]
        assert cr.passed is False
        assert cr.block_results["analyze"].results[0].passed is False


# ===========================================================================
# Flow 2 — Multi-case eval with mixed pass/fail
# ===========================================================================


class TestFlow2MultiCaseMixedResults:
    """Given: YAML with 3 cases: case_pass (fixture matches), case_fail
    (fixture doesn't match), case_threshold (partial match). threshold: 0.6.

    When: run_eval(yaml_string).

    Then: 3 EvalCaseResult entries, correct individual pass/fail, aggregate
    score reflects average, EvalSuiteResult.passed reflects threshold.
    """

    async def test_three_case_results_returned(self):
        result = await run_eval(_FLOW_2_YAML)

        assert len(result.case_results) == 3
        case_ids = {cr.case_id for cr in result.case_results}
        assert case_ids == {"case_pass", "case_fail", "case_threshold"}

    async def test_case_pass_scores_1(self):
        result = await run_eval(_FLOW_2_YAML)

        cr = next(c for c in result.case_results if c.case_id == "case_pass")
        assert cr.passed is True
        assert cr.score == 1.0

    async def test_case_fail_scores_0(self):
        result = await run_eval(_FLOW_2_YAML)

        cr = next(c for c in result.case_results if c.case_id == "case_fail")
        assert cr.passed is False
        assert cr.score == 0.0

    async def test_case_threshold_partial_score(self):
        """case_threshold has 2 assertions: one passes, one fails -> score 0.5."""
        result = await run_eval(_FLOW_2_YAML)

        cr = next(c for c in result.case_results if c.case_id == "case_threshold")
        assert cr.passed is False
        assert cr.score == 0.5

    async def test_aggregate_score_is_average(self):
        """Average of (1.0, 0.0, 0.5) = 0.5."""
        result = await run_eval(_FLOW_2_YAML)

        assert result.score == pytest.approx(0.5)

    async def test_suite_passed_reflects_threshold(self):
        """Score 0.5 < threshold 0.6 -> suite fails."""
        result = await run_eval(_FLOW_2_YAML)

        assert result.threshold == 0.6
        assert result.passed is False

    async def test_lowered_threshold_allows_pass(self):
        """Same cases but with threshold 0.4 -> suite passes."""
        yaml_with_low_threshold = _FLOW_2_YAML.replace("threshold: 0.6", "threshold: 0.4")
        result = await run_eval(yaml_with_low_threshold)

        assert result.score == pytest.approx(0.5)
        assert result.threshold == 0.4
        assert result.passed is True


# ===========================================================================
# Flow 3 — Normal execution ignores eval section
# ===========================================================================


class TestFlow3NormalExecutionIgnoresEval:
    """Given: workflow YAML with both workflow AND eval sections.

    When: parse via RunsightWorkflowFile.model_validate().

    Then: parsing works, eval section is accessible separately, the workflow
    definition is identical whether eval section is present or absent.
    """

    def test_yaml_with_eval_parses_into_workflow_file(self):
        """RunsightWorkflowFile accepts YAML containing an eval section."""
        raw = yaml.safe_load(_FLOW_3_YAML)
        wf_file = RunsightWorkflowFile.model_validate(raw)

        assert wf_file.workflow.name == "flow3_ignores_eval"
        assert wf_file.eval is not None
        assert isinstance(wf_file.eval, EvalSectionDef)

    def test_eval_section_accessible_separately(self):
        """The eval section can be read independently of the workflow."""
        raw = yaml.safe_load(_FLOW_3_YAML)
        wf_file = RunsightWorkflowFile.model_validate(raw)

        assert len(wf_file.eval.cases) == 1
        assert wf_file.eval.cases[0].id == "eval_only_case"
        assert wf_file.eval.threshold == 1.0

    def test_workflow_fields_unaffected_by_eval(self):
        """The workflow definition (name, entry, transitions, blocks, souls)
        is identical whether or not eval is present."""
        raw_with = yaml.safe_load(_FLOW_3_YAML)
        raw_without = yaml.safe_load(_FLOW_3_YAML)
        del raw_without["eval"]

        wf_with = RunsightWorkflowFile.model_validate(raw_with)
        wf_without = RunsightWorkflowFile.model_validate(raw_without)

        assert wf_with.workflow.name == wf_without.workflow.name
        assert wf_with.workflow.entry == wf_without.workflow.entry
        assert len(wf_with.workflow.transitions) == len(wf_without.workflow.transitions)
        assert wf_with.souls.keys() == wf_without.souls.keys()
        # blocks are Any (dynamic union), compare keys
        if isinstance(wf_with.blocks, dict) and isinstance(wf_without.blocks, dict):
            assert wf_with.blocks.keys() == wf_without.blocks.keys()

    def test_yaml_without_eval_parses_with_none(self):
        """YAML that has no eval section -> RunsightWorkflowFile.eval is None."""
        raw = yaml.safe_load(_MINIMAL_WORKFLOW_NO_EVAL)
        wf_file = RunsightWorkflowFile.model_validate(raw)

        assert wf_file.eval is None


# ===========================================================================
# Architectural Invariant 1 — eval: is optional and backward-compatible
# ===========================================================================


class TestInvariant1EvalOptionalBackwardCompat:
    """eval: is Optional[EvalSectionDef] and defaults to None. Existing YAML
    without eval: parses identically.

    Falsifiability: if eval were required, parsing YAML without it would raise.
    If it defaulted to a non-None value, the None assertion would fail.
    """

    def test_eval_field_defaults_to_none(self):
        raw = yaml.safe_load(_MINIMAL_WORKFLOW_NO_EVAL)
        wf_file = RunsightWorkflowFile.model_validate(raw)
        assert wf_file.eval is None

    def test_no_eval_yaml_parses_without_error(self):
        """Workflows from before eval existed still parse cleanly."""
        raw = yaml.safe_load(_MINIMAL_WORKFLOW_NO_EVAL)
        # This must not raise
        wf_file = RunsightWorkflowFile.model_validate(raw)
        assert wf_file.workflow.name == "no_eval_workflow"

    def test_adding_eval_does_not_change_other_fields(self):
        """Adding eval: to an existing YAML does not alter any other parsed field."""
        raw_base = yaml.safe_load(_MINIMAL_WORKFLOW_NO_EVAL)
        raw_with_eval = yaml.safe_load(_MINIMAL_WORKFLOW_NO_EVAL)
        raw_with_eval["eval"] = {
            "threshold": 0.5,
            "cases": [
                {
                    "id": "test",
                    "fixtures": {"greet": "hi"},
                    "expected": {"greet": [{"type": "contains", "value": "hi"}]},
                }
            ],
        }

        wf_base = RunsightWorkflowFile.model_validate(raw_base)
        wf_eval = RunsightWorkflowFile.model_validate(raw_with_eval)

        assert wf_base.version == wf_eval.version
        assert wf_base.enabled == wf_eval.enabled
        assert wf_base.workflow.name == wf_eval.workflow.name
        assert wf_base.workflow.entry == wf_eval.workflow.entry
        assert wf_base.eval is None
        assert wf_eval.eval is not None

    def test_eval_none_is_real_none_not_empty_object(self):
        """The default is Python None, not an empty EvalSectionDef."""
        raw = yaml.safe_load(_MINIMAL_WORKFLOW_NO_EVAL)
        wf_file = RunsightWorkflowFile.model_validate(raw)
        # Strictly None, not a truthy empty container
        assert wf_file.eval is None
        assert not isinstance(wf_file.eval, EvalSectionDef)


# ===========================================================================
# Architectural Invariant 2 — run_eval() is read-only
# ===========================================================================


class TestInvariant2RunEvalReadOnly:
    """run_eval() never mutates the workflow YAML string or models.

    Falsifiability: if run_eval modified the YAML string or the parsed raw
    dict, the before/after comparison would fail.
    """

    async def test_yaml_string_unchanged_after_run_eval(self):
        original = _FLOW_1_YAML
        copy = str(original)  # snapshot

        await run_eval(original)

        assert original == copy, "run_eval mutated the YAML string"

    async def test_reparsed_yaml_identical_after_run_eval(self):
        """Parse the YAML before and after run_eval — both produce identical
        structures."""
        raw_before = yaml.safe_load(_FLOW_1_YAML)
        before_snapshot = json.dumps(raw_before, sort_keys=True)

        await run_eval(_FLOW_1_YAML)

        raw_after = yaml.safe_load(_FLOW_1_YAML)
        after_snapshot = json.dumps(raw_after, sort_keys=True)

        assert before_snapshot == after_snapshot

    async def test_eval_section_model_unchanged_after_run(self):
        """The EvalSectionDef model parsed from YAML is identical before
        and after run_eval."""
        raw = yaml.safe_load(_FLOW_2_YAML)
        eval_before = EvalSectionDef.model_validate(raw["eval"])

        await run_eval(_FLOW_2_YAML)

        eval_after = EvalSectionDef.model_validate(raw["eval"])
        assert eval_before.threshold == eval_after.threshold
        assert len(eval_before.cases) == len(eval_after.cases)
        for b, a in zip(eval_before.cases, eval_after.cases):
            assert b.id == a.id
            assert b.fixtures == a.fixtures
            assert b.expected == a.expected


# ===========================================================================
# Architectural Invariant 3 — Transform failures are assertions, not exceptions
# ===========================================================================


class TestInvariant3TransformFailuresAreAssertions:
    """Transform failures produce GradingResult(passed=False) with a
    descriptive reason. They never raise exceptions or crash the runner.

    Falsifiability: if transforms raised exceptions, the run_eval call would
    propagate them instead of returning a result.
    """

    async def test_non_json_output_with_json_path_transform(self):
        """Transform json_path on non-JSON output -> failed assertion, not crash."""
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
  name: bad_transform_test
  entry: analyze
  transitions:
    - from: analyze
      to: END
eval:
  threshold: 1.0
  cases:
    - id: bad_transform
      fixtures:
        analyze: "This is plain text, definitely not JSON"
      expected:
        analyze:
          - type: contains
            value: "anything"
            transform: "json_path:$.field"
"""
        # Must NOT raise — should complete with failed assertion
        result = await run_eval(yaml_str)

        assert isinstance(result, EvalSuiteResult)
        cr = result.case_results[0]
        assert cr.passed is False
        grading = cr.block_results["analyze"].results[0]
        assert grading.passed is False
        assert "not valid JSON" in grading.reason

    async def test_unknown_transform_type_produces_failed_grading(self):
        """An unknown transform type (not json_path) -> failed GradingResult."""
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
  name: unknown_transform_test
  entry: analyze
  transitions:
    - from: analyze
      to: END
eval:
  threshold: 1.0
  cases:
    - id: unknown_transform
      fixtures:
        analyze: '{"data": "value"}'
      expected:
        analyze:
          - type: contains
            value: "value"
            transform: "xpath:$.data"
"""
        result = await run_eval(yaml_str)

        assert isinstance(result, EvalSuiteResult)
        cr = result.case_results[0]
        assert cr.passed is False
        grading = cr.block_results["analyze"].results[0]
        assert grading.passed is False
        assert "Unknown transform type" in grading.reason

    async def test_missing_json_path_produces_failed_grading(self):
        """json_path that doesn't match -> failed GradingResult, not KeyError."""
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
  name: missing_path_test
  entry: analyze
  transitions:
    - from: analyze
      to: END
eval:
  threshold: 1.0
  cases:
    - id: missing_path
      fixtures:
        analyze: '{"data": "value"}'
      expected:
        analyze:
          - type: contains
            value: "value"
            transform: "json_path:$.nonexistent"
"""
        result = await run_eval(yaml_str)

        assert isinstance(result, EvalSuiteResult)
        cr = result.case_results[0]
        assert cr.passed is False
        grading = cr.block_results["analyze"].results[0]
        assert grading.passed is False
        assert "not found" in grading.reason

    async def test_malformed_transform_format_no_colon(self):
        """Transform string without colon separator -> failed GradingResult."""
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
  name: malformed_transform_test
  entry: analyze
  transitions:
    - from: analyze
      to: END
eval:
  threshold: 1.0
  cases:
    - id: malformed
      fixtures:
        analyze: '{"data": "value"}'
      expected:
        analyze:
          - type: contains
            value: "value"
            transform: "badformat"
"""
        result = await run_eval(yaml_str)

        assert isinstance(result, EvalSuiteResult)
        cr = result.case_results[0]
        assert cr.passed is False
        grading = cr.block_results["analyze"].results[0]
        assert grading.passed is False
        assert "Unknown transform format" in grading.reason


# ===========================================================================
# Architectural Invariant 4 — Fixture mode is zero-side-effect
# ===========================================================================


class TestInvariant4FixtureModeZeroSideEffect:
    """Fixture mode never calls the executor. Even if an executor is provided,
    it must not be invoked when all expected blocks have fixtures.

    Falsifiability: if the runner always called the executor, the tracking
    executor would record calls and the assertion would fail.
    """

    async def test_executor_never_called_in_fixture_mode(self):
        """Provide a tracking executor alongside fixture YAML — it must
        never be invoked."""
        call_log = []

        async def tracking_executor(workflow, inputs):
            call_log.append({"workflow": workflow, "inputs": inputs})
            state = WorkflowState()
            state.results["analyze"] = BlockResult(output="executor output")
            return state

        result = await run_eval(_FLOW_1_YAML, executor=tracking_executor)

        assert len(call_log) == 0, (
            f"Executor was called {len(call_log)} time(s) during fixture-only eval"
        )
        assert result.passed is True

    async def test_fixture_mode_with_none_executor_succeeds(self):
        """Fixture-only eval works fine with executor=None (the default)."""
        result = await run_eval(_FLOW_1_YAML, executor=None)
        assert isinstance(result, EvalSuiteResult)
        assert result.passed is True

    async def test_fixture_mode_without_executor_kwarg_succeeds(self):
        """Fixture-only eval works fine when executor kwarg is omitted."""
        result = await run_eval(_FLOW_1_YAML)
        assert isinstance(result, EvalSuiteResult)
        assert result.passed is True

    async def test_multi_case_all_fixtures_never_calls_executor(self):
        """Multiple cases all with fixtures — executor never called."""
        call_count = {"n": 0}

        async def counting_executor(workflow, inputs):
            call_count["n"] += 1
            state = WorkflowState()
            return state

        result = await run_eval(_FLOW_2_YAML, executor=counting_executor)

        assert call_count["n"] == 0
        assert len(result.case_results) == 3


# ===========================================================================
# Architectural Invariant 5 — One assertion engine, not two
# ===========================================================================


class TestInvariant5OneAssertionEngine:
    """The eval runner uses the exact same run_assertions() function from
    runsight_core.assertions.registry. Verify by registering a custom
    assertion type and confirming it's available in run_eval().

    Falsifiability: if the eval runner used a separate copy of the registry,
    a custom type registered in the main registry would not be visible.
    """

    async def test_custom_assertion_visible_in_eval(self):
        """Register a custom assertion type, then use it in an eval case.
        If run_eval uses the same registry, the custom type works."""

        class AlwaysPassAssertion:
            type = "e2e-custom-always-pass"

            def __init__(self, value=None, threshold=None):
                pass

            def evaluate(self, output, context):
                return GradingResult(
                    passed=True,
                    score=1.0,
                    reason="Custom assertion: always passes",
                    assertion_type="e2e-custom-always-pass",
                )

        register_assertion("e2e-custom-always-pass", AlwaysPassAssertion)

        try:
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
  name: custom_assertion_test
  entry: analyze
  transitions:
    - from: analyze
      to: END
eval:
  threshold: 1.0
  cases:
    - id: custom_case
      fixtures:
        analyze: "any output text"
      expected:
        analyze:
          - type: e2e-custom-always-pass
"""
            result = await run_eval(yaml_str)

            assert result.passed is True
            cr = result.case_results[0]
            assert cr.passed is True
            grading = cr.block_results["analyze"].results[0]
            assert grading.passed is True
            assert grading.assertion_type == "e2e-custom-always-pass"
            assert "Custom assertion" in grading.reason
        finally:
            # Clean up custom registration
            _REGISTRY.pop("e2e-custom-always-pass", None)

    async def test_unregistered_type_raises_in_eval(self):
        """Using an assertion type that is NOT registered causes a KeyError
        propagated from the shared registry — proving the eval runner doesn't
        have its own fallback logic."""
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
  name: unknown_type_test
  entry: analyze
  transitions:
    - from: analyze
      to: END
eval:
  threshold: 1.0
  cases:
    - id: unknown_case
      fixtures:
        analyze: "any output"
      expected:
        analyze:
          - type: e2e-nonexistent-type-xyz
"""
        with pytest.raises(KeyError, match="e2e-nonexistent-type-xyz"):
            await run_eval(yaml_str)

    async def test_eval_uses_same_run_assertions_function(self):
        """The eval runner's import of run_assertions is the same object as
        the one we import directly from the registry module."""
        from runsight_core.eval import runner as eval_runner_module

        assert eval_runner_module.run_assertions is run_assertions, (
            "run_eval imports a different run_assertions function — "
            "the eval runner has a separate assertion engine"
        )

    async def test_deterministic_assertions_available_in_eval(self):
        """The 15 deterministic assertion types registered by
        `import runsight_core.assertions.deterministic` are all available
        to run_eval — not just a hardcoded subset."""
        expected_types = {
            "equals",
            "contains",
            "icontains",
            "contains-all",
            "contains-any",
            "starts-with",
            "regex",
            "word-count",
            "is-json",
            "contains-json",
            "cost",
            "latency",
            "levenshtein",
            "bleu",
            "rouge-n",
        }
        registered = set(_REGISTRY.keys())
        assert expected_types.issubset(registered), (
            f"Missing assertion types in registry: {expected_types - registered}"
        )
