"""
Comprehensive unit tests for ConditionalBlock, Condition, ConditionGroup, Case.

Coverage:
 - All 15 operators
 - AND combinator (all must pass)
 - OR combinator (any must pass)
 - First-match-wins (short-circuit; second case not reached when first matches)
 - Default fallback when no case matches
 - Missing eval_source -> descriptive ValueError
 - Dot-notation nested key access
 - JSON auto-parse of string results
 - Numeric type coercion
 - is_empty / not_empty with None, "", [], {}
 - exists / not_exists
 - regex operator (valid and invalid pattern)
 - State immutability (model_copy, no mutation)
 - Message appended to state.messages
 - cost/tokens unchanged (no LLM calls)
"""

import json

import pytest

from runsight_core.blocks.implementations import (
    Case,
    Condition,
    ConditionGroup,
    ConditionalBlock,
)
from runsight_core.state import WorkflowState


# ── Helpers ──────────────────────────────────────────────────────────────────


def _state(**results) -> WorkflowState:
    """Create a minimal WorkflowState with the given results dict."""
    return WorkflowState(results={k: v for k, v in results.items()})


def _simple_case(
    case_id: str,
    eval_source: str,
    eval_key: str,
    operator: str,
    value=None,
    combinator: str = "and",
) -> Case:
    """Build a single-condition Case for concise test construction."""
    return Case(
        case_id=case_id,
        condition_group=ConditionGroup(
            conditions=[
                Condition(
                    eval_source=eval_source,
                    eval_key=eval_key,
                    operator=operator,
                    value=value,
                )
            ],
            combinator=combinator,
        ),
    )


# ── String operators ─────────────────────────────────────────────────────────


class TestStringOperators:
    @pytest.mark.asyncio
    async def test_equals_match(self):
        block = ConditionalBlock("b", [_simple_case("yes", "src", "status", "equals", "ok")])
        state = _state(src=json.dumps({"status": "ok"}))
        out = await block.execute(state)
        assert out.results["b"] == "yes"
        assert out.metadata["b_decision"] == "yes"

    @pytest.mark.asyncio
    async def test_equals_no_match(self):
        block = ConditionalBlock(
            "b", [_simple_case("yes", "src", "status", "equals", "ok")], default="no"
        )
        state = _state(src=json.dumps({"status": "fail"}))
        out = await block.execute(state)
        assert out.results["b"] == "no"

    @pytest.mark.asyncio
    async def test_not_equals_match(self):
        block = ConditionalBlock("b", [_simple_case("diff", "src", "val", "not_equals", "x")])
        state = _state(src=json.dumps({"val": "y"}))
        out = await block.execute(state)
        assert out.results["b"] == "diff"

    @pytest.mark.asyncio
    async def test_not_equals_no_match(self):
        block = ConditionalBlock(
            "b", [_simple_case("diff", "src", "val", "not_equals", "x")], default="same"
        )
        state = _state(src=json.dumps({"val": "x"}))
        out = await block.execute(state)
        assert out.results["b"] == "same"

    @pytest.mark.asyncio
    async def test_contains_match(self):
        block = ConditionalBlock("b", [_simple_case("found", "src", "text", "contains", "hello")])
        state = _state(src=json.dumps({"text": "say hello world"}))
        out = await block.execute(state)
        assert out.results["b"] == "found"

    @pytest.mark.asyncio
    async def test_contains_no_match(self):
        block = ConditionalBlock(
            "b", [_simple_case("found", "src", "text", "contains", "bye")], default="notfound"
        )
        state = _state(src=json.dumps({"text": "say hello world"}))
        out = await block.execute(state)
        assert out.results["b"] == "notfound"

    @pytest.mark.asyncio
    async def test_not_contains_match(self):
        block = ConditionalBlock("b", [_simple_case("ok", "src", "text", "not_contains", "error")])
        state = _state(src=json.dumps({"text": "everything is fine"}))
        out = await block.execute(state)
        assert out.results["b"] == "ok"

    @pytest.mark.asyncio
    async def test_not_contains_no_match(self):
        block = ConditionalBlock(
            "b", [_simple_case("ok", "src", "text", "not_contains", "error")], default="bad"
        )
        state = _state(src=json.dumps({"text": "there was an error here"}))
        out = await block.execute(state)
        assert out.results["b"] == "bad"

    @pytest.mark.asyncio
    async def test_starts_with_match(self):
        block = ConditionalBlock("b", [_simple_case("sw", "src", "msg", "starts_with", "Hello")])
        state = _state(src=json.dumps({"msg": "Hello world"}))
        out = await block.execute(state)
        assert out.results["b"] == "sw"

    @pytest.mark.asyncio
    async def test_starts_with_no_match(self):
        block = ConditionalBlock(
            "b", [_simple_case("sw", "src", "msg", "starts_with", "Hi")], default="no"
        )
        state = _state(src=json.dumps({"msg": "Hello world"}))
        out = await block.execute(state)
        assert out.results["b"] == "no"

    @pytest.mark.asyncio
    async def test_ends_with_match(self):
        block = ConditionalBlock("b", [_simple_case("ew", "src", "msg", "ends_with", "world")])
        state = _state(src=json.dumps({"msg": "Hello world"}))
        out = await block.execute(state)
        assert out.results["b"] == "ew"

    @pytest.mark.asyncio
    async def test_ends_with_no_match(self):
        block = ConditionalBlock(
            "b", [_simple_case("ew", "src", "msg", "ends_with", "earth")], default="no"
        )
        state = _state(src=json.dumps({"msg": "Hello world"}))
        out = await block.execute(state)
        assert out.results["b"] == "no"


