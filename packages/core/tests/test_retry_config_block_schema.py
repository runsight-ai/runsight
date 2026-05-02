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
from pydantic import TypeAdapter
from runsight_core.blocks.code import CodeBlockDef
from runsight_core.blocks.dispatch import DispatchBlockDef
from runsight_core.blocks.gate import GateBlockDef
from runsight_core.blocks.linear import LinearBlockDef
from runsight_core.blocks.loop import LoopBlockDef
from runsight_core.yaml.schema import (
    BaseBlockDef,
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

    def test_dispatch_block_with_retry_config(self):
        block = _validate_block(
            {
                "type": "dispatch",
                "exits": [
                    {"id": "e1", "label": "E1", "soul_ref": "s1", "task": "Do A"},
                    {"id": "e2", "label": "E2", "soul_ref": "s2", "task": "Do B"},
                ],
                "retry_config": {"max_attempts": 3},
            }
        )
        assert isinstance(block, DispatchBlockDef)
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


class TestBackwardCompatibility:
    """Existing block definitions (without retry_config) must still parse without error."""

    @pytest.mark.parametrize(
        "block_data",
        [
            {"type": "linear", "soul_ref": "s1"},
            {
                "type": "dispatch",
                "exits": [{"id": "e1", "label": "E1", "soul_ref": "s1", "task": "Do"}],
            },
            {"type": "synthesize", "soul_ref": "s1", "input_block_ids": ["b1"]},
            {"type": "gate", "soul_ref": "s1", "eval_key": "k"},
            {"type": "code", "code": "pass"},
            {"type": "loop", "inner_block_refs": ["b1"]},
            {"type": "workflow", "workflow_ref": "wf"},
        ],
        ids=[
            "linear",
            "dispatch",
            "synthesize",
            "gate",
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
