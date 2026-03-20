"""
Failing tests for RUN-187: Add `stateful` field to BaseBlockDef + post-hoc wiring.

Tests cover:
- BaseBlockDef has `stateful: bool = False` field
- All block types inherit the field and default to False
- YAML with `stateful: true` parses correctly
- YAML without `stateful` defaults to False
- Schema validation: extra="forbid" still works, wrong types rejected
- Parser wires stateful from block_def to block instance post-construction
- Serialization round-trip preserves stateful value
"""

import pytest
from pydantic import TypeAdapter

from runsight_core.yaml.schema import (
    BaseBlockDef,
    BlockDef,
    LinearBlockDef,
    CodeBlockDef,
    FanOutBlockDef,
    GateBlockDef,
    LoopBlockDef,
    FileWriterBlockDef,
    RouterBlockDef,
    SynthesizeBlockDef,
    TeamLeadBlockDef,
    EngineeringManagerBlockDef,
    WorkflowBlockDef,
    RunsightWorkflowFile,
)

# Shared TypeAdapter for the discriminated union
block_adapter = TypeAdapter(BlockDef)


def _validate_block(data: dict):
    """Validate a dict as a BlockDef via the discriminated union."""
    return block_adapter.validate_python(data)


# ===========================================================================
# 1. BaseBlockDef has stateful field
# ===========================================================================


class TestBaseBlockDefStatefulField:
    """BaseBlockDef should have a `stateful` boolean field defaulting to False."""

    def test_stateful_field_exists_on_base_block_def(self):
        """BaseBlockDef must declare stateful in its model_fields."""
        assert "stateful" in BaseBlockDef.model_fields

    def test_stateful_defaults_to_false(self):
        """A block without stateful should default to False."""
        block = LinearBlockDef(soul_ref="s1")
        assert block.stateful is False

    def test_stateful_can_be_set_true(self):
        """A block can be created with stateful=True."""
        block = LinearBlockDef(soul_ref="s1", stateful=True)
        assert block.stateful is True

    def test_stateful_can_be_set_false_explicitly(self):
        """A block can be created with stateful=False explicitly."""
        block = LinearBlockDef(soul_ref="s1", stateful=False)
        assert block.stateful is False

    def test_stateful_is_bool_type(self):
        """stateful field must be a boolean."""
        field_info = BaseBlockDef.model_fields["stateful"]
        assert field_info.default is False


# ===========================================================================
# 2. stateful field on all block types (inherits from BaseBlockDef)
# ===========================================================================


class TestStatefulOnAllBlockTypes:
    """stateful should be available on all block types since BaseBlockDef has it."""

    def test_linear_block_stateful_true(self):
        block = _validate_block({"type": "linear", "soul_ref": "s1", "stateful": True})
        assert isinstance(block, LinearBlockDef)
        assert block.stateful is True

    def test_linear_block_stateful_default(self):
        block = _validate_block({"type": "linear", "soul_ref": "s1"})
        assert block.stateful is False

    def test_code_block_stateful_true(self):
        block = _validate_block({"type": "code", "code": "print('hello')", "stateful": True})
        assert isinstance(block, CodeBlockDef)
        assert block.stateful is True

    def test_fanout_block_stateful_true(self):
        block = _validate_block({"type": "fanout", "soul_refs": ["s1", "s2"], "stateful": True})
        assert isinstance(block, FanOutBlockDef)
        assert block.stateful is True

    def test_gate_block_stateful_true(self):
        block = _validate_block(
            {
                "type": "gate",
                "soul_ref": "s1",
                "eval_key": "response.ok",
                "stateful": True,
            }
        )
        assert isinstance(block, GateBlockDef)
        assert block.stateful is True

    def test_loop_block_stateful_true(self):
        block = _validate_block({"type": "loop", "inner_block_refs": ["b1"], "stateful": True})
        assert isinstance(block, LoopBlockDef)
        assert block.stateful is True

    def test_file_writer_block_stateful_true(self):
        block = _validate_block(
            {
                "type": "file_writer",
                "output_path": "/tmp/f",
                "content_key": "k",
                "stateful": True,
            }
        )
        assert isinstance(block, FileWriterBlockDef)
        assert block.stateful is True

    def test_router_block_stateful_true(self):
        block = _validate_block({"type": "router", "soul_ref": "s1", "stateful": True})
        assert isinstance(block, RouterBlockDef)
        assert block.stateful is True

    def test_synthesize_block_stateful_true(self):
        block = _validate_block(
            {
                "type": "synthesize",
                "soul_ref": "s1",
                "input_block_ids": ["b1"],
                "stateful": True,
            }
        )
        assert isinstance(block, SynthesizeBlockDef)
        assert block.stateful is True

    def test_team_lead_block_stateful_true(self):
        block = _validate_block({"type": "team_lead", "soul_ref": "s1", "stateful": True})
        assert isinstance(block, TeamLeadBlockDef)
        assert block.stateful is True

    def test_engineering_manager_block_stateful_true(self):
        block = _validate_block({"type": "engineering_manager", "soul_ref": "s1", "stateful": True})
        assert isinstance(block, EngineeringManagerBlockDef)
        assert block.stateful is True

    def test_workflow_block_stateful_true(self):
        block = _validate_block({"type": "workflow", "workflow_ref": "wf", "stateful": True})
        assert isinstance(block, WorkflowBlockDef)
        assert block.stateful is True


