"""Residual parser tool-resolution compatibility tests.

The behavior-owner suites cover declared whitelist, custom discovery, and
delegate exit-schema contracts. This file keeps small cross-soul resolution
checks that do not belong to one of those owners.
"""

from __future__ import annotations

from parser_yaml_helpers import (
    tool_validation_soul_workflow_yaml,
    tool_validation_two_soul_workflow_yaml,
)
from runsight_core.yaml.parser import parse_workflow_yaml


def test_soul_without_tools_field_keeps_resolved_tools_unset() -> None:
    workflow = parse_workflow_yaml(
        tool_validation_soul_workflow_yaml(
            tool_ids=("http",),
            soul_id="plain_agent",
            soul_name="Plain Agent",
            soul_role="Plain Agent",
            soul_prompt="Do plain things.",
            soul_tools=None,
        )
    )

    soul = workflow.blocks["tool_validation_block"].soul
    assert soul.resolved_tools is None


def test_workflow_without_declared_tools_and_soul_without_tools_keeps_resolution_unset() -> None:
    workflow = parse_workflow_yaml(
        tool_validation_soul_workflow_yaml(
            tool_ids=None,
            soul_id="researcher",
            soul_name="Senior Researcher",
            soul_role="Senior Researcher",
            soul_prompt="You research topics.",
            soul_tools=None,
        )
    )

    soul = workflow.blocks["tool_validation_block"].soul
    assert soul.resolved_tools is None


def test_two_souls_get_only_their_own_declared_tools() -> None:
    workflow = parse_workflow_yaml(
        tool_validation_two_soul_workflow_yaml(
            tool_ids=("http", "file_io"),
            first_soul_id="http_agent",
            first_soul_tools=("http",),
            second_soul_id="file_agent",
            second_soul_tools=("file_io",),
        )
    )

    soul_a = workflow.blocks["block_a"].soul
    soul_b = workflow.blocks["block_b"].soul

    assert soul_a.resolved_tools is not None
    assert [tool.name for tool in soul_a.resolved_tools] == ["http_request"]
    assert soul_b.resolved_tools is not None
    assert [tool.name for tool in soul_b.resolved_tools] == ["file_io"]


def test_soul_with_tools_and_soul_without_tools_keep_separate_resolution_state() -> None:
    workflow = parse_workflow_yaml(
        tool_validation_two_soul_workflow_yaml(
            tool_ids=("http",),
            first_soul_id="tool_agent",
            first_soul_tools=("http",),
            second_soul_id="plain_agent",
            second_soul_tools=None,
        )
    )

    soul_a = workflow.blocks["block_a"].soul
    soul_b = workflow.blocks["block_b"].soul

    assert soul_a.resolved_tools is not None
    assert [tool.name for tool in soul_a.resolved_tools] == ["http_request"]
    assert soul_b.resolved_tools is None
