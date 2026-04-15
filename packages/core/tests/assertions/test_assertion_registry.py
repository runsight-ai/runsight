"""Tests for assertion plugin registry, not- prefix handling, run_assertion, and run_assertions."""

import pytest
from runsight_core.assertions.base import (
    AssertionContext,
    GradingResult,
)
from runsight_core.assertions.registry import (
    register_assertion,
    run_assertion,
    run_assertions,
    run_assertions_sync,
)
from runsight_core.assertions.scoring import AssertionsResult

# ---------------------------------------------------------------------------
# Helpers
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
    """Stub assertion that checks if `value` is contained in output."""

    type: str = "contains"

    def evaluate(self, output: str, context: AssertionContext) -> GradingResult:
        passed = self._value in output
        return GradingResult(
            passed=passed,
            score=1.0 if passed else 0.0,
            reason=f"'contains' check for '{self._value}'",
            assertion_type="contains",
        )

    def __init__(self, value: str = ""):
        self._value = value


class _EqualsAssertion:
    """Stub assertion that checks exact equality."""

    type: str = "equals"

    def evaluate(self, output: str, context: AssertionContext) -> GradingResult:
        passed = output == self._value
        return GradingResult(
            passed=passed,
            score=1.0 if passed else 0.0,
            reason="'equals' check",
            assertion_type="equals",
        )

    def __init__(self, value: str = ""):
        self._value = value


# ---------------------------------------------------------------------------
# AC-9: Plugin registry dispatches by type string
# ---------------------------------------------------------------------------


class TestRegistryDispatch:
    def test_register_and_dispatch_by_type(self):
        """AC-9: register an assertion handler by type string, then dispatch to it."""
        register_assertion("contains", _ContainsAssertion)
        register_assertion("equals", _EqualsAssertion)

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

    def test_dispatch_unknown_type_raises(self):
        """Dispatching an unregistered type should raise an error."""
        ctx = _make_context()
        with pytest.raises((KeyError, ValueError)):
            run_assertion(
                type="nonexistent-assertion-type",
                output="test",
                context=ctx,
                value="x",
            )

    def test_register_overwrites_existing(self):
        """Registering the same type twice overwrites the previous handler."""

        class AlternateContains:
            type: str = "contains"

            def evaluate(self, output: str, context: AssertionContext) -> GradingResult:
                return GradingResult(passed=False, score=0.0, reason="Alternate always fails")

        register_assertion("contains", AlternateContains)
        ctx = _make_context()
        result = run_assertion(type="contains", output="Hello", context=ctx, value="Hello")
        assert result.passed is False

        # Restore original for other tests
        register_assertion("contains", _ContainsAssertion)


# ---------------------------------------------------------------------------
# AC-10: not- prefix handling
# ---------------------------------------------------------------------------


class TestNotPrefixHandling:
    def test_not_prefix_inverts_score(self):
        """AC-10: 'not-contains' strips prefix, runs 'contains', inverts score."""
        register_assertion("contains", _ContainsAssertion)
        ctx = _make_context()

        # "Hello" IS in "Hello world", so contains passes (score=1.0)
        # not-contains should invert: score = 1 - 1.0 = 0.0
        result = run_assertion(
            type="not-contains",
            output="Hello world",
            context=ctx,
            value="Hello",
        )
        assert result.score == 0.0
        assert result.passed is False

    def test_not_prefix_inverts_passing_to_failing(self):
        """AC-10: not- prefix inverts passed flag."""
        register_assertion("contains", _ContainsAssertion)
        ctx = _make_context()

        # "xyz" is NOT in "Hello world", so contains fails (score=0.0)
        # not-contains should invert: score = 1 - 0.0 = 1.0, passed = True
        result = run_assertion(
            type="not-contains",
            output="Hello world",
            context=ctx,
            value="xyz",
        )
        assert result.score == 1.0
        assert result.passed is True

    def test_not_prefix_with_partial_score(self):
        """AC-10: not- prefix inverts continuous scores (1 - score)."""

        class SimilarityAssertion:
            type: str = "similarity"

            def evaluate(self, output: str, context: AssertionContext) -> GradingResult:
                return GradingResult(passed=True, score=0.7, reason="70% similar")

        register_assertion("similarity", SimilarityAssertion)
        ctx = _make_context()

        result = run_assertion(
            type="not-similarity",
            output="anything",
            context=ctx,
            value="ref",
        )
        assert abs(result.score - 0.3) < 1e-9

    def test_not_prefix_unknown_base_type_raises(self):
        """not-<unknown> should raise because the base type doesn't exist."""
        ctx = _make_context()
        with pytest.raises((KeyError, ValueError)):
            run_assertion(
                type="not-nonexistent",
                output="test",
                context=ctx,
                value="x",
            )


