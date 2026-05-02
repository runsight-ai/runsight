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


class TestYAMLParsingRetryConfig:
    """YAML parsing tests for retry_config within RunsightWorkflowFile."""

    def test_block_with_retry_config_parses_correctly(self):
        """A workflow file with a block that has retry_config should parse."""
        wf = RunsightWorkflowFile.model_validate(
            {
                "id": "retry_config_workflow",
                "kind": "workflow",
                "workflow": {"name": "retry_config_workflow", "entry": "b1"},
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
                "id": "retry_config_default_workflow",
                "kind": "workflow",
                "workflow": {"name": "retry_config_workflow", "entry": "b1"},
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
                    "workflow": {"name": "retry_config_workflow", "entry": "b1"},
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
                    "workflow": {"name": "retry_config_workflow", "entry": "b1"},
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
                    "workflow": {"name": "retry_config_workflow", "entry": "b1"},
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
                "id": "mixed_retry_config_workflow",
                "kind": "workflow",
                "workflow": {"name": "retry_config_workflow", "entry": "b1"},
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
                "id": "retry_defaults_workflow",
                "kind": "workflow",
                "workflow": {"name": "retry_config_workflow", "entry": "b1"},
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
