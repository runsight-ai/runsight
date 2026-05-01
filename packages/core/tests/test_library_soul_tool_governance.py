"""Library soul tool governance tests.

The suite verifies workflow-local tool declarations are applied to discovered
library soul files, including linear blocks, dispatch branch soul refs, missing
tool declarations, and invalid source-style tool references.

Owner: packages/core workflow YAML parser.
Boundary: parser governance for library soul tool declarations must use isolated
tmp_path fixtures and never repo-root custom assets.
Exit criteria: remove when library soul tool governance is covered by parser
contract tests.
"""

from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path
from textwrap import dedent
from typing import ContextManager

import pytest
from runsight_core.yaml.parser import parse_workflow_yaml

# ---------------------------------------------------------------------------
# Helpers: write workflow YAML and soul YAML files to an isolated workflow root
# ---------------------------------------------------------------------------


def _write_workflow_file(base_dir: Path, yaml_content: str) -> str:
    """Write workflow YAML to a file so parse_workflow_yaml infers workflow_base_dir."""
    workflow_file = base_dir / "workflow.yaml"
    content = dedent(yaml_content)
    lines = content.lstrip().splitlines()
    first_key = lines[0].split(":")[0].strip() if lines else ""
    if first_key != "id":
        content = "id: test-workflow\nkind: workflow\n" + content
    workflow_file.write_text(content, encoding="utf-8")
    return str(workflow_file)


def _isolated_workflow_root(tmp_path: Path) -> ContextManager[Path]:
    """Expose the pytest-managed temp path as the workflow root for fixture files."""
    return nullcontext(tmp_path)


