"""build_block_context behavior coverage for LinearBlock.

Tests cover:
1. Declared input resolution for empty, single, multiple, missing, and JSON refs.
2. Parity with the canonical _resolve_ref helper.
3. BlockContext field population for LinearBlock.
4. Conversation history shallow-copy behavior.
5. fit_to_budget request construction.
6. artifact_store passthrough from WorkflowState.
"""

from unittest.mock import MagicMock, patch

import pytest
from runsight_core.artifacts import InMemoryArtifactStore
from runsight_core.block_io import (  # noqa: F401
    BlockContext,
    build_block_context,
)
from runsight_core.blocks.linear import LinearBlock
from runsight_core.context_governance import ContextResolutionError
from runsight_core.memory.budget import BudgetedContext, BudgetReport
from runsight_core.primitives import Soul, Step
from runsight_core.state import BlockResult, WorkflowState

# ==============================================================================
# Helpers
# ==============================================================================

_MODEL = "gpt-4o"


def make_soul(soul_id: str = "research_soul", model_name: str = _MODEL) -> Soul:
    return Soul(
        id=soul_id,
        kind="soul",
        name="Researcher Soul",
        role="Researcher",
        system_prompt="You are a researcher.",
        model_name=model_name,
    )


def make_runner(model_name: str = _MODEL) -> MagicMock:
    runner = MagicMock()
    runner.model_name = model_name
    return runner


def make_linear_block(block_id: str = "research_block", soul: Soul | None = None) -> LinearBlock:
    if soul is None:
        soul = make_soul()
    return LinearBlock(block_id=block_id, soul=soul, runner=make_runner())


def make_state(**kwargs) -> WorkflowState:
    return WorkflowState(**kwargs)


def make_artifact_store() -> InMemoryArtifactStore:
    return InMemoryArtifactStore(run_id="block-context-test-run")


def _make_budgeted_context(
    instruction: str = "Do the thing",
    context: str | None = None,
    messages: list | None = None,
) -> BudgetedContext:
    """Construct a fake BudgetedContext returned by mocked fit_to_budget."""
    report = BudgetReport(
        model=_MODEL,
        max_input_tokens=128000,
        output_reserve=4096,
        effective_budget=100000,
        p1_tokens=10,
        p2_tokens_before=5,
        p2_tokens_after=5,
        p3_tokens_before=0,
        p3_tokens_after=0,
        p3_pairs_dropped=0,
        total_tokens=15,
        headroom=99985,
        warnings=[],
    )
    return BudgetedContext(
        instruction=instruction, context=context, messages=messages or [], report=report
    )


# ==============================================================================
# Input resolution for empty, single, multiple, missing, and JSON refs
# ==============================================================================


