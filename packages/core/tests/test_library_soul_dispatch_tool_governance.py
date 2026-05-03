"""Library soul tool governance for dispatch exit soul references.

Owner: packages/core workflow parser/runtime behavior.
Boundary: dispatch exit library souls must resolve only workflow-declared
tools and must not revive legacy global tool discovery.
Exit criteria: delete once dispatch exit soul tool resolution is covered by
the canonical workflow parser behavior suite.
"""

from __future__ import annotations

from pathlib import Path

from library_soul_tool_helpers import write_soul_file, write_workflow_file
from runsight_core.yaml.parser import parse_workflow_yaml


def _dispatch_workflow_yaml(*, tools_section: str = "") -> str:
    return f"""\
    version: "1.0"
    config:
      model_name: gpt-4o
    {tools_section}
    blocks:
      fan:
        type: dispatch
        exits:
          - id: branch_a
            label: Branch A
            soul_ref: tooled_branch
            task: Do task A
          - id: branch_b
            label: Branch B
            soul_ref: plain_branch
            task: Do task B
    workflow:
      name: dispatch_tool_gov_test
      entry: fan
      transitions:
        - from: fan
          to: null
    """


def test_dispatch_exit_soul_with_undeclared_tool_has_empty_resolved_tools(tmp_path: Path) -> None:
    write_soul_file(
        tmp_path, "tooled_branch", role="Tooled Branch", prompt="I use tools.", tools=["http"]
    )
    write_soul_file(tmp_path, "plain_branch", role="Plain Branch", prompt="No tools needed.")
    path = write_workflow_file(tmp_path, _dispatch_workflow_yaml())

    block = parse_workflow_yaml(path).blocks["fan"]
    inner = getattr(block, "inner_block", block)

    assert inner.branches[0].soul.resolved_tools == []
    assert inner.branches[1].soul.resolved_tools is None


def test_dispatch_exit_soul_with_declared_tool_resolves(tmp_path: Path) -> None:
    write_soul_file(
        tmp_path, "tooled_branch", role="Tooled Branch", prompt="I use tools.", tools=["http"]
    )
    write_soul_file(tmp_path, "plain_branch", role="Plain Branch", prompt="No tools.")
    path = write_workflow_file(
        tmp_path, _dispatch_workflow_yaml(tools_section="tools:\n      - http")
    )

    block = parse_workflow_yaml(path).blocks["fan"]
    inner = getattr(block, "inner_block", block)

    assert inner.branches[0].soul.role == "Tooled Branch"
    assert [tool.name for tool in inner.branches[0].soul.resolved_tools] == ["http_request"]
    assert inner.branches[1].soul.role == "Plain Branch"
