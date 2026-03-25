"""Tests for assertion base models: GradingResult, TokenUsage, AssertionContext, Assertion protocol."""

import json
from dataclasses import asdict

from runsight_core.assertions.base import (
    Assertion,
    AssertionContext,
    GradingResult,
    TokenUsage,
)


class TestTokenUsage:
    def test_defaults_to_zero(self):
        usage = TokenUsage()
        assert usage.prompt == 0
        assert usage.completion == 0
        assert usage.total == 0

    def test_custom_values(self):
        usage = TokenUsage(prompt=100, completion=50, total=150)
        assert usage.prompt == 100
        assert usage.completion == 50
        assert usage.total == 150

    def test_json_serializable(self):
        usage = TokenUsage(prompt=10, completion=20, total=30)
        data = asdict(usage)
        serialized = json.dumps(data)
        restored = json.loads(serialized)
        assert restored == {"prompt": 10, "completion": 20, "total": 30}


class TestGradingResult:
    def test_required_fields(self):
        result = GradingResult(passed=True, score=1.0, reason="All good")
        assert result.passed is True
        assert result.score == 1.0
        assert result.reason == "All good"

    def test_default_optional_fields(self):
        result = GradingResult(passed=False, score=0.0, reason="Failed")
        assert result.named_scores == {}
        assert result.tokens_used is None
        assert result.component_results == []
        assert result.assertion_type is None
        assert result.metadata == {}

    def test_named_scores(self):
        result = GradingResult(
            passed=True,
            score=0.8,
            reason="Partial match",
            named_scores={"accuracy": 0.9, "coherence": 0.7},
        )
        assert result.named_scores["accuracy"] == 0.9
        assert result.named_scores["coherence"] == 0.7

    def test_tokens_used(self):
        usage = TokenUsage(prompt=100, completion=50, total=150)
        result = GradingResult(passed=True, score=1.0, reason="OK", tokens_used=usage)
        assert result.tokens_used is not None
        assert result.tokens_used.prompt == 100
        assert result.tokens_used.total == 150

    def test_component_results_nesting(self):
        child1 = GradingResult(passed=True, score=1.0, reason="Child 1 passed")
        child2 = GradingResult(passed=False, score=0.3, reason="Child 2 failed")
        parent = GradingResult(
            passed=False,
            score=0.65,
            reason="Composite",
            component_results=[child1, child2],
        )
        assert len(parent.component_results) == 2
        assert parent.component_results[0].passed is True
        assert parent.component_results[1].score == 0.3

    def test_assertion_type_field(self):
        result = GradingResult(
            passed=True, score=1.0, reason="Contains match", assertion_type="contains"
        )
        assert result.assertion_type == "contains"

    def test_metadata_field(self):
        result = GradingResult(
            passed=True,
            score=1.0,
            reason="OK",
            metadata={"latency_ms": 42, "model": "gpt-4"},
        )
        assert result.metadata["latency_ms"] == 42
        assert result.metadata["model"] == "gpt-4"

    def test_json_serializable(self):
        usage = TokenUsage(prompt=10, completion=20, total=30)
        child = GradingResult(passed=True, score=1.0, reason="Sub-check")
        result = GradingResult(
            passed=True,
            score=0.95,
            reason="Overall good",
            named_scores={"relevance": 0.9},
            tokens_used=usage,
            component_results=[child],
            assertion_type="llm-rubric",
            metadata={"model": "gpt-4"},
        )
        data = asdict(result)
        serialized = json.dumps(data)
        restored = json.loads(serialized)
        assert restored["passed"] is True
        assert restored["score"] == 0.95
        assert restored["tokens_used"]["prompt"] == 10
        assert len(restored["component_results"]) == 1
        assert restored["assertion_type"] == "llm-rubric"

    def test_score_boundary_zero(self):
        result = GradingResult(passed=False, score=0.0, reason="Total failure")
        assert result.score == 0.0

    def test_score_boundary_one(self):
        result = GradingResult(passed=True, score=1.0, reason="Perfect")
        assert result.score == 1.0


