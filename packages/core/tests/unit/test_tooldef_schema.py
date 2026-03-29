"""
Failing tests for RUN-274: ToolDef YAML schema, SoulDef + Soul tools update.

Tests target:
- ToolDef model (new): type="builtin", source required
- RunsightWorkflowFile: tools dict top-level section
- SoulDef.tools: List[str] (was List[Dict])
- SoulDef.max_tool_iterations: defaults to 5
- Soul.tools: List[str] (was List[Dict])
- Soul.max_tool_iterations: defaults to 5
- Soul.resolved_tools: excluded from serialization
"""

import pytest
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# AC1: ToolDef model — YAML `tools:` section parses correctly
# ---------------------------------------------------------------------------


class TestToolDef:
    """Tests for the new ToolDef schema model."""

    def test_tooldef_valid_builtin(self):
        """ToolDef with type='builtin' and source is valid."""
        from runsight_core.yaml.schema import ToolDef

        td = ToolDef(type="builtin", source="runsight/http")
        assert td.type == "builtin"
        assert td.source == "runsight/http"

    def test_tooldef_requires_source(self):
        """ToolDef without source raises ValidationError."""
        from runsight_core.yaml.schema import ToolDef

        with pytest.raises(ValidationError):
            ToolDef(type="builtin")  # type: ignore  # missing source

    def test_tooldef_requires_type(self):
        """ToolDef without type raises ValidationError."""
        from runsight_core.yaml.schema import ToolDef

        with pytest.raises(ValidationError):
            ToolDef(source="runsight/http")  # type: ignore  # missing type

    def test_tooldef_rejects_invalid_type(self):
        """ToolDef rejects type values other than 'builtin'."""
        from runsight_core.yaml.schema import ToolDef

        with pytest.raises(ValidationError):
            ToolDef(type="custom", source="runsight/http")

    def test_tooldef_type_literal_builtin_only(self):
        """ToolDef type field is Literal['builtin'] — only 'builtin' accepted."""
        from runsight_core.yaml.schema import ToolDef

        td = ToolDef(type="builtin", source="runsight/search")
        assert td.type == "builtin"

        with pytest.raises(ValidationError):
            ToolDef(type="external", source="runsight/search")


# ---------------------------------------------------------------------------
# AC1: RunsightWorkflowFile — tools top-level section
# ---------------------------------------------------------------------------


class TestRunsightWorkflowFileTools:
    """Tests for tools dict on RunsightWorkflowFile."""

    def test_workflow_file_tools_default_empty(self):
        """RunsightWorkflowFile.tools defaults to empty dict."""
        from runsight_core.yaml.schema import RunsightWorkflowFile, WorkflowDef

        wf = RunsightWorkflowFile(
            workflow=WorkflowDef(name="test", entry="start"),
        )
        assert wf.tools == {}

    def test_workflow_file_accepts_tools_dict(self):
        """RunsightWorkflowFile accepts a tools dict with ToolDef values."""
        from runsight_core.yaml.schema import (
            RunsightWorkflowFile,
            ToolDef,
            WorkflowDef,
        )

        wf = RunsightWorkflowFile(
            workflow=WorkflowDef(name="test", entry="start"),
            tools={
                "http_tool": ToolDef(type="builtin", source="runsight/http"),
                "search_tool": ToolDef(type="builtin", source="runsight/search"),
            },
        )
        assert len(wf.tools) == 2
        assert "http_tool" in wf.tools
        assert wf.tools["http_tool"].type == "builtin"
        assert wf.tools["http_tool"].source == "runsight/http"

    def test_workflow_file_tools_in_model_dump(self):
        """RunsightWorkflowFile.model_dump() includes tools section."""
        from runsight_core.yaml.schema import (
            RunsightWorkflowFile,
            ToolDef,
            WorkflowDef,
        )

        wf = RunsightWorkflowFile(
            workflow=WorkflowDef(name="test", entry="start"),
            tools={"my_tool": ToolDef(type="builtin", source="runsight/http")},
        )
        dump = wf.model_dump()
        assert "tools" in dump
        assert dump["tools"]["my_tool"]["type"] == "builtin"
        assert dump["tools"]["my_tool"]["source"] == "runsight/http"


# ---------------------------------------------------------------------------
# AC2: SoulDef.tools accepts List[str]
# ---------------------------------------------------------------------------


