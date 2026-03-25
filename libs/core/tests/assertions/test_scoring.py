"""Tests for AssertionsResult scoring aggregation."""

from runsight_core.assertions.base import GradingResult
from runsight_core.assertions.scoring import AssertionsResult


class TestAssertionsResultAddResult:
    def test_add_single_result(self):
        agg = AssertionsResult()
        result = GradingResult(passed=True, score=0.8, reason="Good")
        agg.add_result(result, weight=1.0)
        assert len(agg.results) == 1
        assert agg.results[0] is result

    def test_add_multiple_results(self):
        agg = AssertionsResult()
        r1 = GradingResult(passed=True, score=1.0, reason="A")
        r2 = GradingResult(passed=False, score=0.4, reason="B")
        agg.add_result(r1, weight=1.0)
        agg.add_result(r2, weight=1.0)
        assert len(agg.results) == 2

    def test_add_result_accumulates_total_score(self):
        agg = AssertionsResult()
        agg.add_result(GradingResult(passed=True, score=0.8, reason="A"), weight=2.0)
        agg.add_result(GradingResult(passed=True, score=0.6, reason="B"), weight=1.0)
        # total_score = 0.8*2 + 0.6*1 = 2.2
        assert abs(agg.total_score - 2.2) < 1e-9

    def test_add_result_accumulates_total_weight(self):
        agg = AssertionsResult()
        agg.add_result(GradingResult(passed=True, score=0.5, reason="A"), weight=3.0)
        agg.add_result(GradingResult(passed=True, score=0.5, reason="B"), weight=2.0)
        assert abs(agg.total_weight - 5.0) < 1e-9

    def test_add_result_collects_named_scores(self):
        agg = AssertionsResult()
        r = GradingResult(
            passed=True,
            score=0.9,
            reason="OK",
            named_scores={"accuracy": 0.95, "fluency": 0.85},
        )
        agg.add_result(r, weight=1.0)
        assert agg.named_scores["accuracy"] == 0.95
        assert agg.named_scores["fluency"] == 0.85


class TestAssertionsResultAggregateScore:
    def test_single_result_aggregate(self):
        agg = AssertionsResult()
        agg.add_result(GradingResult(passed=True, score=0.7, reason="OK"), weight=1.0)
        assert abs(agg.aggregate_score - 0.7) < 1e-9

    def test_weighted_average(self):
        """AC-6: aggregate_score = sum(score * weight) / sum(weight)"""
        agg = AssertionsResult()
        agg.add_result(GradingResult(passed=True, score=1.0, reason="A"), weight=3.0)
        agg.add_result(GradingResult(passed=False, score=0.0, reason="B"), weight=1.0)
        # (1.0*3 + 0.0*1) / (3+1) = 0.75
        assert abs(agg.aggregate_score - 0.75) < 1e-9

    def test_equal_weights(self):
        agg = AssertionsResult()
        agg.add_result(GradingResult(passed=True, score=0.8, reason="A"), weight=1.0)
        agg.add_result(GradingResult(passed=True, score=0.6, reason="B"), weight=1.0)
        # (0.8 + 0.6) / 2 = 0.7
        assert abs(agg.aggregate_score - 0.7) < 1e-9

    def test_zero_total_weight_returns_zero(self):
        """When no weighted results exist, aggregate_score should be 0.0."""
        agg = AssertionsResult()
        assert agg.aggregate_score == 0.0

    def test_weight_zero_excluded_from_aggregate(self):
        """AC-8: Weight=0 assertions do NOT contribute to aggregate score."""
        agg = AssertionsResult()
        agg.add_result(GradingResult(passed=True, score=1.0, reason="Weighted"), weight=2.0)
        agg.add_result(
            GradingResult(
                passed=False,
                score=0.0,
                reason="Info only",
                named_scores={"info_metric": 0.42},
            ),
            weight=0.0,
        )
        # Only the weight=2.0 result counts: 1.0*2 / 2 = 1.0
        assert abs(agg.aggregate_score - 1.0) < 1e-9

    def test_weight_zero_still_contributes_named_scores(self):
        """AC-8: Weight=0 assertions still contribute to named_scores."""
        agg = AssertionsResult()
        agg.add_result(GradingResult(passed=True, score=1.0, reason="Main"), weight=1.0)
        agg.add_result(
            GradingResult(
                passed=True,
                score=0.5,
                reason="Metadata",
                named_scores={"side_metric": 0.77},
            ),
            weight=0.0,
        )
        assert "side_metric" in agg.named_scores
        assert agg.named_scores["side_metric"] == 0.77


class TestAssertionsResultPassed:
    def test_passed_with_threshold_above(self):
        """AC-7: passed(threshold) returns True if aggregate_score >= threshold."""
        agg = AssertionsResult()
        agg.add_result(GradingResult(passed=True, score=0.9, reason="OK"), weight=1.0)
        assert agg.passed(threshold=0.8) is True

    def test_passed_with_threshold_below(self):
        """AC-7: passed(threshold) returns False if aggregate_score < threshold."""
        agg = AssertionsResult()
        agg.add_result(GradingResult(passed=False, score=0.3, reason="Bad"), weight=1.0)
        assert agg.passed(threshold=0.5) is False

    def test_passed_with_threshold_exact(self):
        """AC-7: passed(threshold) returns True when aggregate_score == threshold."""
        agg = AssertionsResult()
        agg.add_result(GradingResult(passed=True, score=0.5, reason="Borderline"), weight=1.0)
        assert agg.passed(threshold=0.5) is True

    def test_passed_no_threshold_all_passed(self):
        """When threshold is None, passed() returns True if all individual results passed."""
        agg = AssertionsResult()
        agg.add_result(GradingResult(passed=True, score=1.0, reason="A"), weight=1.0)
        agg.add_result(GradingResult(passed=True, score=0.8, reason="B"), weight=1.0)
        assert agg.passed(threshold=None) is True

    def test_passed_no_threshold_one_failed(self):
        """When threshold is None, passed() returns False if any individual result failed."""
        agg = AssertionsResult()
        agg.add_result(GradingResult(passed=True, score=1.0, reason="A"), weight=1.0)
        agg.add_result(GradingResult(passed=False, score=0.0, reason="B"), weight=1.0)
        assert agg.passed(threshold=None) is False

    def test_passed_default_threshold_is_none(self):
        """Calling passed() with no arguments should behave as threshold=None."""
        agg = AssertionsResult()
        agg.add_result(GradingResult(passed=True, score=0.9, reason="OK"), weight=1.0)
        assert agg.passed() is True

    def test_passed_no_results(self):
        """With no results, passed() should return True (vacuously true)."""
        agg = AssertionsResult()
        assert agg.passed() is True


class TestAssertionsResultInitialState:
    def test_initial_total_score_is_zero(self):
        agg = AssertionsResult()
        assert agg.total_score == 0.0

    def test_initial_total_weight_is_zero(self):
        agg = AssertionsResult()
        assert agg.total_weight == 0.0

    def test_initial_results_is_empty(self):
        agg = AssertionsResult()
        assert agg.results == []

    def test_initial_named_scores_is_empty(self):
        agg = AssertionsResult()
        assert agg.named_scores == {}

    def test_instances_do_not_share_mutable_defaults(self):
        """Each AssertionsResult instance should have independent mutable fields."""
        a = AssertionsResult()
        b = AssertionsResult()
        a.add_result(GradingResult(passed=True, score=1.0, reason="X"), weight=1.0)
        assert len(b.results) == 0
        assert b.total_score == 0.0