def _write_soul_file(
    base_dir: Path,
    name: str,
    *,
    role: str,
    prompt: str,
    tools: list[str] | None = None,
) -> None:
    """Create a soul YAML file in the isolated library directory."""
    souls_dir = base_dir / "custom" / "souls"
    souls_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        f"id: {name}",
        "kind: soul",
        f"name: {role}",
        f"role: {role}",
        f"system_prompt: {prompt}",
    ]
    if tools is not None:
        tools_str = ", ".join(tools)
        lines.append(f"tools: [{tools_str}]")
    (souls_dir / f"{name}.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


# ===========================================================================
# Library souls with undeclared tools parse with empty resolved tools
# ===========================================================================


class TestLibrarySoulToolWithoutWorkflowTools:
    """Library souls with undeclared tools parse with empty resolved tools."""

    def test_soul_with_tool_in_workflow_without_tools_section_parses_with_empty_resolved_tools(
        self,
        tmp_path: Path,
    ):
        """Soul declares tools but workflow has no tools section."""
        with _isolated_workflow_root(tmp_path) as base:
            _write_soul_file(
                base,
                "fetcher",
                role="Fetcher",
                prompt="You fetch data.",
                tools=["http"],
            )
            path = _write_workflow_file(
                base,
                """\
                version: "1.0"
                config:
                  model_name: gpt-4o
                blocks:
                  step:
                    type: linear
                    soul_ref: fetcher
                workflow:
                  name: no_tools_section_test
                  entry: step
                  transitions:
                    - from: step
                      to: null
                """,
            )
            wf = parse_workflow_yaml(path)
            block = wf.blocks["step"]
            inner = getattr(block, "inner_block", block)
            assert inner.soul.resolved_tools == []

    def test_soul_with_tool_in_workflow_with_empty_tools_section_parses_with_empty_resolved_tools(
        self,
        tmp_path: Path,
    ):
        """Soul declares tools but workflow tools are empty."""
        with _isolated_workflow_root(tmp_path) as base:
            _write_soul_file(
                base,
                "fetcher",
                role="Fetcher",
                prompt="You fetch data.",
                tools=["http"],
            )
            path = _write_workflow_file(
                base,
                """\
                version: "1.0"
                config:
                  model_name: gpt-4o
                tools: []
                blocks:
                  step:
                    type: linear
                    soul_ref: fetcher
                workflow:
                  name: empty_tools_test
                  entry: step
                  transitions:
                    - from: step
                      to: null
                """,
            )
            wf = parse_workflow_yaml(path)
            block = wf.blocks["step"]
            inner = getattr(block, "inner_block", block)
            assert inner.soul.resolved_tools == []


# ===========================================================================
# Library souls with matching workflow tools resolve successfully
# ===========================================================================


class TestLibrarySoulToolWithMatchingWorkflowTools:
    """Library soul tools resolve when the workflow declares them."""

    def test_soul_tool_declared_in_workflow_tools_resolves(self, tmp_path: Path):
        """Soul and workflow both declare the same tool."""
        with _isolated_workflow_root(tmp_path) as base:
            _write_soul_file(
                base,
                "fetcher",
                role="Fetcher",
                prompt="You fetch data.",
                tools=["http"],
            )
            path = _write_workflow_file(
                base,
                """\
                version: "1.0"
                config:
                  model_name: gpt-4o
                tools:
                  - http
                blocks:
                  step:
                    type: linear
                    soul_ref: fetcher
                workflow:
                  name: matching_tools_test
                  entry: step
                  transitions:
                    - from: step
                      to: null
                """,
            )
            wf = parse_workflow_yaml(path)
            block = wf.blocks["step"]
            inner = getattr(block, "inner_block", block)
            assert inner.soul.role == "Fetcher"
            assert inner.soul.resolved_tools is not None
            assert [tool.name for tool in inner.soul.resolved_tools] == ["http_request"]

    def test_soul_with_multiple_tools_all_declared_resolves(self, tmp_path: Path):
        """Soul with multiple tools resolves when all are declared in workflow."""
        with _isolated_workflow_root(tmp_path) as base:
            _write_soul_file(
                base,
                "agent",
                role="Agent",
                prompt="You do things.",
                tools=["http", "file_io"],
            )
            path = _write_workflow_file(
                base,
                """\
                version: "1.0"
                config:
                  model_name: gpt-4o
                tools:
                  - http
                  - file_io
                blocks:
                  step:
                    type: linear
                    soul_ref: agent
                workflow:
                  name: multi_tools_test
                  entry: step
                  transitions:
                    - from: step
                      to: null
                """,
            )
            wf = parse_workflow_yaml(path)
            block = wf.blocks["step"]
            inner = getattr(block, "inner_block", block)
            assert inner.soul.role == "Agent"
            assert inner.soul.resolved_tools is not None
            assert {tool.name for tool in inner.soul.resolved_tools} == {
                "http_request",
                "file_io",
            }


# ===========================================================================
# Undeclared tool references are preserved on unresolved souls
# ===========================================================================


class TestUndeclaredToolResolution:
    """Unresolved library soul tools remain visible for governance callers."""

    def test_unresolved_tool_keeps_raw_tool_reference(self, tmp_path: Path):
        """The unresolved tool reference remains available on the parsed soul."""
        with _isolated_workflow_root(tmp_path) as base:
            _write_soul_file(
                base,
                "data_fetcher",
                role="Data Fetcher",
                prompt="Fetch data.",
                tools=["http"],
            )
            path = _write_workflow_file(
                base,
                """\
                version: "1.0"
                config:
                  model_name: gpt-4o
                blocks:
                  step:
                    type: linear
                    soul_ref: data_fetcher
                workflow:
                  name: unresolved_tool_soul_key_test
                  entry: step
                  transitions:
                    - from: step
                      to: null
                """,
            )
            wf = parse_workflow_yaml(path)
            block = wf.blocks["step"]
            inner = getattr(block, "inner_block", block)
            assert inner.soul.resolved_tools == []
            assert inner.soul.tools == ["http"]

    def test_unresolved_tool_preserves_tool_name(self, tmp_path: Path):
        """The undeclared tool name remains available on the parsed soul."""
        with _isolated_workflow_root(tmp_path) as base:
            _write_soul_file(
                base,
                "worker",
                role="Worker",
                prompt="You work.",
                tools=["missing_tool"],
            )
            path = _write_workflow_file(
                base,
                """\
                version: "1.0"
                config:
                  model_name: gpt-4o
                blocks:
                  step:
                    type: linear
                    soul_ref: worker
                workflow:
                  name: unresolved_tool_name_test
                  entry: step
                  transitions:
                    - from: step
                      to: null
                """,
            )
            wf = parse_workflow_yaml(path)
            block = wf.blocks["step"]
            inner = getattr(block, "inner_block", block)
            assert inner.soul.resolved_tools == []
            assert inner.soul.tools == ["missing_tool"]


# ===========================================================================
# Souls without tools parse cleanly
# ===========================================================================


class TestSoulsWithoutToolsParseCleanly:
    """Souls that don't declare any tools should still parse cleanly."""

    def test_soul_without_tools_parses_without_governance_error(self, tmp_path: Path):
        """Soul with no tools field parses without governance errors."""
        with _isolated_workflow_root(tmp_path) as base:
            _write_soul_file(
                base,
                "plain_agent",
                role="Plain Agent",
                prompt="I have no tools.",
            )
            path = _write_workflow_file(
                base,
                """\
                version: "1.0"
                config:
                  model_name: gpt-4o
                blocks:
                  step:
                    type: linear
                    soul_ref: plain_agent
                workflow:
                  name: no_tools_soul_test
                  entry: step
                  transitions:
                    - from: step
                      to: null
                """,
            )
            wf = parse_workflow_yaml(path)
            block = wf.blocks["step"]
            inner = getattr(block, "inner_block", block)
            assert inner.soul.role == "Plain Agent"

    def test_mixed_souls_with_and_without_tools_only_omits_tooled_soul_resolution(
        self, tmp_path: Path
    ):
        """Only the soul with undeclared tools receives empty resolved tools."""
        with _isolated_workflow_root(tmp_path) as base:
            _write_soul_file(
                base,
                "plain",
                role="Plain",
                prompt="No tools.",
            )
            _write_soul_file(
                base,
                "tooled",
                role="Tooled",
                prompt="I use tools.",
                tools=["http"],
            )
            path = _write_workflow_file(
                base,
                """\
                version: "1.0"
                config:
                  model_name: gpt-4o
                blocks:
                  plain_step:
                    type: linear
                    soul_ref: plain
                  tooled_step:
                    type: linear
                    soul_ref: tooled
                workflow:
                  name: mixed_souls_test
                  entry: plain_step
                  transitions:
                    - from: plain_step
                      to: tooled_step
                    - from: tooled_step
                      to: null
                """,
            )
            wf = parse_workflow_yaml(path)
            plain_block = wf.blocks["plain_step"]
            tooled_block = wf.blocks["tooled_step"]
            plain_inner = getattr(plain_block, "inner_block", plain_block)
            tooled_inner = getattr(tooled_block, "inner_block", tooled_block)
            assert plain_inner.soul.resolved_tools is None
            assert tooled_inner.soul.resolved_tools == []


# ===========================================================================
# Dispatch exit soul refs participate in tool governance
# ===========================================================================


class TestDispatchExitSoulRefsValidated:
    """Tool governance applies to souls referenced by dispatch exit soul refs."""

    def test_dispatch_exit_soul_with_undeclared_tool_has_empty_resolved_tools(self, tmp_path: Path):
        """Dispatch exit soul_ref with undeclared tools yields empty resolved tools."""
        with _isolated_workflow_root(tmp_path) as base:
            _write_soul_file(
                base,
                "branch_agent",
                role="Branch Agent",
                prompt="I handle branches.",
                tools=["http"],
            )
            _write_soul_file(
                base,
                "plain_branch",
                role="Plain Branch",
                prompt="No tools needed.",
            )
            path = _write_workflow_file(
                base,
                """\
                version: "1.0"
                config:
                  model_name: gpt-4o
                blocks:
                  fan:
                    type: dispatch
                    exits:
                      - id: branch_a
                        label: Branch A
                        soul_ref: branch_agent
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
                """,
            )
            wf = parse_workflow_yaml(path)
            block = wf.blocks["fan"]
            inner = getattr(block, "inner_block", block)
            assert inner.branches[0].soul.resolved_tools == []
            assert inner.branches[1].soul.resolved_tools is None

    def test_dispatch_exit_soul_with_declared_tool_resolves(self, tmp_path: Path):
        """Dispatch exit soul_ref with declared tools resolves normally."""
        with _isolated_workflow_root(tmp_path) as base:
            _write_soul_file(
                base,
                "tooled_branch",
                role="Tooled Branch",
                prompt="I use tools.",
                tools=["http"],
            )
            _write_soul_file(
                base,
                "plain_branch",
                role="Plain Branch",
                prompt="No tools.",
            )
            path = _write_workflow_file(
                base,
                """\
                version: "1.0"
                config:
                  model_name: gpt-4o
                tools:
                  - http
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
                  name: dispatch_declared_tool_test
                  entry: fan
                  transitions:
                    - from: fan
                      to: null
                """,
            )
            wf = parse_workflow_yaml(path)
            block = wf.blocks["fan"]
            inner = getattr(block, "inner_block", block)
            assert inner.branches[0].soul.role == "Tooled Branch"
            assert inner.branches[0].soul.resolved_tools is not None
            assert [tool.name for tool in inner.branches[0].soul.resolved_tools] == ["http_request"]
            assert inner.branches[1].soul.role == "Plain Branch"


# ===========================================================================
# Edge Cases
# ===========================================================================


class TestEdgeCases:
    """Edge cases for library soul tool governance."""

    def test_soul_declares_multiple_tools_one_missing_omits_missing_tool(self, tmp_path: Path):
        """Soul declares multiple tools, only one is missing -> resolution omits the missing tool."""
        with _isolated_workflow_root(tmp_path) as base:
            _write_soul_file(
                base,
                "multi_tool_agent",
                role="Multi-Tool Agent",
                prompt="I use many tools.",
                tools=["http", "missing_file_tool"],
            )
            path = _write_workflow_file(
                base,
                """\
                version: "1.0"
                config:
                  model_name: gpt-4o
                tools:
                  - http
                blocks:
                  step:
                    type: linear
                    soul_ref: multi_tool_agent
                workflow:
                  name: partial_tools_test
                  entry: step
                  transitions:
                    - from: step
                      to: null
                """,
            )
            wf = parse_workflow_yaml(path)
            block = wf.blocks["step"]
            inner = getattr(block, "inner_block", block)
            assert [tool.name for tool in inner.soul.resolved_tools] == ["http_request"]

    def test_multiple_souls_reference_same_undeclared_tool_omits_resolution_for_each(
        self, tmp_path: Path
    ):
        """Multiple souls reference the same undeclared tool -> each soul omits it from resolution."""
        with _isolated_workflow_root(tmp_path) as base:
            _write_soul_file(
                base,
                "agent_a",
                role="Agent A",
                prompt="I am A.",
                tools=["undeclared_tool"],
            )
            _write_soul_file(
                base,
                "agent_b",
                role="Agent B",
                prompt="I am B.",
                tools=["undeclared_tool"],
            )
            path = _write_workflow_file(
                base,
                """\
                version: "1.0"
                config:
                  model_name: gpt-4o
                blocks:
                  step_a:
                    type: linear
                    soul_ref: agent_a
                  step_b:
                    type: linear
                    soul_ref: agent_b
                workflow:
                  name: multi_soul_same_tool_test
                  entry: step_a
                  transitions:
                    - from: step_a
                      to: step_b
                    - from: step_b
                      to: null
                """,
            )
            wf = parse_workflow_yaml(path)
            assert wf.blocks["step_a"].soul.resolved_tools == []
            assert wf.blocks["step_b"].soul.resolved_tools == []

    def test_soul_tool_ref_matches_workflow_tool_key_not_source(self, tmp_path: Path):
        """Soul's tool ref must match the canonical workflow tool id exactly."""
        with _isolated_workflow_root(tmp_path) as base:
            # Soul references a legacy source string instead of the canonical workflow tool id.
            _write_soul_file(
                base,
                "source_ref_agent",
                role="Source Ref Agent",
                prompt="I reference by source.",
                tools=["runsight/http"],
            )
            path = _write_workflow_file(
                base,
                """\
                version: "1.0"
                config:
                  model_name: gpt-4o
                tools:
                  - http
                blocks:
                  step:
                    type: linear
                    soul_ref: source_ref_agent
                workflow:
                  name: key_vs_source_test
                  entry: step
                  transitions:
                    - from: step
                      to: null
                """,
            )
            # Legacy source strings must not match canonical workflow ids.
            with pytest.raises(ValueError) as exc_info:
                parse_workflow_yaml(path)
            error_msg = str(exc_info.value)
            assert "runsight/http" in error_msg