# ── is_empty / not_empty ─────────────────────────────────────────────────────


class TestIsEmptyNotEmpty:
    @pytest.mark.asyncio
    async def test_is_empty_with_none(self):
        """Key exists but value is JSON null (None after parse)."""
        block = ConditionalBlock("b", [_simple_case("empty", "src", "val", "is_empty")])
        state = _state(src=json.dumps({"val": None}))
        out = await block.execute(state)
        assert out.results["b"] == "empty"

    @pytest.mark.asyncio
    async def test_is_empty_with_empty_string(self):
        block = ConditionalBlock("b", [_simple_case("empty", "src", "val", "is_empty")])
        state = _state(src=json.dumps({"val": ""}))
        out = await block.execute(state)
        assert out.results["b"] == "empty"

    @pytest.mark.asyncio
    async def test_is_empty_with_empty_list(self):
        block = ConditionalBlock("b", [_simple_case("empty", "src", "val", "is_empty")])
        state = _state(src=json.dumps({"val": []}))
        out = await block.execute(state)
        assert out.results["b"] == "empty"

    @pytest.mark.asyncio
    async def test_is_empty_with_empty_dict(self):
        block = ConditionalBlock("b", [_simple_case("empty", "src", "val", "is_empty")])
        state = _state(src=json.dumps({"val": {}}))
        out = await block.execute(state)
        assert out.results["b"] == "empty"

    @pytest.mark.asyncio
    async def test_is_empty_with_nonempty_string(self):
        block = ConditionalBlock(
            "b", [_simple_case("empty", "src", "val", "is_empty")], default="notempty"
        )
        state = _state(src=json.dumps({"val": "hello"}))
        out = await block.execute(state)
        assert out.results["b"] == "notempty"

    @pytest.mark.asyncio
    async def test_not_empty_with_nonempty_string(self):
        block = ConditionalBlock("b", [_simple_case("ok", "src", "val", "not_empty")])
        state = _state(src=json.dumps({"val": "data"}))
        out = await block.execute(state)
        assert out.results["b"] == "ok"

    @pytest.mark.asyncio
    async def test_not_empty_with_none_returns_false(self):
        block = ConditionalBlock(
            "b", [_simple_case("ok", "src", "val", "not_empty")], default="fallback"
        )
        state = _state(src=json.dumps({"val": None}))
        out = await block.execute(state)
        assert out.results["b"] == "fallback"

    @pytest.mark.asyncio
    async def test_not_empty_with_empty_string_returns_false(self):
        block = ConditionalBlock(
            "b", [_simple_case("ok", "src", "val", "not_empty")], default="fallback"
        )
        state = _state(src=json.dumps({"val": ""}))
        out = await block.execute(state)
        assert out.results["b"] == "fallback"

    @pytest.mark.asyncio
    async def test_not_empty_with_nonempty_list(self):
        block = ConditionalBlock("b", [_simple_case("ok", "src", "val", "not_empty")])
        state = _state(src=json.dumps({"val": [1, 2]}))
        out = await block.execute(state)
        assert out.results["b"] == "ok"

    @pytest.mark.asyncio
    async def test_is_empty_missing_key_treated_as_none(self):
        """Key not present in parsed result — treated as None, so is_empty is True."""
        block = ConditionalBlock("b", [_simple_case("empty", "src", "missing_key", "is_empty")])
        state = _state(src=json.dumps({"other": "val"}))
        out = await block.execute(state)
        assert out.results["b"] == "empty"


