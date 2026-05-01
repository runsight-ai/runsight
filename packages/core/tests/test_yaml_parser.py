"""YAML parser and standard-library block coverage.

This module tests:
- BlockTypeRegistry completeness.
- Valid YAML parsing scenarios.
- Error paths that raise ValueError.
- Soul resolution and merging with built-ins.
- YAML schema version validation.
"""

from unittest.mock import Mock, patch

import pytest
from parser_yaml_helpers import (
    RESEARCHER_SOUL_DICT,
    researcher_reviewer_souls_yaml,
    researcher_soul_yaml,
)
from pydantic import ValidationError
from runsight_core.blocks._registry import BLOCK_BUILDER_REGISTRY as BLOCK_TYPE_REGISTRY
from runsight_core.primitives import Soul
from runsight_core.workflow import Workflow
from runsight_core.yaml.parser import (
    parse_workflow_yaml,
)


class TestBlockTypeRegistry:
    """Tests for BlockTypeRegistry completeness."""

    def test_block_type_registry_has_all_7_types(self):
        """Verify BLOCK_TYPE_REGISTRY contains all 7 block types."""
        expected_types = {
            "linear",
            "dispatch",
            "synthesize",
            "loop",
            "gate",
            "code",
            "workflow",
        }
        assert set(BLOCK_TYPE_REGISTRY.keys()) == expected_types
        assert len(BLOCK_TYPE_REGISTRY) == 7

    def test_all_block_builders_are_callable(self):
        """Verify all builders in registry are callable."""
        for block_type, builder in BLOCK_TYPE_REGISTRY.items():
            assert callable(builder), f"Builder for {block_type} is not callable"


class TestLinearBlock:
    """Tests for LinearBlock (block type: linear)."""

    def test_linear_block_valid_yaml(self):
        """Parse a valid linear block with soul_ref."""
        yaml_content = """
version: "1.0"
id: linear_workflow
kind: workflow
config:
  model_name: gpt-4o
souls:
  research_soul:
    id: research_soul
    kind: soul
    name: Custom Researcher
    role: Custom Researcher
    system_prompt: Do research
blocks:
  linear_block:
    type: linear
    soul_ref: research_soul
workflow:
  id: linear_workflow
  kind: workflow
  name: linear_workflow
  entry: linear_block
  transitions:
    - from: linear_block
      to: null
"""
        workflow = parse_workflow_yaml(yaml_content)
        assert isinstance(workflow, Workflow)
        assert workflow.name == "linear_workflow"

    def test_parse_workflow_yaml_does_not_use_config_model_name_for_runner(self):
        """Parser does not source runtime model resolution from workflow config."""
        yaml_content = """
version: "1.0"
id: runner_model_resolution
kind: workflow
config:
  model_name: gpt-4o-mini
blocks:
  linear_block:
    type: linear
    soul_ref: configured_soul
workflow:
  id: runner_model_resolution
  kind: workflow
  name: runner_model_resolution
  entry: linear_block
  transitions:
    - from: linear_block
      to: null
"""
        souls_map = {
            "configured_soul": Soul(
                id="configured_soul",
                kind="soul",
                name="Custom Researcher",
                role="Custom Researcher",
                system_prompt="Do research",
                provider="anthropic",
                model_name="claude-sonnet-4",
            )
        }
        with (
            patch("runsight_core.yaml.parser.RunsightTeamRunner") as mock_runner,
            patch("runsight_core.yaml.parser.SoulScanner") as mock_scanner,
        ):
            mock_runner.return_value = Mock()
            mock_scanner.return_value.scan.return_value.ids.return_value = souls_map
            parse_workflow_yaml(yaml_content)

        assert mock_runner.call_args is not None
        assert mock_runner.call_args.kwargs["model_name"] == "claude-sonnet-4"

    def test_parse_workflow_yaml_does_not_fall_back_to_hidden_gpt_4o_runner_model(self):
        """Parser does not keep the legacy hidden gpt-4o runner path alive."""
        yaml_content = """
version: "1.0"
config: {}
id: hidden_runner_model_guard
kind: workflow
blocks:
  linear_block:
    type: linear
    soul_ref: configured_soul
workflow:
  id: hidden_runner_model_guard
  kind: workflow
  name: hidden_runner_model_guard
  entry: linear_block
  transitions:
    - from: linear_block
      to: null
"""
        souls_map = {
            "configured_soul": Soul(
                id="configured_soul",
                kind="soul",
                name="Custom Researcher",
                role="Custom Researcher",
                system_prompt="Do research",
                provider="anthropic",
                model_name="claude-sonnet-4",
            )
        }
        with (
            patch("runsight_core.yaml.parser.RunsightTeamRunner") as mock_runner,
            patch("runsight_core.yaml.parser.SoulScanner") as mock_scanner,
        ):
            mock_runner.return_value = Mock()
            mock_scanner.return_value.scan.return_value.ids.return_value = souls_map
            parse_workflow_yaml(yaml_content)

        assert mock_runner.call_args is not None
        assert mock_runner.call_args.kwargs["model_name"] == "claude-sonnet-4"

    def test_linear_block_missing_soul_ref_raises_error(self):
        """LinearBlock without soul_ref raises ValueError."""
        yaml_content = """
version: "1.0"
blocks:
  linear_block:
    type: linear
id: linear_block_workflow
kind: workflow
workflow:
  id: linear_block_workflow
  kind: workflow
  name: linear_block_workflow
  entry: linear_block
"""
        with pytest.raises(ValueError, match="soul_ref"):
            parse_workflow_yaml(yaml_content)

    def test_linear_block_with_defined_soul(self):
        """LinearBlock can use explicitly defined souls."""
        yaml_content = f"""
version: "1.0"
id: linear_block_workflow
kind: workflow
{researcher_soul_yaml()}
blocks:
  linear_block:
    type: linear
    soul_ref: researcher
workflow:
  id: linear_block_workflow
  kind: workflow
  name: linear_block_workflow
  entry: linear_block
  transitions:
    - from: linear_block
      to: null
"""
        workflow = parse_workflow_yaml(yaml_content)
        assert isinstance(workflow, Workflow)