class TestInputResolution:
    """build_block_context resolves declared_inputs from step.declared_inputs."""

    def test_empty_declared_inputs_produces_empty_ctx_inputs(self):
        """When step.declared_inputs is empty, ctx.inputs is an empty dict."""
        block = make_linear_block()
        state = make_state()
        step = Step(block, declared_inputs={})

        budgeted = _make_budgeted_context()
        with patch("runsight_core.block_io.fit_to_budget", return_value=budgeted):
            ctx = build_block_context(block, state, step=step)

        assert ctx.inputs == {}

    def test_single_input_resolved_from_state_results(self):
        """Single declared input resolves to the matching BlockResult.output."""
        block = make_linear_block()
        state = make_state(
            results={"upstream_review_block": BlockResult(output="defective")},
        )
        step = Step(block, declared_inputs={"reason": "upstream_review_block"})

        budgeted = _make_budgeted_context()
        with patch("runsight_core.block_io.fit_to_budget", return_value=budgeted):
            ctx = build_block_context(block, state, step=step)

        assert ctx.inputs["reason"] == "defective"

    def test_multiple_inputs_resolved_correctly(self):
        """Multiple declared inputs each resolve to their respective BlockResult.output."""
        block = make_linear_block()
        state = make_state(
            results={
                "upstream_alpha_block": BlockResult(output="alpha"),
                "upstream_beta_block": BlockResult(output="beta"),
            },
        )
        step = Step(
            block,
            declared_inputs={"input_a": "upstream_alpha_block", "input_b": "upstream_beta_block"},
        )

        budgeted = _make_budgeted_context()
        with patch("runsight_core.block_io.fit_to_budget", return_value=budgeted):
            ctx = build_block_context(block, state, step=step)

        assert ctx.inputs["input_a"] == "alpha"
        assert ctx.inputs["input_b"] == "beta"

    def test_missing_source_raises_value_error(self):
        """Referencing a non-existent block_id in declared_inputs raises ValueError."""
        block = make_linear_block()
        state = make_state(results={})
        step = Step(block, declared_inputs={"x": "nonexistent"})

        budgeted = _make_budgeted_context()
        with patch("runsight_core.block_io.fit_to_budget", return_value=budgeted):
            with pytest.raises(ValueError, match="nonexistent"):
                build_block_context(block, state, step=step)

    def test_json_auto_parse_dot_path_resolution(self):
        """JSON output is parsed and dot-path resolution extracts the correct field."""
        block = make_linear_block()
        state = make_state(
            results={"research_block": BlockResult(output='{"key": "val"}')},
        )
        step = Step(block, declared_inputs={"extracted": "research_block.key"})

        budgeted = _make_budgeted_context()
        with patch("runsight_core.block_io.fit_to_budget", return_value=budgeted):
            ctx = build_block_context(block, state, step=step)

        assert ctx.inputs["extracted"] == "val"

    def test_non_json_string_with_arbitrary_dot_path_raises_resolution_error(self):
        """Arbitrary field paths into non-JSON output fail clearly."""
        block = make_linear_block()
        state = make_state(
            results={"research_block": BlockResult(output="plain text")},
        )
        step = Step(block, declared_inputs={"data": "research_block.subfield"})

        budgeted = _make_budgeted_context()
        with patch("runsight_core.block_io.fit_to_budget", return_value=budgeted):
            with pytest.raises(
                (ContextResolutionError, ValueError), match="research_block.subfield"
            ):
                build_block_context(block, state, step=step)


# ==============================================================================
# Parity with canonical reference resolution
# ==============================================================================


class TestParityWithResolveRef:
    """build_block_context input resolution uses _resolve_ref (canonical resolver).
    These tests verify that the canonical _resolve_ref in block_io produces
    correct results."""

    def test_resolve_ref_single_plain_output(self):
        """For a plain output ref, build_block_context resolves correctly."""
        from runsight_core.block_io import _resolve_ref

        block = make_linear_block()
        state = make_state(
            results={"src": BlockResult(output="the output")},
        )
        step = Step(block, declared_inputs={"result": "src"})

        expected = _resolve_ref("src", state)

        budgeted = _make_budgeted_context()
        with patch("runsight_core.block_io.fit_to_budget", return_value=budgeted):
            ctx = build_block_context(block, state, step=step)

        assert ctx.inputs["result"] == expected

    def test_resolve_ref_json_dot_path(self):
        """JSON auto-parse dot-path resolution works correctly."""
        from runsight_core.block_io import _resolve_ref

        block = make_linear_block()
        state = make_state(
            results={"src": BlockResult(output='{"nested": {"value": 42}}')},
        )
        step = Step(block, declared_inputs={"num": "src.nested.value"})

        expected = _resolve_ref("src.nested.value", state)

        budgeted = _make_budgeted_context()
        with patch("runsight_core.block_io.fit_to_budget", return_value=budgeted):
            ctx = build_block_context(block, state, step=step)

        assert ctx.inputs["num"] == expected

    def test_resolve_ref_missing_source_raises_value_error(self):
        """Both _resolve_ref and build_block_context raise ValueError for missing src."""
        from runsight_core.block_io import _resolve_ref

        block = make_linear_block()
        state = make_state(results={})
        step = Step(block, declared_inputs={"x": "missing_source_block"})

        with pytest.raises(ValueError):
            _resolve_ref("missing_source_block", state)

        budgeted = _make_budgeted_context()
        with patch("runsight_core.block_io.fit_to_budget", return_value=budgeted):
            with pytest.raises(ValueError):
                build_block_context(block, state, step=step)


# ==============================================================================
# LinearBlock context population
# ==============================================================================