# ---------------------------------------------------------------------------
# AC-11: run_assertion() dispatches single assertion
# ---------------------------------------------------------------------------


class TestRunAssertion:
    def test_run_assertion_passes_value(self):
        """run_assertion passes the `value` parameter to the assertion handler."""
        register_assertion("contains", _ContainsAssertion)
        ctx = _make_context()

        result = run_assertion(
            type="contains",
            output="The quick brown fox",
            context=ctx,
            value="quick",
        )
        assert result.passed is True

    def test_run_assertion_returns_grading_result(self):
        register_assertion("equals", _EqualsAssertion)
        ctx = _make_context()

        result = run_assertion(
            type="equals",
            output="exact match",
            context=ctx,
            value="exact match",
        )
        assert isinstance(result, GradingResult)
        assert result.passed is True

    def test_run_assertion_passes_threshold_to_cost_constructor(self, monkeypatch):
        """Cost assertions receive the configured threshold during construction."""
        import runsight_core.assertions.deterministic  # noqa: F401
        from runsight_core.assertions.deterministic.performance import CostAssertion

        register_assertion("cost", CostAssertion)
        ctx = _make_context(cost_usd=0.04)
        captured: dict[str, object] = {}
        original_init = CostAssertion.__init__

        def recording_init(self, value=None, threshold=None, config=None):
            captured["value"] = value
            captured["threshold"] = threshold
            captured["config"] = config
            original_init(self, value=value, threshold=threshold)

        monkeypatch.setattr(CostAssertion, "__init__", recording_init)

        run_assertion(
            type="cost",
            output="Hello",
            context=ctx,
            threshold=0.05,
        )

        assert captured["threshold"] == 0.05

    def test_run_assertion_raises_when_constructor_rejects_kwargs(self):
        """Unsupported assertion constructors should fail loudly instead of falling back."""

        class NoKwargsAssertion:
            type: str = "no-kwargs"

            def __init__(self):
                self.initialized = True

            def evaluate(self, output: str, context: AssertionContext) -> GradingResult:
                return GradingResult(
                    passed=True,
                    score=1.0,
                    reason="unexpected success",
                    assertion_type="no-kwargs",
                )

        register_assertion("no-kwargs", NoKwargsAssertion)
        ctx = _make_context()

        with pytest.raises(TypeError):
            run_assertion(
                type="no-kwargs",
                output="Hello",
                context=ctx,
                value="Hello",
                threshold=0.5,
            )

    def test_run_assertion_accepts_threshold_and_weight_and_metric(self):
        """run_assertion accepts threshold, weight, and metric parameters."""
        register_assertion("contains", _ContainsAssertion)
        ctx = _make_context()

        # Should not raise when extra parameters are provided
        result = run_assertion(
            type="contains",
            output="Hello",
            context=ctx,
            value="Hello",
            threshold=0.5,
            weight=2.0,
            metric="accuracy",
        )
        assert isinstance(result, GradingResult)

    def test_run_assertion_passes_config_to_builtin_constructor_without_changing_behavior(
        self, monkeypatch
    ):
        """Builtins receive config in the constructor and still behave the same."""
        import runsight_core.assertions.deterministic  # noqa: F401
        from runsight_core.assertions.deterministic.performance import CostAssertion

        register_assertion("cost", CostAssertion)
        ctx = _make_context(cost_usd=0.04)
        captured: dict[str, object] = {}
        original_init = CostAssertion.__init__

        def recording_init(self, value=None, threshold=None, config=None):
            captured["config"] = config
            original_init(self, value=value, threshold=threshold, config=config)

        monkeypatch.setattr(CostAssertion, "__init__", recording_init)

        result = run_assertion(
            type="cost",
            output="Hello",
            context=ctx,
            threshold=0.05,
            config={"mode": "strict"},
        )

        assert captured["config"] == {"mode": "strict"}
        assert result.passed is True


