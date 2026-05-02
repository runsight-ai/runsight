"""YAML parser and standard-library block coverage.

This module tests:
- BlockTypeRegistry completeness.
- Valid YAML parsing scenarios.
- Error paths that raise ValueError.
- Soul resolution and merging with built-ins.
- YAML schema version validation.
"""

from runsight_core.workflow import Workflow
from runsight_core.yaml.parser import (
    parse_workflow_yaml,
)


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
