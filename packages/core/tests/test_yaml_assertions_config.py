"""Tests for retiring soul assertions while preserving block assertions."""

from unittest.mock import patch

import pytest
from pydantic import ValidationError
from runsight_core.blocks.base import BaseBlock
from runsight_core.primitives import Soul
from runsight_core.state import WorkflowState
from runsight_core.yaml.parser import parse_workflow_yaml
from workflow_fixture_helpers import workflow_fixture_text

BLOCK_ASSERTIONS_FIXTURE = "block-assertions-propagation.yaml"
BLOCK_WITHOUT_ASSERTIONS_FIXTURE = "block-assertions-omitted.yaml"
INVALID_SOUL_ASSERTIONS_FIXTURE = "soul-level-assertions-rejected.yaml"


class DummyBlock(BaseBlock):
    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        return state


class TestSoulAssertionRemoval:
    def test_souldef_has_no_assertions_field(self):
        """SoulDef should not expose a soul-level assertions field anymore."""
        from runsight_core.yaml.schema import SoulDef

        assert "assertions" not in SoulDef.model_fields

    def test_soul_has_no_assertions_field(self):
        """Soul primitive should no longer expose a runtime assertions field."""
        assert "assertions" not in Soul.model_fields


class TestBaseBlockDefAssertions:
    def test_baseblockdef_accepts_assertions_field(self):
        """BaseBlockDef can be instantiated with an assertions field."""
        from runsight_core.yaml.schema import BaseBlockDef

        block_def = BaseBlockDef(
            type="linear",
            assertions=[
                {"type": "is-json", "weight": 1.0},
                {"type": "contains", "value": "result", "weight": 2.0},
            ],
        )
        assert block_def.assertions is not None
        assert len(block_def.assertions) == 2

    def test_baseblockdef_assertions_defaults_to_none(self):
        """BaseBlockDef.assertions defaults to None when not provided."""
        from runsight_core.yaml.schema import BaseBlockDef

        block_def = BaseBlockDef(type="linear")
        assert block_def.assertions is None


class TestBaseBlockAssertionsAttribute:
    """BaseBlock runtime instances must expose block-owned assertions."""

    def test_base_block_has_assertions_attribute(self):
        """BaseBlock should initialize a runtime assertions attribute."""
        block = DummyBlock("assertion_runtime_block")
        assert hasattr(block, "assertions")

    def test_base_block_assertions_default_none(self):
        """Runtime blocks default assertions to None before parser bridging."""
        block = DummyBlock("assertion_runtime_block")
        assert hasattr(block, "assertions")
        assert block.assertions is None


class TestAssertionConfigsPropagation:
    """Parser should bridge block assertions onto the built runtime block."""

    def test_parser_bridges_block_assertions_to_runtime_block(self):
        """Parsed runtime block exposes block_def.assertions after build."""
        wf = parse_workflow_yaml(workflow_fixture_text(BLOCK_ASSERTIONS_FIXTURE))

        block = wf._blocks["analyze"]
        assert block.assertions is not None
        assert len(block.assertions) == 2

    def test_parser_preserves_block_assertion_fields(self):
        """Bridged block assertions retain the YAML config fields."""
        wf = parse_workflow_yaml(workflow_fixture_text(BLOCK_ASSERTIONS_FIXTURE))

        block = wf._blocks["analyze"]
        assert block.assertions is not None
        assert block.assertions[0]["type"] == "contains"
        assert block.assertions[0]["value"] == "analysis"
        assert block.assertions[1]["type"] == "cost"
        assert block.assertions[1]["threshold"] == 0.02

    def test_parser_leaves_runtime_block_assertions_none_when_omitted(self):
        """Blocks without YAML assertions still expose assertions=None."""
        wf = parse_workflow_yaml(workflow_fixture_text(BLOCK_WITHOUT_ASSERTIONS_FIXTURE))

        block = wf._blocks["analyze"]
        assert hasattr(block, "assertions")
        assert block.assertions is None

    def test_parser_rejects_soul_level_assertions_in_yaml(self):
        """Soul YAML should fail validation when assertions are declared on a soul."""
        with pytest.raises(ValidationError):
            parse_workflow_yaml(workflow_fixture_text(INVALID_SOUL_ASSERTIONS_FIXTURE))

    def test_parser_does_not_pass_assertions_kwarg_to_soul(self):
        """Parser should stop threading assertions into runtime Soul validation."""
        captured_payloads = []
        real_soul = Soul

        class _RecordingSoul:
            @staticmethod
            def model_validate(payload, *args, **kwargs):
                captured_payloads.append(payload)
                return real_soul.model_validate(payload, *args, **kwargs)

        with patch("runsight_core.yaml.parser.Soul", _RecordingSoul):
            parse_workflow_yaml(workflow_fixture_text(BLOCK_WITHOUT_ASSERTIONS_FIXTURE))

        assert captured_payloads
        assert "assertions" not in captured_payloads[0]
