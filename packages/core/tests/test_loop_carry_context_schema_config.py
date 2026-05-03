"""LoopBlock carry-context schema and constructor contracts."""

from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError
from runsight_core.blocks.loop import LoopBlockDef
from runsight_core.yaml.schema import BlockDef, RunsightWorkflowFile

block_adapter = TypeAdapter(BlockDef)


def validate_block(data: dict):
    """Validate a dict as a BlockDef via the discriminated union."""
    return block_adapter.validate_python(data)


class TestCarryContextConfigSchema:
    """CarryContextConfig validates its public schema fields."""

    def test_import_carry_context_config(self):
        from runsight_core.blocks.loop import CarryContextConfig

        assert CarryContextConfig is not None

    def test_default_values(self):
        from runsight_core.blocks.loop import CarryContextConfig

        config = CarryContextConfig()
        assert config.enabled is True
        assert config.mode == "last"
        assert config.source_blocks is None
        assert config.inject_as == "previous_round_context"

    def test_mode_accepts_last(self):
        from runsight_core.blocks.loop import CarryContextConfig

        config = CarryContextConfig(mode="last")
        assert config.mode == "last"

    def test_mode_accepts_all(self):
        from runsight_core.blocks.loop import CarryContextConfig

        config = CarryContextConfig(mode="all")
        assert config.mode == "all"

    def test_mode_rejects_invalid(self):
        from runsight_core.blocks.loop import CarryContextConfig

        with pytest.raises(ValidationError, match="mode"):
            CarryContextConfig(mode="invalid")

    def test_source_blocks_accepts_list(self):
        from runsight_core.blocks.loop import CarryContextConfig

        config = CarryContextConfig(source_blocks=["draft_block", "review_block"])
        assert config.source_blocks == ["draft_block", "review_block"]

    def test_source_blocks_none_means_all_inner_blocks(self):
        from runsight_core.blocks.loop import CarryContextConfig

        config = CarryContextConfig(source_blocks=None)
        assert config.source_blocks is None

    def test_inject_as_accepts_custom_key(self):
        from runsight_core.blocks.loop import CarryContextConfig

        config = CarryContextConfig(inject_as="feedback")
        assert config.inject_as == "feedback"

    def test_enabled_false_disables_config(self):
        from runsight_core.blocks.loop import CarryContextConfig

        config = CarryContextConfig(enabled=False)
        assert config.enabled is False


class TestLoopBlockDefCarryContextSchema:
    """LoopBlockDef parses the optional carry_context field."""

    def test_carry_context_accepts_config(self):
        block = validate_block(
            {
                "type": "loop",
                "inner_block_refs": ["draft_block"],
                "max_rounds": 5,
                "carry_context": {
                    "enabled": True,
                    "mode": "last",
                    "inject_as": "previous_round_context",
                },
            }
        )
        assert isinstance(block, LoopBlockDef)
        assert block.carry_context is not None
        assert block.carry_context.enabled is True
        assert block.carry_context.mode == "last"

    def test_carry_context_defaults_to_none(self):
        block = validate_block(
            {
                "type": "loop",
                "inner_block_refs": ["draft_block"],
                "max_rounds": 5,
            }
        )
        assert isinstance(block, LoopBlockDef)
        assert block.carry_context is None

    def test_carry_context_accepts_source_blocks_and_custom_key(self):
        block = validate_block(
            {
                "type": "loop",
                "inner_block_refs": ["writer", "critic"],
                "max_rounds": 3,
                "carry_context": {
                    "source_blocks": ["critic"],
                    "inject_as": "feedback",
                },
            }
        )
        assert isinstance(block, LoopBlockDef)
        assert block.carry_context.source_blocks == ["critic"]
        assert block.carry_context.inject_as == "feedback"

    def test_carry_context_mode_all_parses(self):
        block = validate_block(
            {
                "type": "loop",
                "inner_block_refs": ["draft_block"],
                "max_rounds": 5,
                "carry_context": {"mode": "all"},
            }
        )
        assert isinstance(block, LoopBlockDef)
        assert block.carry_context.mode == "all"

    def test_carry_context_parses_inside_workflow_file(self):
        raw = {
            "version": "1.0",
            "id": "carry_context_workflow",
            "kind": "workflow",
            "souls": {
                "writer": {
                    "id": "writer",
                    "kind": "soul",
                    "name": "Writer",
                    "role": "Writer",
                    "system_prompt": "You write.",
                },
                "critic": {
                    "id": "critic",
                    "kind": "soul",
                    "name": "Critic",
                    "role": "Critic",
                    "system_prompt": "You critique.",
                },
            },
            "blocks": {
                "write_block": {"type": "linear", "soul_ref": "writer"},
                "critic_block": {"type": "linear", "soul_ref": "critic"},
                "loop_block": {
                    "type": "loop",
                    "inner_block_refs": ["write_block", "critic_block"],
                    "max_rounds": 3,
                    "carry_context": {
                        "mode": "last",
                        "source_blocks": ["critic_block"],
                        "inject_as": "feedback",
                    },
                },
            },
            "workflow": {
                "id": "carry_context_workflow",
                "kind": "workflow",
                "name": "carry context workflow",
                "entry": "loop_block",
                "transitions": [{"from": "loop_block", "to": None}],
            },
        }
        file_def = RunsightWorkflowFile.model_validate(raw)
        loop_def = file_def.blocks["loop_block"]
        assert isinstance(loop_def, LoopBlockDef)
        assert loop_def.carry_context is not None
        assert loop_def.carry_context.mode == "last"
        assert loop_def.carry_context.source_blocks == ["critic_block"]
        assert loop_def.carry_context.inject_as == "feedback"

    def test_carry_context_enabled_false_parses(self):
        block = validate_block(
            {
                "type": "loop",
                "inner_block_refs": ["draft_block"],
                "max_rounds": 5,
                "carry_context": {"enabled": False},
            }
        )
        assert isinstance(block, LoopBlockDef)
        assert block.carry_context is not None
        assert block.carry_context.enabled is False


class TestLoopBlockConstructorCarryContext:
    """LoopBlock constructor accepts and validates carry_context."""

    def test_constructor_accepts_carry_context_config(self):
        from runsight_core import LoopBlock
        from runsight_core.blocks.loop import CarryContextConfig

        config = CarryContextConfig(mode="last", inject_as="feedback")
        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["writer", "critic"],
            max_rounds=3,
            carry_context=config,
        )
        assert loop.carry_context is config

    def test_constructor_defaults_carry_context_to_none(self):
        from runsight_core import LoopBlock

        loop = LoopBlock(
            block_id="loop_block",
            inner_block_refs=["inner"],
            max_rounds=3,
        )
        assert loop.carry_context is None

    def test_constructor_rejects_unknown_source_block(self):
        from runsight_core import LoopBlock
        from runsight_core.blocks.loop import CarryContextConfig

        config = CarryContextConfig(source_blocks=["nonexistent_block"], inject_as="ctx")
        with pytest.raises(ValueError, match="nonexistent_block"):
            LoopBlock(
                block_id="loop_block",
                inner_block_refs=["writer", "critic"],
                max_rounds=3,
                carry_context=config,
            )

    def test_constructor_reports_partial_source_block_mismatch(self):
        from runsight_core import LoopBlock
        from runsight_core.blocks.loop import CarryContextConfig

        config = CarryContextConfig(source_blocks=["writer", "ghost_block"], inject_as="ctx")
        with pytest.raises(ValueError, match="ghost_block"):
            LoopBlock(
                block_id="loop_block",
                inner_block_refs=["writer", "critic"],
                max_rounds=3,
                carry_context=config,
            )
