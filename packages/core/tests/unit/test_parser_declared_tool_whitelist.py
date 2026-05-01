"""Parser tests for workflow-declared tool whitelist behavior."""

from __future__ import annotations

import pytest
import runsight_core.yaml.parser as parser_module
import yaml
from parser_yaml_helpers import (
    tool_validation_soul_workflow_yaml,
    workflow_with_raw_tools_section_yaml,
)
from pydantic import ValidationError
from runsight_core.tools import ToolInstance
from runsight_core.yaml.parser import _resolve_soul_tool_definition, parse_workflow_yaml
from runsight_core.yaml.schema import RunsightWorkflowFile
from runsight_core.yaml.validation import ValidationResult


def _tool_soul(workflow):
    return workflow.blocks["tool_validation_block"].soul


def test_declared_builtin_tool_ids_resolve_to_tool_instances() -> None:
    workflow = parse_workflow_yaml(
        tool_validation_soul_workflow_yaml(
            tool_ids=("http", "file_io"),
            soul_tools=("http", "file_io"),
        )
    )

    soul = _tool_soul(workflow)

    assert soul.tools == ["http", "file_io"]
    assert soul.resolved_tools is not None
    assert all(isinstance(tool, ToolInstance) for tool in soul.resolved_tools)
    assert {tool.name for tool in soul.resolved_tools} == {"http_request", "file_io"}


def test_builtin_soul_tools_without_workflow_declarations_resolve_empty() -> None:
    workflow = parse_workflow_yaml(
        tool_validation_soul_workflow_yaml(
            tool_ids=None,
            soul_tools=("http", "file_io"),
        )
    )

    assert _tool_soul(workflow).resolved_tools == []


def test_parser_no_longer_exports_user_assignable_bypass_constant() -> None:
    assert not hasattr(parser_module, "USER_ASSIGNABLE_SOUL_TOOL_SOURCES"), (
        "Parser still exposes USER_ASSIGNABLE_SOUL_TOOL_SOURCES, leaving the bypass easy to resurrect"
    )


def test_resolve_soul_tool_definition_only_uses_workflow_tools() -> None:
    assert _resolve_soul_tool_definition("http", {}) is None


def test_validate_tool_governance_exists_for_api_layer_reuse() -> None:
    validator = getattr(parser_module, "validate_tool_governance", None)
    assert callable(validator), (
        "Expected parser.validate_tool_governance() for API-layer governance validation reuse"
    )

    raw = yaml.safe_load(
        tool_validation_soul_workflow_yaml(
            tool_ids=None,
            soul_id="reviewer",
            soul_name="Reviewer",
            soul_role="Reviewer",
            soul_prompt="Review the draft.",
            soul_tools=("http",),
        )
    )
    validator(RunsightWorkflowFile.model_validate(raw))


def test_validate_tool_governance_accepts_declared_tool_id_refs_from_whitelist() -> None:
    raw = yaml.safe_load(
        tool_validation_soul_workflow_yaml(
            tool_ids=("http", "lookup_profile", "delegate"),
            soul_id="reviewer",
            soul_name="Reviewer",
            soul_role="Reviewer",
            soul_prompt="Review the draft.",
            soul_tools=("http", "lookup_profile"),
        )
    )
    file_def = RunsightWorkflowFile.model_validate(raw)

    result = parser_module.validate_tool_governance(file_def)

    assert isinstance(result, ValidationResult)
    assert result.issues == []
    assert result.has_errors is False
    assert result.has_warnings is False


def test_duplicate_workflow_tool_ids_raise_explicit_valueerror() -> None:
    yaml_str = tool_validation_soul_workflow_yaml(
        tool_ids=("http", "http"),
        soul_tools=("http",),
    )

    with pytest.raises(ValueError, match=r"duplicate.*http"):
        parse_workflow_yaml(yaml_str)


def test_unknown_declared_tool_id_parses_with_empty_resolved_tools() -> None:
    workflow = parse_workflow_yaml(
        tool_validation_soul_workflow_yaml(
            tool_ids=("missing_lookup",),
            soul_tools=("missing_lookup",),
        )
    )

    soul = _tool_soul(workflow)
    assert soul.tools == ["missing_lookup"]
    assert soul.resolved_tools == []


def test_empty_tools_list_with_soul_reference_resolves_empty() -> None:
    workflow = parse_workflow_yaml(
        tool_validation_soul_workflow_yaml(
            tool_ids=(),
            soul_tools=("http",),
        )
    )

    assert _tool_soul(workflow).resolved_tools == []


def test_legacy_typed_tool_definitions_fail_schema_validation() -> None:
    yaml_str = workflow_with_raw_tools_section_yaml(
        """
        tools:
          http:
            type: builtin
            source: runsight/http
        """
    )

    with pytest.raises(ValidationError, match="list"):
        parse_workflow_yaml(yaml_str)


def test_inline_http_tool_definitions_fail_schema_validation() -> None:
    yaml_str = workflow_with_raw_tools_section_yaml(
        """
        tools:
          http:
            type: http
            method: GET
            url: https://tool-catalog.test/users/{{ user_id }}
        """
    )

    with pytest.raises(ValidationError, match="list"):
        parse_workflow_yaml(yaml_str)


def test_soul_reference_outside_workflow_tool_whitelist_resolves_empty() -> None:
    workflow = parse_workflow_yaml(
        tool_validation_soul_workflow_yaml(
            tool_ids=("http",),
            soul_tools=("foo",),
        )
    )

    assert _tool_soul(workflow).resolved_tools == []


def test_library_soul_undeclared_tool_reference_stays_parseable() -> None:
    workflow = parse_workflow_yaml(
        tool_validation_soul_workflow_yaml(
            tool_ids=("http", "file_io"),
            soul_id="researcher_agent",
            soul_name="Researcher",
            soul_role="Researcher",
            soul_prompt="Research stuff.",
            soul_tools=("nonexistent_tool",),
        )
    )

    assert _tool_soul(workflow).resolved_tools == []


@pytest.mark.parametrize("tool_id", ["runsight/unknown", "runsight/nonexistent"])
def test_source_like_unknown_tool_ids_parse_with_empty_resolved_tools(tool_id: str) -> None:
    workflow = parse_workflow_yaml(
        tool_validation_soul_workflow_yaml(
            tool_ids=(tool_id,),
            soul_tools=(tool_id,),
        )
    )

    soul = _tool_soul(workflow)
    assert soul.tools == [tool_id]
    assert soul.resolved_tools == []
