"""
Validation test suite for RUN-113: JSON Schema Publishing + Validation.

Tests exercise the Pydantic schema models from runsight_core.yaml.schema,
covering:
- Type discrimination (correct type -> correct model, wrong fields rejected)
- output_conditions validation (operators, case_id, empty lists)
- inputs validation (from path structure)
- extra="forbid" enforcement on every block type
- PlaceholderBlock allows description but rejects other extras
- JSON schema generation script in --check mode
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from runsight_core.yaml.schema import (
    BlockDef,
    CodeBlockDef,
    DebateBlockDef,
    FanOutBlockDef,
    GateBlockDef,
    LinearBlockDef,
    PlaceholderBlockDef,
    RetryBlockDef,
    RouterBlockDef,
    RunsightWorkflowFile,
    SynthesizeBlockDef,
    WorkflowBlockDef,
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


class TestTypeDiscrimination:
    """Ensure the discriminated union routes to the correct model and rejects bad data."""

    def test_linear_valid(self):
        block = _validate_block({"type": "linear", "soul_ref": "s1"})
        assert isinstance(block, LinearBlockDef)
        assert block.soul_ref == "s1"

    def test_linear_with_wrong_field_iterations(self):
        """LinearBlockDef does not have 'iterations'; extra='forbid' rejects it."""
        with pytest.raises(ValidationError, match="iterations"):
            _validate_block({"type": "linear", "soul_ref": "s1", "iterations": 5})

    def test_debate_valid(self):
        block = _validate_block(
            {"type": "debate", "soul_a_ref": "a", "soul_b_ref": "b", "iterations": 3}
        )
        assert isinstance(block, DebateBlockDef)
        assert block.iterations == 3

    def test_debate_missing_soul_a_ref(self):
        """DebateBlockDef requires soul_a_ref."""
        with pytest.raises(ValidationError, match="soul_a_ref"):
            _validate_block({"type": "debate", "soul_b_ref": "b", "iterations": 3})

    def test_unknown_type_rejected(self):
        """A type value not in any Literal causes a ValidationError."""
        with pytest.raises(ValidationError):
            _validate_block({"type": "unknown_type", "soul_ref": "s1"})

    def test_conditional_type_rejected(self):
        """'conditional' was removed in RUN-114 — must not be accepted."""
        with pytest.raises(ValidationError):
            _validate_block({"type": "conditional"})

    def test_fanout_valid(self):
        block = _validate_block({"type": "fanout", "soul_refs": ["s1", "s2"]})
        assert isinstance(block, FanOutBlockDef)

    def test_synthesize_valid(self):
        block = _validate_block(
            {"type": "synthesize", "soul_ref": "s1", "input_block_ids": ["b1", "b2"]}
        )
        assert isinstance(block, SynthesizeBlockDef)

    def test_code_valid(self):
        block = _validate_block({"type": "code", "code": "print(1)"})
        assert isinstance(block, CodeBlockDef)
        assert block.timeout_seconds == 30  # default

    def test_router_valid(self):
        block = _validate_block({"type": "router", "soul_ref": "s1"})
        assert isinstance(block, RouterBlockDef)

    def test_gate_valid(self):
        block = _validate_block({"type": "gate", "soul_ref": "s1", "eval_key": "response.ok"})
        assert isinstance(block, GateBlockDef)

    def test_retry_valid(self):
        block = _validate_block({"type": "retry", "inner_block_ref": "b1"})
        assert isinstance(block, RetryBlockDef)

    def test_workflow_block_valid(self):
        block = _validate_block({"type": "workflow", "workflow_ref": "sub_wf"})
        assert isinstance(block, WorkflowBlockDef)


# ===========================================================================
# 2. output_conditions tests
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


class TestExtraForbid:
    """Every block type model has extra='forbid' and must reject unrecognized fields."""

    @pytest.mark.parametrize(
        "block_data",
        [
            {"type": "linear", "soul_ref": "s1"},
            {"type": "fanout", "soul_refs": ["s1"]},
            {"type": "synthesize", "soul_ref": "s1", "input_block_ids": ["b1"]},
            {"type": "debate", "soul_a_ref": "a", "soul_b_ref": "b", "iterations": 1},
            {"type": "message_bus", "soul_refs": ["s1"], "iterations": 1},
            {"type": "router", "soul_ref": "s1"},
            {"type": "team_lead", "soul_ref": "s1"},
            {"type": "engineering_manager", "soul_ref": "s1"},
            {"type": "gate", "soul_ref": "s1", "eval_key": "k"},
            {"type": "placeholder"},
            {"type": "file_writer", "output_path": "/tmp/f", "content_key": "k"},
            {"type": "code", "code": "pass"},
            {"type": "retry", "inner_block_ref": "b1"},
            {"type": "workflow", "workflow_ref": "wf"},
        ],
        ids=[
            "linear",
            "fanout",
            "synthesize",
            "debate",
            "message_bus",
            "router",
            "team_lead",
            "engineering_manager",
            "gate",
            "placeholder",
            "file_writer",
            "code",
            "retry",
            "workflow",
        ],
    )
    def test_extra_field_rejected(self, block_data):
        """Adding an unrecognized field to any block type must raise ValidationError."""
        block_data_with_extra = {**block_data, "totally_unknown_field": "nope"}
        with pytest.raises(ValidationError, match="totally_unknown_field"):
            _validate_block(block_data_with_extra)

    def test_placeholder_allows_description(self):
        """PlaceholderBlockDef has an explicit 'description' field — it must be accepted."""
        block = _validate_block({"type": "placeholder", "description": "A TODO block"})
        assert isinstance(block, PlaceholderBlockDef)
        assert block.description == "A TODO block"

    def test_placeholder_rejects_other_extras(self):
        """PlaceholderBlockDef should reject fields beyond its declared set."""
        with pytest.raises(ValidationError, match="random_field"):
            _validate_block({"type": "placeholder", "description": "ok", "random_field": "bad"})


# ===========================================================================
# 5. Full RunsightWorkflowFile validation
# ===========================================================================


class TestRunsightWorkflowFile:
    """End-to-end validation of the root model."""

    def test_minimal_valid_file(self):
        wf = RunsightWorkflowFile.model_validate(
            {
                "workflow": {"name": "test", "entry": "b1"},
                "blocks": {"b1": {"type": "placeholder"}},
            }
        )
        assert wf.workflow.name == "test"
        assert "b1" in wf.blocks
        assert isinstance(wf.blocks["b1"], PlaceholderBlockDef)

    def test_missing_workflow_key(self):
        """workflow is required at root level."""
        with pytest.raises(ValidationError, match="workflow"):
            RunsightWorkflowFile.model_validate({"blocks": {}})

    def test_block_discrimination_in_file(self):
        """Blocks inside the file should be discriminated correctly."""
        wf = RunsightWorkflowFile.model_validate(
            {
                "workflow": {"name": "test", "entry": "b1"},
                "blocks": {
                    "b1": {"type": "linear", "soul_ref": "s1"},
                    "b2": {"type": "code", "code": "x = 1"},
                },
            }
        )
        assert isinstance(wf.blocks["b1"], LinearBlockDef)
        assert isinstance(wf.blocks["b2"], CodeBlockDef)


# ===========================================================================
# 6. Schema generation script tests
# ===========================================================================


class TestSchemaGenerationScript:
    """Test the generate_schema.py script in --check mode."""

    SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "generate_schema.py"
    SCHEMA_PATH = Path(__file__).resolve().parent.parent / "runsight-workflow-schema.json"

    def test_check_passes_when_in_sync(self):
        """--check should exit 0 when the schema file matches."""
        result = subprocess.run(
            [sys.executable, str(self.SCRIPT_PATH), "--check"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
        assert "OK" in result.stdout

    def test_schema_file_exists(self):
        """The schema file should exist after generation."""
        assert self.SCHEMA_PATH.exists(), f"{self.SCHEMA_PATH} not found"

    def test_schema_is_valid_json(self):
        """The schema file must be valid JSON."""
        content = self.SCHEMA_PATH.read_text()
        schema = json.loads(content)
        assert "$defs" in schema or "properties" in schema
