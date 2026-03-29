"""Tests for deterministic linguistic assertion plugins.

Covers: levenshtein, bleu, rouge-n.

These tests are RED — the implementation modules do not exist yet.
They must fail with ImportError until Green creates
`runsight_core.assertions.deterministic.linguistic`.
"""

from runsight_core.assertions.base import AssertionContext, GradingResult

# ── Import the implementations (will fail until Green creates them) ──────────
from runsight_core.assertions.deterministic.linguistic import (
    BleuAssertion,
    LevenshteinAssertion,
    RougeNAssertion,
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
# levenshtein
# ═════════════════════════════════════════════════════════════════════════════


class TestLevenshteinAssertion:
    """AC-1: levenshtein — edit distance <= threshold."""

    def test_type_attribute(self):
        a = LevenshteinAssertion(value="hello", threshold=5)
        assert a.type == "levenshtein"

    # ── Identical strings (from promptfoo) ───────────────────────────────

    def test_identical_strings_pass(self):
        a = LevenshteinAssertion(value="hello world", threshold=5)
        ctx = make_context("hello world")
        result = a.evaluate("hello world", ctx)
        assert result.passed is True
        assert result.score == 1.0

    # ── Within threshold (from promptfoo) ────────────────────────────────

    def test_within_threshold_passes(self):
        """One character difference, threshold=5 — should pass."""
        a = LevenshteinAssertion(value="hello", threshold=5)
        ctx = make_context("hallo")
        result = a.evaluate("hallo", ctx)
        assert result.passed is True

    def test_exactly_at_threshold_passes(self):
        """Edit distance equals threshold — should pass."""
        a = LevenshteinAssertion(value="abc", threshold=3)
        ctx = make_context("xyz")  # distance = 3
        result = a.evaluate("xyz", ctx)
        assert result.passed is True

    # ── Exceeds threshold (from promptfoo) ───────────────────────────────

    def test_exceeds_threshold_fails(self):
        a = LevenshteinAssertion(value="hello", threshold=1)
        ctx = make_context("world")
        result = a.evaluate("world", ctx)
        assert result.passed is False

    def test_large_distance_fails(self):
        a = LevenshteinAssertion(value="cat", threshold=2)
        ctx = make_context("completely different")
        result = a.evaluate("completely different", ctx)
        assert result.passed is False

    # ── Default threshold (from promptfoo: default=5) ────────────────────

    def test_default_threshold_is_five(self):
        """When threshold is not specified, default should be 5."""
        a = LevenshteinAssertion(value="hello")
        ctx = make_context("hallo")  # distance = 1, <= 5
        result = a.evaluate("hallo", ctx)
        assert result.passed is True

    def test_default_threshold_exceeds(self):
        a = LevenshteinAssertion(value="a")
        ctx = make_context("abcdefgh")  # distance = 7, > 5
        result = a.evaluate("abcdefgh", ctx)
        assert result.passed is False

    # ── Empty strings (from promptfoo) ───────────────────────────────────

    def test_empty_output_and_empty_value(self):
        a = LevenshteinAssertion(value="", threshold=0)
        ctx = make_context("")
        result = a.evaluate("", ctx)
        assert result.passed is True

    def test_empty_output_nonempty_value(self):
        a = LevenshteinAssertion(value="hello", threshold=3)
        ctx = make_context("")
        result = a.evaluate("", ctx)
        assert result.passed is False  # distance = 5 > 3

    def test_nonempty_output_empty_value(self):
        a = LevenshteinAssertion(value="", threshold=3)
        ctx = make_context("hi")
        result = a.evaluate("hi", ctx)
        assert result.passed is True  # distance = 2 <= 3

    # ── Long strings (from promptfoo) ────────────────────────────────────

    def test_long_identical_strings(self):
        long_str = "a" * 1000
        a = LevenshteinAssertion(value=long_str, threshold=0)
        ctx = make_context(long_str)
        result = a.evaluate(long_str, ctx)
        assert result.passed is True

    # ── Return type / reason (AC-7) ──────────────────────────────────────

    def test_returns_grading_result(self):
        a = LevenshteinAssertion(value="hello", threshold=5)
        ctx = make_context("hello")
        result = a.evaluate("hello", ctx)
        assert isinstance(result, GradingResult)

    def test_reason_is_meaningful(self):
        a = LevenshteinAssertion(value="hello", threshold=1)
        ctx = make_context("world")
        result = a.evaluate("world", ctx)
        assert isinstance(result.reason, str)
        assert len(result.reason) > 0


# ═════════════════════════════════════════════════════════════════════════════
# bleu
# ═════════════════════════════════════════════════════════════════════════════


class TestBleuAssertion:
    """AC-5: bleu returns continuous scores [0,1], pass when >= threshold."""

    def test_type_attribute(self):
        a = BleuAssertion(value="reference text", threshold=0.5)
        assert a.type == "bleu"

    # ── Identical sentences ~1.0 (from promptfoo) ────────────────────────

    def test_identical_sentences_high_score(self):
        ref = "The quick brown fox jumps over the lazy dog"
        a = BleuAssertion(value=ref, threshold=0.5)
        ctx = make_context(ref)
        result = a.evaluate(ref, ctx)
        assert result.passed is True
        assert result.score >= 0.9  # should be ~1.0

    # ── Different sentences ~0.0 (from promptfoo) ────────────────────────

    def test_completely_different_sentences_low_score(self):
        a = BleuAssertion(
            value="The quick brown fox jumps over the lazy dog",
            threshold=0.5,
        )
        ctx = make_context("An entirely unrelated sentence about something else")
        result = a.evaluate("An entirely unrelated sentence about something else", ctx)
        assert result.passed is False
        assert result.score < 0.3

    # ── Partial match 0.5-1.0 (from promptfoo) ──────────────────────────

    def test_partial_match_moderate_score(self):
        ref = "The quick brown fox jumps over the lazy dog"
        candidate = "The quick brown fox leaps over a lazy dog"
        a = BleuAssertion(value=ref, threshold=0.3)
        ctx = make_context(candidate)
        result = a.evaluate(candidate, ctx)
        assert result.passed is True
        assert 0.3 <= result.score <= 1.0

    # ── Custom threshold (from promptfoo) ────────────────────────────────

    def test_custom_threshold_high(self):
        ref = "The quick brown fox jumps over the lazy dog"
        candidate = "The quick brown fox leaps over a lazy dog"
        a = BleuAssertion(value=ref, threshold=0.9)
        ctx = make_context(candidate)
        result = a.evaluate(candidate, ctx)
        assert result.passed is False  # partial match won't reach 0.9

    def test_custom_threshold_low_passes(self):
        ref = "The quick brown fox"
        candidate = "The quick brown cat"
        a = BleuAssertion(value=ref, threshold=0.1)
        ctx = make_context(candidate)
        result = a.evaluate(candidate, ctx)
        assert result.passed is True

    # ── Default threshold = 0.5 (from promptfoo) ────────────────────────

    def test_default_threshold_is_half(self):
        ref = "identical sentence for testing"
        a = BleuAssertion(value=ref)  # no explicit threshold
        ctx = make_context(ref)
        result = a.evaluate(ref, ctx)
        assert result.passed is True  # identical -> score ~1.0, >= 0.5

    def test_default_threshold_fails_different(self):
        a = BleuAssertion(value="The quick brown fox jumps over the lazy dog")
        ctx = make_context("Completely different unrelated text here now")
        result = a.evaluate("Completely different unrelated text here now", ctx)
        assert result.passed is False  # score << 0.5

    # ── Score boundaries (AC-5) ──────────────────────────────────────────

    def test_score_is_between_zero_and_one(self):
        a = BleuAssertion(value="reference", threshold=0.0)
        ctx = make_context("something else")
        result = a.evaluate("something else", ctx)
        assert 0.0 <= result.score <= 1.0

    def test_score_continuous_not_binary(self):
        """AC-5: BLEU should produce continuous scores, not just 0/1."""
        ref = "The quick brown fox jumps over the lazy dog"
        candidate = "The quick brown fox leaps over a lazy dog"
        a = BleuAssertion(value=ref, threshold=0.0)
        ctx = make_context(candidate)
        result = a.evaluate(candidate, ctx)
        # Should be between 0 and 1, not exactly 0.0 or 1.0
        assert 0.0 < result.score < 1.0

    # ── Edge cases ───────────────────────────────────────────────────────

    def test_empty_output(self):
        a = BleuAssertion(value="reference text", threshold=0.5)
        ctx = make_context("")
        result = a.evaluate("", ctx)
        assert result.passed is False
        assert result.score == 0.0

    def test_empty_reference(self):
        a = BleuAssertion(value="", threshold=0.5)
        ctx = make_context("some output")
        result = a.evaluate("some output", ctx)
        # BLEU with empty reference is not well-defined; should handle gracefully
        assert isinstance(result, GradingResult)

    # ── Return type / reason (AC-7) ──────────────────────────────────────

    def test_returns_grading_result(self):
        a = BleuAssertion(value="ref", threshold=0.5)
        ctx = make_context("ref")
        result = a.evaluate("ref", ctx)
        assert isinstance(result, GradingResult)

    def test_reason_is_meaningful(self):
        a = BleuAssertion(value="ref", threshold=0.9)
        ctx = make_context("different")
        result = a.evaluate("different", ctx)
        assert isinstance(result.reason, str)
        assert len(result.reason) > 0


# ═════════════════════════════════════════════════════════════════════════════
# rouge-n
# ═════════════════════════════════════════════════════════════════════════════


class TestRougeNAssertion:
    """AC-5: rouge-n returns continuous scores [0,1], pass when >= threshold."""

    def test_type_attribute(self):
        a = RougeNAssertion(value="reference text", threshold=0.75)
        assert a.type == "rouge-n"

    # ── Above threshold (from promptfoo) ─────────────────────────────────

    def test_identical_text_passes(self):
        ref = "The quick brown fox jumps over the lazy dog"
        a = RougeNAssertion(value=ref, threshold=0.75)
        ctx = make_context(ref)
        result = a.evaluate(ref, ctx)
        assert result.passed is True
        assert result.score >= 0.9

    def test_high_overlap_passes(self):
        ref = "The quick brown fox jumps over the lazy dog"
        candidate = "The quick brown fox jumps over the lazy cat"
        a = RougeNAssertion(value=ref, threshold=0.75)
        ctx = make_context(candidate)
        result = a.evaluate(candidate, ctx)
        assert result.passed is True

    # ── Below threshold (from promptfoo) ─────────────────────────────────

    def test_completely_different_fails(self):
        a = RougeNAssertion(
            value="The quick brown fox jumps over the lazy dog",
            threshold=0.75,
        )
        ctx = make_context("An entirely unrelated sentence about programming")
        result = a.evaluate("An entirely unrelated sentence about programming", ctx)
        assert result.passed is False

    def test_low_overlap_below_threshold(self):
        a = RougeNAssertion(
            value="Machine learning is a subset of artificial intelligence",
            threshold=0.75,
        )
        ctx = make_context("Deep learning uses neural networks for computation")
        result = a.evaluate("Deep learning uses neural networks for computation", ctx)
        assert result.passed is False

    # ── Default threshold = 0.75 (from promptfoo) ───────────────────────

    def test_default_threshold_is_075(self):
        ref = "identical sentence for testing purposes here"
        a = RougeNAssertion(value=ref)  # no explicit threshold
        ctx = make_context(ref)
        result = a.evaluate(ref, ctx)
        assert result.passed is True  # identical -> score ~1.0, >= 0.75

    def test_default_threshold_fails_different(self):
        a = RougeNAssertion(value="The quick brown fox jumps over the lazy dog")
        ctx = make_context("An entirely different text about programming languages")
        result = a.evaluate("An entirely different text about programming languages", ctx)
        assert result.passed is False

    # ── Custom threshold (from promptfoo) ────────────────────────────────

    def test_custom_threshold_low_passes(self):
        a = RougeNAssertion(
            value="The quick brown fox jumps over the lazy dog",
            threshold=0.3,
        )
        ctx = make_context("The quick fox is lazy")
        result = a.evaluate("The quick fox is lazy", ctx)
        assert result.passed is True

    def test_custom_threshold_high_fails(self):
        a = RougeNAssertion(
            value="The quick brown fox jumps over the lazy dog",
            threshold=0.99,
        )
        candidate = "The quick brown fox jumps over the lazy cat"
        ctx = make_context(candidate)
        result = a.evaluate(candidate, ctx)
        assert result.passed is False

    # ── Score boundaries (AC-5) ──────────────────────────────────────────

    def test_score_is_between_zero_and_one(self):
        a = RougeNAssertion(value="reference", threshold=0.0)
        ctx = make_context("something")
        result = a.evaluate("something", ctx)
        assert 0.0 <= result.score <= 1.0

    def test_score_continuous_not_binary(self):
        """AC-5: ROUGE-N should produce continuous scores, not just 0/1."""
        ref = "The quick brown fox jumps over the lazy dog"
        candidate = "The quick brown fox jumps over a lazy cat"
        a = RougeNAssertion(value=ref, threshold=0.0)
        ctx = make_context(candidate)
        result = a.evaluate(candidate, ctx)
        assert 0.0 < result.score < 1.0

    # ── Edge cases ───────────────────────────────────────────────────────

    def test_empty_output(self):
        a = RougeNAssertion(value="reference text", threshold=0.75)
        ctx = make_context("")
        result = a.evaluate("", ctx)
        assert result.passed is False

    def test_empty_reference(self):
        a = RougeNAssertion(value="", threshold=0.75)
        ctx = make_context("some output")
        result = a.evaluate("some output", ctx)
        assert isinstance(result, GradingResult)

    # ── Return type / reason (AC-7) ──────────────────────────────────────

    def test_returns_grading_result(self):
        a = RougeNAssertion(value="ref", threshold=0.5)
        ctx = make_context("ref")
        result = a.evaluate("ref", ctx)
        assert isinstance(result, GradingResult)

    def test_reason_is_meaningful(self):
        a = RougeNAssertion(value="ref", threshold=0.99)
        ctx = make_context("different")
        result = a.evaluate("different", ctx)
        assert isinstance(result.reason, str)
        assert len(result.reason) > 0
