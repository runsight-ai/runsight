"""
Failing tests for RUN-415: Remove BUILT_IN_SOULS from parser.

After implementation, the parser must no longer seed a souls_map with
built-in souls.  Every soul_ref used in YAML must be explicitly defined
in the ``souls:`` section of that YAML file.

Tests verify:
1. BUILT_IN_SOULS symbol no longer importable from parser
2. parse_workflow_yaml starts with an empty souls_map (soul_ref to a
   previously-built-in name without a souls: definition raises ValueError)
3. All 6 previously-built-in names are NOT special-cased
4. YAML that explicitly defines its souls still parses successfully
"""

from __future__ import annotations

import pytest
from runsight_core.workflow import Workflow
from runsight_core.yaml.parser import parse_workflow_yaml

# ═══════════════════════════════════════════════════════════════════════════════
# 1. BUILT_IN_SOULS symbol removed from parser module
# ═══════════════════════════════════════════════════════════════════════════════


class TestBuiltInSoulsRemoved:
    """BUILT_IN_SOULS must no longer exist as a public symbol in parser.py."""

    def test_built_in_souls_not_importable(self):
        """Importing BUILT_IN_SOULS from runsight_core.yaml.parser must raise ImportError."""
        with pytest.raises(ImportError):
            from runsight_core.yaml.parser import BUILT_IN_SOULS  # noqa: F401

    def test_built_in_souls_not_in_parser_dir(self):
        """BUILT_IN_SOULS must not appear in dir(runsight_core.yaml.parser)."""
        import runsight_core.yaml.parser as parser_mod

        assert "BUILT_IN_SOULS" not in dir(parser_mod), (
            "BUILT_IN_SOULS still exists in parser module namespace — it must be deleted"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Empty souls_map by default — implicit soul_ref raises ValueError
# ═══════════════════════════════════════════════════════════════════════════════


class TestEmptySoulsMapByDefault:
    """parse_workflow_yaml must start with an empty souls_map, so any
    soul_ref that is not defined in the YAML's ``souls:`` section must
    raise ValueError."""

    def test_undefined_soul_ref_raises_value_error(self):
        """soul_ref: researcher without a souls: section must raise ValueError."""
        yaml_content = """\
version: "1.0"
blocks:
  linear_block:
    type: linear
    soul_ref: researcher
workflow:
  name: test_empty_souls_map
  entry: linear_block
  transitions:
    - from: linear_block
      to: null
"""
        with pytest.raises(ValueError, match="researcher"):
            parse_workflow_yaml(yaml_content)

    def test_undefined_soul_ref_with_empty_souls_section(self):
        """soul_ref: reviewer with an empty souls: {} section must raise ValueError."""
        yaml_content = """\
version: "1.0"
souls: {}
blocks:
  linear_block:
    type: linear
    soul_ref: reviewer
workflow:
  name: test_empty_souls_section
  entry: linear_block
  transitions:
    - from: linear_block
      to: null
"""
        with pytest.raises(ValueError, match="reviewer"):
            parse_workflow_yaml(yaml_content)


# ═══════════════════════════════════════════════════════════════════════════════
# 3. All 6 previously-built-in names are NOT special
# ═══════════════════════════════════════════════════════════════════════════════

PREVIOUSLY_BUILTIN_NAMES = [
    "researcher",
    "reviewer",
    "coder",
    "architect",
    "synthesizer",
    "generalist",
]


class TestNoPreviouslyBuiltInNamesAreSpecial:
    """Each of the 6 formerly-built-in soul names must raise ValueError
    when referenced without an explicit definition in the YAML."""

    @pytest.mark.parametrize("soul_name", PREVIOUSLY_BUILTIN_NAMES)
    def test_previously_builtin_soul_raises_without_definition(self, soul_name: str):
        """soul_ref: {soul_name} without souls: definition must raise ValueError."""
        yaml_content = f"""\
version: "1.0"
blocks:
  linear_block:
    type: linear
    soul_ref: {soul_name}
workflow:
  name: test_no_builtin_{soul_name}
  entry: linear_block
  transitions:
    - from: linear_block
      to: null
"""
        with pytest.raises(ValueError, match=soul_name):
            parse_workflow_yaml(yaml_content)


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Explicit soul definitions still work
# ═══════════════════════════════════════════════════════════════════════════════


class TestExplicitSoulsStillWork:
    """Defining souls inline in the YAML must still parse successfully.
    This proves the parser's soul-resolution path is intact — only the
    implicit built-in seeding is removed."""

    def test_explicit_soul_linear_block(self):
        """YAML with an inline soul definition parses a linear block successfully."""
        yaml_content = """\
version: "1.0"
souls:
  researcher:
    id: researcher_1
    role: Senior Researcher
    system_prompt: You are an expert researcher.
blocks:
  linear_block:
    type: linear
    soul_ref: researcher
workflow:
  name: test_explicit_soul
  entry: linear_block
  transitions:
    - from: linear_block
      to: null
"""
        workflow = parse_workflow_yaml(yaml_content)
        assert isinstance(workflow, Workflow)
        assert workflow.name == "test_explicit_soul"

    def test_explicit_soul_fanout_block(self):
        """YAML with inline soul definitions parses a fanout block successfully."""
        yaml_content = """\
version: "1.0"
souls:
  researcher:
    id: researcher_1
    role: Senior Researcher
    system_prompt: You are an expert researcher.
  reviewer:
    id: reviewer_1
    role: Peer Reviewer
    system_prompt: You are a strict peer reviewer.
blocks:
  fanout_block:
    type: fanout
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
  name: test_explicit_fanout
  entry: fanout_block
  transitions:
    - from: fanout_block
      to: null
"""
        workflow = parse_workflow_yaml(yaml_content)
        assert isinstance(workflow, Workflow)
        assert workflow.name == "test_explicit_fanout"

    def test_multiple_explicit_souls_all_resolve(self):
        """YAML defining all 6 previously-built-in names explicitly must parse."""
        yaml_content = """\
version: "1.0"
souls:
  researcher:
    id: researcher_1
    role: Senior Researcher
    system_prompt: You are an expert researcher.
  reviewer:
    id: reviewer_1
    role: Peer Reviewer
    system_prompt: You are a strict peer reviewer.
  coder:
    id: coder_1
    role: Software Engineer
    system_prompt: You write clean code.
  architect:
    id: architect_1
    role: Systems Architect
    system_prompt: You design systems.
  synthesizer:
    id: synthesizer_1
    role: Synthesis Agent
    system_prompt: You synthesize inputs.
  generalist:
    id: generalist_1
    role: General-purpose Assistant
    system_prompt: You handle diverse tasks.
blocks:
  linear_block:
    type: linear
    soul_ref: researcher
workflow:
  name: test_all_explicit
  entry: linear_block
  transitions:
    - from: linear_block
      to: null
"""
        workflow = parse_workflow_yaml(yaml_content)
        assert isinstance(workflow, Workflow)
        assert workflow.name == "test_all_explicit"
