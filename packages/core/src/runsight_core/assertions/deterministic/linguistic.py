"""Deterministic linguistic assertion plugins.

Covers: levenshtein, bleu, rouge-n.
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Any

import editdistance
from rouge_score import rouge_scorer

from runsight_core.assertions.base import AssertionContext, GradingResult


class LevenshteinAssertion:
    """Edit distance <= threshold."""

    type = "levenshtein"

    def __init__(
        self,
        value: Any = "",
        threshold: float | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        self.value = str(value)
        self.threshold = threshold if threshold is not None else 5
        self.config = config

    def evaluate(self, output: str, context: AssertionContext) -> GradingResult:
        distance = editdistance.eval(output, self.value)
        passed = distance <= self.threshold
        score = 1.0 if passed else 0.0
        reason = f"Levenshtein distance is {distance} (threshold {self.threshold})"
        return GradingResult(passed=passed, score=score, reason=reason)


class BleuAssertion:
    """BLEU-4 score >= threshold. Inline implementation (no nltk)."""

    type = "bleu"

    def __init__(
        self,
        value: Any = "",
        threshold: float | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        self.value = str(value)
        self.threshold = threshold if threshold is not None else 0.5
        self.config = config

    def evaluate(self, output: str, context: AssertionContext) -> GradingResult:
        score = _compute_bleu(reference=self.value, candidate=output)
        passed = score >= self.threshold
        reason = f"BLEU score {score:.4f} {'>='}  threshold {self.threshold}"
        if not passed:
            reason = f"BLEU score {score:.4f} < threshold {self.threshold}"
        return GradingResult(passed=passed, score=score, reason=reason)


class RougeNAssertion:
    """ROUGE-N score >= threshold using rouge-score library."""

    type = "rouge-n"

    def __init__(
        self,
        value: Any = "",
        threshold: float | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        self.value = str(value)
        self.threshold = threshold if threshold is not None else 0.75
        self.config = config

    def evaluate(self, output: str, context: AssertionContext) -> GradingResult:
        if not output or not self.value:
            score = 0.0
        else:
            scorer = rouge_scorer.RougeScorer(["rouge1"], use_stemmer=False)
            scores = scorer.score(self.value, output)
            score = scores["rouge1"].fmeasure

        passed = score >= self.threshold
        if passed:
            reason = f"ROUGE-N score {score:.4f} >= threshold {self.threshold}"
        else:
            reason = f"ROUGE-N score {score:.4f} < threshold {self.threshold}"
        return GradingResult(passed=passed, score=score, reason=reason)


# ── Inline BLEU-4 implementation ────────────────────────────────────────────


def _get_ngrams(tokens: list[str], n: int) -> Counter[tuple[str, ...]]:
    """Extract n-grams from a token list."""
    return Counter(tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1))


def _compute_bleu(reference: str, candidate: str, max_n: int = 4) -> float:
    """Compute BLEU score with smoothing (method 1: add 1 to numerator/denominator).

    Ported from promptfoo's BLEU implementation.
    """
    ref_tokens = reference.lower().split()
    cand_tokens = candidate.lower().split()

    if not cand_tokens:
        return 0.0
    if not ref_tokens:
        return 0.0

    # Brevity penalty
    bp = 1.0
    if len(cand_tokens) < len(ref_tokens):
        bp = math.exp(1.0 - len(ref_tokens) / len(cand_tokens))

    # Modified precision for each n-gram order with smoothing
    log_avg = 0.0
    for n in range(1, max_n + 1):
        ref_ngrams = _get_ngrams(ref_tokens, n)
        cand_ngrams = _get_ngrams(cand_tokens, n)

        # Clipped counts
        clipped = 0
        total = 0
        for ngram, count in cand_ngrams.items():
            clipped += min(count, ref_ngrams.get(ngram, 0))
            total += count

        # Smoothing: add 1 to both numerator and denominator when n > 1
        if n == 1:
            if total == 0:
                return 0.0
            precision = clipped / total
            if precision == 0:
                return 0.0
        else:
            precision = (clipped + 1) / (total + 1)

        log_avg += math.log(precision) / max_n

    return bp * math.exp(log_avg)