class TestAssertionContext:
    def test_all_fields_present(self):
        ctx = AssertionContext(
            output="Hello world",
            prompt="Say hello",
            prompt_hash="abc123",
            soul_id="soul-1",
            soul_version="v1",
            block_id="block-1",
            block_type="LinearBlock",
            cost_usd=0.002,
            total_tokens=150,
            latency_ms=320.5,
            variables={"name": "Alice"},
            run_id="run-001",
            workflow_id="wf-001",
        )
        assert ctx.output == "Hello world"
        assert ctx.prompt == "Say hello"
        assert ctx.prompt_hash == "abc123"
        assert ctx.soul_id == "soul-1"
        assert ctx.soul_version == "v1"
        assert ctx.block_id == "block-1"
        assert ctx.block_type == "LinearBlock"
        assert ctx.cost_usd == 0.002
        assert ctx.total_tokens == 150
        assert ctx.latency_ms == 320.5
        assert ctx.variables == {"name": "Alice"}
        assert ctx.run_id == "run-001"
        assert ctx.workflow_id == "wf-001"

    def test_json_serializable(self):
        ctx = AssertionContext(
            output="out",
            prompt="in",
            prompt_hash="h",
            soul_id="s",
            soul_version="v",
            block_id="b",
            block_type="t",
            cost_usd=0.0,
            total_tokens=0,
            latency_ms=0.0,
            variables={},
            run_id="r",
            workflow_id="w",
        )
        data = asdict(ctx)
        serialized = json.dumps(data)
        restored = json.loads(serialized)
        assert restored["output"] == "out"
        assert restored["workflow_id"] == "w"

    def test_variables_supports_nested_dicts(self):
        ctx = AssertionContext(
            output="x",
            prompt="p",
            prompt_hash="h",
            soul_id="s",
            soul_version="v",
            block_id="b",
            block_type="t",
            cost_usd=0.0,
            total_tokens=0,
            latency_ms=0.0,
            variables={"nested": {"key": "value"}},
            run_id="r",
            workflow_id="w",
        )
        assert ctx.variables["nested"]["key"] == "value"


class TestAssertionProtocol:
    def test_protocol_requires_type_and_evaluate(self):
        """A class with `type: str` and `evaluate(output, context) -> GradingResult`
        should satisfy the Assertion protocol."""

        class MyAssertion:
            type: str = "my-check"

            def evaluate(self, output: str, context: AssertionContext) -> GradingResult:
                return GradingResult(passed=True, score=1.0, reason="OK")

        assertion = MyAssertion()
        assert isinstance(assertion, Assertion)

    def test_protocol_rejects_missing_evaluate(self):
        """A class missing `evaluate` should NOT satisfy the Assertion protocol."""

        class NotAnAssertion:
            type: str = "bad"

        obj = NotAnAssertion()
        assert not isinstance(obj, Assertion)

    def test_protocol_rejects_missing_type(self):
        """A class missing `type` should NOT satisfy the Assertion protocol."""

        class NoType:
            def evaluate(self, output: str, context: AssertionContext) -> GradingResult:
                return GradingResult(passed=True, score=1.0, reason="OK")

        obj = NoType()
        assert not isinstance(obj, Assertion)

    def test_evaluate_returns_grading_result(self):
        """The evaluate method should return a GradingResult instance."""

        class CheckAssertion:
            type: str = "check"

            def evaluate(self, output: str, context: AssertionContext) -> GradingResult:
                return GradingResult(
                    passed="hello" in output,
                    score=1.0 if "hello" in output else 0.0,
                    reason="Checked for hello",
                )

        ctx = AssertionContext(
            output="hello world",
            prompt="say hi",
            prompt_hash="h",
            soul_id="s",
            soul_version="v",
            block_id="b",
            block_type="t",
            cost_usd=0.0,
            total_tokens=0,
            latency_ms=0.0,
            variables={},
            run_id="r",
            workflow_id="w",
        )
        assertion = CheckAssertion()
        result = assertion.evaluate("hello world", ctx)
        assert isinstance(result, GradingResult)
        assert result.passed is True
        assert result.score == 1.0
