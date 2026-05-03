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


class TestInputs:
    """Validate InputRef / inputs field on blocks."""

    def test_valid_input_ref(self):
        block = _validate_block(
            {
                "type": "linear",
                "soul_ref": "s1",
                "inputs": {"context": {"from": "step_a.output_field"}},
            }
        )
        assert block.inputs["context"].from_ref == "step_a.output_field"

    def test_input_ref_extra_field_rejected(self):
        """InputRef has extra='forbid'."""
        with pytest.raises(ValidationError):
            _validate_block(
                {
                    "type": "linear",
                    "soul_ref": "s1",
                    "inputs": {"ctx": {"from": "a.b", "garbage": True}},
                }
            )

    def test_input_ref_missing_from(self):
        """InputRef requires 'from' (aliased to from_ref)."""
        with pytest.raises(ValidationError):
            _validate_block(
                {
                    "type": "linear",
                    "soul_ref": "s1",
                    "inputs": {"ctx": {}},
                }
            )

    def test_input_ref_from_field_name_accepted(self):
        """InputRef should accept 'from' key via alias."""
        block = _validate_block(
            {
                "type": "linear",
                "soul_ref": "s1",
                "inputs": {"data": {"from": "upstream.result"}},
            }
        )
        assert block.inputs["data"].from_ref == "upstream.result"


# ===========================================================================
# 4. extra="forbid" tests — every block type rejects unknown fields
# ===========================================================================
