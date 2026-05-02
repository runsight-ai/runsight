"""Smoke coverage for the offline eval runner public API."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from eval_fixture_helpers import eval_fixture_text
from runsight_core.assertions.base import AssertionContext, GradingResult
from runsight_core.assertions.registry import register_assertion
from runsight_core.assertions.scoring import AssertionsResult
from runsight_core.eval.runner import EvalSuiteResult, run_eval
from runsight_core.state import BlockResult, WorkflowState

_TWO_CASE_WORKFLOW_YAML = eval_fixture_text("eval-runner-two-case.yaml")
_FIXTURE_CASE_YAML = eval_fixture_text("eval-runner-fixture-case.yaml")


class _ContainsAssertion:
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
    from runsight_core.assertions.registry import _REGISTRY

    saved = {k: v for k, v in _REGISTRY.items() if k == "contains"}
    register_assertion("contains", _ContainsAssertion)
    yield
    if "contains" in saved:
        _REGISTRY["contains"] = saved["contains"]
    else:
        _REGISTRY.pop("contains", None)


def _make_executor_returning(block_outputs: list[dict[str, str]]) -> AsyncMock:
    call_count = {"n": 0}

    async def _executor(workflow, inputs):
        idx = call_count["n"]
        call_count["n"] += 1
        state = WorkflowState()
        for block_id, output_text in block_outputs[idx].items():
            state.results[block_id] = BlockResult(output=output_text)
        return state

    return AsyncMock(side_effect=_executor)


@pytest.mark.asyncio
async def test_executor_mode_runs_cases_and_scores_assertions():
    executor = _make_executor_returning(
        [
            {"analyze": "LLM research findings"},
            {"analyze": "transformer architecture details"},
        ]
    )

    result = await run_eval(_TWO_CASE_WORKFLOW_YAML, executor=executor)

    assert isinstance(result, EvalSuiteResult)
    assert executor.call_count == 2
    assert result.passed is True
    assert result.score == 1.0
    assert [case.case_id for case in result.case_results] == ["case_1", "case_2"]
    assert all(
        isinstance(case.block_results["analyze"], AssertionsResult) for case in result.case_results
    )


@pytest.mark.asyncio
async def test_fixture_mode_skips_executor_and_uses_fixture_outputs():
    executor = AsyncMock()

    result = await run_eval(_FIXTURE_CASE_YAML, executor=executor)

    executor.assert_not_called()
    assert isinstance(result, EvalSuiteResult)
    assert result.case_results[0].case_id == "fixture_case"
    assert result.case_results[0].passed is True
    assert result.case_results[0].score == 1.0
