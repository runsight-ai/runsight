"""Fixture-mode eval runner transforms, scoring, and executor isolation."""

from __future__ import annotations

import pytest
import runsight_core.assertions.deterministic  # noqa: F401
from eval_fixture_helpers import eval_fixture_text
from runsight_core.eval.runner import EvalCaseResult, EvalSuiteResult, run_eval
from runsight_core.state import BlockResult, WorkflowState

FIXTURE_TRANSFORM_YAML = eval_fixture_text("fixture-transform-pipeline.yaml")
MIXED_CASE_YAML = eval_fixture_text("mixed-case-eval.yaml")


@pytest.mark.asyncio
async def test_fixture_mode_applies_json_path_transform_to_assertion_input() -> None:
    result = await run_eval(FIXTURE_TRANSFORM_YAML)

    assert isinstance(result, EvalSuiteResult)
    assert result.passed is True
    case = result.case_results[0]
    assert isinstance(case, EvalCaseResult)
    assert case.case_id == "transform_case"
    assert case.block_results["analyze"].results[0].passed is True

    result_without_matching_summary = await run_eval(
        FIXTURE_TRANSFORM_YAML.replace('value: "transform"', 'value: "Deep dive"')
    )
    assert (
        result_without_matching_summary.case_results[0].block_results["analyze"].results[0].passed
        is False
    )


@pytest.mark.asyncio
async def test_fixture_mode_scores_mixed_cases_and_threshold() -> None:
    result = await run_eval(MIXED_CASE_YAML)

    scores = {case.case_id: case.score for case in result.case_results}
    passed = {case.case_id: case.passed for case in result.case_results}
    assert scores == {"matching_fixture": 1.0, "missing_keyword": 0.0, "partial_threshold": 0.5}
    assert passed == {
        "matching_fixture": True,
        "missing_keyword": False,
        "partial_threshold": False,
    }
    assert result.score == pytest.approx(0.5)
    assert result.threshold == 0.6
    assert result.passed is False

    low_threshold_result = await run_eval(
        MIXED_CASE_YAML.replace("threshold: 0.6", "threshold: 0.4")
    )
    assert low_threshold_result.passed is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("fixture_name", "reason_fragment"),
    [
        ("bad-transform-test.yaml", "not valid JSON"),
        ("unknown-transform-test.yaml", "Unknown transform type"),
        ("missing-path-test.yaml", "not found"),
        ("malformed-transform-test.yaml", "Unknown transform format"),
    ],
)
async def test_transform_failures_return_failed_grading_results(
    fixture_name: str,
    reason_fragment: str,
) -> None:
    result = await run_eval(eval_fixture_text(fixture_name))

    grading = result.case_results[0].block_results["analyze"].results[0]
    assert result.case_results[0].passed is False
    assert grading.passed is False
    assert reason_fragment in grading.reason


@pytest.mark.asyncio
async def test_fixture_mode_does_not_call_executor_when_cases_provide_fixtures() -> None:
    call_count = 0

    async def counting_executor(workflow, inputs):
        nonlocal call_count
        call_count += 1
        state = WorkflowState()
        state.results["analyze"] = BlockResult(output="executor output")
        return state

    result = await run_eval(MIXED_CASE_YAML, executor=counting_executor)

    assert call_count == 0
    assert len(result.case_results) == 3