class TestSoulDefToolsUpdate:
    """Tests for SoulDef.tools type change from List[Dict] to List[str]."""

    def test_souldef_tools_accepts_list_of_strings(self):
        """SoulDef.tools accepts a list of tool name strings."""
        from runsight_core.yaml.schema import SoulDef

        sd = SoulDef(
            id="test_soul",
            role="Tester",
            system_prompt="Test prompt",
            tools=["http_tool", "search_tool"],
        )
        assert sd.tools == ["http_tool", "search_tool"]

    def test_souldef_tools_rejects_list_of_dicts(self):
        """SoulDef.tools rejects the old List[Dict] format."""
        from runsight_core.yaml.schema import SoulDef

        with pytest.raises(ValidationError):
            SoulDef(
                id="test_soul",
                role="Tester",
                system_prompt="Test prompt",
                tools=[{"name": "http_tool", "description": "Makes HTTP requests"}],
            )

    def test_souldef_tools_defaults_to_none(self):
        """SoulDef.tools defaults to None when not provided; max_tool_iterations defaults to 5."""
        from runsight_core.yaml.schema import SoulDef

        sd = SoulDef(
            id="test_soul",
            role="Tester",
            system_prompt="Test prompt",
        )
        assert sd.tools is None
        assert sd.max_tool_iterations == 5  # new field must exist with default

    def test_souldef_tools_empty_list(self):
        """SoulDef.tools accepts an empty list; max_tool_iterations defaults to 5."""
        from runsight_core.yaml.schema import SoulDef

        sd = SoulDef(
            id="test_soul",
            role="Tester",
            system_prompt="Test prompt",
            tools=[],
        )
        assert sd.tools == []
        assert sd.max_tool_iterations == 5  # new field must exist with default


# ---------------------------------------------------------------------------
# AC3: SoulDef.max_tool_iterations defaults to 5
# ---------------------------------------------------------------------------


class TestSoulDefMaxToolIterations:
    """Tests for SoulDef.max_tool_iterations field."""

    def test_souldef_max_tool_iterations_default(self):
        """SoulDef.max_tool_iterations defaults to 5."""
        from runsight_core.yaml.schema import SoulDef

        sd = SoulDef(
            id="test_soul",
            role="Tester",
            system_prompt="Test prompt",
        )
        assert sd.max_tool_iterations == 5

    def test_souldef_max_tool_iterations_custom(self):
        """SoulDef.max_tool_iterations accepts a custom value."""
        from runsight_core.yaml.schema import SoulDef

        sd = SoulDef(
            id="test_soul",
            role="Tester",
            system_prompt="Test prompt",
            max_tool_iterations=10,
        )
        assert sd.max_tool_iterations == 10


# ---------------------------------------------------------------------------
# AC2 + AC3: Soul primitive — tools as List[str], max_tool_iterations
# ---------------------------------------------------------------------------


class TestSoulToolsUpdate:
    """Tests for Soul.tools type change and max_tool_iterations."""

    def test_soul_tools_accepts_list_of_strings(self):
        """Soul.tools accepts a list of tool name strings."""
        from runsight_core.primitives import Soul

        soul = Soul(
            id="test_soul",
            role="Tester",
            system_prompt="Test prompt",
            tools=["http_tool", "search_tool"],
        )
        assert soul.tools == ["http_tool", "search_tool"]

    def test_soul_tools_rejects_list_of_dicts(self):
        """Soul.tools rejects the old List[Dict] format (breaking change)."""
        from runsight_core.primitives import Soul

        with pytest.raises(ValidationError):
            Soul(
                id="test_soul",
                role="Tester",
                system_prompt="Test prompt",
                tools=[{"name": "tool1", "description": "A tool"}],
            )

    def test_soul_max_tool_iterations_default(self):
        """Soul.max_tool_iterations defaults to 5."""
        from runsight_core.primitives import Soul

        soul = Soul(
            id="test_soul",
            role="Tester",
            system_prompt="Test prompt",
        )
        assert soul.max_tool_iterations == 5

    def test_soul_max_tool_iterations_custom(self):
        """Soul.max_tool_iterations accepts a custom value."""
        from runsight_core.primitives import Soul

        soul = Soul(
            id="test_soul",
            role="Tester",
            system_prompt="Test prompt",
            max_tool_iterations=15,
        )
        assert soul.max_tool_iterations == 15

    def test_soul_without_tools_still_works(self):
        """Soul without tools (backward compat) still creates successfully."""
        from runsight_core.primitives import Soul

        soul = Soul(
            id="basic_soul",
            role="Worker",
            system_prompt="Do work.",
        )
        assert soul.tools is None
        assert soul.max_tool_iterations == 5


# ---------------------------------------------------------------------------
# AC4: Soul.resolved_tools excluded from serialization
# ---------------------------------------------------------------------------


