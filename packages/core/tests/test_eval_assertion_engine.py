"""Eval runner integration with the shared assertion registry."""

from __future__ import annotations

import pytest
import runsight_core.assertions.deterministic  # noqa: F401
from eval_fixture_helpers import eval_fixture_text
from runsight_core.assertions.base import GradingResult
from runsight_core.assertions.registry import _REGISTRY, register_assertion, run_assertions
from runsight_core.eval.runner import run_eval


@pytest.mark.asyncio
async def test_custom_assertion_registered_in_shared_registry_is_visible_to_eval() -> None:
    class AlwaysPassAssertion:
        type = "eval-custom-always-pass"

        def __init__(self, value=None, threshold=None):
            pass

        def evaluate(self, output, context):
            return GradingResult(
                passed=True,
                score=1.0,
                reason="Custom assertion: always passes",
                assertion_type="eval-custom-always-pass",
            )

    register_assertion("eval-custom-always-pass", AlwaysPassAssertion)
    try:
        result = await run_eval(eval_fixture_text("custom-assertion-test.yaml"))
    finally:
        _REGISTRY.pop("eval-custom-always-pass", None)

    grading = result.case_results[0].block_results["analyze"].results[0]
    assert result.passed is True
    assert grading.passed is True
    assert grading.assertion_type == "eval-custom-always-pass"


@pytest.mark.asyncio
async def test_unregistered_assertion_type_raises_from_shared_registry() -> None:
    with pytest.raises(KeyError, match="eval-nonexistent-type"):
        await run_eval(eval_fixture_text("unknown-type-test.yaml"))


def test_eval_runner_uses_shared_assertion_function_and_deterministic_registrations() -> None:
    from runsight_core.eval import runner as eval_runner_module

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

    assert eval_runner_module.run_assertions is run_assertions
    assert expected_types.issubset(_REGISTRY.keys())