# ── Numeric operators ─────────────────────────────────────────────────────────


class TestNumericOperators:
    @pytest.mark.asyncio
    async def test_eq_match(self):
        block = ConditionalBlock("b", [_simple_case("hit", "src", "score", "eq", "42")])
        state = _state(src=json.dumps({"score": 42}))
        out = await block.execute(state)
        assert out.results["b"] == "hit"

    @pytest.mark.asyncio
    async def test_neq_match(self):
        block = ConditionalBlock("b", [_simple_case("diff", "src", "score", "neq", "0")])
        state = _state(src=json.dumps({"score": 99}))
        out = await block.execute(state)
        assert out.results["b"] == "diff"

    @pytest.mark.asyncio
    async def test_gt_match(self):
        block = ConditionalBlock("b", [_simple_case("big", "src", "n", "gt", "10")])
        state = _state(src=json.dumps({"n": 11}))
        out = await block.execute(state)
        assert out.results["b"] == "big"

    @pytest.mark.asyncio
    async def test_gt_no_match(self):
        block = ConditionalBlock(
            "b", [_simple_case("big", "src", "n", "gt", "10")], default="small"
        )
        state = _state(src=json.dumps({"n": 10}))
        out = await block.execute(state)
        assert out.results["b"] == "small"

    @pytest.mark.asyncio
    async def test_lt_match(self):
        block = ConditionalBlock("b", [_simple_case("small", "src", "n", "lt", "5")])
        state = _state(src=json.dumps({"n": 3}))
        out = await block.execute(state)
        assert out.results["b"] == "small"

    @pytest.mark.asyncio
    async def test_gte_match_equal(self):
        block = ConditionalBlock("b", [_simple_case("ok", "src", "n", "gte", "7")])
        state = _state(src=json.dumps({"n": 7}))
        out = await block.execute(state)
        assert out.results["b"] == "ok"

    @pytest.mark.asyncio
    async def test_gte_match_greater(self):
        block = ConditionalBlock("b", [_simple_case("ok", "src", "n", "gte", "7")])
        state = _state(src=json.dumps({"n": 8}))
        out = await block.execute(state)
        assert out.results["b"] == "ok"

    @pytest.mark.asyncio
    async def test_lte_match_equal(self):
        block = ConditionalBlock("b", [_simple_case("ok", "src", "n", "lte", "10")])
        state = _state(src=json.dumps({"n": 10}))
        out = await block.execute(state)
        assert out.results["b"] == "ok"

    @pytest.mark.asyncio
    async def test_numeric_coercion_string_number(self):
        """eval_key value is string "42", comparison value "42" — should coerce and match."""
        block = ConditionalBlock("b", [_simple_case("hit", "src", "val", "eq", "42")])
        # "42" as top-level string result; eval_key "val" won't resolve from a plain string,
        # so test the canonical case: JSON result where the key maps to a numeric string.
        state2 = _state(src=json.dumps({"val": "42"}))
        out2 = await block.execute(state2)
        assert out2.results["b"] == "hit"

    @pytest.mark.asyncio
    async def test_numeric_non_numeric_fallback_warning(self):
        """Non-numeric value with gt operator — falls back to string comparison, adds warning."""
        block = ConditionalBlock(
            "b", [_simple_case("case1", "src", "val", "gt", "5")], default="fallback"
        )
        state = _state(src=json.dumps({"val": "abc"}))
        out = await block.execute(state)
        # Non-numeric ordered comparison returns False -> fallback
        assert out.results["b"] == "fallback"
        assert "b_warnings" in out.metadata


# ── exists / not_exists ───────────────────────────────────────────────────────


