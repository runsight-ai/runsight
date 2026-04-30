"""Tests for deterministic structural assertion plugins.

Covers: is-json, contains-json.
"""

from runsight_core.assertions.base import AssertionContext, GradingResult

# Implementation imports
from runsight_core.assertions.deterministic.structural import (
    ContainsJsonAssertion,
    IsJsonAssertion,
)

# ── Helper ───────────────────────────────────────────────────────────────────


def make_context(output: str = "", **overrides) -> AssertionContext:
    defaults = dict(
        output=output,
        prompt="test prompt",
        prompt_hash="abc123",
        soul_id="assertion-soul",
        soul_version="v1",
        block_id="assertion-block",
        block_type="linear",
        cost_usd=0.001,
        total_tokens=100,
        latency_ms=500.0,
        variables={},
        run_id="assertion-run",
        workflow_id="assertion-workflow",
    )
    defaults.update(overrides)
    return AssertionContext(**defaults)


# ═════════════════════════════════════════════════════════════════════════════
# is-json
# ═════════════════════════════════════════════════════════════════════════════


class TestIsJsonAssertion:
    """is-json validates JSON, optional JSON Schema validation."""

    def test_type_attribute(self):
        a = IsJsonAssertion()
        assert a.type == "is-json"

    # ── Basic JSON validation (no schema) ────────────────────────────────

    def test_valid_json_object_passes(self):
        a = IsJsonAssertion()
        output = '{"name": "Alice", "age": 30}'
        ctx = make_context(output)
        result = a.evaluate(output, ctx)
        assert result.passed is True
        assert result.score == 1.0

    def test_valid_json_array_passes(self):
        a = IsJsonAssertion()
        output = "[1, 2, 3]"
        ctx = make_context(output)
        result = a.evaluate(output, ctx)
        assert result.passed is True

    def test_valid_json_string_passes(self):
        a = IsJsonAssertion()
        output = '"hello"'
        ctx = make_context(output)
        result = a.evaluate(output, ctx)
        assert result.passed is True

    def test_valid_json_number_passes(self):
        a = IsJsonAssertion()
        output = "42"
        ctx = make_context(output)
        result = a.evaluate(output, ctx)
        assert result.passed is True

    def test_valid_json_boolean_passes(self):
        a = IsJsonAssertion()
        output = "true"
        ctx = make_context(output)
        result = a.evaluate(output, ctx)
        assert result.passed is True

    def test_valid_json_null_passes(self):
        a = IsJsonAssertion()
        output = "null"
        ctx = make_context(output)
        result = a.evaluate(output, ctx)
        assert result.passed is True

    def test_invalid_json_fails(self):
        a = IsJsonAssertion()
        output = "not json at all"
        ctx = make_context(output)
        result = a.evaluate(output, ctx)
        assert result.passed is False
        assert result.score == 0.0

    def test_empty_string_fails(self):
        a = IsJsonAssertion()
        ctx = make_context("")
        result = a.evaluate("", ctx)
        assert result.passed is False

    def test_malformed_json_fails(self):
        a = IsJsonAssertion()
        output = '{"key": "value"'  # missing closing brace
        ctx = make_context(output)
        result = a.evaluate(output, ctx)
        assert result.passed is False

    # ── JSON Schema validation ────────────────────────────────────

    def test_schema_validation_passes(self):
        """when value is a JSON Schema, validate the parsed JSON against it."""
        schema = {
            "type": "object",
            "required": ["name", "age"],
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
            },
        }
        a = IsJsonAssertion(value=schema)
        output = '{"name": "Alice", "age": 30}'
        ctx = make_context(output)
        result = a.evaluate(output, ctx)
        assert result.passed is True

    def test_schema_validation_fails_missing_required(self):
        schema = {
            "type": "object",
            "required": ["name", "age"],
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
            },
        }
        a = IsJsonAssertion(value=schema)
        output = '{"name": "Alice"}'  # missing 'age'
        ctx = make_context(output)
        result = a.evaluate(output, ctx)
        assert result.passed is False

    def test_schema_validation_fails_wrong_type(self):
        schema = {
            "type": "object",
            "properties": {
                "age": {"type": "integer"},
            },
        }
        a = IsJsonAssertion(value=schema)
        output = '{"age": "not a number"}'
        ctx = make_context(output)
        result = a.evaluate(output, ctx)
        assert result.passed is False

    def test_schema_validation_with_array(self):
        schema = {
            "type": "array",
            "items": {"type": "integer"},
        }
        a = IsJsonAssertion(value=schema)
        output = "[1, 2, 3]"
        ctx = make_context(output)
        result = a.evaluate(output, ctx)
        assert result.passed is True

    def test_schema_validation_array_wrong_type_fails(self):
        schema = {
            "type": "array",
            "items": {"type": "integer"},
        }
        a = IsJsonAssertion(value=schema)
        output = '[1, "two", 3]'
        ctx = make_context(output)
        result = a.evaluate(output, ctx)
        assert result.passed is False

    def test_no_schema_value_none(self):
        """When value=None, just validate that the output is valid JSON."""
        a = IsJsonAssertion(value=None)
        output = '{"key": "val"}'
        ctx = make_context(output)
        result = a.evaluate(output, ctx)
        assert result.passed is True

    # ── Return type / reason ──────────────────────────────────────

    def test_returns_grading_result(self):
        a = IsJsonAssertion()
        ctx = make_context("{}")
        result = a.evaluate("{}", ctx)
        assert isinstance(result, GradingResult)

    def test_reason_is_meaningful(self):
        a = IsJsonAssertion()
        ctx = make_context("not json")
        result = a.evaluate("not json", ctx)
        assert isinstance(result.reason, str)
        assert len(result.reason) > 0


