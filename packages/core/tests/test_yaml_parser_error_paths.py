"""YAML parser and standard-library block coverage.

This module tests:
- BlockTypeRegistry completeness.
- Valid YAML parsing scenarios.
- Error paths that raise ValueError.
- Soul resolution and merging with built-ins.
- YAML schema version validation.
"""

import pytest
from pydantic import ValidationError
from runsight_core.yaml.parser import (
    parse_workflow_yaml,
)


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
