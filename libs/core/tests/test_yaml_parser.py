"""
Tests for YAML Parser and Standard Library.

This module tests:
- All 11 block types in BlockTypeRegistry
- Valid YAML parsing scenarios
- Error paths that raise ValueError
- Soul resolution and merging with built-ins
"""

import pytest
from pydantic import ValidationError
from runsight_core.yaml.parser import (
    parse_workflow_yaml,
    parse_task_yaml,
    BUILT_IN_SOULS,
)
from runsight_core.blocks._registry import BLOCK_BUILDER_REGISTRY as BLOCK_TYPE_REGISTRY
from runsight_core.workflow import Workflow
from runsight_core.primitives import Task


class TestBlockTypeRegistry:
    """Tests for BlockTypeRegistry completeness."""

    def test_block_type_registry_has_all_7_types(self):
        """Verify BLOCK_TYPE_REGISTRY contains all 7 block types."""
        expected_types = {
            "linear",
            "fanout",
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


class TestBuiltInSouls:
    """Tests for built-in souls."""

    def test_built_in_souls_exist(self):
        """Verify BUILT_IN_SOULS contains expected souls."""
        expected_souls = {
            "researcher",
            "reviewer",
            "coder",
            "architect",
            "synthesizer",
            "generalist",
        }
        assert set(BUILT_IN_SOULS.keys()) == expected_souls
        assert len(BUILT_IN_SOULS) == 6

    def test_built_in_souls_have_required_fields(self):
        """Verify each built-in soul has required fields."""
        for soul_key, soul in BUILT_IN_SOULS.items():
            assert soul.id is not None
            assert soul.role is not None
            assert soul.system_prompt is not None


class TestLinearBlock:
    """Tests for LinearBlock (block type: linear)."""

    def test_linear_block_valid_yaml(self):
        """AC-1: Parse valid linear block with soul_ref."""
        yaml_content = """
version: "1.0"
config:
  model_name: gpt-4o
souls:
  my_soul:
    id: my_soul_1
    role: Custom Researcher
    system_prompt: Do research
blocks:
  linear_block:
    type: linear
    soul_ref: my_soul
workflow:
  name: test_linear
  entry: linear_block
  transitions:
    - from: linear_block
      to: null
"""
        workflow = parse_workflow_yaml(yaml_content)
        assert isinstance(workflow, Workflow)
        assert workflow.name == "test_linear"

    def test_linear_block_missing_soul_ref_raises_error(self):
        """AC-2: LinearBlock without soul_ref raises ValueError."""
        yaml_content = """
version: "1.0"
blocks:
  linear_block:
    type: linear
workflow:
  name: test_linear
  entry: linear_block
"""
        with pytest.raises(ValueError, match="soul_ref"):
            parse_workflow_yaml(yaml_content)

    def test_linear_block_with_builtin_soul(self):
        """AC-3: LinearBlock can use built-in souls."""
        yaml_content = """
version: "1.0"
blocks:
  linear_block:
    type: linear
    soul_ref: researcher
workflow:
  name: test_linear
  entry: linear_block
  transitions:
    - from: linear_block
      to: null
"""
        workflow = parse_workflow_yaml(yaml_content)
        assert isinstance(workflow, Workflow)


class TestFanOutBlock:
    """Tests for FanOutBlock (block type: fanout)."""

    def test_fanout_block_valid_yaml(self):
        """AC-4: Parse valid fanout block with multiple soul_refs."""
        yaml_content = """
version: "1.0"
blocks:
  fanout_block:
    type: fanout
    soul_refs:
      - researcher
      - reviewer
workflow:
  name: test_fanout
  entry: fanout_block
  transitions:
    - from: fanout_block
      to: null
"""
        workflow = parse_workflow_yaml(yaml_content)
        assert isinstance(workflow, Workflow)
        assert workflow.name == "test_fanout"

    def test_fanout_block_missing_soul_refs_raises_error(self):
        """AC-5: FanOutBlock without soul_refs raises ValueError."""
        yaml_content = """
version: "1.0"
blocks:
  fanout_block:
    type: fanout
workflow:
  name: test_fanout
  entry: fanout_block
"""
        with pytest.raises(ValueError, match="soul_refs"):
            parse_workflow_yaml(yaml_content)

    def test_fanout_block_empty_soul_refs_raises_error(self):
        """AC-6: FanOutBlock with empty soul_refs raises ValueError."""
        yaml_content = """
version: "1.0"
blocks:
  fanout_block:
    type: fanout
    soul_refs: []
workflow:
  name: test_fanout
  entry: fanout_block
"""
        with pytest.raises(ValueError, match="soul_refs is required"):
            parse_workflow_yaml(yaml_content)


class TestSynthesizeBlock:
    """Tests for SynthesizeBlock (block type: synthesize)."""

    def test_synthesize_block_valid_yaml(self):
        """AC-7: Parse valid synthesize block with dependencies."""
        yaml_content = """
version: "1.0"
blocks:
  block_a:
    type: linear
    soul_ref: researcher
  block_b:
    type: linear
    soul_ref: reviewer
  synthesize_block:
    type: synthesize
    soul_ref: synthesizer
    input_block_ids:
      - block_a
      - block_b
workflow:
  name: test_synthesize
  entry: block_a
  transitions:
    - from: block_a
      to: block_b
    - from: block_b
      to: synthesize_block
    - from: synthesize_block
      to: null
"""
        workflow = parse_workflow_yaml(yaml_content)
        assert isinstance(workflow, Workflow)

    def test_synthesize_block_missing_soul_ref_raises_error(self):
        """AC-8: SynthesizeBlock without soul_ref raises ValueError."""
        yaml_content = """
version: "1.0"
blocks:
  synthesize_block:
    type: synthesize
    input_block_ids:
      - block_a
workflow:
  name: test_synthesize
  entry: synthesize_block
"""
        with pytest.raises(ValueError, match="soul_ref"):
            parse_workflow_yaml(yaml_content)

    def test_synthesize_block_missing_input_block_ids_raises_error(self):
        """AC-9: SynthesizeBlock without input_block_ids raises ValueError."""
        yaml_content = """
version: "1.0"
blocks:
  synthesize_block:
    type: synthesize
    soul_ref: synthesizer
workflow:
  name: test_synthesize
  entry: synthesize_block
"""
        with pytest.raises(ValueError, match="input_block_ids"):
            parse_workflow_yaml(yaml_content)


class TestSoulResolution:
    """Tests for soul resolution and merging."""

    def test_soul_resolution_missing_soul_raises_error(self):
        """AC-28: Referencing non-existent soul raises ValueError."""
        yaml_content = """
version: "1.0"
blocks:
  linear_block:
    type: linear
    soul_ref: nonexistent_soul
workflow:
  name: test_souls
  entry: linear_block
"""
        with pytest.raises(ValueError, match="Soul reference 'nonexistent_soul' not found"):
            parse_workflow_yaml(yaml_content)

    def test_custom_soul_overrides_builtin(self):
        """AC-29: Custom soul definition overrides built-in soul."""
        yaml_content = """
version: "1.0"
souls:
  researcher:
    id: custom_researcher
    role: Custom Researcher
    system_prompt: Custom research prompt
blocks:
  linear_block:
    type: linear
    soul_ref: researcher
workflow:
  name: test_override
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
        """AC-30: Syntactically invalid YAML raises error."""
        yaml_content = """
version: "1.0"
blocks:
  block: [invalid yaml structure
"""
        with pytest.raises(Exception):  # yaml.YAMLError
            parse_workflow_yaml(yaml_content)

    def test_missing_workflow_section_raises_error(self):
        """AC-31: Missing required workflow section raises ValidationError."""
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
        """AC-32: Unknown block type raises ValueError (ValidationError via discriminated union)."""
        yaml_content = """
version: "1.0"
blocks:
  unknown_block:
    type: unknown_type
workflow:
  name: test_unknown
  entry: unknown_block
"""
        with pytest.raises(ValueError, match="unknown_type"):
            parse_workflow_yaml(yaml_content)


class TestParseFromDict:
    """Tests for parsing from dict input."""

    def test_parse_from_dict_valid(self):
        """AC-33: parse_workflow_yaml accepts dict input."""
        workflow_dict = {
            "version": "1.0",
            "blocks": {
                "linear_block": {
                    "type": "linear",
                    "soul_ref": "researcher",
                }
            },
            "workflow": {
                "name": "test_dict",
                "entry": "linear_block",
                "transitions": [{"from": "linear_block", "to": None}],
            },
        }
        workflow = parse_workflow_yaml(workflow_dict)
        assert isinstance(workflow, Workflow)
        assert workflow.name == "test_dict"


class TestComplexWorkflow:
    """Tests for complex multi-block workflows."""

    def test_complex_workflow_all_block_types(self):
        """AC-34: Parse workflow using multiple block types together."""
        yaml_content = """
version: "1.0"
config:
  model_name: gpt-4o
blocks:
  research_block:
    type: linear
    soul_ref: researcher
  review_block:
    type: fanout
    soul_refs:
      - reviewer
      - coder
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


class TestParseTaskYAML:
    """Tests for parse_task_yaml function."""

    def test_parse_task_yaml_from_yaml_string_with_all_fields(self):
        """AC-1: parse_task_yaml accepts YAML string with id, instruction, context."""
        yaml_content = """
version: "1.0"
task:
  id: task_1
  instruction: "Review this code for bugs"
  context: "This is a Python function with a potential off-by-one error"
"""
        task = parse_task_yaml(yaml_content)
        assert isinstance(task, Task)
        assert task.id == "task_1"
        assert task.instruction == "Review this code for bugs"
        assert task.context == "This is a Python function with a potential off-by-one error"

    def test_parse_task_yaml_from_yaml_string_without_context(self):
        """AC-2: parse_task_yaml handles optional context field."""
        yaml_content = """
version: "1.0"
task:
  id: task_2
  instruction: "Summarize the main points"
"""
        task = parse_task_yaml(yaml_content)
        assert isinstance(task, Task)
        assert task.id == "task_2"
        assert task.instruction == "Summarize the main points"
        assert task.context is None

    def test_parse_task_yaml_from_dict_with_all_fields(self):
        """AC-3: parse_task_yaml accepts dict with id, instruction, context."""
        task_dict = {
            "version": "1.0",
            "task": {
                "id": "task_3",
                "instruction": "Write unit tests",
                "context": "Test coverage should be at least 80%",
            },
        }
        task = parse_task_yaml(task_dict)
        assert isinstance(task, Task)
        assert task.id == "task_3"
        assert task.instruction == "Write unit tests"
        assert task.context == "Test coverage should be at least 80%"

    def test_parse_task_yaml_from_dict_without_context(self):
        """AC-4: parse_task_yaml handles optional context in dict."""
        task_dict = {
            "version": "1.0",
            "task": {
                "id": "task_4",
                "instruction": "Generate API documentation",
            },
        }
        task = parse_task_yaml(task_dict)
        assert isinstance(task, Task)
        assert task.id == "task_4"
        assert task.instruction == "Generate API documentation"
        assert task.context is None

    def test_parse_task_yaml_missing_id_raises_validation_error(self):
        """AC-5: parse_task_yaml raises ValidationError when id is missing."""
        yaml_content = """
version: "1.0"
task:
  instruction: "Do something"
  context: "Some context"
"""
        with pytest.raises(ValidationError):
            parse_task_yaml(yaml_content)

    def test_parse_task_yaml_missing_instruction_raises_validation_error(self):
        """AC-6: parse_task_yaml raises ValidationError when instruction is missing."""
        yaml_content = """
version: "1.0"
task:
  id: task_5
  context: "Some context"
"""
        with pytest.raises(ValidationError):
            parse_task_yaml(yaml_content)

    def test_parse_task_yaml_missing_both_required_fields_raises_validation_error(self):
        """AC-7: parse_task_yaml raises ValidationError when both required fields missing."""
        yaml_content = """
version: "1.0"
task:
  context: "Some context"
"""
        with pytest.raises(ValidationError):
            parse_task_yaml(yaml_content)

    def test_parse_task_yaml_empty_dict_raises_validation_error(self):
        """AC-8: parse_task_yaml raises ValidationError for empty dict."""
        with pytest.raises(ValidationError):
            parse_task_yaml({})

    def test_parse_task_yaml_invalid_yaml_raises_error(self):
        """AC-9: parse_task_yaml raises error for syntactically invalid YAML."""
        yaml_content = """
version: "1.0"
task:
  id: task
  instruction: [invalid yaml structure
"""
        with pytest.raises(Exception):  # yaml.YAMLError
            parse_task_yaml(yaml_content)

    def test_parse_task_yaml_wrong_type_for_id_raises_validation_error(self):
        """AC-10: parse_task_yaml raises ValidationError when id is wrong type."""
        task_dict = {
            "version": "1.0",
            "task": {
                "id": 123,  # should be string
                "instruction": "Do something",
            },
        }
        with pytest.raises(ValidationError):
            parse_task_yaml(task_dict)

    def test_parse_task_yaml_wrong_type_for_instruction_raises_validation_error(self):
        """AC-11: parse_task_yaml raises ValidationError when instruction is wrong type."""
        task_dict = {
            "version": "1.0",
            "task": {
                "id": "task_6",
                "instruction": ["list", "instead", "of", "string"],  # should be string
            },
        }
        with pytest.raises(ValidationError):
            parse_task_yaml(task_dict)

    def test_parse_task_yaml_returns_task_primitive(self):
        """AC-12: parse_task_yaml returns Task primitive instance."""
        yaml_content = """
version: "1.0"
task:
  id: task_7
  instruction: "Test instruction"
"""
        result = parse_task_yaml(yaml_content)
        assert isinstance(result, Task)
        assert hasattr(result, "id")
        assert hasattr(result, "instruction")
        assert hasattr(result, "context")

    def test_parse_task_yaml_with_multiline_instruction(self):
        """AC-13: parse_task_yaml handles multiline instruction text."""
        yaml_content = """
version: "1.0"
task:
  id: task_8
  instruction: |
    This is a multiline instruction.
    It spans multiple lines.
    Each line provides more detail.
  context: "Some context"
"""
        task = parse_task_yaml(yaml_content)
        assert task.id == "task_8"
        assert "multiline instruction" in task.instruction
        assert "spans multiple lines" in task.instruction
        assert task.context == "Some context"

    def test_parse_task_yaml_with_multiline_context(self):
        """AC-14: parse_task_yaml handles multiline context text."""
        yaml_content = """
version: "1.0"
task:
  id: task_9
  instruction: "Simple instruction"
  context: |
    This is multiline context.
    With multiple paragraphs.
    Providing rich background.
"""
        task = parse_task_yaml(yaml_content)
        assert task.id == "task_9"
        assert "multiline context" in task.context
        assert "multiple paragraphs" in task.context


# This ensures we have at least 8 distinct test functions across all classes
# Count of actual test functions (test_* methods):
# TestBlockTypeRegistry: 2
# TestBuiltInSouls: 2
# TestLinearBlock: 3
# TestFanOutBlock: 3
# TestSynthesizeBlock: 3
# TestSoulResolution: 2
# TestInvalidYAML: 3
# TestParseFromDict: 1
# TestComplexWorkflow: 1
# TestParseTaskYAML: 14
# Total: 43+ test functions