# ═════════════════════════════════════════════════════════════════════════════
# contains-json
# ═════════════════════════════════════════════════════════════════════════════


class TestContainsJsonAssertion:
    """contains-json — extract valid JSON substring, optional schema."""

    def test_type_attribute(self):
        a = ContainsJsonAssertion()
        assert a.type == "contains-json"

    def test_json_embedded_in_text_passes(self):
        a = ContainsJsonAssertion()
        output = 'Here is the result: {"status": "ok"} and more text.'
        ctx = make_context(output)
        result = a.evaluate(output, ctx)
        assert result.passed is True
        assert result.score == 1.0

    def test_json_array_embedded_passes(self):
        a = ContainsJsonAssertion()
        output = "Items: [1, 2, 3] found."
        ctx = make_context(output)
        result = a.evaluate(output, ctx)
        assert result.passed is True

    def test_no_json_in_text_fails(self):
        a = ContainsJsonAssertion()
        output = "This is plain text with no JSON."
        ctx = make_context(output)
        result = a.evaluate(output, ctx)
        assert result.passed is False
        assert result.score == 0.0

    def test_empty_output_fails(self):
        a = ContainsJsonAssertion()
        ctx = make_context("")
        result = a.evaluate("", ctx)
        assert result.passed is False

    def test_pure_json_output_passes(self):
        a = ContainsJsonAssertion()
        output = '{"key": "value"}'
        ctx = make_context(output)
        result = a.evaluate(output, ctx)
        assert result.passed is True

    # ── With JSON Schema validation ──────────────────────────────────────

    def test_schema_on_extracted_json_passes(self):
        schema = {
            "type": "object",
            "required": ["status"],
            "properties": {"status": {"type": "string"}},
        }
        a = ContainsJsonAssertion(value=schema)
        output = 'Result: {"status": "ok"} end.'
        ctx = make_context(output)
        result = a.evaluate(output, ctx)
        assert result.passed is True

    def test_schema_on_extracted_json_fails(self):
        schema = {
            "type": "object",
            "required": ["status"],
            "properties": {"status": {"type": "string"}},
        }
        a = ContainsJsonAssertion(value=schema)
        output = 'Result: {"name": "Alice"} end.'  # missing 'status'
        ctx = make_context(output)
        result = a.evaluate(output, ctx)
        assert result.passed is False

    def test_no_schema_value_none(self):
        a = ContainsJsonAssertion(value=None)
        output = 'prefix {"a": 1} suffix'
        ctx = make_context(output)
        result = a.evaluate(output, ctx)
        assert result.passed is True

    # ── Return type / reason ──────────────────────────────────────

    def test_returns_grading_result(self):
        a = ContainsJsonAssertion()
        ctx = make_context('{"x": 1}')
        result = a.evaluate('{"x": 1}', ctx)
        assert isinstance(result, GradingResult)

    def test_reason_is_meaningful(self):
        a = ContainsJsonAssertion()
        ctx = make_context("no json here")
        result = a.evaluate("no json here", ctx)
        assert isinstance(result.reason, str)
        assert len(result.reason) > 0