class TestExistsNotExists:
    @pytest.mark.asyncio
    async def test_exists_key_present(self):
        block = ConditionalBlock("b", [_simple_case("yes", "src", "key", "exists")])
        state = _state(src=json.dumps({"key": "value"}))
        out = await block.execute(state)
        assert out.results["b"] == "yes"

    @pytest.mark.asyncio
    async def test_exists_key_missing(self):
        block = ConditionalBlock(
            "b", [_simple_case("yes", "src", "missing", "exists")], default="no"
        )
        state = _state(src=json.dumps({"other": "value"}))
        out = await block.execute(state)
        assert out.results["b"] == "no"

    @pytest.mark.asyncio
    async def test_exists_source_missing(self):
        """eval_source not in state.results — exists returns False (no exception)."""
        block = ConditionalBlock(
            "b", [_simple_case("yes", "no_src", "key", "exists")], default="no"
        )
        state = _state(src=json.dumps({"key": "value"}))
        out = await block.execute(state)
        assert out.results["b"] == "no"

    @pytest.mark.asyncio
    async def test_not_exists_key_absent(self):
        block = ConditionalBlock("b", [_simple_case("absent", "src", "missing", "not_exists")])
        state = _state(src=json.dumps({"other": "val"}))
        out = await block.execute(state)
        assert out.results["b"] == "absent"

    @pytest.mark.asyncio
    async def test_not_exists_key_present(self):
        block = ConditionalBlock(
            "b", [_simple_case("absent", "src", "key", "not_exists")], default="present"
        )
        state = _state(src=json.dumps({"key": "val"}))
        out = await block.execute(state)
        assert out.results["b"] == "present"

    @pytest.mark.asyncio
    async def test_not_exists_source_missing(self):
        """eval_source not in state.results — not_exists returns True (no exception)."""
        block = ConditionalBlock("b", [_simple_case("absent", "no_src", "key", "not_exists")])
        state = _state(other="data")
        out = await block.execute(state)
        assert out.results["b"] == "absent"


# ── Regex operator ────────────────────────────────────────────────────────────


class TestRegexOperator:
    @pytest.mark.asyncio
    async def test_regex_match(self):
        block = ConditionalBlock(
            "b", [_simple_case("match", "src", "text", "regex", r"^\d{3}-\d{4}$")]
        )
        state = _state(src=json.dumps({"text": "555-1234"}))
        out = await block.execute(state)
        assert out.results["b"] == "match"

    @pytest.mark.asyncio
    async def test_regex_no_match(self):
        block = ConditionalBlock(
            "b", [_simple_case("match", "src", "text", "regex", r"^\d+$")], default="nomatch"
        )
        state = _state(src=json.dumps({"text": "abc"}))
        out = await block.execute(state)
        assert out.results["b"] == "nomatch"

    @pytest.mark.asyncio
    async def test_regex_partial_match_via_search(self):
        """re.search() finds pattern anywhere in string."""
        block = ConditionalBlock(
            "b", [_simple_case("found", "src", "msg", "regex", r"error\s+\d+")]
        )
        state = _state(src=json.dumps({"msg": "encountered error 42 in module"}))
        out = await block.execute(state)
        assert out.results["b"] == "found"

    @pytest.mark.asyncio
    async def test_regex_invalid_pattern_raises(self):
        block = ConditionalBlock("b", [_simple_case("m", "src", "text", "regex", r"[invalid")])
        state = _state(src=json.dumps({"text": "hello"}))
        with pytest.raises(ValueError, match="invalid regex pattern"):
            await block.execute(state)


# ── AND / OR combinators ──────────────────────────────────────────────────────


