"""Tests for RUN-696: Transform hooks for structured output assertions.

Transform spec format: ``transform: "json_path:$.field.path"``

Covers:
  AC1 – json_path transform extracts field before assertion evaluates
  AC2 – non-JSON output / missing path → assertion fails with clear reason, no crash
  AC3 – no transform field → backward-compatible behavior unchanged
"""

import json

import pytest
from runsight_core.assertions.base import (
    AssertionContext,
    GradingResult,
)
from runsight_core.assertions.registry import (
    register_assertion,
    run_assertion,
    run_assertions,
)
from runsight_core.assertions.scoring import AssertionsResult

# ---------------------------------------------------------------------------
# Helpers (mirroring test_registry.py conventions)
# ---------------------------------------------------------------------------


def _make_context(**overrides) -> AssertionContext:
    """Build a minimal AssertionContext with sensible defaults."""
    defaults = dict(
        output="Hello world",
        prompt="Say hello",
        prompt_hash="abc123",
        soul_id="soul-1",
        soul_version="v1",
        block_id="block-1",
        block_type="LinearBlock",
        cost_usd=0.001,
        total_tokens=100,
        latency_ms=200.0,
        variables={},
        run_id="run-1",
        workflow_id="wf-1",
    )
    defaults.update(overrides)
    return AssertionContext(**defaults)


class _ContainsAssertion:
    """Stub assertion: checks if ``value`` is contained in output."""

    type: str = "contains"

    def __init__(self, value: str = ""):
        self._value = value

    def evaluate(self, output: str, context: AssertionContext) -> GradingResult:
        passed = self._value in output
        return GradingResult(
            passed=passed,
            score=1.0 if passed else 0.0,
            reason=f"'contains' check for '{self._value}'",
            assertion_type="contains",
        )


class _EqualsAssertion:
    """Stub assertion: checks exact equality."""

    type: str = "equals"

    def __init__(self, value: str = ""):
        self._value = value

    def evaluate(self, output: str, context: AssertionContext) -> GradingResult:
        passed = output == self._value
        return GradingResult(
            passed=passed,
            score=1.0 if passed else 0.0,
            reason="'equals' check",
            assertion_type="equals",
        )


@pytest.fixture(autouse=True)
def _register_stubs():
    """Ensure stub handlers are registered before every test."""
    register_assertion("contains", _ContainsAssertion)
    register_assertion("equals", _EqualsAssertion)


# ---------------------------------------------------------------------------
# AC1 – json_path transform extracts field, assertion evaluates on extracted value
# ---------------------------------------------------------------------------


