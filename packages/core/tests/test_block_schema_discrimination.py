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
from runsight_core.blocks.code import CodeBlockDef
from runsight_core.blocks.dispatch import DispatchBlockDef
from runsight_core.blocks.gate import GateBlockDef
from runsight_core.blocks.linear import LinearBlockDef
from runsight_core.blocks.loop import LoopBlockDef
from runsight_core.blocks.synthesize import SynthesizeBlockDef
from runsight_core.blocks.workflow_block import WorkflowBlockDef
from runsight_core.yaml.schema import (
    BlockDef,
    RunsightWorkflowFile,
    SoulDef,
    TransitionDef,
    WorkflowDef,
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

    def test_unknown_type_rejected(self):
        """A type value not in any Literal causes a ValidationError."""
        with pytest.raises(ValidationError):
            _validate_block({"type": "unknown_type", "soul_ref": "s1"})

    def test_conditional_type_rejected(self):
        """'conditional' is not a supported block type."""
        with pytest.raises(ValidationError):
            _validate_block({"type": "conditional"})

    def test_dispatch_valid(self):
        block = _validate_block(
            {
                "type": "dispatch",
                "exits": [
                    {"id": "e1", "label": "E1", "soul_ref": "s1", "task": "Do A"},
                    {"id": "e2", "label": "E2", "soul_ref": "s2", "task": "Do B"},
                ],
            }
        )
        assert isinstance(block, DispatchBlockDef)

    def test_synthesize_valid(self):
        block = _validate_block(
            {"type": "synthesize", "soul_ref": "s1", "input_block_ids": ["b1", "b2"]}
        )
        assert isinstance(block, SynthesizeBlockDef)

    def test_code_valid(self):
        block = _validate_block({"type": "code", "code": "print(1)"})
        assert isinstance(block, CodeBlockDef)
        assert block.timeout_seconds == 30  # default

    def test_gate_valid(self):
        block = _validate_block({"type": "gate", "soul_ref": "s1", "eval_key": "response.ok"})
        assert isinstance(block, GateBlockDef)

    def test_loop_valid(self):
        block = _validate_block({"type": "loop", "inner_block_refs": ["b1"]})
        assert isinstance(block, LoopBlockDef)

    def test_workflow_block_valid(self):
        block = _validate_block({"type": "workflow", "workflow_ref": "sub_workflow"})
        assert isinstance(block, WorkflowBlockDef)


class TestCoreSchemaModelConstructors:
    """Basic schema model constructors preserve aliases and defaults."""

    def test_soul_def_constructor_preserves_required_identity_fields(self):
        soul = SoulDef(
            id="soul1",
            kind="soul",
            name="Researcher",
            role="Researcher",
            system_prompt="You are a researcher.",
        )

        assert soul.id == "soul1"
        assert soul.kind == "soul"
        assert soul.name == "Researcher"
        assert soul.role == "Researcher"

    def test_transition_def_accepts_from_alias(self):
        transition = TransitionDef(**{"from": "block1", "to": "block2"})

        assert transition.from_ == "block1"
        assert transition.to == "block2"

    def test_runsight_workflow_file_applies_version_default(self):
        workflow = WorkflowDef(name="schema_constructor_workflow", entry="block1")
        file_def = RunsightWorkflowFile(
            id="schema_constructor_workflow",
            kind="workflow",
            workflow=workflow,
        )

        assert file_def.workflow.name == "schema_constructor_workflow"
        assert file_def.version == "1.0"


# ===========================================================================
# 2. output_conditions tests
# ===========================================================================
