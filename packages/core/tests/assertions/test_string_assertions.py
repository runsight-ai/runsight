"""Tests for deterministic string assertion plugins.

Covers: equals, contains, icontains, contains-all, contains-any,
starts-with, regex, word-count.

These tests are RED — the implementation modules do not exist yet.
They must fail with ImportError until Green creates
`runsight_core.assertions.deterministic.string`.
"""

from runsight_core.assertions.base import AssertionContext, GradingResult

# ── Import the implementations (will fail until Green creates them) ──────────
from runsight_core.assertions.deterministic.string import (
    ContainsAllAssertion,
    ContainsAnyAssertion,
    ContainsAssertion,
    EqualsAssertion,
    IContainsAssertion,
    RegexAssertion,
    StartsWithAssertion,
    WordCountAssertion,
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
# equals
# ═════════════════════════════════════════════════════════════════════════════


class TestEqualsAssertion:
    """AC-1: registered as 'equals', exact string match by default."""

    def test_type_attribute(self):
        a = EqualsAssertion(value="x")
        assert a.type == "equals"

    def test_exact_match_passes(self):
        a = EqualsAssertion(value="Hello world")
        ctx = make_context("Hello world")
        result = a.evaluate("Hello world", ctx)
        assert result.passed is True
        assert result.score == 1.0

    def test_mismatch_fails(self):
        a = EqualsAssertion(value="Hello world")
        ctx = make_context("Goodbye world")
        result = a.evaluate("Goodbye world", ctx)
        assert result.passed is False
        assert result.score == 0.0

    def test_case_sensitive(self):
        a = EqualsAssertion(value="Hello")
        ctx = make_context("hello")
        result = a.evaluate("hello", ctx)
        assert result.passed is False

    def test_empty_string_equals_empty(self):
        a = EqualsAssertion(value="")
        ctx = make_context("")
        result = a.evaluate("", ctx)
        assert result.passed is True

    def test_empty_output_fails_nonempty_value(self):
        a = EqualsAssertion(value="expected")
        ctx = make_context("")
        result = a.evaluate("", ctx)
        assert result.passed is False

    def test_default_string_mode_does_not_do_implicit_json_deep_equal(self):
        a = EqualsAssertion(value='{"b": 2, "a": 1}')
        ctx = make_context('{"a": 1, "b": 2}')
        result = a.evaluate('{"a": 1, "b": 2}', ctx)
        assert result.passed is False

    def test_json_mode_deep_equal(self):
        """JSON deep-equal is available only through explicit config."""
        a = EqualsAssertion(value='{"b": 2, "a": 1}', config={"mode": "json"})
        ctx = make_context('{"a": 1, "b": 2}')
        result = a.evaluate('{"a": 1, "b": 2}', ctx)
        assert result.passed is True

    def test_json_mode_fails_different_values(self):
        a = EqualsAssertion(value='{"a": 1}', config={"mode": "json"})
        ctx = make_context('{"a": 2}')
        result = a.evaluate('{"a": 2}', ctx)
        assert result.passed is False

    def test_json_mode_fails_invalid_json(self):
        a = EqualsAssertion(value='{"a": 1}', config={"mode": "json"})
        ctx = make_context("not json")
        result = a.evaluate("not json", ctx)
        assert result.passed is False
        assert "not valid JSON" in result.reason

    def test_invalid_mode_fails_explicitly(self):
        a = EqualsAssertion(value="x", config={"mode": "yaml"})
        ctx = make_context("x")
        result = a.evaluate("x", ctx)
        assert result.passed is False
        assert "Unsupported equals mode" in result.reason

    def test_returns_grading_result(self):
        a = EqualsAssertion(value="x")
        ctx = make_context("x")
        result = a.evaluate("x", ctx)
        assert isinstance(result, GradingResult)

    def test_reason_is_meaningful(self):
        a = EqualsAssertion(value="expected")
        ctx = make_context("actual")
        result = a.evaluate("actual", ctx)
        assert isinstance(result.reason, str)
        assert len(result.reason) > 0


# ═════════════════════════════════════════════════════════════════════════════
# contains
# ═════════════════════════════════════════════════════════════════════════════


class TestContainsAssertion:
    """AC-1: registered as 'contains', substring present."""

    def test_type_attribute(self):
        a = ContainsAssertion(value="hello")
        assert a.type == "contains"

    def test_substring_present_passes(self):
        a = ContainsAssertion(value="world")
        ctx = make_context("Hello world")
        result = a.evaluate("Hello world", ctx)
        assert result.passed is True
        assert result.score == 1.0

    def test_substring_absent_fails(self):
        a = ContainsAssertion(value="xyz")
        ctx = make_context("Hello world")
        result = a.evaluate("Hello world", ctx)
        assert result.passed is False
        assert result.score == 0.0

    def test_case_sensitive(self):
        a = ContainsAssertion(value="HELLO")
        ctx = make_context("hello world")
        result = a.evaluate("hello world", ctx)
        assert result.passed is False

    def test_empty_output(self):
        a = ContainsAssertion(value="something")
        ctx = make_context("")
        result = a.evaluate("", ctx)
        assert result.passed is False

    def test_empty_value_always_passes(self):
        """Empty string is a substring of every string."""
        a = ContainsAssertion(value="")
        ctx = make_context("anything")
        result = a.evaluate("anything", ctx)
        assert result.passed is True

    def test_handles_numbers_as_value(self):
        """promptfoo: handles numbers — value should be coerced to string."""
        a = ContainsAssertion(value=42)
        ctx = make_context("The answer is 42")
        result = a.evaluate("The answer is 42", ctx)
        assert result.passed is True

    def test_returns_grading_result_with_reason(self):
        a = ContainsAssertion(value="x")
        ctx = make_context("x")
        result = a.evaluate("x", ctx)
        assert isinstance(result, GradingResult)
        assert len(result.reason) > 0


# ═════════════════════════════════════════════════════════════════════════════
# icontains
# ═════════════════════════════════════════════════════════════════════════════


class TestIContainsAssertion:
    """AC-1: registered as 'icontains', case-insensitive substring."""

    def test_type_attribute(self):
        a = IContainsAssertion(value="hello")
        assert a.type == "icontains"

    def test_case_insensitive_match(self):
        a = IContainsAssertion(value="HELLO")
        ctx = make_context("hello world")
        result = a.evaluate("hello world", ctx)
        assert result.passed is True

    def test_case_insensitive_absent(self):
        a = IContainsAssertion(value="xyz")
        ctx = make_context("hello world")
        result = a.evaluate("hello world", ctx)
        assert result.passed is False

    def test_mixed_case_both_sides(self):
        a = IContainsAssertion(value="HeLLo")
        ctx = make_context("hElLO wOrLd")
        result = a.evaluate("hElLO wOrLd", ctx)
        assert result.passed is True

    def test_empty_output(self):
        a = IContainsAssertion(value="something")
        ctx = make_context("")
        result = a.evaluate("", ctx)
        assert result.passed is False

    def test_returns_grading_result(self):
        a = IContainsAssertion(value="x")
        ctx = make_context("X")
        result = a.evaluate("X", ctx)
        assert isinstance(result, GradingResult)


# ═════════════════════════════════════════════════════════════════════════════
# contains-all
# ═════════════════════════════════════════════════════════════════════════════


class TestContainsAllAssertion:
    """AC-1: registered as 'contains-all', all substrings present."""

    def test_type_attribute(self):
        a = ContainsAllAssertion(value=["a", "b"])
        assert a.type == "contains-all"

    def test_all_present_passes(self):
        a = ContainsAllAssertion(value=["Hello", "world"])
        ctx = make_context("Hello world")
        result = a.evaluate("Hello world", ctx)
        assert result.passed is True
        assert result.score == 1.0

    def test_one_missing_fails(self):
        a = ContainsAllAssertion(value=["Hello", "xyz"])
        ctx = make_context("Hello world")
        result = a.evaluate("Hello world", ctx)
        assert result.passed is False

    def test_all_missing_fails(self):
        a = ContainsAllAssertion(value=["abc", "xyz"])
        ctx = make_context("Hello world")
        result = a.evaluate("Hello world", ctx)
        assert result.passed is False

    def test_empty_list_passes(self):
        a = ContainsAllAssertion(value=[])
        ctx = make_context("anything")
        result = a.evaluate("anything", ctx)
        assert result.passed is True

    def test_empty_output(self):
        a = ContainsAllAssertion(value=["something"])
        ctx = make_context("")
        result = a.evaluate("", ctx)
        assert result.passed is False

    def test_returns_grading_result_with_reason(self):
        a = ContainsAllAssertion(value=["a"])
        ctx = make_context("a")
        result = a.evaluate("a", ctx)
        assert isinstance(result, GradingResult)
        assert len(result.reason) > 0


# ═════════════════════════════════════════════════════════════════════════════
# contains-any
# ═════════════════════════════════════════════════════════════════════════════


class TestContainsAnyAssertion:
    """AC-1: registered as 'contains-any', any substring present."""

    def test_type_attribute(self):
        a = ContainsAnyAssertion(value=["a", "b"])
        assert a.type == "contains-any"

    def test_one_present_passes(self):
        a = ContainsAnyAssertion(value=["xyz", "world"])
        ctx = make_context("Hello world")
        result = a.evaluate("Hello world", ctx)
        assert result.passed is True
        assert result.score == 1.0

    def test_none_present_fails(self):
        a = ContainsAnyAssertion(value=["abc", "xyz"])
        ctx = make_context("Hello world")
        result = a.evaluate("Hello world", ctx)
        assert result.passed is False
        assert result.score == 0.0

    def test_all_present_passes(self):
        a = ContainsAnyAssertion(value=["Hello", "world"])
        ctx = make_context("Hello world")
        result = a.evaluate("Hello world", ctx)
        assert result.passed is True

    def test_empty_list_fails(self):
        """No candidates to match — should fail."""
        a = ContainsAnyAssertion(value=[])
        ctx = make_context("anything")
        result = a.evaluate("anything", ctx)
        assert result.passed is False

    def test_empty_output(self):
        a = ContainsAnyAssertion(value=["something"])
        ctx = make_context("")
        result = a.evaluate("", ctx)
        assert result.passed is False

    def test_returns_grading_result(self):
        a = ContainsAnyAssertion(value=["a"])
        ctx = make_context("a")
        result = a.evaluate("a", ctx)
        assert isinstance(result, GradingResult)


# ═════════════════════════════════════════════════════════════════════════════
# starts-with
# ═════════════════════════════════════════════════════════════════════════════


class TestStartsWithAssertion:
    """AC-1: registered as 'starts-with', string prefix."""

    def test_type_attribute(self):
        a = StartsWithAssertion(value="Hello")
        assert a.type == "starts-with"

    def test_prefix_present_passes(self):
        a = StartsWithAssertion(value="Hello")
        ctx = make_context("Hello world")
        result = a.evaluate("Hello world", ctx)
        assert result.passed is True
        assert result.score == 1.0

    def test_prefix_absent_fails(self):
        a = StartsWithAssertion(value="Goodbye")
        ctx = make_context("Hello world")
        result = a.evaluate("Hello world", ctx)
        assert result.passed is False
        assert result.score == 0.0

    def test_case_sensitive(self):
        a = StartsWithAssertion(value="hello")
        ctx = make_context("Hello world")
        result = a.evaluate("Hello world", ctx)
        assert result.passed is False

    def test_empty_output(self):
        a = StartsWithAssertion(value="something")
        ctx = make_context("")
        result = a.evaluate("", ctx)
        assert result.passed is False

    def test_empty_prefix_always_passes(self):
        a = StartsWithAssertion(value="")
        ctx = make_context("anything")
        result = a.evaluate("anything", ctx)
        assert result.passed is True

    def test_returns_grading_result(self):
        a = StartsWithAssertion(value="x")
        ctx = make_context("x")
        result = a.evaluate("x", ctx)
        assert isinstance(result, GradingResult)


# ═════════════════════════════════════════════════════════════════════════════
# regex
# ═════════════════════════════════════════════════════════════════════════════


class TestRegexAssertion:
    """AC-1: registered as 'regex', regex match."""

    def test_type_attribute(self):
        a = RegexAssertion(value=r"\d+")
        assert a.type == "regex"

    def test_pattern_matches_passes(self):
        a = RegexAssertion(value=r"\d{3}-\d{4}")
        ctx = make_context("Call 555-1234 now")
        result = a.evaluate("Call 555-1234 now", ctx)
        assert result.passed is True
        assert result.score == 1.0

    def test_pattern_no_match_fails(self):
        a = RegexAssertion(value=r"\d{3}-\d{4}")
        ctx = make_context("No phone here")
        result = a.evaluate("No phone here", ctx)
        assert result.passed is False
        assert result.score == 0.0

    def test_full_regex_features(self):
        """Support anchors, groups, quantifiers."""
        a = RegexAssertion(value=r"^Hello.*world$")
        ctx = make_context("Hello beautiful world")
        result = a.evaluate("Hello beautiful world", ctx)
        assert result.passed is True

    def test_empty_output(self):
        a = RegexAssertion(value=r".+")
        ctx = make_context("")
        result = a.evaluate("", ctx)
        assert result.passed is False

    def test_case_sensitive_by_default(self):
        a = RegexAssertion(value=r"hello")
        ctx = make_context("HELLO")
        result = a.evaluate("HELLO", ctx)
        assert result.passed is False

    def test_invalid_regex_raises_or_fails(self):
        """Invalid regex pattern should either raise or return a failed result."""
        a = RegexAssertion(value=r"[invalid")
        ctx = make_context("test")
        try:
            result = a.evaluate("test", ctx)
            # If it doesn't raise, it should indicate failure
            assert result.passed is False
        except (ValueError, Exception):
            pass  # Raising is also acceptable

    def test_returns_grading_result(self):
        a = RegexAssertion(value=r"x")
        ctx = make_context("x")
        result = a.evaluate("x", ctx)
        assert isinstance(result, GradingResult)


# ═════════════════════════════════════════════════════════════════════════════
# word-count
# ═════════════════════════════════════════════════════════════════════════════


class TestWordCountAssertion:
    """AC-1: registered as 'word-count', count in range.

    Follows promptfoo wordCount patterns:
    - Single int = exact count
    - Dict with min/max = range
    """

    def test_type_attribute(self):
        a = WordCountAssertion(value=5)
        assert a.type == "word-count"

    # ── Exact count (int) ────────────────────────────────────────────────

    def test_exact_count_passes(self):
        a = WordCountAssertion(value=3)
        ctx = make_context("one two three")
        result = a.evaluate("one two three", ctx)
        assert result.passed is True
        assert result.score == 1.0

    def test_exact_count_fails_too_many(self):
        a = WordCountAssertion(value=2)
        ctx = make_context("one two three")
        result = a.evaluate("one two three", ctx)
        assert result.passed is False

    def test_exact_count_fails_too_few(self):
        a = WordCountAssertion(value=5)
        ctx = make_context("one two three")
        result = a.evaluate("one two three", ctx)
        assert result.passed is False

    # ── Range (dict) ─────────────────────────────────────────────────────

    def test_range_within_passes(self):
        a = WordCountAssertion(value={"min": 2, "max": 5})
        ctx = make_context("one two three")
        result = a.evaluate("one two three", ctx)
        assert result.passed is True

    def test_range_below_min_fails(self):
        a = WordCountAssertion(value={"min": 5, "max": 10})
        ctx = make_context("one two three")
        result = a.evaluate("one two three", ctx)
        assert result.passed is False

    def test_range_above_max_fails(self):
        a = WordCountAssertion(value={"min": 1, "max": 2})
        ctx = make_context("one two three")
        result = a.evaluate("one two three", ctx)
        assert result.passed is False

    def test_min_only(self):
        """Only min specified — no upper bound."""
        a = WordCountAssertion(value={"min": 2})
        ctx = make_context("one two three four five")
        result = a.evaluate("one two three four five", ctx)
        assert result.passed is True

    def test_max_only(self):
        """Only max specified — no lower bound."""
        a = WordCountAssertion(value={"max": 10})
        ctx = make_context("one two three")
        result = a.evaluate("one two three", ctx)
        assert result.passed is True

    def test_max_only_fails(self):
        a = WordCountAssertion(value={"max": 2})
        ctx = make_context("one two three")
        result = a.evaluate("one two three", ctx)
        assert result.passed is False

    # ── Whitespace edge cases (from promptfoo) ───────────────────────────

    def test_multiple_spaces(self):
        """Multiple spaces between words should not inflate count."""
        a = WordCountAssertion(value=3)
        ctx = make_context("one   two   three")
        result = a.evaluate("one   two   three", ctx)
        assert result.passed is True

    def test_newlines_as_separators(self):
        a = WordCountAssertion(value=3)
        ctx = make_context("one\ntwo\nthree")
        result = a.evaluate("one\ntwo\nthree", ctx)
        assert result.passed is True

    def test_tabs_as_separators(self):
        a = WordCountAssertion(value=3)
        ctx = make_context("one\ttwo\tthree")
        result = a.evaluate("one\ttwo\tthree", ctx)
        assert result.passed is True

    def test_empty_string_zero_words(self):
        a = WordCountAssertion(value=0)
        ctx = make_context("")
        result = a.evaluate("", ctx)
        assert result.passed is True

    def test_empty_string_nonzero_fails(self):
        a = WordCountAssertion(value=3)
        ctx = make_context("")
        result = a.evaluate("", ctx)
        assert result.passed is False

    # ── Error cases (from promptfoo) ─────────────────────────────────────

    def test_invalid_value_type_raises(self):
        """Non-int, non-dict value should raise or return failure."""
        a = WordCountAssertion(value="not a number")
        ctx = make_context("one two three")
        try:
            result = a.evaluate("one two three", ctx)
            assert result.passed is False
        except (TypeError, ValueError):
            pass

    def test_min_greater_than_max_raises(self):
        """min > max should raise or return failure."""
        a = WordCountAssertion(value={"min": 10, "max": 5})
        ctx = make_context("one two three")
        try:
            result = a.evaluate("one two three", ctx)
            assert result.passed is False
        except (ValueError, TypeError):
            pass

    def test_returns_grading_result_with_reason(self):
        a = WordCountAssertion(value=3)
        ctx = make_context("one two three")
        result = a.evaluate("one two three", ctx)
        assert isinstance(result, GradingResult)
        assert len(result.reason) > 0
