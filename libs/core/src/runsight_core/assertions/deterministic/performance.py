"""Deterministic performance assertion plugins.

Covers: cost, latency.
"""

from __future__ import annotations

from typing import Any

from runsight_core.assertions.base import AssertionContext, GradingResult


class CostAssertion:
    """Check that cost_usd from context is within threshold."""

    type = "cost"

    def __init__(self, value: Any = None, threshold: float | None = None) -> None:
        self.value = value
        self.threshold = threshold

    def evaluate(self, output: str, context: AssertionContext) -> GradingResult:
        cost = context.cost_usd
        threshold = self.threshold if self.threshold is not None else 0.0
        if cost <= threshold:
            return GradingResult(
                passed=True,
                score=1.0,
                reason=f"Cost ${cost:.4f} is within threshold ${threshold:.4f}",
            )
        return GradingResult(
            passed=False, score=0.0, reason=f"Cost ${cost:.4f} exceeds threshold ${threshold:.4f}"
        )


class LatencyAssertion:
    """Check that latency_ms from context is within threshold."""

    type = "latency"

    def __init__(self, value: Any = None, threshold: float | None = None) -> None:
        self.value = value
        self.threshold = threshold

    def evaluate(self, output: str, context: AssertionContext) -> GradingResult:
        latency = context.latency_ms
        threshold = self.threshold if self.threshold is not None else 0.0
        if latency <= threshold:
            return GradingResult(
                passed=True,
                score=1.0,
                reason=f"Latency {latency:.1f}ms is within threshold {threshold:.1f}ms",
            )
        return GradingResult(
            passed=False,
            score=0.0,
            reason=f"Latency {latency:.1f}ms exceeds threshold {threshold:.1f}ms",
        )
