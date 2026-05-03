"""YAML parser and standard-library block coverage.

This module tests:
- BlockTypeRegistry completeness.
- Valid YAML parsing scenarios.
- Error paths that raise ValueError.
- Soul resolution and merging with built-ins.
- YAML schema version validation.
"""

import pytest
from runsight_core.workflow import Workflow
from runsight_core.yaml.parser import (
    parse_workflow_yaml,
)


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