class TestDispatchBlock:
    """Tests for DispatchBlock (block type: dispatch)."""

    def test_dispatch_block_valid_yaml(self):
        """Parse a valid dispatch block with exits."""
        yaml_content = f"""
version: "1.0"
id: dispatch_block_workflow
kind: workflow
{researcher_reviewer_souls_yaml()}
blocks:
  dispatch_block:
    type: dispatch
    exits:
      - id: exit_research
        label: Research
        soul_ref: researcher
        task: Research the topic
      - id: exit_review
        label: Review
        soul_ref: reviewer
        task: Review the topic
workflow:
  id: dispatch_block_workflow
  kind: workflow
  name: dispatch_block_workflow
  entry: dispatch_block
  transitions:
    - from: dispatch_block
      to: null
"""
        workflow = parse_workflow_yaml(yaml_content)
        assert isinstance(workflow, Workflow)
        assert workflow.name == "dispatch_block_workflow"

    def test_dispatch_block_missing_exits_raises_error(self):
        """DispatchBlock without exits raises ValidationError."""
        yaml_content = """
version: "1.0"
blocks:
  dispatch_block:
    type: dispatch
id: dispatch_block_workflow
kind: workflow
workflow:
  id: dispatch_block_workflow
  kind: workflow
  name: dispatch_block_workflow
  entry: dispatch_block
"""
        with pytest.raises((ValueError, Exception), match="exits"):
            parse_workflow_yaml(yaml_content)

    def test_dispatch_block_empty_exits_raises_error(self):
        """DispatchBlock with empty exits raises ValueError."""
        yaml_content = """
version: "1.0"
blocks:
  dispatch_block:
    type: dispatch
    exits: []
id: dispatch_block_workflow
kind: workflow
workflow:
  id: dispatch_block_workflow
  kind: workflow
  name: dispatch_block_workflow
  entry: dispatch_block
"""
        with pytest.raises(ValueError, match="exits"):
            parse_workflow_yaml(yaml_content)