# ---------------------------------------------------------------------------
# AC-11: run_assertions() runs all with concurrency limit
# ---------------------------------------------------------------------------


class TestRunAssertions:
    @pytest.mark.asyncio
    async def test_run_assertions_returns_assertions_result(self):
        """AC-11: run_assertions returns an AssertionsResult."""
        register_assertion("contains", _ContainsAssertion)
        ctx = _make_context()

        config = [
            {"type": "contains", "value": "Hello"},
        ]
        result = await run_assertions(config, output="Hello world", context=ctx)
        assert isinstance(result, AssertionsResult)

    @pytest.mark.asyncio
    async def test_run_assertions_multiple_assertions(self):
        """AC-11: run_assertions processes all assertions in config."""
        register_assertion("contains", _ContainsAssertion)
        register_assertion("equals", _EqualsAssertion)
        ctx = _make_context()

        config = [
            {"type": "contains", "value": "Hello"},
            {"type": "equals", "value": "Hello world"},
        ]
        result = await run_assertions(config, output="Hello world", context=ctx)
        assert len(result.results) == 2
        assert result.results[0].passed is True
        assert result.results[1].passed is True

    @pytest.mark.asyncio
    async def test_run_assertions_respects_weights(self):
        """run_assertions applies weights from config to AssertionsResult."""
        register_assertion("contains", _ContainsAssertion)
        ctx = _make_context()

        config = [
            {"type": "contains", "value": "Hello", "weight": 3.0},
            {"type": "contains", "value": "xyz", "weight": 1.0},
        ]
        result = await run_assertions(config, output="Hello world", context=ctx)
        # "Hello" passes (score=1.0, weight=3), "xyz" fails (score=0.0, weight=1)
        # aggregate = (1.0*3 + 0.0*1) / (3+1) = 0.75
        assert abs(result.aggregate_score - 0.75) < 1e-9

    @pytest.mark.asyncio
    async def test_run_assertions_default_concurrency_limit(self):
        """AC-11: Default max_concurrent is 10."""
        register_assertion("contains", _ContainsAssertion)
        ctx = _make_context()

        # 15 assertions — should still complete with default concurrency=10
        config = [{"type": "contains", "value": "x"} for _ in range(15)]
        result = await run_assertions(config, output="no match", context=ctx)
        assert len(result.results) == 15

    @pytest.mark.asyncio
    async def test_run_assertions_custom_concurrency_limit(self):
        """AC-11: run_assertions accepts a max_concurrent parameter."""
        register_assertion("contains", _ContainsAssertion)
        ctx = _make_context()

        config = [{"type": "contains", "value": "x"} for _ in range(5)]
        result = await run_assertions(config, output="no match", context=ctx, max_concurrent=2)
        assert len(result.results) == 5

    @pytest.mark.asyncio
    async def test_run_assertions_empty_config(self):
        """run_assertions with an empty config returns an empty AssertionsResult."""
        ctx = _make_context()
        result = await run_assertions([], output="anything", context=ctx)
        assert isinstance(result, AssertionsResult)
        assert len(result.results) == 0
        assert result.aggregate_score == 0.0

    @pytest.mark.asyncio
    async def test_run_assertions_handles_not_prefix(self):
        """run_assertions correctly handles not- prefixed assertions in config."""
        register_assertion("contains", _ContainsAssertion)
        ctx = _make_context()

        config = [
            {"type": "not-contains", "value": "forbidden"},
        ]
        result = await run_assertions(config, output="safe output", context=ctx)
        assert len(result.results) == 1
        assert result.results[0].passed is True
        assert result.results[0].score == 1.0

    @pytest.mark.asyncio
    async def test_run_assertions_weight_zero_in_config(self):
        """AC-8: Weight=0 assertions in config contribute named_scores but not aggregate."""
        register_assertion("contains", _ContainsAssertion)
        ctx = _make_context()

        config = [
            {"type": "contains", "value": "Hello", "weight": 1.0},
            {"type": "contains", "value": "Hello", "weight": 0.0, "metric": "info_check"},
        ]
        result = await run_assertions(config, output="Hello world", context=ctx)
        # Only weight=1.0 assertion in aggregate
        assert abs(result.aggregate_score - 1.0) < 1e-9

    @pytest.mark.asyncio
    async def test_run_assertions_passes_config_to_custom_handler_constructor(self):
        captured: list[object] = []

        class RecordingAssertion:
            type = "recording-async-config"

            def __init__(self, value="", threshold=None, config=None):
                captured.append(config)

            def evaluate(self, output: str, context: AssertionContext) -> GradingResult:
                return GradingResult(
                    passed=True,
                    score=1.0,
                    reason="config recorded",
                    assertion_type=self.type,
                )

        register_assertion("recording-async-config", RecordingAssertion)
        ctx = _make_context()

        result = await run_assertions(
            [{"type": "recording-async-config", "config": {"mode": "strict"}}],
            output="Hello world",
            context=ctx,
        )

        assert result.results[0].passed is True
        assert captured == [{"mode": "strict"}]

    @pytest.mark.asyncio
    async def test_run_assertions_missing_config_defaults_to_none(self):
        captured: list[object] = []

        class RecordingAssertion:
            type = "recording-none-config"

            def __init__(self, value="", threshold=None, config=None):
                captured.append(config)

            def evaluate(self, output: str, context: AssertionContext) -> GradingResult:
                return GradingResult(
                    passed=True,
                    score=1.0,
                    reason="config recorded",
                    assertion_type=self.type,
                )

        register_assertion("recording-none-config", RecordingAssertion)
        ctx = _make_context()

        result = await run_assertions(
            [{"type": "recording-none-config"}],
            output="Hello world",
            context=ctx,
        )

        assert result.results[0].passed is True
        assert captured == [None]