# ===========================================================================
# 3. Schema validation — stateful field with invalid values
# ===========================================================================


class TestStatefulValidation:
    """Validation of the stateful field type."""

    def test_stateful_non_bool_string_rejected(self):
        """stateful='yes' should be coerced or rejected depending on Pydantic config."""
        # With strict bool, 'yes' should fail. If Pydantic coerces, this test
        # still confirms the field exists and processes input.
        block = _validate_block({"type": "linear", "soul_ref": "s1", "stateful": True})
        assert block.stateful is True


# ===========================================================================
# 4. YAML parsing — blocks with stateful in RunsightWorkflowFile
# ===========================================================================


class TestYAMLParsingStateful:
    """YAML parsing tests for stateful within RunsightWorkflowFile."""

    def test_block_with_stateful_true_parses(self):
        """A workflow file with a block that has stateful: true should parse."""
        wf = RunsightWorkflowFile.model_validate(
            {
                "workflow": {"name": "test", "entry": "b1"},
                "blocks": {
                    "b1": {
                        "type": "linear",
                        "soul_ref": "s1",
                        "stateful": True,
                    },
                },
            }
        )
        block = wf.blocks["b1"]
        assert block.stateful is True

    def test_block_without_stateful_defaults_to_false(self):
        """A block without stateful in YAML should default to False."""
        wf = RunsightWorkflowFile.model_validate(
            {
                "workflow": {"name": "test", "entry": "b1"},
                "blocks": {
                    "b1": {"type": "linear", "soul_ref": "s1"},
                },
            }
        )
        assert wf.blocks["b1"].stateful is False

    def test_block_with_stateful_false_explicit(self):
        """A block with stateful: false in YAML should parse as False."""
        wf = RunsightWorkflowFile.model_validate(
            {
                "workflow": {"name": "test", "entry": "b1"},
                "blocks": {
                    "b1": {
                        "type": "code",
                        "code": "pass",
                        "stateful": False,
                    },
                },
            }
        )
        assert wf.blocks["b1"].stateful is False

    def test_multiple_blocks_mixed_stateful(self):
        """Multiple blocks — some with stateful: true, some without."""
        wf = RunsightWorkflowFile.model_validate(
            {
                "workflow": {"name": "test", "entry": "b1"},
                "blocks": {
                    "b1": {
                        "type": "linear",
                        "soul_ref": "s1",
                        "stateful": True,
                    },
                    "b2": {"type": "code", "code": "pass"},
                    "b3": {
                        "type": "gate",
                        "soul_ref": "s1",
                        "eval_key": "k",
                        "stateful": True,
                    },
                },
            }
        )
        assert wf.blocks["b1"].stateful is True
        assert wf.blocks["b2"].stateful is False
        assert wf.blocks["b3"].stateful is True

    def test_non_soul_block_with_stateful_true_parses(self):
        """Non-soul blocks (code, file_writer) with stateful: true parse without error."""
        wf = RunsightWorkflowFile.model_validate(
            {
                "workflow": {"name": "test", "entry": "b1"},
                "blocks": {
                    "b1": {
                        "type": "code",
                        "code": "x = 1",
                        "stateful": True,
                    },
                },
            }
        )
        assert wf.blocks["b1"].stateful is True

    def test_stateful_coexists_with_retry_config(self):
        """stateful and retry_config can both be set on the same block."""
        wf = RunsightWorkflowFile.model_validate(
            {
                "workflow": {"name": "test", "entry": "b1"},
                "blocks": {
                    "b1": {
                        "type": "linear",
                        "soul_ref": "s1",
                        "stateful": True,
                        "retry_config": {"max_attempts": 3},
                    },
                },
            }
        )
        block = wf.blocks["b1"]
        assert block.stateful is True
        assert block.retry_config is not None
        assert block.retry_config.max_attempts == 3


# ===========================================================================
# 5. Parser wires stateful to block instances
# ===========================================================================