class TestSynthesizeBlock:
    """Tests for SynthesizeBlock (block type: synthesize)."""

    def test_synthesize_block_valid_yaml(self):
        """Parse a valid synthesize block with dependencies."""
        yaml_content = """
version: "1.0"
id: synthesize_block_workflow
kind: workflow
souls:
  researcher:
    id: researcher
    kind: soul
    name: Senior Researcher
    role: Senior Researcher
    system_prompt: You research topics.
  reviewer:
    id: reviewer
    kind: soul
    name: Peer Reviewer
    role: Peer Reviewer
    system_prompt: You review topics.
  synthesizer:
    id: synthesizer
    kind: soul
    name: Synthesis Agent
    role: Synthesis Agent
    system_prompt: You synthesize inputs.
blocks:
  research_block:
    type: linear
    soul_ref: researcher
  review_block:
    type: linear
    soul_ref: reviewer
  synthesize_block:
    type: synthesize
    soul_ref: synthesizer
    input_block_ids:
      - research_block
      - review_block
workflow:
  id: synthesize_block_workflow
  kind: workflow
  name: synthesize_block_workflow
  entry: research_block
  transitions:
    - from: research_block
      to: review_block
    - from: review_block
      to: synthesize_block
    - from: synthesize_block
      to: null
"""
        workflow = parse_workflow_yaml(yaml_content)
        assert isinstance(workflow, Workflow)

    def test_synthesize_block_missing_soul_ref_raises_error(self):
        """SynthesizeBlock without soul_ref raises ValueError."""
        yaml_content = """
version: "1.0"
blocks:
  synthesize_block:
    type: synthesize
    input_block_ids:
      - research_block
workflow:
  id: synthesize_block_workflow
  kind: workflow
  name: synthesize_block_workflow
  entry: synthesize_block
"""
        with pytest.raises(ValueError, match="soul_ref"):
            parse_workflow_yaml(yaml_content)

    def test_synthesize_block_missing_input_block_ids_raises_error(self):
        """SynthesizeBlock without input_block_ids raises ValueError."""
        yaml_content = """
version: "1.0"
souls:
  synthesizer:
    id: synthesizer
    kind: soul
    name: Synthesis Agent
    role: Synthesis Agent
    system_prompt: You synthesize inputs.
blocks:
  synthesize_block:
    type: synthesize
    soul_ref: synthesizer
workflow:
  id: synthesize_block_workflow
  kind: workflow
  name: synthesize_block_workflow
  entry: synthesize_block
"""
        with pytest.raises(ValueError, match="input_block_ids"):
            parse_workflow_yaml(yaml_content)


class TestSoulResolution:
    """Tests for soul resolution and merging."""

    def test_soul_resolution_missing_soul_raises_error(self):
        """Referencing a non-existent soul raises ValueError."""
        yaml_content = """
version: "1.0"
blocks:
  linear_block:
    type: linear
    soul_ref: nonexistent_soul
id: missing_soul_workflow
kind: workflow
workflow:
  id: missing_soul_workflow
  kind: workflow
  name: missing_soul_workflow
  entry: linear_block
"""
        with pytest.raises(ValueError, match="Soul reference 'soul:nonexistent_soul' not found"):
            parse_workflow_yaml(yaml_content)

    def test_custom_soul_definition_works(self):
        """Custom soul definition in YAML works correctly."""
        yaml_content = """
version: "1.0"
id: custom_soul_workflow
kind: workflow
souls:
  researcher:
    id: researcher
    kind: soul
    name: Custom Researcher
    role: Custom Researcher
    system_prompt: Custom research prompt
blocks:
  linear_block:
    type: linear
    soul_ref: researcher
workflow:
  id: custom_soul_workflow
  kind: workflow
  name: custom_soul_workflow
  entry: linear_block
  transitions:
    - from: linear_block
      to: null
"""
        workflow = parse_workflow_yaml(yaml_content)
        assert isinstance(workflow, Workflow)


class TestInvalidYAML:
    """Tests for invalid YAML handling."""

    def test_invalid_yaml_syntax_raises_error(self):
        """Syntactically invalid YAML raises error."""
        yaml_content = """
version: "1.0"
blocks:
  block: [invalid yaml structure
"""
        with pytest.raises(Exception):  # yaml.YAMLError
            parse_workflow_yaml(yaml_content)

    def test_missing_workflow_section_raises_error(self):
        """Missing required workflow section raises ValidationError."""
        yaml_content = """
version: "1.0"
blocks:
  linear_block:
    type: linear
    soul_ref: researcher
"""
        with pytest.raises(ValidationError):
            parse_workflow_yaml(yaml_content)

    def test_unknown_block_type_raises_error(self):
        """Unknown block type raises ValueError."""
        yaml_content = """
version: "1.0"
blocks:
  unknown_block:
    type: unknown_type
id: unknown_block_workflow
kind: workflow
workflow:
  id: unknown_block_workflow
  kind: workflow
  name: unknown_block_workflow
  entry: unknown_block
"""
        with pytest.raises(ValueError, match="unknown_type"):
            parse_workflow_yaml(yaml_content)


class TestParseFromDict:
    """Tests for parsing from dict input."""

    def test_parse_from_dict_valid(self):
        """parse_workflow_yaml accepts dict input."""
        workflow_dict = {
            "version": "1.0",
            "id": "dict_input_workflow",
            "kind": "workflow",
            "souls": {"researcher": RESEARCHER_SOUL_DICT},
            "blocks": {
                "linear_block": {
                    "type": "linear",
                    "soul_ref": "researcher",
                }
            },
            "workflow": {
                "id": "dict_input_workflow",
                "kind": "workflow",
                "name": "dict_input_workflow",
                "entry": "linear_block",
                "transitions": [{"from": "linear_block", "to": None}],
            },
        }
        workflow = parse_workflow_yaml(workflow_dict)
        assert isinstance(workflow, Workflow)
        assert workflow.name == "dict_input_workflow"


