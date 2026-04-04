"""Tests for deterministic performance assertion plugins.

Covers: cost, latency.

These tests are RED — the implementation modules do not exist yet.
They must fail with ImportError until Green creates
`runsight_core.assertions.deterministic.performance`.
"""

from runsight_core.assertions.base import AssertionContext, GradingResult

# ── Import the implementations (will fail until Green creates them) ──────────
from runsight_core.assertions.deterministic.performance import (
    CostAssertion,
    LatencyAssertion,
)

# ── Helper ───────────────────────────────────────────────────────────────────


def make_context(output: str = "", **overrides) -> AssertionContext:
    defaults = dict(
        output=output,
        prompt="test prompt",
        prompt_hash="abc123",
        soul_id="soul_1",
        soul_version="v1",
        block_id="block_1",
        block_type="linear",
        cost_usd=0.001,
        total_tokens=100,
        latency_ms=500.0,
        variables={},
        run_id="run_1",
        workflow_id="wf_1",
    )
    defaults.update(overrides)
    return AssertionContext(**defaults)


# ═════════════════════════════════════════════════════════════════════════════
# cost
# ═════════════════════════════════════════════════════════════════════════════


class TestCostAssertion:
    """AC-6: cost reads from AssertionContext.cost_usd, not output text."""

    def test_type_attribute(self):
        a = CostAssertion(threshold=0.01)
        assert a.type == "cost"

    def test_cost_below_threshold_passes(self):
        a = CostAssertion(threshold=0.01)
        ctx = make_context("any output", cost_usd=0.005)
        result = a.evaluate("any output", ctx)
        assert result.passed is True
        assert result.score == 1.0

    def test_cost_equal_threshold_passes(self):
        a = CostAssertion(threshold=0.01)
        ctx = make_context("any output", cost_usd=0.01)
        result = a.evaluate("any output", ctx)
        assert result.passed is True

    def test_cost_above_threshold_fails(self):
        a = CostAssertion(threshold=0.01)
        ctx = make_context("any output", cost_usd=0.02)
        result = a.evaluate("any output", ctx)
        assert result.passed is False
        assert result.score == 0.0

    def test_ignores_output_text(self):
        """AC-6: cost should read from context, not from output string."""
        a = CostAssertion(threshold=0.01)
        ctx = make_context("cost is $100.00", cost_usd=0.005)
        result = a.evaluate("cost is $100.00", ctx)
        assert result.passed is True  # context cost is below threshold

    def test_zero_cost_passes(self):
        a = CostAssertion(threshold=0.01)
        ctx = make_context("output", cost_usd=0.0)
        result = a.evaluate("output", ctx)
        assert result.passed is True

    def test_zero_threshold(self):
        """threshold=0 means only zero cost passes."""
        a = CostAssertion(threshold=0.0)
        ctx = make_context("output", cost_usd=0.0)
        result = a.evaluate("output", ctx)
        assert result.passed is True

    def test_zero_threshold_any_cost_fails(self):
        a = CostAssertion(threshold=0.0)
        ctx = make_context("output", cost_usd=0.001)
        result = a.evaluate("output", ctx)
        assert result.passed is False

    def test_returns_grading_result(self):
        a = CostAssertion(threshold=1.0)
        ctx = make_context("output", cost_usd=0.5)
        result = a.evaluate("output", ctx)
        assert isinstance(result, GradingResult)

    def test_reason_is_meaningful(self):
        a = CostAssertion(threshold=0.01)
        ctx = make_context("output", cost_usd=0.05)
        result = a.evaluate("output", ctx)
        assert isinstance(result.reason, str)
        assert len(result.reason) > 0


# ═════════════════════════════════════════════════════════════════════════════
# latency
# ═════════════════════════════════════════════════════════════════════════════


class TestLatencyAssertion:
    """AC-6: latency reads from AssertionContext.latency_ms, not output text."""

    def test_type_attribute(self):
        a = LatencyAssertion(threshold=1000)
        assert a.type == "latency"

    def test_latency_below_threshold_passes(self):
        a = LatencyAssertion(threshold=1000)
        ctx = make_context("any output", latency_ms=500.0)
        result = a.evaluate("any output", ctx)
        assert result.passed is True
        assert result.score == 1.0

    def test_latency_equal_threshold_passes(self):
        a = LatencyAssertion(threshold=1000)
        ctx = make_context("any output", latency_ms=1000.0)
        result = a.evaluate("any output", ctx)
        assert result.passed is True

    def test_latency_above_threshold_fails(self):
        a = LatencyAssertion(threshold=1000)
        ctx = make_context("any output", latency_ms=1500.0)
        result = a.evaluate("any output", ctx)
        assert result.passed is False
        assert result.score == 0.0

    def test_ignores_output_text(self):
        """AC-6: latency should read from context, not from output string."""
        a = LatencyAssertion(threshold=1000)
        ctx = make_context("latency was 9999ms", latency_ms=200.0)
        result = a.evaluate("latency was 9999ms", ctx)
        assert result.passed is True

    def test_zero_latency_passes(self):
        a = LatencyAssertion(threshold=1000)
        ctx = make_context("output", latency_ms=0.0)
        result = a.evaluate("output", ctx)
        assert result.passed is True

    def test_zero_threshold(self):
        a = LatencyAssertion(threshold=0)
        ctx = make_context("output", latency_ms=0.0)
        result = a.evaluate("output", ctx)
        assert result.passed is True

    def test_zero_threshold_any_latency_fails(self):
        a = LatencyAssertion(threshold=0)
        ctx = make_context("output", latency_ms=1.0)
        result = a.evaluate("output", ctx)
        assert result.passed is False

    def test_returns_grading_result(self):
        a = LatencyAssertion(threshold=1000)
        ctx = make_context("output", latency_ms=500.0)
        result = a.evaluate("output", ctx)
        assert isinstance(result, GradingResult)

    def test_reason_is_meaningful(self):
        a = LatencyAssertion(threshold=100)
        ctx = make_context("output", latency_ms=500.0)
        result = a.evaluate("output", ctx)
        assert isinstance(result.reason, str)
        assert len(result.reason) > 0
