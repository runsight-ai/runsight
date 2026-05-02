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
