"""Library soul tool governance for linear blocks."""

from __future__ import annotations

from pathlib import Path

import pytest
from library_soul_tool_helpers import linear_workflow_yaml, write_soul_file, write_workflow_file
from runsight_core.yaml.parser import parse_workflow_yaml


def _linear_soul(workflow) -> object:
    block = workflow.blocks["step"]
    inner = getattr(block, "inner_block", block)
    return inner.soul


@pytest.mark.parametrize("tools_section", ["", "tools: []"])
def test_library_soul_with_undeclared_tool_parses_with_empty_resolved_tools(
    tmp_path: Path,
    tools_section: str,
) -> None:
    write_soul_file(tmp_path, "fetcher", role="Fetcher", prompt="You fetch data.", tools=["http"])
    path = write_workflow_file(
        tmp_path, linear_workflow_yaml(soul_ref="fetcher", tools_section=tools_section)
    )

    soul = _linear_soul(parse_workflow_yaml(path))

    assert soul.tools == ["http"]
    assert soul.resolved_tools == []


def test_library_soul_tool_declared_in_workflow_resolves(tmp_path: Path) -> None:
    write_soul_file(
        tmp_path, "agent", role="Agent", prompt="You do things.", tools=["http", "file_io"]
    )
    path = write_workflow_file(
        tmp_path,
        linear_workflow_yaml(
            soul_ref="agent", tools_section="tools:\n      - http\n      - file_io"
        ),
    )

    soul = _linear_soul(parse_workflow_yaml(path))

    assert soul.role == "Agent"
    assert {tool.name for tool in soul.resolved_tools} == {"http_request", "file_io"}


def test_library_soul_without_tools_keeps_resolution_unset(tmp_path: Path) -> None:
    write_soul_file(tmp_path, "plain_agent", role="Plain Agent", prompt="No tools.")
    path = write_workflow_file(tmp_path, linear_workflow_yaml(soul_ref="plain_agent"))

    soul = _linear_soul(parse_workflow_yaml(path))

    assert soul.role == "Plain Agent"
    assert soul.resolved_tools is None


def test_library_soul_declared_and_missing_tools_omit_missing_resolution(tmp_path: Path) -> None:
    write_soul_file(
        tmp_path,
        "multi_tool_agent",
        role="Multi-Tool Agent",
        prompt="I use many tools.",
        tools=["http", "missing_file_tool"],
    )
    path = write_workflow_file(
        tmp_path,
        linear_workflow_yaml(soul_ref="multi_tool_agent", tools_section="tools:\n      - http"),
    )

    soul = _linear_soul(parse_workflow_yaml(path))

    assert [tool.name for tool in soul.resolved_tools] == ["http_request"]


def test_library_soul_tool_ref_matches_workflow_tool_key_not_legacy_source(tmp_path: Path) -> None:
    write_soul_file(
        tmp_path,
        "source_ref_agent",
        role="Source Ref Agent",
        prompt="I reference by source.",
        tools=["runsight/http"],
    )
    path = write_workflow_file(
        tmp_path,
        linear_workflow_yaml(soul_ref="source_ref_agent", tools_section="tools:\n      - http"),
    )

    with pytest.raises(ValueError, match="runsight/http"):
        parse_workflow_yaml(path)
