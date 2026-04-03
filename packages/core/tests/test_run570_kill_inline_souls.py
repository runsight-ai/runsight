"""
Failing tests for RUN-570: Remove ``souls:`` section from workflow YAML schema.

After implementation:
1. ``RunsightWorkflowFile`` rejects non-empty ``souls:`` key with a clear error
2. Parser no longer constructs ``Soul`` objects from inline definitions
3. ``SoulDef`` model remains available (used by library file loading)
4. Clear, actionable error message when ``souls:`` section is present in YAML

All tests should FAIL until the schema validator and parser changes land.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from runsight_core.yaml.parser import parse_workflow_yaml
from runsight_core.yaml.schema import RunsightWorkflowFile, SoulDef

# ---------------------------------------------------------------------------
# Helper: minimal YAML builder (follows test_parser_tool_validation.py pattern)
# ---------------------------------------------------------------------------


def _make_yaml(
    *,
    souls: str = "",
    tools: str = "",
    blocks: str = "",
    transitions: str = "",
    entry: str = "my_block",
) -> str:
    """Build a complete workflow YAML string for inline-soul tests."""
    return f"""\
version: "1.0"
config:
  model_name: gpt-4o
{souls}
{tools}
blocks:
{blocks}
workflow:
  name: inline_soul_test
  entry: {entry}
  transitions:
{transitions}
"""


# ===========================================================================
# AC1: RunsightWorkflowFile no longer accepts a non-empty ``souls:`` key
# ===========================================================================


class TestSchemaRejectsInlineSouls:
    """RunsightWorkflowFile must reject any non-empty ``souls:`` key."""

    def test_non_empty_souls_dict_raises_error(self):
        """Providing a souls dict with entries must raise an error."""
        raw = {
            "version": "1.0",
            "workflow": {"name": "test", "entry": "block1"},
            "souls": {
                "researcher": {
                    "id": "researcher_1",
                    "role": "Researcher",
                    "system_prompt": "You research.",
                }
            },
        }
        with pytest.raises((ValidationError, ValueError)):
            RunsightWorkflowFile.model_validate(raw)

    def test_single_soul_entry_raises_error(self):
        """Even a single soul entry must be rejected."""
        raw = {
            "version": "1.0",
            "workflow": {"name": "test", "entry": "block1"},
            "souls": {
                "coder": {
                    "id": "coder_1",
                    "role": "Coder",
                    "system_prompt": "You write code.",
                }
            },
        }
        with pytest.raises((ValidationError, ValueError)):
            RunsightWorkflowFile.model_validate(raw)

    def test_empty_souls_dict_is_accepted(self):
        """An empty ``souls: {}`` must still be accepted (default behavior)."""
        raw = {
            "version": "1.0",
            "workflow": {"name": "test", "entry": "block1"},
            "souls": {},
        }
        file_def = RunsightWorkflowFile.model_validate(raw)
        assert file_def.souls == {}

    def test_missing_souls_key_is_accepted(self):
        """Omitting ``souls:`` entirely must still work (defaults to empty dict)."""
        raw = {
            "version": "1.0",
            "workflow": {"name": "test", "entry": "block1"},
        }
        file_def = RunsightWorkflowFile.model_validate(raw)
        assert file_def.souls == {}


# ===========================================================================
# AC4: Clear error message when ``souls:`` section is present
# ===========================================================================


class TestInlineSoulsErrorMessage:
    """The error message must be actionable — mention soul_ref and custom/souls/."""

    def test_error_mentions_inline_souls_not_supported(self):
        """Error must mention 'Inline souls are not supported'."""
        raw = {
            "version": "1.0",
            "workflow": {"name": "test", "entry": "block1"},
            "souls": {
                "agent": {
                    "id": "agent_1",
                    "role": "Agent",
                    "system_prompt": "You help.",
                }
            },
        }
        with pytest.raises(
            (ValidationError, ValueError),
            match=r"[Ii]nline souls are not supported",
        ):
            RunsightWorkflowFile.model_validate(raw)

    def test_error_mentions_soul_ref(self):
        """Error must guide users toward soul_ref."""
        raw = {
            "version": "1.0",
            "workflow": {"name": "test", "entry": "block1"},
            "souls": {
                "writer": {
                    "id": "writer_1",
                    "role": "Writer",
                    "system_prompt": "You write.",
                }
            },
        }
        with pytest.raises(
            (ValidationError, ValueError),
            match=r"soul_ref",
        ):
            RunsightWorkflowFile.model_validate(raw)

    def test_error_mentions_custom_souls_directory(self):
        """Error must mention custom/souls/ as the correct location."""
        raw = {
            "version": "1.0",
            "workflow": {"name": "test", "entry": "block1"},
            "souls": {
                "planner": {
                    "id": "planner_1",
                    "role": "Planner",
                    "system_prompt": "You plan.",
                }
            },
        }
        with pytest.raises(
            (ValidationError, ValueError),
            match=r"custom/souls/",
        ):
            RunsightWorkflowFile.model_validate(raw)


# ===========================================================================
# AC2: Parser does not construct Soul objects from inline definitions
# ===========================================================================


class TestParserNoInlineSoulConstruction:
    """parse_workflow_yaml must not build Soul objects from inline soul defs."""

    def test_yaml_with_inline_souls_raises_at_parse_time(self):
        """YAML containing inline souls must raise a clear error during parsing."""
        yaml_str = _make_yaml(
            souls="""\
