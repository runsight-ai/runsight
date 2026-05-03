"""
JSON schema publishing and validation behavior.

Tests exercise the Pydantic schema models from runsight_core.yaml.schema,
covering:
- Type discrimination (correct type -> correct model, wrong fields rejected)
- output_conditions validation (operators, case_id, empty lists)
- inputs validation (from path structure)
- extra="forbid" enforcement on every block type
- JSON schema generation script in --check mode
"""

from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError
from runsight_core.yaml.schema import (
    BlockDef,
)

# Shared TypeAdapter for the discriminated union
block_adapter = TypeAdapter(BlockDef)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _validate_block(data: dict):
    """Validate a dict as a BlockDef via the discriminated union."""
    return block_adapter.validate_python(data)


# ===========================================================================
# 1. Type discrimination tests
# ===========================================================================


class TestExtraForbid:
    """Every block type model has extra='forbid' and must reject unrecognized fields."""

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
    def test_extra_field_rejected(self, block_data):
        """Adding an unrecognized field to any block type must raise ValidationError."""
        block_data_with_extra = {**block_data, "totally_unknown_field": "nope"}
        with pytest.raises(ValidationError, match="totally_unknown_field"):
            _validate_block(block_data_with_extra)


# ===========================================================================
# 5. Full RunsightWorkflowFile validation
# ===========================================================================