class TestTransformJsonPathExtraction:
    """AC1: json_path transform extracts the target field before the assertion runs."""

    def test_run_assertion_json_path_extracts_field(self):
        """run_assertion with transform='json_path:$.summary' extracts the summary
        field so that a contains assertion on 'transformative' passes."""
        ctx = _make_context()
        output = json.dumps(
            {
                "summary": "LLMs are transformative",
                "details": "Long explanation here...",
            }
        )

        result = run_assertion(
            type="contains",
            output=output,
            context=ctx,
            value="transformative",
            transform="json_path:$.summary",
        )
        assert isinstance(result, GradingResult)
        assert result.passed is True
        assert result.score == 1.0

    def test_run_assertion_json_path_assertion_sees_extracted_not_original(self):
        """The assertion must evaluate on the *extracted* value, not the original
        JSON blob.  'details' is only in the original — it should not match when
        the transform selects ``$.summary``."""
        ctx = _make_context()
        output = json.dumps(
            {
                "summary": "Short summary",
                "details": "secret details content",
            }
        )

        result = run_assertion(
            type="contains",
            output=output,
            context=ctx,
            value="secret details",
            transform="json_path:$.summary",
        )
        assert isinstance(result, GradingResult)
        assert result.passed is False

    def test_run_assertion_json_path_nested_field(self):
        """Deeply nested json_path like ``$.data.nested.field`` should work."""
        ctx = _make_context()
        output = json.dumps(
            {
                "data": {"nested": {"field": "deep value here"}},
            }
        )

        result = run_assertion(
            type="contains",
            output=output,
            context=ctx,
            value="deep value",
            transform="json_path:$.data.nested.field",
        )
        assert isinstance(result, GradingResult)
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_run_assertions_json_path_in_config(self):
        """run_assertions (async) respects transform in the config dict.

        Uses ``equals`` so the assertion can only pass if the transform actually
        extracts the field value (the raw JSON string would never equal it).
        """
        ctx = _make_context()
        output = json.dumps(
            {
                "summary": "LLMs are transformative",
                "details": "Long explanation",
            }
        )

        config = [
            {
                "type": "equals",
                "value": "LLMs are transformative",
                "transform": "json_path:$.summary",
            },
        ]
        result = await run_assertions(config, output=output, context=ctx)
        assert isinstance(result, AssertionsResult)
        assert len(result.results) == 1
        assert result.results[0].passed is True

    @pytest.mark.asyncio
    async def test_run_assertions_mixed_transform_and_plain(self):
        """Config with some assertions using transform and others without.

        The first assertion uses ``equals`` with a transform so it can only pass
        if the transform actually extracts the field.  The second uses plain
        ``contains`` on the raw JSON (no transform) — that should pass regardless.
        """
        ctx = _make_context()
        output = json.dumps(
            {
                "summary": "LLMs are transformative",
                "details": "Long explanation",
            }
        )

        config = [
            {
                "type": "equals",
                "value": "LLMs are transformative",
                "transform": "json_path:$.summary",
            },
            {
                "type": "contains",
                "value": "summary",  # present in raw JSON string
            },
        ]
        result = await run_assertions(config, output=output, context=ctx)
        assert len(result.results) == 2
        # First: transform extracts $.summary → "LLMs are transformative" → equals passes
        assert result.results[0].passed is True
        # Second: no transform, raw output is JSON string containing "summary" → passes
        assert result.results[1].passed is True


# ---------------------------------------------------------------------------
# AC2 – non-JSON output / missing path → graceful failure, no crash
# ---------------------------------------------------------------------------


class TestTransformGracefulFailure:
    """AC2: json_path transform on invalid/non-matching output fails with
    a clear reason and never crashes."""

    def test_non_json_output_fails_with_reason(self):
        """json_path transform on plain-text output → passed=False,
        reason mentions invalid JSON (not an exception)."""
        ctx = _make_context()

        result = run_assertion(
            type="contains",
            output="This is plain text, not JSON",
            context=ctx,
            value="anything",
            transform="json_path:$.summary",
        )
        assert isinstance(result, GradingResult)
        assert result.passed is False
        assert result.score == 0.0
        reason_lower = result.reason.lower()
        assert "json" in reason_lower, f"Reason should mention JSON problem, got: {result.reason}"

    def test_json_path_no_match_fails_with_reason(self):
        """json_path that resolves to nothing → passed=False,
        reason mentions path not found."""
        ctx = _make_context()
        output = json.dumps({"title": "something"})

        result = run_assertion(
            type="contains",
            output=output,
            context=ctx,
            value="anything",
            transform="json_path:$.nonexistent",
        )
        assert isinstance(result, GradingResult)
        assert result.passed is False
        assert result.score == 0.0
        reason_lower = result.reason.lower()
        assert "not found" in reason_lower or "no match" in reason_lower, (
            f"Reason should indicate path not found, got: {result.reason}"
        )

    def test_empty_string_output_with_transform(self):
        """json_path transform on empty string → fails gracefully."""
        ctx = _make_context()

        result = run_assertion(
            type="contains",
            output="",
            context=ctx,
            value="anything",
            transform="json_path:$.field",
        )
        assert isinstance(result, GradingResult)
        assert result.passed is False
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_run_assertions_non_json_no_crash(self):
        """run_assertions with json_path transform on non-JSON → no crash,
        result has passed=False with a reason mentioning JSON."""
        ctx = _make_context()

        config = [
            {
                "type": "contains",
                "value": "anything",
                "transform": "json_path:$.summary",
            },
        ]
        result = await run_assertions(config, output="plain text, not json", context=ctx)
        assert isinstance(result, AssertionsResult)
        assert len(result.results) == 1
        assert result.results[0].passed is False
        # The reason must indicate the transform failed due to invalid JSON,
        # not just that the contains check didn't match.
        reason_lower = result.results[0].reason.lower()
        assert "json" in reason_lower, (
            f"Reason should mention JSON problem, got: {result.results[0].reason}"
        )