class TestCombinators:
    @pytest.mark.asyncio
    async def test_and_all_pass(self):
        """Both conditions pass -> case matches."""
        case = Case(
            case_id="both",
            condition_group=ConditionGroup(
                conditions=[
                    Condition("src", "a", "equals", "1"),
                    Condition("src", "b", "equals", "2"),
                ],
                combinator="and",
            ),
        )
        block = ConditionalBlock("b", [case], default="neither")
        state = _state(src=json.dumps({"a": "1", "b": "2"}))
        out = await block.execute(state)
        assert out.results["b"] == "both"

    @pytest.mark.asyncio
    async def test_and_one_fails(self):
        """First condition passes but second fails -> AND fails, default wins."""
        case = Case(
            case_id="both",
            condition_group=ConditionGroup(
                conditions=[
                    Condition("src", "a", "equals", "1"),
                    Condition("src", "b", "equals", "99"),
                ],
                combinator="and",
            ),
        )
        block = ConditionalBlock("b", [case], default="neither")
        state = _state(src=json.dumps({"a": "1", "b": "2"}))
        out = await block.execute(state)
        assert out.results["b"] == "neither"

    @pytest.mark.asyncio
    async def test_or_first_passes(self):
        """First condition passes -> OR group matches."""
        case = Case(
            case_id="either",
            condition_group=ConditionGroup(
                conditions=[
                    Condition("src", "a", "equals", "1"),
                    Condition("src", "b", "equals", "99"),
                ],
                combinator="or",
            ),
        )
        block = ConditionalBlock("b", [case], default="neither")
        state = _state(src=json.dumps({"a": "1", "b": "2"}))
        out = await block.execute(state)
        assert out.results["b"] == "either"

    @pytest.mark.asyncio
    async def test_or_second_passes(self):
        """Only second condition passes -> OR group still matches."""
        case = Case(
            case_id="either",
            condition_group=ConditionGroup(
                conditions=[
                    Condition("src", "a", "equals", "99"),
                    Condition("src", "b", "equals", "2"),
                ],
                combinator="or",
            ),
        )
        block = ConditionalBlock("b", [case], default="neither")
        state = _state(src=json.dumps({"a": "1", "b": "2"}))
        out = await block.execute(state)
        assert out.results["b"] == "either"

    @pytest.mark.asyncio
    async def test_or_none_passes(self):
        """Neither condition passes -> default wins."""
        case = Case(
            case_id="either",
            condition_group=ConditionGroup(
                conditions=[
                    Condition("src", "a", "equals", "99"),
                    Condition("src", "b", "equals", "99"),
                ],
                combinator="or",
            ),
        )
        block = ConditionalBlock("b", [case], default="neither")
        state = _state(src=json.dumps({"a": "1", "b": "2"}))
        out = await block.execute(state)
        assert out.results["b"] == "neither"


# ── First-match-wins ──────────────────────────────────────────────────────────


class TestFirstMatchWins:
    @pytest.mark.asyncio
    async def test_first_case_wins_when_both_match(self):
        """Two cases both match; first case_id must be returned."""
        case1 = _simple_case("first", "src", "val", "equals", "hello")
        case2 = _simple_case("second", "src", "val", "equals", "hello")
        block = ConditionalBlock("b", [case1, case2])
        state = _state(src=json.dumps({"val": "hello"}))
        out = await block.execute(state)
        assert out.results["b"] == "first"

    @pytest.mark.asyncio
    async def test_second_case_wins_when_first_fails(self):
        """First case does not match; second case matches."""
        case1 = _simple_case("first", "src", "val", "equals", "nope")
        case2 = _simple_case("second", "src", "val", "equals", "hello")
        block = ConditionalBlock("b", [case1, case2])
        state = _state(src=json.dumps({"val": "hello"}))
        out = await block.execute(state)
        assert out.results["b"] == "second"

    @pytest.mark.asyncio
    async def test_first_match_stops_evaluation(self):
        """
        Second case references a missing eval_source; if first-match-wins is correct,
        execution must never reach the second case when first matches.
        """
        case1 = _simple_case("first", "src", "val", "equals", "hello")
        # This case would raise ValueError if evaluated (missing eval_source)
        case2 = _simple_case("second", "DOES_NOT_EXIST", "val", "equals", "hello")
        block = ConditionalBlock("b", [case1, case2])
        state = _state(src=json.dumps({"val": "hello"}))
        # Should not raise, because case1 matches before case2 is evaluated
        out = await block.execute(state)
        assert out.results["b"] == "first"


# ── Default fallback ──────────────────────────────────────────────────────────


class TestDefaultFallback:
    @pytest.mark.asyncio
    async def test_default_when_no_case_matches(self):
        block = ConditionalBlock(
            "b", [_simple_case("case_a", "src", "x", "equals", "99")], default="fallback"
        )
        state = _state(src=json.dumps({"x": "1"}))
        out = await block.execute(state)
        assert out.results["b"] == "fallback"
        assert out.metadata["b_decision"] == "fallback"

    @pytest.mark.asyncio
    async def test_default_value_is_default_string(self):
        """ConditionalBlock default argument defaults to 'default'."""
        block = ConditionalBlock("b", [_simple_case("case_a", "src", "x", "equals", "nope")])
        state = _state(src=json.dumps({"x": "yes"}))
        out = await block.execute(state)
        assert out.results["b"] == "default"

    @pytest.mark.asyncio
    async def test_empty_cases_returns_default(self):
        block = ConditionalBlock("b", [], default="fallback")
        state = WorkflowState()
        out = await block.execute(state)
        assert out.results["b"] == "fallback"