class TestSoulResolvedTools:
    """Tests for Soul.resolved_tools field."""

    def test_soul_resolved_tools_defaults_to_none(self):
        """Soul.resolved_tools defaults to None."""
        from runsight_core.primitives import Soul

        soul = Soul(
            id="test_soul",
            role="Tester",
            system_prompt="Test prompt",
        )
        assert soul.resolved_tools is None

    def test_soul_resolved_tools_accepts_value(self):
        """Soul.resolved_tools can be set to a list."""
        from runsight_core.primitives import Soul

        soul = Soul(
            id="test_soul",
            role="Tester",
            system_prompt="Test prompt",
            resolved_tools=[{"callable": lambda x: x}],
        )
        assert soul.resolved_tools is not None
        assert len(soul.resolved_tools) == 1

    def test_soul_resolved_tools_excluded_from_model_dump(self):
        """Soul.resolved_tools is excluded from model_dump() even when set."""
        from runsight_core.primitives import Soul

        soul = Soul(
            id="test_soul",
            role="Tester",
            system_prompt="Test prompt",
            resolved_tools=[{"callable": "some_tool"}],
        )
        # The field must exist on the instance
        assert soul.resolved_tools is not None
        # But must be excluded from serialization
        dump = soul.model_dump()
        assert "resolved_tools" not in dump

    def test_soul_resolved_tools_excluded_from_model_dump_json(self):
        """Soul.resolved_tools is excluded from model_dump(mode='json') even when set."""
        from runsight_core.primitives import Soul

        soul = Soul(
            id="test_soul",
            role="Tester",
            system_prompt="Test prompt",
            resolved_tools=["tool_a", "tool_b"],
        )
        # The field must exist on the instance
        assert soul.resolved_tools is not None
        # But must be excluded from JSON serialization
        json_dump = soul.model_dump(mode="json")
        assert "resolved_tools" not in json_dump


# ---------------------------------------------------------------------------
# AC1 + AC2: Full YAML parse round-trip — tools section + soul referencing
# ---------------------------------------------------------------------------


class TestFullYamlToolsParse:
    """End-to-end test: tools section defined, soul referencing tool names."""

    def test_full_workflow_with_tools_section_and_soul_refs(self):
        """Parse a complete workflow with tools section and soul tool references."""
        from runsight_core.yaml.schema import (
            RunsightWorkflowFile,
            SoulDef,
            ToolDef,
            WorkflowDef,
        )

        wf = RunsightWorkflowFile(
            version="1.0",
            workflow=WorkflowDef(name="tool_test", entry="start"),
            tools={
                "http_client": ToolDef(type="builtin", source="runsight/http"),
                "file_reader": ToolDef(type="builtin", source="runsight/file_read"),
            },
            souls={
                "agent_a": SoulDef(
                    id="agent_a",
                    role="HTTP Agent",
                    system_prompt="You make HTTP calls.",
                    tools=["http_client"],
                    max_tool_iterations=3,
                ),
                "agent_b": SoulDef(
                    id="agent_b",
                    role="File Agent",
                    system_prompt="You read files.",
                    tools=["file_reader", "http_client"],
                ),
            },
        )

        # Verify tools section
        assert len(wf.tools) == 2
        assert wf.tools["http_client"].source == "runsight/http"

        # Verify soul tool references are strings
        assert wf.souls["agent_a"].tools == ["http_client"]
        assert wf.souls["agent_a"].max_tool_iterations == 3
        assert wf.souls["agent_b"].tools == ["file_reader", "http_client"]
        assert wf.souls["agent_b"].max_tool_iterations == 5  # default

    def test_workflow_model_validate_with_tools_raw_dict(self):
        """RunsightWorkflowFile.model_validate parses raw dict with tools."""
        from runsight_core.yaml.schema import RunsightWorkflowFile

        raw = {
            "version": "1.0",
            "workflow": {"name": "test", "entry": "start"},
            "tools": {
                "search": {"type": "builtin", "source": "runsight/search"},
            },
            "souls": {
                "searcher": {
                    "id": "searcher",
                    "role": "Searcher",
                    "system_prompt": "Search things.",
                    "tools": ["search"],
                    "max_tool_iterations": 8,
                },
            },
        }

        wf = RunsightWorkflowFile.model_validate(raw)
        assert len(wf.tools) == 1
        assert wf.tools["search"].type == "builtin"
        assert wf.souls["searcher"].tools == ["search"]
        assert wf.souls["searcher"].max_tool_iterations == 8