class TestComplexWorkflow:
    """Tests for complex multi-block workflows."""

    def test_complex_workflow_all_block_types(self):
        """Parse a workflow using multiple block types together."""
        yaml_content = """
version: "1.0"
id: complex_workflow
kind: workflow
config:
  model_name: gpt-4o
souls:
  researcher:
    id: researcher
    kind: soul
    name: Senior Researcher
    role: Senior Researcher
    system_prompt: You research topics.
  reviewer:
    id: reviewer
    kind: soul
    name: Peer Reviewer
    role: Peer Reviewer
    system_prompt: You review topics.
  coder:
    id: coder
    kind: soul
    name: Software Engineer
    role: Software Engineer
    system_prompt: You write code.
  synthesizer:
    id: synthesizer
    kind: soul
    name: Synthesis Agent
    role: Synthesis Agent
    system_prompt: You synthesize inputs.
  generalist:
    id: generalist
    kind: soul
    name: General-purpose Assistant
    role: General-purpose Assistant
    system_prompt: You handle diverse tasks.
blocks:
  research_block:
    type: linear
    soul_ref: researcher
  review_block:
    type: dispatch
    exits:
      - id: exit_reviewer
        label: Reviewer
        soul_ref: reviewer
        task: Review the research
      - id: exit_coder
        label: Coder
        soul_ref: coder
        task: Code review
  synthesize_block:
    type: synthesize
    soul_ref: synthesizer
    input_block_ids:
      - research_block
      - review_block
  final_block:
    type: linear
    soul_ref: generalist
workflow:
  id: complex_workflow
  kind: workflow
  name: complex_workflow
  entry: research_block
  transitions:
    - from: research_block
      to: review_block
    - from: review_block
      to: synthesize_block
    - from: synthesize_block
      to: final_block
    - from: final_block
      to: null
"""
        workflow = parse_workflow_yaml(yaml_content)
        assert isinstance(workflow, Workflow)
        assert workflow.name == "complex_workflow"


class TestVersionValidation:
    """Tests for YAML schema version validation."""

    # -- Minimal valid workflow YAML used as a base for version tests --------
    _BASE_YAML_TEMPLATE = f"""
version: "{{version}}"
id: version_test
kind: workflow
{researcher_soul_yaml()}
blocks:
  version_entry_block:
    type: linear
    soul_ref: researcher
workflow:
  id: version_test
  kind: workflow
  name: version_test
  entry: version_entry_block
  transitions:
    - from: version_entry_block
      to: null
"""

    _BASE_DICT_NO_VERSION = {
        "id": "version_test",
        "kind": "workflow",
        "souls": {"researcher": RESEARCHER_SOUL_DICT},
        "blocks": {"version_entry_block": {"type": "linear", "soul_ref": "researcher"}},
        "workflow": {
            "id": "version_test",
            "kind": "workflow",
            "name": "version_test",
            "entry": "version_entry_block",
            "transitions": [{"from": "version_entry_block", "to": None}],
        },
    }

    def test_version_1_0_accepted_without_warning(self):
        """Version '1.0' is the current version and parses without error."""
        yaml_content = self._BASE_YAML_TEMPLATE.format(version="1.0")
        workflow = parse_workflow_yaml(yaml_content)
        assert isinstance(workflow, Workflow)
        assert workflow.name == "version_test"

    def test_unknown_version_raises_value_error(self):
        """Unknown version raises ValueError."""
        yaml_content = self._BASE_YAML_TEMPLATE.format(version="2.0")
        with pytest.raises(ValueError, match="version"):
            parse_workflow_yaml(yaml_content)

    def test_unknown_version_999_raises_value_error(self):
        """Another unknown version also raises ValueError."""
        yaml_content = self._BASE_YAML_TEMPLATE.format(version="999.0")
        with pytest.raises(ValueError, match="version"):
            parse_workflow_yaml(yaml_content)

    def test_missing_version_defaults_to_1_0(self):
        """Missing version field works and defaults to '1.0'."""
        workflow = parse_workflow_yaml(dict(self._BASE_DICT_NO_VERSION))
        assert isinstance(workflow, Workflow)
        assert workflow.name == "version_test"

    def test_unknown_version_error_message_includes_supported_versions(self):
        """Error message for unknown version includes supported versions."""
        yaml_content = self._BASE_YAML_TEMPLATE.format(version="3.0")
        with pytest.raises(ValueError, match="1.0"):
            parse_workflow_yaml(yaml_content)

    def test_unknown_version_error_message_includes_provided_version(self):
        """Error message for unknown version includes the provided version."""
        yaml_content = self._BASE_YAML_TEMPLATE.format(version="42.0")
        with pytest.raises(ValueError, match="42.0"):
            parse_workflow_yaml(yaml_content)
