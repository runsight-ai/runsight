"""
RetryConfig property behavior on BaseBlockDef.

Tests cover:
- RetryConfig model: defaults, full specification, validation constraints
- BaseBlockDef integration: optional retry_config field
- YAML parsing: blocks with/without retry_config, invalid values rejected
- Backward compatibility: existing blocks parse without error
- Edge cases: max_attempts=1, empty list vs None for non_retryable_errors
"""

import pytest
from pydantic import TypeAdapter, ValidationError
from runsight_core.blocks.linear import LinearBlockDef
from runsight_core.yaml.schema import (
    BlockDef,
    RetryConfig,
)

# Shared TypeAdapter for the discriminated union
block_adapter = TypeAdapter(BlockDef)


def _validate_block(data: dict):
    """Validate a dict as a BlockDef via the discriminated union."""
    return block_adapter.validate_python(data)


# ===========================================================================
# 1. RetryConfig model — defaults and valid instantiation
# ===========================================================================


class TestRetryConfigDefaults:
    """RetryConfig instantiation with default values."""

    def test_default_max_attempts(self):
        """Default max_attempts should be 3."""
        config = RetryConfig()
        assert config.max_attempts == 3

    def test_default_backoff(self):
        """Default backoff strategy should be 'fixed'."""
        config = RetryConfig()
        assert config.backoff == "fixed"

    def test_default_backoff_base_seconds(self):
        """Default backoff_base_seconds should be 1.0."""
        config = RetryConfig()
        assert config.backoff_base_seconds == 1.0

    def test_default_non_retryable_errors(self):
        """Default non_retryable_errors should be None."""
        config = RetryConfig()
        assert config.non_retryable_errors is None


class TestRetryConfigFullSpec:
    """RetryConfig with all fields explicitly specified."""

    def test_all_fields_specified(self):
        """All four fields can be explicitly provided."""
        config = RetryConfig(
            max_attempts=5,
            backoff="exponential",
            backoff_base_seconds=2.5,
            non_retryable_errors=["ValueError", "TypeError"],
        )
        assert config.max_attempts == 5
        assert config.backoff == "exponential"
        assert config.backoff_base_seconds == 2.5
        assert config.non_retryable_errors == ["ValueError", "TypeError"]

    def test_backoff_fixed_explicit(self):
        """Explicitly setting backoff='fixed' is valid."""
        config = RetryConfig(backoff="fixed")
        assert config.backoff == "fixed"

    def test_backoff_exponential(self):
        """Setting backoff='exponential' is valid."""
        config = RetryConfig(backoff="exponential")
        assert config.backoff == "exponential"


# ===========================================================================
# 2. RetryConfig validation constraints
# ===========================================================================


class TestRetryConfigValidation:
    """Validation constraints on RetryConfig fields."""

    def test_max_attempts_zero_rejected(self):
        """max_attempts=0 is below minimum (ge=1), must be rejected."""
        with pytest.raises(ValidationError):
            RetryConfig(max_attempts=0)

    def test_max_attempts_negative_rejected(self):
        """max_attempts=-1 is below minimum, must be rejected."""
        with pytest.raises(ValidationError):
            RetryConfig(max_attempts=-1)

    def test_max_attempts_21_rejected(self):
        """max_attempts=21 exceeds maximum (le=20), must be rejected."""
        with pytest.raises(ValidationError):
            RetryConfig(max_attempts=21)

    def test_max_attempts_100_rejected(self):
        """max_attempts=100 far exceeds maximum, must be rejected."""
        with pytest.raises(ValidationError):
            RetryConfig(max_attempts=100)

    def test_max_attempts_1_valid(self):
        """max_attempts=1 means 'run once, no retry' — valid edge case."""
        config = RetryConfig(max_attempts=1)
        assert config.max_attempts == 1

    def test_max_attempts_20_valid(self):
        """max_attempts=20 is the upper boundary — valid."""
        config = RetryConfig(max_attempts=20)
        assert config.max_attempts == 20

    def test_backoff_base_seconds_zero_rejected(self):
        """backoff_base_seconds=0 is below minimum (ge=0.1), must be rejected."""
        with pytest.raises(ValidationError):
            RetryConfig(backoff_base_seconds=0)

    def test_backoff_base_seconds_negative_rejected(self):
        """backoff_base_seconds=-1.0 is below minimum, must be rejected."""
        with pytest.raises(ValidationError):
            RetryConfig(backoff_base_seconds=-1.0)

    def test_backoff_base_seconds_too_small_rejected(self):
        """backoff_base_seconds=0.05 is below minimum (ge=0.1), must be rejected."""
        with pytest.raises(ValidationError):
            RetryConfig(backoff_base_seconds=0.05)

    def test_backoff_base_seconds_61_rejected(self):
        """backoff_base_seconds=61 exceeds maximum (le=60.0), must be rejected."""
        with pytest.raises(ValidationError):
            RetryConfig(backoff_base_seconds=61)

    def test_backoff_base_seconds_0_1_valid(self):
        """backoff_base_seconds=0.1 is the lower boundary — valid."""
        config = RetryConfig(backoff_base_seconds=0.1)
        assert config.backoff_base_seconds == 0.1

    def test_backoff_base_seconds_60_valid(self):
        """backoff_base_seconds=60.0 is the upper boundary — valid."""
        config = RetryConfig(backoff_base_seconds=60.0)
        assert config.backoff_base_seconds == 60.0

    def test_invalid_backoff_strategy_rejected(self):
        """backoff must be 'fixed' or 'exponential' — other values rejected."""
        with pytest.raises(ValidationError):
            RetryConfig(backoff="linear")

    def test_invalid_backoff_strategy_random_string_rejected(self):
        """Arbitrary string for backoff must be rejected."""
        with pytest.raises(ValidationError):
            RetryConfig(backoff="random_strategy")


