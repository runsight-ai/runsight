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
    researcher_soul_yaml,
)
from runsight_core.primitives import Soul
from runsight_core.workflow import Workflow
from runsight_core.yaml.parser import (
    parse_workflow_yaml,
)


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