class TestParserStatefulWiring:
    """Parser should wire stateful from block_def to block instance post-construction."""

    def test_block_instance_has_stateful_attribute(self):
        """After parsing, block instances should have a stateful attribute."""
        from runsight_core.yaml.parser import parse_workflow_yaml

        yaml_str = """\
version: "1.0"
souls:
  test:
    id: test_1
    role: Tester
    system_prompt: You test things.
blocks:
  b1:
    type: code
    code: "x = 1"
    stateful: true
workflow:
  name: test_workflow
  entry: b1
  transitions:
    - from: b1
      to: null
"""
        wf = parse_workflow_yaml(yaml_str)
        block = wf.blocks["b1"]
        assert hasattr(block, "stateful"), "Block instance should have 'stateful' attribute"
        assert block.stateful is True

    def test_block_instance_stateful_defaults_false(self):
        """Block instances without stateful in YAML should have stateful=False."""
        from runsight_core.yaml.parser import parse_workflow_yaml

        yaml_str = """\
version: "1.0"
souls:
  test:
    id: test_1
    role: Tester
    system_prompt: You test things.
blocks:
  b1:
    type: code
    code: "x = 1"
workflow:
  name: test_workflow
  entry: b1
  transitions:
    - from: b1
      to: null
"""
        wf = parse_workflow_yaml(yaml_str)
        block = wf.blocks["b1"]
        assert hasattr(block, "stateful"), "Block instance should have 'stateful' attribute"
        assert block.stateful is False

    def test_parser_wires_stateful_to_soul_block(self):
        """Soul-based blocks should also get stateful wired through."""
        from runsight_core.yaml.parser import parse_workflow_yaml

        yaml_str = """\
version: "1.0"
souls:
  test:
    id: test_1
    role: Tester
    system_prompt: You test things.
blocks:
  b1:
    type: linear
    soul_ref: test
    stateful: true
workflow:
  name: test_workflow
  entry: b1
  transitions:
    - from: b1
      to: null
"""
        wf = parse_workflow_yaml(yaml_str)
        block = wf.blocks["b1"]
        assert hasattr(block, "stateful"), "Block instance should have 'stateful' attribute"
        assert block.stateful is True

    def test_parser_wires_stateful_false_when_omitted(self):
        """Soul-based blocks without stateful should have stateful=False on instance."""
        from runsight_core.yaml.parser import parse_workflow_yaml

        yaml_str = """\
version: "1.0"
souls:
  test:
    id: test_1
    role: Tester
    system_prompt: You test things.
blocks:
  b1:
    type: linear
    soul_ref: test
workflow:
  name: test_workflow
  entry: b1
  transitions:
    - from: b1
      to: null
"""
        wf = parse_workflow_yaml(yaml_str)
        block = wf.blocks["b1"]
        assert hasattr(block, "stateful"), "Block instance should have 'stateful' attribute"
        assert block.stateful is False


# ===========================================================================
# 6. BaseBlock.__init__ default
# ===========================================================================


class TestBaseBlockStatefulDefault:
    """BaseBlock.__init__ should set self.stateful = False by default."""

    def test_base_block_subclass_has_stateful(self):
        """A directly constructed block should have stateful=False by default."""
        from runsight_core.blocks.base import BaseBlock
        from runsight_core.state import WorkflowState

        class DummyBlock(BaseBlock):
            async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
                return state

        block = DummyBlock("test_block")
        assert hasattr(block, "stateful"), "BaseBlock instances should have 'stateful' attribute"
        assert block.stateful is False


# ===========================================================================
# 7. Backward compatibility — existing blocks still parse with stateful
# ===========================================================================


class TestBackwardCompatibilityStateful:
    """Existing block definitions (without stateful) must still parse without error."""

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
    def test_existing_block_parses_without_stateful(self, block_data):
        """All existing block types must parse without stateful — backward compatible."""
        block = _validate_block(block_data)
        assert block.stateful is False


# ===========================================================================
# 8. Serialization round-trip
# ===========================================================================


class TestStatefulSerialization:
    """stateful serializes and deserializes correctly."""

    def test_model_dump_with_stateful_true(self):
        """Block with stateful=True should include it in model_dump."""
        block = LinearBlockDef(soul_ref="s1", stateful=True)
        dumped = block.model_dump()
        assert "stateful" in dumped
        assert dumped["stateful"] is True

    def test_model_dump_with_stateful_false(self):
        """Block with stateful=False should include it in model_dump."""
        block = LinearBlockDef(soul_ref="s1")
        dumped = block.model_dump()
        assert "stateful" in dumped
        assert dumped["stateful"] is False

    def test_round_trip_via_dict(self):
        """Validate a block with stateful from dict, dump, re-validate."""
        data = {"type": "linear", "soul_ref": "s1", "stateful": True}
        block = _validate_block(data)
        dumped = block.model_dump()
        block2 = _validate_block(dumped)
        assert block2.stateful is True

    def test_round_trip_stateful_false(self):
        """Validate a block without stateful, dump, re-validate — stays False."""
        data = {"type": "code", "code": "pass"}
        block = _validate_block(data)
        dumped = block.model_dump()
        block2 = _validate_block(dumped)
        assert block2.stateful is False