# ── Missing eval_source error ─────────────────────────────────────────────────


class TestMissingEvalSource:
    @pytest.mark.asyncio
    async def test_missing_eval_source_raises_value_error(self):
        block = ConditionalBlock(
            "b", [_simple_case("case_a", "nonexistent_block", "key", "equals", "x")]
        )
        state = WorkflowState(results={"other_block": "data"})
        with pytest.raises(
            ValueError, match="eval_source 'nonexistent_block' not found in state.results"
        ):
            await block.execute(state)

    @pytest.mark.asyncio
    async def test_error_message_includes_available_keys(self):
        block = ConditionalBlock("b", [_simple_case("case_a", "missing", "key", "equals", "x")])
        state = WorkflowState(results={"block_a": "data", "block_b": "data2"})
        with pytest.raises(ValueError, match="block_a"):
            await block.execute(state)


# ── Dot-notation nested key access ───────────────────────────────────────────


class TestDotNotation:
    @pytest.mark.asyncio
    async def test_nested_two_levels(self):
        block = ConditionalBlock(
            "b", [_simple_case("match", "src", "outer.inner", "equals", "deep")]
        )
        state = _state(src=json.dumps({"outer": {"inner": "deep"}}))
        out = await block.execute(state)
        assert out.results["b"] == "match"

    @pytest.mark.asyncio
    async def test_nested_three_levels(self):
        block = ConditionalBlock("b", [_simple_case("match", "src", "a.b.c", "equals", "leaf")])
        state = _state(src=json.dumps({"a": {"b": {"c": "leaf"}}}))
        out = await block.execute(state)
        assert out.results["b"] == "match"

    @pytest.mark.asyncio
    async def test_missing_nested_key_treated_as_none(self):
        """Path 'a.missing' does not exist — is_empty returns True for None."""
        block = ConditionalBlock("b", [_simple_case("empty", "src", "a.missing", "is_empty")])
        state = _state(src=json.dumps({"a": {"other": "val"}}))
        out = await block.execute(state)
        assert out.results["b"] == "empty"

    @pytest.mark.asyncio
    async def test_flat_key(self):
        """eval_key with no dots — top-level key resolution."""
        block = ConditionalBlock("b", [_simple_case("match", "src", "score", "gt", "50")])
        state = _state(src=json.dumps({"score": 75}))
        out = await block.execute(state)
        assert out.results["b"] == "match"


# ── JSON auto-parse ───────────────────────────────────────────────────────────


class TestJSONAutoParse:
    @pytest.mark.asyncio
    async def test_result_is_json_string_auto_parsed(self):
        """state.results[eval_source] is a JSON string — auto-parsed before key resolution."""
        payload = json.dumps({"status": "ready", "count": 5})
        block = ConditionalBlock("b", [_simple_case("ready", "src", "status", "equals", "ready")])
        state = WorkflowState(results={"src": payload})
        out = await block.execute(state)
        assert out.results["b"] == "ready"

    @pytest.mark.asyncio
    async def test_non_json_string_used_as_raw(self):
        """state.results[eval_source] is a plain string — used as-is for is_empty.

        A plain string cannot be dotted into; "missing" path on a raw string won't resolve
        => treated as None => is_empty returns True.
        """
        block = ConditionalBlock("b2", [_simple_case("empty", "src2", "missing", "is_empty")])
        state = WorkflowState(results={"src2": "plain text"})
        out = await block.execute(state)
        assert out.results["b2"] == "empty"

    @pytest.mark.asyncio
    async def test_nested_json_object(self):
        """Deeply nested JSON correctly resolved via dot-notation."""
        payload = json.dumps({"result": {"metrics": {"score": 0.95}}})
        block = ConditionalBlock(
            "b", [_simple_case("highscore", "src", "result.metrics.score", "gte", "0.9")]
        )
        state = WorkflowState(results={"src": payload})
        out = await block.execute(state)
        assert out.results["b"] == "highscore"


# ── State patterns ────────────────────────────────────────────────────────────


