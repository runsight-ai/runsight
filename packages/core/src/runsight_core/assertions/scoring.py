"""Weighted aggregation of assertion results."""

from __future__ import annotations

from dataclasses import dataclass, field

from runsight_core.assertions.base import GradingResult


@dataclass
class AssertionsResult:
    """Accumulates weighted assertion results and computes aggregate scores."""

    results: list[GradingResult] = field(default_factory=list)
    named_scores: dict[str, float] = field(default_factory=dict)
    total_score: float = 0.0
    total_weight: float = 0.0

    def add_result(self, result: GradingResult, weight: float = 1.0) -> None:
        """Add a grading result with the given weight."""
        self.results.append(result)
        self.named_scores.update(result.named_scores)
        if weight > 0:
            self.total_score += result.score * weight
            self.total_weight += weight

    @property
    def aggregate_score(self) -> float:
        """Weighted average score. Returns 0.0 when no weighted results exist."""
        if self.total_weight == 0:
            return 0.0
        return self.total_score / self.total_weight

    def passed(self, threshold: float | None = None) -> bool:
        """Check if the assertion suite passed.

        If threshold is given, checks aggregate_score >= threshold.
        If threshold is None, returns True only if all individual results passed.
        """
        if threshold is not None:
            return self.aggregate_score >= threshold
        return all(r.passed for r in self.results)
