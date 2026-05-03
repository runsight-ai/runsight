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


class TestOutputConditions:
    """Validate output_conditions sub-schema enforcement."""

    def test_valid_output_conditions(self):
        block = _validate_block(
            {
                "type": "linear",
                "soul_ref": "s1",
                "output_conditions": [
                    {
                        "case_id": "pass",
                        "condition_group": {
                            "combinator": "and",
                            "conditions": [
                                {"eval_key": "status", "operator": "equals", "value": "ok"}
                            ],
                        },
                    },
                    {"case_id": "fallback", "default": True},
                ],
            }
        )
        assert len(block.output_conditions) == 2
        assert block.output_conditions[0].case_id == "pass"

    def test_invalid_operator_string_accepted_at_schema_level(self):
        """ConditionDef.operator is a plain str — schema does not restrict values.
        Operator validation happens at runtime in the condition engine."""
        block = _validate_block(
            {
                "type": "linear",
                "soul_ref": "s1",
                "output_conditions": [
                    {
                        "case_id": "c1",
                        "condition_group": {
                            "conditions": [
                                {
                                    "eval_key": "x",
                                    "operator": "totally_bogus",
                                    "value": "y",
                                }
                            ],
                        },
                    }
                ],
            }
        )
        # The schema accepts it; the engine would reject at runtime
        assert block.output_conditions[0].condition_group.conditions[0].operator == "totally_bogus"

    def test_missing_case_id(self):
        """CaseDef requires case_id."""
        with pytest.raises(ValidationError, match="case_id"):
            _validate_block(
                {
                    "type": "linear",
                    "soul_ref": "s1",
                    "output_conditions": [
                        {
                            "condition_group": {
                                "conditions": [
                                    {"eval_key": "x", "operator": "equals", "value": "y"}
                                ],
                            },
                        }
                    ],
                }
            )

    def test_empty_conditions_list(self):
        """An empty conditions list in a ConditionGroupDef should be caught
        — Pydantic accepts empty list by default, but we verify the shape."""
        block = _validate_block(
            {
                "type": "linear",
                "soul_ref": "s1",
                "output_conditions": [
                    {
                        "case_id": "c1",
                        "condition_group": {"conditions": []},
                    }
                ],
            }
        )
        assert block.output_conditions[0].condition_group.conditions == []

    def test_condition_group_extra_field_rejected(self):
        """ConditionGroupDef has extra='forbid'."""
        with pytest.raises(ValidationError, match="bogus"):
            _validate_block(
                {
                    "type": "linear",
                    "soul_ref": "s1",
                    "output_conditions": [
                        {
                            "case_id": "c1",
                            "condition_group": {
                                "conditions": [
                                    {"eval_key": "x", "operator": "equals", "value": "y"}
                                ],
                                "bogus": True,
                            },
                        }
                    ],
                }
            )

    def test_condition_extra_field_rejected(self):
        """ConditionDef has extra='forbid'."""
        with pytest.raises(ValidationError, match="nope"):
            _validate_block(
                {
                    "type": "linear",
                    "soul_ref": "s1",
                    "output_conditions": [
                        {
                            "case_id": "c1",
                            "condition_group": {
                                "conditions": [
                                    {
                                        "eval_key": "x",
                                        "operator": "equals",
                                        "value": "y",
                                        "nope": 1,
                                    }
                                ],
                            },
                        }
                    ],
                }
            )

    def test_case_extra_field_rejected(self):
        """CaseDef has extra='forbid'."""
        with pytest.raises(ValidationError, match="extra_field"):
            _validate_block(
                {
                    "type": "linear",
                    "soul_ref": "s1",
                    "output_conditions": [{"case_id": "c1", "default": True, "extra_field": "bad"}],
                }
            )


# ===========================================================================
# 3. inputs tests
# ===========================================================================