class TestStatePatterns:
    @pytest.mark.asyncio
    async def test_original_state_not_mutated(self):
        """model_copy ensures original state is unchanged."""
        block = ConditionalBlock("b", [_simple_case("yes", "src", "val", "equals", "x")])
        state = _state(src=json.dumps({"val": "x"}))
        original_results = dict(state.results)
        original_metadata = dict(state.metadata)

        await block.execute(state)

        assert state.results == original_results
        assert state.metadata == original_metadata

    @pytest.mark.asyncio
    async def test_message_appended(self):
        """A system message is appended to state.messages."""
        block = ConditionalBlock("b", [_simple_case("yes", "src", "val", "equals", "x")])
        state = _state(src=json.dumps({"val": "x"}))
        out = await block.execute(state)
        assert len(out.messages) == 1
        msg = out.messages[0]
        assert msg["role"] == "system"
        assert "[Block b]" in msg["content"]
        assert "ConditionalBlock" in msg["content"]
        assert "yes" in msg["content"]

    @pytest.mark.asyncio
    async def test_no_cost_change(self):
        """total_cost_usd and total_tokens must not change (no LLM calls)."""
        block = ConditionalBlock("b", [_simple_case("yes", "src", "val", "equals", "x")])
        state = WorkflowState(
            results={"src": json.dumps({"val": "x"})},
            total_cost_usd=3.14,
            total_tokens=1234,
        )
        out = await block.execute(state)
        assert out.total_cost_usd == 3.14
        assert out.total_tokens == 1234

    @pytest.mark.asyncio
    async def test_decision_written_to_results_and_metadata(self):
        """Winning case_id is in both state.results[block_id] and state.metadata[block_id_decision]."""
        block = ConditionalBlock("myblock", [_simple_case("branch_a", "src", "x", "equals", "1")])
        state = _state(src=json.dumps({"x": "1"}))
        out = await block.execute(state)
        assert out.results["myblock"] == "branch_a"
        assert out.metadata["myblock_decision"] == "branch_a"

    @pytest.mark.asyncio
    async def test_existing_state_fields_preserved(self):
        """Other state fields (shared_memory, messages, etc.) are unchanged."""
        block = ConditionalBlock("b", [_simple_case("yes", "src", "v", "equals", "1")])
        state = WorkflowState(
            results={"src": json.dumps({"v": "1"}), "prior_result": "kept"},
            shared_memory={"key": "preserved"},
            messages=[{"role": "user", "content": "prior"}],
            total_cost_usd=1.0,
        )
        out = await block.execute(state)
        assert out.results["prior_result"] == "kept"
        assert out.shared_memory["key"] == "preserved"
        assert out.messages[0] == {"role": "user", "content": "prior"}
        assert out.total_cost_usd == 1.0


# ── Unknown operator error ────────────────────────────────────────────────────


class TestUnknownOperator:
    @pytest.mark.asyncio
    async def test_unknown_operator_raises(self):
        block = ConditionalBlock("b", [_simple_case("x", "src", "val", "UNSUPPORTED_OP")])
        state = _state(src=json.dumps({"val": "hello"}))
        with pytest.raises(ValueError, match="unknown operator 'UNSUPPORTED_OP'"):
            await block.execute(state)


# ── Switch-style multi-case scenario ─────────────────────────────────────────


class TestSwitchStyle:
    @pytest.mark.asyncio
    async def test_switch_low_medium_high(self):
        """Simulates a switch on a numeric score: low/medium/high/default."""
        cases = [
            _simple_case("high", "score_block", "value", "gte", "80"),
            _simple_case("medium", "score_block", "value", "gte", "50"),
            _simple_case("low", "score_block", "value", "gte", "0"),
        ]
        block = ConditionalBlock("router", cases, default="unknown")

        for score, expected in [(95, "high"), (65, "medium"), (30, "low")]:
            state = _state(score_block=json.dumps({"value": score}))
            out = await block.execute(state)
            assert out.results["router"] == expected, f"score={score} expected={expected}"

    @pytest.mark.asyncio
    async def test_switch_no_match_returns_default(self):
        cases = [_simple_case("positive", "src", "n", "gt", "0")]
        block = ConditionalBlock("router", cases, default="nonpositive")
        state = _state(src=json.dumps({"n": -5}))
        out = await block.execute(state)
        assert out.results["router"] == "nonpositive"
