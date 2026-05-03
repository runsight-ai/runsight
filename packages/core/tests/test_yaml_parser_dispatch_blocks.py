"""YAML parser and standard-library block coverage.

This module tests:
- BlockTypeRegistry completeness.
- Valid YAML parsing scenarios.
- Error paths that raise ValueError.
- Soul resolution and merging with built-ins.
- YAML schema version validation.
"""

import pytest
from parser_yaml_helpers import (
    researcher_reviewer_souls_yaml,
)
from runsight_core.workflow import Workflow
from runsight_core.yaml.parser import (
    parse_workflow_yaml,
)


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