# ===========================================================================
# 3. non_retryable_errors field
# ===========================================================================


class TestNonRetryableErrors:
    """non_retryable_errors accepts list[str] and None."""

    def test_none_is_valid(self):
        """None means 'retry all errors'."""
        config = RetryConfig(non_retryable_errors=None)
        assert config.non_retryable_errors is None

    def test_empty_list_is_valid(self):
        """Empty list also means 'retry all errors'."""
        config = RetryConfig(non_retryable_errors=[])
        assert config.non_retryable_errors == []

    def test_list_of_strings(self):
        """List of exception class names is valid."""
        errors = ["ValueError", "KeyError", "TimeoutError"]
        config = RetryConfig(non_retryable_errors=errors)
        assert config.non_retryable_errors == errors

    def test_single_error_string(self):
        """Single-element list is valid."""
        config = RetryConfig(non_retryable_errors=["RuntimeError"])
        assert config.non_retryable_errors == ["RuntimeError"]


# ===========================================================================
# 4. RetryConfig importable from runsight_core.yaml.schema
# ===========================================================================


class TestRetryConfigImport:
    """RetryConfig must be importable from the schema module."""

    def test_retry_config_is_importable(self):
        """RetryConfig should be importable from runsight_core.yaml.schema."""
        from runsight_core.yaml.schema import RetryConfig as RC

        assert RC is not None
        # Verify it's a Pydantic model
        assert hasattr(RC, "model_fields")


# ===========================================================================
# 5. BaseBlockDef has optional retry_config field
# ===========================================================================


class TestRetryConfigSerialization:
    """RetryConfig serializes and deserializes correctly."""

    def test_model_dump_with_retry_config(self):
        """Block with retry_config should include it in model_dump."""
        block = LinearBlockDef(
            soul_ref="s1",
            retry_config=RetryConfig(max_attempts=5, backoff="exponential"),
        )
        dumped = block.model_dump()
        assert "retry_config" in dumped
        assert dumped["retry_config"]["max_attempts"] == 5
        assert dumped["retry_config"]["backoff"] == "exponential"

    def test_model_dump_without_retry_config(self):
        """Block without retry_config should have None in dump."""
        block = LinearBlockDef(soul_ref="s1")
        dumped = block.model_dump()
        assert dumped["retry_config"] is None

    def test_model_dump_exclude_none(self):
        """Block without retry_config, dumped with exclude_none, omits it."""
        block = LinearBlockDef(soul_ref="s1")
        dumped = block.model_dump(exclude_none=True)
        assert "retry_config" not in dumped

    def test_round_trip_via_dict(self):
        """Validate a block with retry_config from dict, dump, re-validate."""
        data = {
            "type": "linear",
            "soul_ref": "s1",
            "retry_config": {
                "max_attempts": 10,
                "backoff": "exponential",
                "backoff_base_seconds": 3.0,
                "non_retryable_errors": ["AuthError", "RateLimitError"],
            },
        }
        block = _validate_block(data)
        dumped = block.model_dump()
        block2 = _validate_block(dumped)
        assert block2.retry_config.max_attempts == 10
        assert block2.retry_config.non_retryable_errors == ["AuthError", "RateLimitError"]
