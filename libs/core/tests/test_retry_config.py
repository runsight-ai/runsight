"""
Failing tests for RUN-156: Add `retry_config` property to BaseBlockDef.

Tests cover:
- RetryConfig model: defaults, full specification, validation constraints
- BaseBlockDef integration: optional retry_config field
- YAML parsing: blocks with/without retry_config, invalid values rejected
- Backward compatibility: existing blocks parse without error
- Edge cases: max_attempts=1, empty list vs None for non_retryable_errors
"""

import pytest
from pydantic import TypeAdapter, ValidationError

from runsight_core.blocks.code import CodeBlockDef
from runsight_core.blocks.fanout import FanOutBlockDef
from runsight_core.blocks.gate import GateBlockDef
from runsight_core.blocks.linear import LinearBlockDef
from runsight_core.blocks.loop import LoopBlockDef
from runsight_core.yaml.schema import (
    BaseBlockDef,
    BlockDef,
    RetryConfig,
    RunsightWorkflowFile,
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


class TestBaseBlockDefRetryConfig:
    """BaseBlockDef should have an optional retry_config field."""

    def test_retry_config_field_exists_on_base_block(self):
        """BaseBlockDef must declare retry_config in its model_fields."""
        assert "retry_config" in BaseBlockDef.model_fields

    def test_retry_config_defaults_to_none(self):
        """A block without retry_config should default to None."""
        block = LinearBlockDef(soul_ref="s1")
        assert block.retry_config is None

    def test_retry_config_can_be_set(self):
        """A block can be created with a retry_config."""
        rc = RetryConfig(max_attempts=5, backoff="exponential")
        block = LinearBlockDef(soul_ref="s1", retry_config=rc)
        assert block.retry_config is not None
        assert block.retry_config.max_attempts == 5
        assert block.retry_config.backoff == "exponential"


# ===========================================================================
# 6. retry_config on various block types (inherits from BaseBlockDef)
# ===========================================================================


class TestRetryConfigOnAllBlockTypes:
    """retry_config should be available on all block types since BaseBlockDef has it."""

    def test_linear_block_with_retry_config(self):
        block = _validate_block(
            {
                "type": "linear",
                "soul_ref": "s1",
                "retry_config": {"max_attempts": 2, "backoff": "fixed"},
            }
        )
        assert isinstance(block, LinearBlockDef)
        assert block.retry_config is not None
        assert block.retry_config.max_attempts == 2

    def test_code_block_with_retry_config(self):
        block = _validate_block(
            {
                "type": "code",
                "code": "print('hello')",
                "retry_config": {
                    "max_attempts": 5,
                    "backoff": "exponential",
                    "backoff_base_seconds": 2.0,
                },
            }
        )
        assert isinstance(block, CodeBlockDef)
        assert block.retry_config.max_attempts == 5
        assert block.retry_config.backoff == "exponential"
        assert block.retry_config.backoff_base_seconds == 2.0

    def test_fanout_block_with_retry_config(self):
        block = _validate_block(
            {
                "type": "fanout",
                "soul_refs": ["s1", "s2"],
                "retry_config": {"max_attempts": 3},
            }
        )
        assert isinstance(block, FanOutBlockDef)
        assert block.retry_config is not None

    def test_gate_block_with_retry_config(self):
        block = _validate_block(
            {
                "type": "gate",
                "soul_ref": "s1",
                "eval_key": "response.ok",
                "retry_config": {"non_retryable_errors": ["AuthError"]},
            }
        )
        assert isinstance(block, GateBlockDef)
        assert block.retry_config.non_retryable_errors == ["AuthError"]

    def test_loop_block_with_retry_config(self):
        """LoopBlockDef can have retry_config — they coexist."""
        block = _validate_block(
            {
                "type": "loop",
                "inner_block_refs": ["b1"],
                "retry_config": {"max_attempts": 2},
            }
        )
        assert isinstance(block, LoopBlockDef)
        assert block.retry_config is not None
        assert block.retry_config.max_attempts == 2

    def test_linear_block_without_retry_config(self):
        """Block without retry_config still works — defaults to None."""
        block = _validate_block({"type": "linear", "soul_ref": "s1"})
        assert block.retry_config is None


# ===========================================================================
# 7. YAML parsing — blocks with retry_config in RunsightWorkflowFile
# ===========================================================================


class TestYAMLParsingRetryConfig:
    """YAML parsing tests for retry_config within RunsightWorkflowFile."""

    def test_block_with_retry_config_parses_correctly(self):
        """A workflow file with a block that has retry_config should parse."""
        wf = RunsightWorkflowFile.model_validate(
            {
                "workflow": {"name": "test", "entry": "b1"},
                "blocks": {
                    "b1": {
                        "type": "linear",
                        "soul_ref": "s1",
                        "retry_config": {
                            "max_attempts": 5,
                            "backoff": "exponential",
                            "backoff_base_seconds": 2.0,
                            "non_retryable_errors": ["ValueError"],
                        },
                    },
                },
            }
        )
        block = wf.blocks["b1"]
        assert isinstance(block, LinearBlockDef)
        assert block.retry_config is not None
        assert block.retry_config.max_attempts == 5
        assert block.retry_config.backoff == "exponential"
        assert block.retry_config.backoff_base_seconds == 2.0
        assert block.retry_config.non_retryable_errors == ["ValueError"]

    def test_block_without_retry_config_defaults_to_none(self):
        """A block without retry_config in YAML should default to None."""
        wf = RunsightWorkflowFile.model_validate(
            {
                "workflow": {"name": "test", "entry": "b1"},
                "blocks": {
                    "b1": {"type": "linear", "soul_ref": "s1"},
                },
            }
        )
        assert wf.blocks["b1"].retry_config is None

    def test_invalid_retry_config_max_attempts_rejected(self):
        """max_attempts=0 inside a workflow file should be rejected."""
        with pytest.raises(ValidationError):
            RunsightWorkflowFile.model_validate(
                {
                    "workflow": {"name": "test", "entry": "b1"},
                    "blocks": {
                        "b1": {
                            "type": "linear",
                            "soul_ref": "s1",
                            "retry_config": {"max_attempts": 0},
                        },
                    },
                }
            )

    def test_invalid_retry_config_backoff_rejected(self):
        """Invalid backoff value inside a workflow file should be rejected."""
        with pytest.raises(ValidationError):
            RunsightWorkflowFile.model_validate(
                {
                    "workflow": {"name": "test", "entry": "b1"},
                    "blocks": {
                        "b1": {
                            "type": "linear",
                            "soul_ref": "s1",
                            "retry_config": {"backoff": "quadratic"},
                        },
                    },
                }
            )

    def test_invalid_retry_config_backoff_base_seconds_rejected(self):
        """backoff_base_seconds=0 inside a workflow file should be rejected."""
        with pytest.raises(ValidationError):
            RunsightWorkflowFile.model_validate(
                {
                    "workflow": {"name": "test", "entry": "b1"},
                    "blocks": {
                        "b1": {
                            "type": "linear",
                            "soul_ref": "s1",
                            "retry_config": {"backoff_base_seconds": 0},
                        },
                    },
                }
            )

    def test_multiple_blocks_mixed_retry_config(self):
        """Multiple blocks — some with retry_config, some without."""
        wf = RunsightWorkflowFile.model_validate(
            {
                "workflow": {"name": "test", "entry": "b1"},
                "blocks": {
                    "b1": {
                        "type": "linear",
                        "soul_ref": "s1",
                        "retry_config": {"max_attempts": 2},
                    },
                    "b2": {"type": "code", "code": "pass"},
                    "b3": {
                        "type": "gate",
                        "soul_ref": "s1",
                        "eval_key": "k",
                        "retry_config": {"backoff": "exponential", "backoff_base_seconds": 5.0},
                    },
                },
            }
        )
        assert wf.blocks["b1"].retry_config is not None
        assert wf.blocks["b1"].retry_config.max_attempts == 2
        assert wf.blocks["b2"].retry_config is None
        assert wf.blocks["b3"].retry_config is not None
        assert wf.blocks["b3"].retry_config.backoff == "exponential"

    def test_retry_config_with_only_defaults_parses(self):
        """retry_config: {} (empty dict) should parse and use all defaults."""
        wf = RunsightWorkflowFile.model_validate(
            {
                "workflow": {"name": "test", "entry": "b1"},
                "blocks": {
                    "b1": {
                        "type": "linear",
                        "soul_ref": "s1",
                        "retry_config": {},
                    },
                },
            }
        )
        rc = wf.blocks["b1"].retry_config
        assert rc is not None
        assert rc.max_attempts == 3
        assert rc.backoff == "fixed"
        assert rc.backoff_base_seconds == 1.0
        assert rc.non_retryable_errors is None


# ===========================================================================
# 8. Backward compatibility — existing blocks still parse
# ===========================================================================


class TestBackwardCompatibility:
    """Existing block definitions (without retry_config) must still parse without error."""

    @pytest.mark.parametrize(
        "block_data",
        [
            {"type": "linear", "soul_ref": "s1"},
            {"type": "fanout", "soul_refs": ["s1"]},
            {"type": "synthesize", "soul_ref": "s1", "input_block_ids": ["b1"]},
            {"type": "router", "soul_ref": "s1"},
            {"type": "team_lead", "soul_ref": "s1"},
            {"type": "engineering_manager", "soul_ref": "s1"},
            {"type": "gate", "soul_ref": "s1", "eval_key": "k"},
            {"type": "file_writer", "output_path": "/tmp/f", "content_key": "k"},
            {"type": "code", "code": "pass"},
            {"type": "loop", "inner_block_refs": ["b1"]},
            {"type": "workflow", "workflow_ref": "wf"},
        ],
        ids=[
            "linear",
            "fanout",
            "synthesize",
            "router",
            "team_lead",
            "engineering_manager",
            "gate",
            "file_writer",
            "code",
            "loop",
            "workflow",
        ],
    )
    def test_existing_block_parses_without_retry_config(self, block_data):
        """All existing block types must parse without retry_config — backward compatible."""
        block = _validate_block(block_data)
        assert block.retry_config is None


# ===========================================================================
# 9. Serialization round-trip
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