# ---------------------------------------------------------------------------
# AC3 – no transform → backward-compatible, unchanged behavior
# ---------------------------------------------------------------------------


class TestNoTransformBackwardCompat:
    """AC3: assertions without a transform field behave exactly as before."""

    def test_run_assertion_no_transform_passes(self):
        """contains assertion without transform works as before."""
        ctx = _make_context()

        result = run_assertion(
            type="contains",
            output="Hello world",
            context=ctx,
            value="Hello",
        )
        assert isinstance(result, GradingResult)
        assert result.passed is True
        assert result.score == 1.0

    def test_run_assertion_no_transform_fails(self):
        """contains assertion without transform fails as before."""
        ctx = _make_context()

        result = run_assertion(
            type="contains",
            output="Hello world",
            context=ctx,
            value="xyz",
        )
        assert isinstance(result, GradingResult)
        assert result.passed is False

    @pytest.mark.asyncio
    async def test_run_assertions_no_transform_unchanged(self):
        """run_assertions without transform in config — backward compatible."""
        ctx = _make_context()

        config = [
            {"type": "contains", "value": "Hello"},
            {"type": "equals", "value": "Hello world"},
        ]
        result = await run_assertions(config, output="Hello world", context=ctx)
        assert len(result.results) == 2
        assert result.results[0].passed is True
        assert result.results[1].passed is True


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestTransformEdgeCases:
    """Edge cases for transform hooks."""

    def test_json_path_extracts_integer_stringified(self):
        """When json_path extracts a non-string value (e.g. integer),
        it should be stringified before the assertion evaluates."""
        ctx = _make_context()
        output = json.dumps({"count": 42, "label": "items"})

        result = run_assertion(
            type="contains",
            output=output,
            context=ctx,
            value="42",
            transform="json_path:$.count",
        )
        assert isinstance(result, GradingResult)
        assert result.passed is True

    def test_json_path_extracts_list_stringified(self):
        """When json_path extracts a list, it should be stringified."""
        ctx = _make_context()
        output = json.dumps({"tags": ["ai", "ml", "nlp"]})

        result = run_assertion(
            type="contains",
            output=output,
            context=ctx,
            value="ml",
            transform="json_path:$.tags",
        )
        assert isinstance(result, GradingResult)
        assert result.passed is True

    def test_unknown_transform_type_fails_gracefully(self):
        """An unrecognized transform prefix (e.g. 'regex:.*') should fail
        gracefully with a clear reason, not crash."""
        ctx = _make_context()

        result = run_assertion(
            type="contains",
            output="some output",
            context=ctx,
            value="some",
            transform="regex:.*",
        )
        assert isinstance(result, GradingResult)
        assert result.passed is False
        assert result.score == 0.0
        reason_lower = result.reason.lower()
        assert "transform" in reason_lower or "unknown" in reason_lower, (
            f"Reason should mention unknown transform, got: {result.reason}"
        )

    def test_json_path_with_equals_assertion(self):
        """Transform works with different assertion types, not just contains."""
        ctx = _make_context()
        output = json.dumps({"status": "completed"})

        result = run_assertion(
            type="equals",
            output=output,
            context=ctx,
            value="completed",
            transform="json_path:$.status",
        )
        assert isinstance(result, GradingResult)
        assert result.passed is True

    def test_json_path_with_not_prefix(self):
        """Transform should work in combination with not- prefix."""
        ctx = _make_context()
        output = json.dumps({"summary": "All good here"})

        result = run_assertion(
            type="not-contains",
            output=output,
            context=ctx,
            value="error",
            transform="json_path:$.summary",
        )
        assert isinstance(result, GradingResult)
        assert result.passed is True
        assert result.score == 1.0
