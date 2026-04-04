"""
Failing tests for RUN-577: workflow tool IDs are the only authoring contract.

Tests target:
- RunsightWorkflowFile.tools: List[str] of canonical tool IDs
- Legacy typed workflow tool maps fail clearly
- SoulDef.tools and Soul.tools remain List[str]
- Soul.resolved_tools stays excluded from serialization
"""

import pytest
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# AC1: RunsightWorkflowFile — tools top-level section
# ---------------------------------------------------------------------------


class TestRunsightWorkflowFileTools:
    """RUN-577: workflow authoring uses a canonical tools whitelist of stable IDs."""

    def test_workflow_file_tools_default_empty_list(self):
        """RunsightWorkflowFile.tools defaults to an empty whitelist."""
        from runsight_core.yaml.schema import RunsightWorkflowFile, WorkflowDef

        wf = RunsightWorkflowFile(
            workflow=WorkflowDef(name="test", entry="start"),
        )
        assert wf.tools == []

    def test_workflow_file_accepts_tools_list_of_stable_ids(self):
        """RunsightWorkflowFile accepts workflow-level tool IDs instead of typed defs."""
        from runsight_core.yaml.schema import RunsightWorkflowFile, WorkflowDef

        wf = RunsightWorkflowFile(
            workflow=WorkflowDef(name="test", entry="start"),
            tools=["http", "file_io", "lookup_profile"],
        )
        assert wf.tools == ["http", "file_io", "lookup_profile"]

    def test_workflow_file_tools_in_model_dump_as_id_list(self):
        """RunsightWorkflowFile.model_dump() preserves the canonical tool ID list."""
        from runsight_core.yaml.schema import RunsightWorkflowFile, WorkflowDef

        wf = RunsightWorkflowFile(
            workflow=WorkflowDef(name="test", entry="start"),
            tools=["http", "lookup_profile"],
        )
        dump = wf.model_dump()
        assert "tools" in dump
        assert dump["tools"] == ["http", "lookup_profile"]

    def test_workflow_file_rejects_legacy_typed_tool_map_authoring(self):
        """Legacy workflow-level builtin/custom/http definitions must fail clearly."""
        from runsight_core.yaml.schema import RunsightWorkflowFile

        with pytest.raises(ValidationError, match="list"):
            RunsightWorkflowFile.model_validate(
                {
                    "workflow": {"name": "test", "entry": "start"},
                    "tools": {
                        "http": {
                            "type": "builtin",
                            "source": "runsight/http",
                        },
                        "lookup_profile": {
                            "type": "custom",
                            "source": "lookup_profile",
                        },
                    },
                }
            )

    def test_workflow_file_rejects_inline_http_tool_authoring(self):
        """Inline HTTP tool config is no longer allowed in workflow YAML."""
        from runsight_core.yaml.schema import RunsightWorkflowFile

        with pytest.raises(ValidationError, match="list"):
            RunsightWorkflowFile.model_validate(
                {
                    "workflow": {"name": "test", "entry": "start"},
                    "tools": {
                        "http": {
                            "type": "http",
                            "method": "GET",
                            "url": "https://example.com/users/{{ user_id }}",
                        }
                    },
                }
            )

    def test_workflow_file_rejects_duplicate_tool_ids(self):
        """Workflow tools whitelist must reject duplicate IDs explicitly."""
        from runsight_core.yaml.schema import RunsightWorkflowFile

        with pytest.raises(ValidationError, match=r"duplicate.*http"):
            RunsightWorkflowFile.model_validate(
                {
                    "workflow": {"name": "test", "entry": "start"},
                    "tools": ["http", "http"],
                }
            )


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
            tools=["http", "file_io"],
        )
        assert sd.tools == ["http", "file_io"]

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
            tools=["http", "file_io"],
        )
        assert soul.tools == ["http", "file_io"]

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

    def test_full_workflow_with_tools_whitelist_and_soul_refs(self):
        """Parse a complete workflow with a tool ID whitelist and soul references."""
        from runsight_core.yaml.schema import RunsightWorkflowFile, SoulDef, WorkflowDef

        wf = RunsightWorkflowFile(
            version="1.0",
            workflow=WorkflowDef(name="tool_test", entry="start"),
            tools=["http", "lookup_profile"],
            souls={
                "agent_a": SoulDef(
                    id="agent_a",
                    role="HTTP Agent",
                    system_prompt="You make HTTP calls.",
                    tools=["http"],
                    max_tool_iterations=3,
                ),
                "agent_b": SoulDef(
                    id="agent_b",
                    role="Lookup Agent",
                    system_prompt="You look profiles up.",
                    tools=["lookup_profile", "http"],
                ),
            },
        )

        # Verify tools whitelist
        assert len(wf.tools) == 2
        assert wf.tools == ["http", "lookup_profile"]

        # Verify soul tool references are strings
        assert wf.souls["agent_a"].tools == ["http"]
        assert wf.souls["agent_a"].max_tool_iterations == 3
        assert wf.souls["agent_b"].tools == ["lookup_profile", "http"]
        assert wf.souls["agent_b"].max_tool_iterations == 5  # default

    def test_workflow_model_validate_with_raw_tool_id_list(self):
        """RunsightWorkflowFile.model_validate parses raw dict with canonical tool IDs."""
        from runsight_core.yaml.schema import RunsightWorkflowFile

        raw = {
            "version": "1.0",
            "workflow": {"name": "test", "entry": "start"},
            "tools": ["http", "search"],
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
        assert wf.tools == ["http", "search"]
        assert wf.souls["searcher"].tools == ["search"]
        assert wf.souls["searcher"].max_tool_iterations == 8
