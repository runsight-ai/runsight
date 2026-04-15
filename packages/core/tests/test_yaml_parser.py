"""
Tests for YAML Parser and Standard Library.

This module tests:
- All 11 block types in BlockTypeRegistry
- Valid YAML parsing scenarios
- Error paths that raise ValueError
- Soul resolution and merging with built-ins
"""

from unittest.mock import Mock, patch

import pytest
from pydantic import ValidationError
from runsight_core.blocks._registry import BLOCK_BUILDER_REGISTRY as BLOCK_TYPE_REGISTRY
from runsight_core.primitives import Soul, Task
from runsight_core.workflow import Workflow
from runsight_core.yaml.parser import (
    parse_task_yaml,
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
        """AC-1: Parse valid linear block with soul_ref."""
        yaml_content = """
version: "1.0"
id: test_linear
kind: workflow
config:
  model_name: gpt-4o
souls:
  my_soul:
    id: my_soul
    kind: soul
    name: Custom Researcher
    role: Custom Researcher
    system_prompt: Do research
blocks:
  linear_block:
    type: linear
    soul_ref: my_soul
workflow:
  id: test_linear
  kind: workflow
  name: test_linear
  entry: linear_block
  transitions:
    - from: linear_block
      to: null
"""
        workflow = parse_workflow_yaml(yaml_content)
        assert isinstance(workflow, Workflow)
        assert workflow.name == "test_linear"

    def test_parse_workflow_yaml_does_not_use_config_model_name_for_runner(self):
        """RUN-585: parser must not source runtime model resolution from workflow config."""
        yaml_content = """
version: "1.0"
id: test_linear
kind: workflow
config:
  model_name: gpt-4o-mini
blocks:
  linear_block:
    type: linear
    soul_ref: my_soul
workflow:
  id: test_linear
  kind: workflow
  name: test_linear
  entry: linear_block
  transitions:
    - from: linear_block
      to: null
"""
        souls_map = {
            "my_soul": Soul(
                id="my_soul",
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
        """RUN-585: parser must not keep the legacy hidden gpt-4o runner path alive."""
        yaml_content = """
version: "1.0"
config: {}
id: test_linear
kind: workflow
blocks:
  linear_block:
    type: linear
    soul_ref: my_soul
workflow:
  id: test_linear
  kind: workflow
  name: test_linear
  entry: linear_block
  transitions:
    - from: linear_block
      to: null
"""
        souls_map = {
            "my_soul": Soul(
                id="my_soul",
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
        """AC-2: LinearBlock without soul_ref raises ValueError."""
        yaml_content = """
version: "1.0"
blocks:
  linear_block:
    type: linear
id: test_linear
kind: workflow
workflow:
  id: test_linear
  kind: workflow
  name: test_linear
  entry: linear_block
"""
        with pytest.raises(ValueError, match="soul_ref"):
            parse_workflow_yaml(yaml_content)

    def test_linear_block_with_defined_soul(self):
        """AC-3: LinearBlock can use explicitly defined souls."""
        yaml_content = """
version: "1.0"
id: test_linear
kind: workflow
souls:
  researcher:
    id: researcher
    kind: soul
    name: Senior Researcher
    role: Senior Researcher
    system_prompt: You research topics.
blocks:
  linear_block:
    type: linear
    soul_ref: researcher
workflow:
  id: test_linear
  kind: workflow
  name: test_linear
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
        """AC-4: Parse valid dispatch block with exits."""
        yaml_content = """
version: "1.0"
id: test_dispatch
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
  id: test_dispatch
  kind: workflow
  name: test_dispatch
  entry: dispatch_block
  transitions:
    - from: dispatch_block
      to: null
"""
        workflow = parse_workflow_yaml(yaml_content)
        assert isinstance(workflow, Workflow)
        assert workflow.name == "test_dispatch"

    def test_dispatch_block_missing_exits_raises_error(self):
        """AC-5: DispatchBlock without exits raises ValidationError."""
        yaml_content = """
version: "1.0"
blocks:
  dispatch_block:
    type: dispatch
id: test_dispatch
kind: workflow
workflow:
  id: test_dispatch
  kind: workflow
  name: test_dispatch
  entry: dispatch_block
"""
        with pytest.raises((ValueError, Exception), match="exits"):
            parse_workflow_yaml(yaml_content)

    def test_dispatch_block_empty_exits_raises_error(self):
        """AC-6: DispatchBlock with empty exits raises ValueError."""
        yaml_content = """
version: "1.0"
blocks:
  dispatch_block:
    type: dispatch
    exits: []
id: test_dispatch
kind: workflow
workflow:
  id: test_dispatch
  kind: workflow
  name: test_dispatch
  entry: dispatch_block
"""
        with pytest.raises(ValueError, match="exits"):
            parse_workflow_yaml(yaml_content)


class TestSynthesizeBlock:
    """Tests for SynthesizeBlock (block type: synthesize)."""

    def test_synthesize_block_valid_yaml(self):
        """AC-7: Parse valid synthesize block with dependencies."""
        yaml_content = """
version: "1.0"
id: test_synthesize
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
  id: test_synthesize
  kind: workflow
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
  id: test_synthesize
  kind: workflow
  name: test_synthesize
  entry: synthesize_block
"""
        with pytest.raises(ValueError, match="soul_ref"):
            parse_workflow_yaml(yaml_content)

    def test_synthesize_block_missing_input_block_ids_raises_error(self):
        """AC-9: SynthesizeBlock without input_block_ids raises ValueError."""
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
  id: test_synthesize
  kind: workflow
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
id: test_souls
kind: workflow
workflow:
  id: test_souls
  kind: workflow
  name: test_souls
  entry: linear_block
"""
        with pytest.raises(ValueError, match="Soul reference 'soul:nonexistent_soul' not found"):
            parse_workflow_yaml(yaml_content)

    def test_custom_soul_definition_works(self):
        """AC-29: Custom soul definition in YAML works correctly."""
        yaml_content = """
version: "1.0"
id: test_override
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
  id: test_override
  kind: workflow
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
id: test_unknown
kind: workflow
workflow:
  id: test_unknown
  kind: workflow
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
            "id": "test_dict",
            "kind": "workflow",
            "souls": {
                "researcher": {
                    "id": "researcher",
                    "kind": "soul",
                    "name": "Senior Researcher",
                    "role": "Senior Researcher",
                    "system_prompt": "You research topics.",
                }
            },
            "blocks": {
                "linear_block": {
                    "type": "linear",
                    "soul_ref": "researcher",
                }
            },
            "workflow": {
                "id": "test_dict",
                "kind": "workflow",
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


class TestVersionValidation:
    """Tests for YAML schema version validation (RUN-323)."""

    # -- Minimal valid workflow YAML used as a base for version tests --------
    _BASE_YAML_TEMPLATE = """
version: "{version}"
id: version_test
kind: workflow
souls:
  researcher:
    id: researcher
    kind: soul
    name: Senior Researcher
    role: Senior Researcher
    system_prompt: You research topics.
blocks:
  b:
    type: linear
    soul_ref: researcher
workflow:
  id: version_test
  kind: workflow
  name: version_test
  entry: b
  transitions:
    - from: b
      to: null
"""

    _BASE_DICT_NO_VERSION = {
        "id": "version_test",
        "kind": "workflow",
        "souls": {
            "researcher": {
                "id": "researcher",
                "kind": "soul",
                "name": "Senior Researcher",
                "role": "Senior Researcher",
                "system_prompt": "You research topics.",
            }
        },
        "blocks": {"b": {"type": "linear", "soul_ref": "researcher"}},
        "workflow": {
            "id": "version_test",
            "kind": "workflow",
            "name": "version_test",
            "entry": "b",
            "transitions": [{"from": "b", "to": None}],
        },
    }

    def test_version_1_0_accepted_without_warning(self):
        """AC-1: version '1.0' is the current version and parses without error."""
        yaml_content = self._BASE_YAML_TEMPLATE.format(version="1.0")
        workflow = parse_workflow_yaml(yaml_content)
        assert isinstance(workflow, Workflow)
        assert workflow.name == "version_test"

    def test_unknown_version_raises_value_error(self):
        """AC-2: Unknown version (e.g., '2.0') raises ValueError."""
        yaml_content = self._BASE_YAML_TEMPLATE.format(version="2.0")
        with pytest.raises(ValueError, match="version"):
            parse_workflow_yaml(yaml_content)

    def test_unknown_version_999_raises_value_error(self):
        """AC-2b: Another unknown version '999.0' also raises ValueError."""
        yaml_content = self._BASE_YAML_TEMPLATE.format(version="999.0")
        with pytest.raises(ValueError, match="version"):
            parse_workflow_yaml(yaml_content)

    def test_missing_version_defaults_to_1_0(self):
        """AC-3: Missing version field works (defaults to '1.0')."""
        workflow = parse_workflow_yaml(dict(self._BASE_DICT_NO_VERSION))
        assert isinstance(workflow, Workflow)
        assert workflow.name == "version_test"

    def test_unknown_version_error_message_includes_supported_versions(self):
        """AC-2c: Error message for unknown version includes list of supported versions."""
        yaml_content = self._BASE_YAML_TEMPLATE.format(version="3.0")
        with pytest.raises(ValueError, match="1.0"):
            parse_workflow_yaml(yaml_content)

    def test_unknown_version_error_message_includes_provided_version(self):
        """AC-2d: Error message for unknown version includes the version that was provided."""
        yaml_content = self._BASE_YAML_TEMPLATE.format(version="42.0")
        with pytest.raises(ValueError, match="42.0"):
            parse_workflow_yaml(yaml_content)


# This ensures we have at least 8 distinct test functions across all classes
# Count of actual test functions (test_* methods):
# TestBlockTypeRegistry: 2
# TestBuiltInSouls: 2
# TestLinearBlock: 3
# TestDispatchBlock: 3
# TestSynthesizeBlock: 3
# TestSoulResolution: 2
# TestInvalidYAML: 3
# TestParseFromDict: 1
# TestComplexWorkflow: 1
# TestParseTaskYAML: 14
# TestVersionValidation: 6
# Total: 40+ test functions