souls:
  researcher:
    id: researcher_1
    role: Senior Researcher
    system_prompt: You are an expert researcher.""",
            blocks="""\
  my_block:
    type: linear
    soul_ref: researcher""",
            transitions="""\
    - from: my_block
      to: null""",
        )
        with pytest.raises((ValidationError, ValueError), match=r"[Ii]nline souls"):
            parse_workflow_yaml(yaml_str)

    def test_yaml_with_multiple_inline_souls_raises(self):
        """YAML with multiple inline souls must raise an error."""
        yaml_str = _make_yaml(
            souls="""\
souls:
  researcher:
    id: researcher_1
    role: Researcher
    system_prompt: You research.
  reviewer:
    id: reviewer_1
    role: Reviewer
    system_prompt: You review.""",
            blocks="""\
  block_a:
    type: linear
    soul_ref: researcher
  block_b:
    type: linear
    soul_ref: reviewer""",
            entry="block_a",
            transitions="""\
    - from: block_a
      to: block_b
    - from: block_b
      to: null""",
        )
        with pytest.raises((ValidationError, ValueError), match=r"[Ii]nline souls"):
            parse_workflow_yaml(yaml_str)

    def test_souls_map_starts_empty_after_removal(self):
        """Without inline souls, soul_ref fails because souls_map is empty.

        After RUN-570, souls_map starts empty. Any soul_ref will fail with
        'not found' until RUN-571 wires library discovery. This is expected.
        """
        yaml_str = _make_yaml(
            blocks="""\
  my_block:
    type: linear
    soul_ref: my_agent""",
            transitions="""\
    - from: my_block
      to: null""",
        )
        with pytest.raises(ValueError, match="my_agent"):
            parse_workflow_yaml(yaml_str)


# ===========================================================================
# Edge case: YAML with empty ``souls:`` still parses (no error)
# ===========================================================================


class TestEmptySoulsStillParses:
    """An empty ``souls: {}`` in YAML must not trigger the rejection."""

    def test_empty_souls_key_in_yaml_parses_successfully(self):
        """YAML with ``souls: {}`` should parse without error."""
        yaml_str = _make_yaml(
            souls="souls: {}",
            blocks="""\
  my_block:
    type: linear
    soul_ref: placeholder""",
            transitions="""\
    - from: my_block
      to: null""",
        )
        # The parse will fail later on soul_ref resolution (expected),
        # but it must NOT fail on the "inline souls" validator.
        with pytest.raises(ValueError, match="placeholder"):
            parse_workflow_yaml(yaml_str)

    def test_omitted_souls_key_parses_successfully(self):
        """YAML without any ``souls:`` key should parse without error."""
        yaml_str = _make_yaml(
            blocks="""\
  my_block:
    type: linear
    soul_ref: placeholder""",
            transitions="""\
    - from: my_block
      to: null""",
        )
        # Fails on soul_ref resolution, NOT on inline souls validator.
        with pytest.raises(ValueError, match="placeholder"):
            parse_workflow_yaml(yaml_str)


# ===========================================================================
# SoulDef model remains available for library file loading
# ===========================================================================


class TestSoulDefStillExists:
    """SoulDef Pydantic model must remain importable and functional."""

    def test_souldef_importable(self):
        """SoulDef must be importable from runsight_core.yaml.schema."""
        assert SoulDef is not None

    def test_souldef_can_be_instantiated(self):
        """SoulDef should still construct instances (used for library loading)."""
        soul_def = SoulDef(
            id="lib_researcher",
            role="Senior Researcher",
            system_prompt="You are an expert researcher.",
        )
        assert soul_def.id == "lib_researcher"
        assert soul_def.role == "Senior Researcher"
        assert soul_def.system_prompt == "You are an expert researcher."

    def test_souldef_with_all_optional_fields(self):
        """SoulDef with tools, model_name, etc. still works for library files."""
        soul_def = SoulDef(
            id="lib_agent",
            role="Agent",
            system_prompt="You help.",
            model_name="gpt-4o",
            tools=["http_tool"],
            max_tool_iterations=5,
        )
        assert soul_def.model_name == "gpt-4o"
        assert soul_def.tools == ["http_tool"]
        assert soul_def.max_tool_iterations == 5
