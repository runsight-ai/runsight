"""
Tests for the standalone condition engine module (runsight_core.conditions.engine).

Red-phase TDD: These tests define the contract for the condition engine extraction
from ConditionalBlock into a shared, reusable module. They import from the NEW
module path and should FAIL until the Green team implements the engine.

The engine evaluates conditions against a block's OWN result (no eval_source).
"""

import json

import pytest
from runsight_core.conditions.engine import (
    ALL_OPERATORS,
    Case,
    Condition,
    ConditionGroup,
    evaluate_condition,
    evaluate_condition_group,
    evaluate_output_conditions,
    resolve_dotted_path,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_case(case_id: str, conditions: list, combinator: str = "and") -> Case:
    """Shorthand to build a Case with a ConditionGroup."""
    return Case(
        case_id=case_id,
        condition_group=ConditionGroup(
            conditions=[Condition(**c) for c in conditions],
            combinator=combinator,
        ),
    )


# ===== resolve_dotted_path =====


class TestResolveDottedPath:
    """Tests for dot-notation key resolution into nested data."""

    def test_flat_key(self):
        """Flat key returns the top-level value."""
        data = {"status": "ok"}
        assert resolve_dotted_path(data, "status") == "ok"

    def test_two_level_nested(self):
        """Two-level dot path resolves correctly."""
        data = {"response": {"status": "ok"}}
        assert resolve_dotted_path(data, "response.status") == "ok"

    def test_three_level_nested(self):
        """Three-level dot path resolves correctly."""
        data = {"a": {"b": {"c": 42}}}
        assert resolve_dotted_path(data, "a.b.c") == 42

    def test_missing_key_returns_none(self):
        """Missing key returns None (not KeyError)."""
        data = {"status": "ok"}
        result = resolve_dotted_path(data, "nonexistent")
        assert result is None

    def test_missing_nested_key_returns_none(self):
        """Missing intermediate key in nested path returns None."""
        data = {"a": {"b": 1}}
        result = resolve_dotted_path(data, "a.x.y")
        assert result is None

    def test_non_dict_intermediate_returns_none(self):
        """Non-dict at intermediate level returns None."""
        data = {"a": "string_value"}
        result = resolve_dotted_path(data, "a.b")
        assert result is None

    def test_empty_dict(self):
        """Empty dict returns None for any key."""
        assert resolve_dotted_path({}, "key") is None

    def test_value_is_none(self):
        """Key that exists but maps to None returns None."""
        data = {"key": None}
        assert resolve_dotted_path(data, "key") is None


# ===== ALL_OPERATORS constant =====


class TestOperatorConstants:
    """Verify the operator set exported by the engine."""

    def test_all_operators_contains_string_operators(self):
        """String operators are present."""
        for op in (
            "equals",
            "not_equals",
            "contains",
            "not_contains",
            "starts_with",
            "ends_with",
            "is_empty",
            "not_empty",
            "regex",
        ):
            assert op in ALL_OPERATORS, f"Missing string operator: {op}"

    def test_all_operators_contains_numeric_operators(self):
        """Numeric comparison operators are present."""
        for op in ("eq", "neq", "gt", "lt", "gte", "lte"):
            assert op in ALL_OPERATORS, f"Missing numeric operator: {op}"

    def test_all_operators_contains_universal_operators(self):
        """Universal operators (exists / not_exists) are present."""
        for op in ("exists", "not_exists"):
            assert op in ALL_OPERATORS, f"Missing universal operator: {op}"


# ===== evaluate_condition — String Operators =====


class TestEvaluateConditionStringOperators:
    """Single-condition evaluation for all string operators."""

    def test_equals_match(self):
        """'equals' returns True when values match."""
        c = Condition(eval_key="status", operator="equals", value="ok")
        assert evaluate_condition(c, {"status": "ok"}) is True

    def test_equals_no_match(self):
        """'equals' returns False when values differ."""
        c = Condition(eval_key="status", operator="equals", value="ok")
        assert evaluate_condition(c, {"status": "error"}) is False

    def test_not_equals_match(self):
        """'not_equals' returns True when values differ."""
        c = Condition(eval_key="status", operator="not_equals", value="ok")
        assert evaluate_condition(c, {"status": "error"}) is True

    def test_not_equals_no_match(self):
        """'not_equals' returns False when values are equal."""
        c = Condition(eval_key="status", operator="not_equals", value="ok")
        assert evaluate_condition(c, {"status": "ok"}) is False

    def test_contains_match(self):
        """'contains' returns True when substring is present."""
        c = Condition(eval_key="msg", operator="contains", value="world")
        assert evaluate_condition(c, {"msg": "hello world"}) is True

    def test_contains_no_match(self):
        """'contains' returns False when substring is absent."""
        c = Condition(eval_key="msg", operator="contains", value="xyz")
        assert evaluate_condition(c, {"msg": "hello world"}) is False

    def test_not_contains_match(self):
        """'not_contains' returns True when substring is absent."""
        c = Condition(eval_key="msg", operator="not_contains", value="xyz")
        assert evaluate_condition(c, {"msg": "hello"}) is True

    def test_not_contains_no_match(self):
        """'not_contains' returns False when substring is present."""
        c = Condition(eval_key="msg", operator="not_contains", value="ello")
        assert evaluate_condition(c, {"msg": "hello"}) is False

    def test_starts_with_match(self):
        """'starts_with' returns True when value starts with prefix."""
        c = Condition(eval_key="msg", operator="starts_with", value="hel")
        assert evaluate_condition(c, {"msg": "hello"}) is True

    def test_starts_with_no_match(self):
        """'starts_with' returns False when prefix is wrong."""
        c = Condition(eval_key="msg", operator="starts_with", value="xyz")
        assert evaluate_condition(c, {"msg": "hello"}) is False

    def test_ends_with_match(self):
        """'ends_with' returns True when value ends with suffix."""
        c = Condition(eval_key="msg", operator="ends_with", value="llo")
        assert evaluate_condition(c, {"msg": "hello"}) is True

    def test_ends_with_no_match(self):
        """'ends_with' returns False when suffix is wrong."""
        c = Condition(eval_key="msg", operator="ends_with", value="xyz")
        assert evaluate_condition(c, {"msg": "hello"}) is False

    def test_is_empty_true_for_empty_string(self):
        """'is_empty' returns True for empty string."""
        c = Condition(eval_key="val", operator="is_empty")
        assert evaluate_condition(c, {"val": ""}) is True

    def test_is_empty_true_for_none(self):
        """'is_empty' returns True for None (missing key)."""
        c = Condition(eval_key="val", operator="is_empty")
        assert evaluate_condition(c, {}) is True

    def test_is_empty_false_for_nonempty(self):
        """'is_empty' returns False for non-empty string."""
        c = Condition(eval_key="val", operator="is_empty")
        assert evaluate_condition(c, {"val": "data"}) is False

    def test_not_empty_true(self):
        """'not_empty' returns True for non-empty string."""
        c = Condition(eval_key="val", operator="not_empty")
        assert evaluate_condition(c, {"val": "data"}) is True

    def test_not_empty_false(self):
        """'not_empty' returns False for empty string."""
        c = Condition(eval_key="val", operator="not_empty")
        assert evaluate_condition(c, {"val": ""}) is False

    def test_regex_match(self):
        """'regex' returns True when pattern matches."""
        c = Condition(eval_key="code", operator="regex", value=r"^\d{3}$")
        assert evaluate_condition(c, {"code": "200"}) is True

    def test_regex_no_match(self):
        """'regex' returns False when pattern does not match."""
        c = Condition(eval_key="code", operator="regex", value=r"^\d{3}$")
        assert evaluate_condition(c, {"code": "20"}) is False

    def test_regex_invalid_pattern_raises(self):
        """'regex' with invalid pattern raises ValueError."""
        c = Condition(eval_key="code", operator="regex", value="[invalid")
        with pytest.raises(ValueError, match="[Rr]egex|[Pp]attern"):
            evaluate_condition(c, {"code": "test"})


# ===== evaluate_condition — Numeric Operators =====


class TestEvaluateConditionNumericOperators:
    """Single-condition evaluation for numeric operators with type coercion."""

    def test_eq_numeric(self):
        """'eq' returns True when numeric values are equal."""
        c = Condition(eval_key="count", operator="eq", value="10")
        assert evaluate_condition(c, {"count": "10"}) is True

    def test_eq_numeric_different(self):
        """'eq' returns False when numeric values differ."""
        c = Condition(eval_key="count", operator="eq", value="10")
        assert evaluate_condition(c, {"count": "20"}) is False

    def test_neq_numeric(self):
        """'neq' returns True when numeric values differ."""
        c = Condition(eval_key="count", operator="neq", value="10")
        assert evaluate_condition(c, {"count": "20"}) is True

    def test_gt_numeric(self):
        """'gt' returns True when actual > expected."""
        c = Condition(eval_key="score", operator="gt", value="50")
        assert evaluate_condition(c, {"score": "75"}) is True

    def test_gt_numeric_equal(self):
        """'gt' returns False when actual == expected."""
        c = Condition(eval_key="score", operator="gt", value="50")
        assert evaluate_condition(c, {"score": "50"}) is False

    def test_lt_numeric(self):
        """'lt' returns True when actual < expected."""
        c = Condition(eval_key="score", operator="lt", value="50")
        assert evaluate_condition(c, {"score": "25"}) is True

    def test_lt_numeric_equal(self):
        """'lt' returns False when actual == expected."""
        c = Condition(eval_key="score", operator="lt", value="50")
        assert evaluate_condition(c, {"score": "50"}) is False

    def test_gte_numeric_greater(self):
        """'gte' returns True when actual > expected."""
        c = Condition(eval_key="score", operator="gte", value="50")
        assert evaluate_condition(c, {"score": "75"}) is True

    def test_gte_numeric_equal(self):
        """'gte' returns True when actual == expected."""
        c = Condition(eval_key="score", operator="gte", value="50")
        assert evaluate_condition(c, {"score": "50"}) is True

    def test_gte_numeric_less(self):
        """'gte' returns False when actual < expected."""
        c = Condition(eval_key="score", operator="gte", value="50")
        assert evaluate_condition(c, {"score": "25"}) is False

    def test_lte_numeric_less(self):
        """'lte' returns True when actual < expected."""
        c = Condition(eval_key="score", operator="lte", value="50")
        assert evaluate_condition(c, {"score": "25"}) is True

    def test_lte_numeric_equal(self):
        """'lte' returns True when actual == expected."""
        c = Condition(eval_key="score", operator="lte", value="50")
        assert evaluate_condition(c, {"score": "50"}) is True

    def test_lte_numeric_greater(self):
        """'lte' returns False when actual > expected."""
        c = Condition(eval_key="score", operator="lte", value="50")
        assert evaluate_condition(c, {"score": "75"}) is False

    def test_numeric_coercion_float(self):
        """Numeric operators handle float strings."""
        c = Condition(eval_key="price", operator="gt", value="9.99")
        assert evaluate_condition(c, {"price": "10.50"}) is True

    def test_numeric_coercion_integer_values(self):
        """Numeric operators handle actual integer values (not strings)."""
        c = Condition(eval_key="count", operator="eq", value=10)
        assert evaluate_condition(c, {"count": 10}) is True


# ===== evaluate_condition — Universal Operators =====


class TestEvaluateConditionUniversalOperators:
    """Tests for exists/not_exists operators that check key presence."""

    def test_exists_true(self):
        """'exists' returns True when key is present (even if value is falsy)."""
        c = Condition(eval_key="key", operator="exists")
        assert evaluate_condition(c, {"key": ""}) is True

    def test_exists_false(self):
        """'exists' returns False when key is absent."""
        c = Condition(eval_key="key", operator="exists")
        assert evaluate_condition(c, {}) is False

    def test_exists_with_none_value(self):
        """'exists' returns True when key exists with None value.

        Implementation note: The `exists` operator must check key *presence*,
        not the resolved value.  `resolve_dotted_path` returns a tuple
        ``(found: bool, value: Any)``.  For a key that exists with a ``None``
        value the return is ``(True, None)``, whereas a missing key yields
        ``(False, None)``.  The ``exists`` operator should use the ``found``
        boolean — not the value — so that ``{"key": None}`` is correctly
        detected as "key exists".
        """
        c = Condition(eval_key="key", operator="exists")
        assert evaluate_condition(c, {"key": None}) is True

    def test_not_exists_true(self):
        """'not_exists' returns True when key is absent."""
        c = Condition(eval_key="key", operator="not_exists")
        assert evaluate_condition(c, {}) is True

    def test_not_exists_false(self):
        """'not_exists' returns False when key is present."""
        c = Condition(eval_key="key", operator="not_exists")
        assert evaluate_condition(c, {"key": "val"}) is False


# ===== evaluate_condition — Edge Cases =====


class TestEvaluateConditionEdgeCases:
    """Edge cases: unknown operator, missing key, JSON auto-parse."""

    def test_unknown_operator_raises(self):
        """Unknown operator raises ValueError."""
        c = Condition(eval_key="x", operator="banana", value="y")
        with pytest.raises(ValueError, match="[Uu]nknown.*operator|[Uu]nsupported.*operator"):
            evaluate_condition(c, {"x": "y"})

    def test_missing_key_treated_as_none(self):
        """Missing key in data resolves to None for comparison."""
        c = Condition(eval_key="missing", operator="equals", value="something")
        # None != "something" -> False
        assert evaluate_condition(c, {"other": "data"}) is False

    def test_json_auto_parse_string_result(self):
        """If block_result is a JSON string, it should be auto-parsed for dot-path access."""
        json_str = json.dumps({"status": "ok", "count": 5})
        c = Condition(eval_key="status", operator="equals", value="ok")
        assert evaluate_condition(c, json_str) is True

    def test_json_auto_parse_nested(self):
        """JSON auto-parse supports nested dot-path access."""
        json_str = json.dumps({"response": {"code": 200}})
        c = Condition(eval_key="response.code", operator="eq", value="200")
        assert evaluate_condition(c, json_str) is True

    def test_non_json_string_result_used_as_is(self):
        """Non-JSON string result: eval_key is ignored, the whole string is the value."""
        # When result is a plain string (not JSON), using eval_key should still work
        # by treating the result as the value itself if eval_key doesn't resolve
        c = Condition(eval_key="status", operator="equals", value="ok")
        # "plain text" is not JSON, key "status" won't resolve -> None != "ok" -> False
        assert evaluate_condition(c, "plain text") is False

    def test_numeric_coercion_non_numeric_string(self):
        """Non-numeric string with numeric operator: should not crash, returns False or warns."""
        c = Condition(eval_key="val", operator="gt", value="10")
        # "abc" can't be coerced to number
        # The engine should either return False or raise — we accept False with warning
        result = evaluate_condition(c, {"val": "abc"})
        assert result is False


# ===== evaluate_condition_group =====


class TestEvaluateConditionGroup:
    """Tests for AND/OR combinator logic on condition groups."""

    def test_and_all_true(self):
        """AND combinator: all conditions True -> True."""
        group = ConditionGroup(
            conditions=[
                Condition(eval_key="a", operator="equals", value="1"),
                Condition(eval_key="b", operator="equals", value="2"),
            ],
            combinator="and",
        )
        assert evaluate_condition_group(group, {"a": "1", "b": "2"}) is True

    def test_and_one_false(self):
        """AND combinator: one condition False -> False."""
        group = ConditionGroup(
            conditions=[
                Condition(eval_key="a", operator="equals", value="1"),
                Condition(eval_key="b", operator="equals", value="wrong"),
            ],
            combinator="and",
        )
        assert evaluate_condition_group(group, {"a": "1", "b": "2"}) is False

    def test_or_one_true(self):
        """OR combinator: one condition True -> True."""
        group = ConditionGroup(
            conditions=[
                Condition(eval_key="a", operator="equals", value="wrong"),
                Condition(eval_key="b", operator="equals", value="2"),
            ],
            combinator="or",
        )
        assert evaluate_condition_group(group, {"a": "1", "b": "2"}) is True

    def test_or_all_false(self):
        """OR combinator: all conditions False -> False."""
        group = ConditionGroup(
            conditions=[
                Condition(eval_key="a", operator="equals", value="wrong"),
                Condition(eval_key="b", operator="equals", value="wrong"),
            ],
            combinator="or",
        )
        assert evaluate_condition_group(group, {"a": "1", "b": "2"}) is False

    def test_unknown_combinator_raises(self):
        """Unknown combinator raises ValueError."""
        group = ConditionGroup(
            conditions=[
                Condition(eval_key="a", operator="equals", value="1"),
            ],
            combinator="xor",
        )
        with pytest.raises(ValueError, match="[Uu]nknown.*combinator|[Uu]nsupported.*combinator"):
            evaluate_condition_group(group, {"a": "1"})

    def test_default_combinator_is_and(self):
        """Default combinator should be 'and'."""
        group = ConditionGroup(
            conditions=[
                Condition(eval_key="a", operator="equals", value="1"),
                Condition(eval_key="b", operator="equals", value="2"),
            ],
        )
        assert group.combinator == "and"
        assert evaluate_condition_group(group, {"a": "1", "b": "2"}) is True


# ===== evaluate_output_conditions =====


class TestEvaluateOutputConditions:
    """Tests for the top-level evaluate_output_conditions function."""

    def test_first_match_wins(self):
        """When multiple cases match, the first one wins."""
        cases = [
            _make_case("first", [{"eval_key": "status", "operator": "equals", "value": "ok"}]),
            _make_case("second", [{"eval_key": "status", "operator": "equals", "value": "ok"}]),
        ]
        decision, warnings = evaluate_output_conditions(cases, {"status": "ok"})
        assert decision == "first"

    def test_second_case_matches(self):
        """When first case fails, second is evaluated and can match."""
        cases = [
            _make_case("first", [{"eval_key": "status", "operator": "equals", "value": "error"}]),
            _make_case("second", [{"eval_key": "status", "operator": "equals", "value": "ok"}]),
        ]
        decision, warnings = evaluate_output_conditions(cases, {"status": "ok"})
        assert decision == "second"

    def test_default_fallback_when_no_match(self):
        """When no case matches, returns the default value."""
        cases = [
            _make_case("only", [{"eval_key": "status", "operator": "equals", "value": "error"}]),
        ]
        decision, warnings = evaluate_output_conditions(cases, {"status": "ok"}, default="fallback")
        assert decision == "fallback"

    def test_empty_cases_returns_default(self):
        """Empty cases list returns default immediately."""
        decision, warnings = evaluate_output_conditions([], {"status": "ok"}, default="none")
        assert decision == "none"

    def test_default_value_is_default_string(self):
        """Default parameter defaults to 'default'."""
        decision, warnings = evaluate_output_conditions([], {})
        assert decision == "default"

    def test_returns_tuple_of_decision_and_warnings(self):
        """Return type is a tuple of (str, List[str])."""
        decision, warnings = evaluate_output_conditions([], {})
        assert isinstance(decision, str)
        assert isinstance(warnings, list)

    def test_json_string_block_result(self):
        """block_result as JSON string is auto-parsed for condition evaluation."""
        cases = [
            _make_case("match", [{"eval_key": "result", "operator": "equals", "value": "pass"}]),
        ]
        json_result = json.dumps({"result": "pass"})
        decision, warnings = evaluate_output_conditions(cases, json_result)
        assert decision == "match"

    def test_nested_dot_path_in_cases(self):
        """Dot-path eval_key works inside cases for nested block results."""
        cases = [
            _make_case("deep", [{"eval_key": "a.b.c", "operator": "equals", "value": "found"}]),
        ]
        decision, warnings = evaluate_output_conditions(cases, {"a": {"b": {"c": "found"}}})
        assert decision == "deep"

    def test_and_combinator_in_case(self):
        """Case with AND combinator requires all conditions to pass."""
        cases = [
            _make_case(
                "both",
                [
                    {"eval_key": "a", "operator": "equals", "value": "1"},
                    {"eval_key": "b", "operator": "equals", "value": "2"},
                ],
                combinator="and",
            ),
        ]
        # Both match
        decision, _ = evaluate_output_conditions(cases, {"a": "1", "b": "2"})
        assert decision == "both"

        # One fails -> default
        decision, _ = evaluate_output_conditions(cases, {"a": "1", "b": "wrong"})
        assert decision == "default"

    def test_or_combinator_in_case(self):
        """Case with OR combinator requires at least one condition to pass."""
        cases = [
            _make_case(
                "either",
                [
                    {"eval_key": "a", "operator": "equals", "value": "1"},
                    {"eval_key": "b", "operator": "equals", "value": "2"},
                ],
                combinator="or",
            ),
        ]
        # Only second matches
        decision, _ = evaluate_output_conditions(cases, {"a": "wrong", "b": "2"})
        assert decision == "either"

    def test_numeric_coercion_warning(self):
        """Non-numeric value with numeric operator produces a warning."""
        cases = [
            _make_case("num", [{"eval_key": "val", "operator": "gt", "value": "10"}]),
        ]
        decision, warnings = evaluate_output_conditions(cases, {"val": "not_a_number"})
        assert decision == "default"
        # Should have at least one warning about coercion
        assert len(warnings) > 0

    def test_multiple_cases_complex_routing(self):
        """Complex scenario: three cases, second one matches."""
        cases = [
            _make_case("high", [{"eval_key": "score", "operator": "gt", "value": "90"}]),
            _make_case("medium", [{"eval_key": "score", "operator": "gte", "value": "50"}]),
            _make_case("low", [{"eval_key": "score", "operator": "lt", "value": "50"}]),
        ]
        decision, _ = evaluate_output_conditions(cases, {"score": "75"})
        assert decision == "medium"

    def test_exists_operator_in_case(self):
        """Case using 'exists' operator matches when key is present."""
        cases = [
            _make_case("has_error", [{"eval_key": "error", "operator": "exists"}]),
            _make_case("no_error", [{"eval_key": "error", "operator": "not_exists"}]),
        ]
        decision, _ = evaluate_output_conditions(cases, {"error": "something went wrong"})
        assert decision == "has_error"

        decision, _ = evaluate_output_conditions(cases, {"result": "ok"})
        assert decision == "no_error"