class TestRunAssertionsSync:
    def test_run_assertions_sync_passes_config_to_custom_handler_constructor(self):
        captured: list[object] = []

        class RecordingAssertion:
            type = "recording-sync-config"

            def __init__(self, value="", threshold=None, config=None):
                captured.append(config)

            def evaluate(self, output: str, context: AssertionContext) -> GradingResult:
                return GradingResult(
                    passed=True,
                    score=1.0,
                    reason="config recorded",
                    assertion_type=self.type,
                )

        register_assertion("recording-sync-config", RecordingAssertion)
        ctx = _make_context()

        result = run_assertions_sync(
            [{"type": "recording-sync-config", "config": {"mode": "strict"}}],
            output="Hello world",
            context=ctx,
        )

        assert result.results[0].passed is True
        assert captured == [{"mode": "strict"}]

    def test_run_assertions_sync_passes_non_dict_config_through_unchanged(self):
        captured: list[object] = []

        class RecordingAssertion:
            type = "recording-raw-config"

            def __init__(self, value="", threshold=None, config=None):
                captured.append(config)

            def evaluate(self, output: str, context: AssertionContext) -> GradingResult:
                return GradingResult(
                    passed=True,
                    score=1.0,
                    reason="config recorded",
                    assertion_type=self.type,
                )

        register_assertion("recording-raw-config", RecordingAssertion)
        ctx = _make_context()

        result = run_assertions_sync(
            [{"type": "recording-raw-config", "config": "raw-config-token"}],
            output="Hello world",
            context=ctx,
        )

        assert result.results[0].passed is True
        assert captured == ["raw-config-token"]
