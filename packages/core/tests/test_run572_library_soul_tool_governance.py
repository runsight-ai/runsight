"""
Failing tests for RUN-572: Library soul tool governance.

After RUN-570 killed inline souls and RUN-571 wired library discovery,
``validate_tool_governance()`` still iterates ``file_def.souls.items()``
which is always empty. It needs to validate library-discovered souls
(from ``souls_map``) against ``file_def.tools`` instead.

All tests should FAIL until validate_tool_governance is updated to check
library souls.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from textwrap import dedent

import pytest
from runsight_core.yaml.parser import parse_workflow_yaml

# ---------------------------------------------------------------------------
# Helpers: write workflow YAML + soul YAML files to a temp directory
# ---------------------------------------------------------------------------


def _write_workflow_file(base_dir: Path, yaml_content: str) -> str:
    """Write workflow YAML to a file so parse_workflow_yaml infers workflow_base_dir."""
    workflow_file = base_dir / "workflow.yaml"
    workflow_file.write_text(dedent(yaml_content), encoding="utf-8")
    return str(workflow_file)


def _write_soul_file(
    base_dir: Path,
    name: str,
    *,
    soul_id: str,
    role: str,
    prompt: str,
    tools: list[str] | None = None,
) -> None:
    """Create a soul YAML file at custom/souls/<name>.yaml."""
    souls_dir = base_dir / "custom" / "souls"
    souls_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        f"id: {soul_id}",
        f"role: {role}",
        f"system_prompt: {prompt}",
    ]
    if tools is not None:
        tools_str = ", ".join(tools)
        lines.append(f"tools: [{tools_str}]")
    (souls_dir / f"{name}.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


# ===========================================================================
# AC1: Library soul with tools in a workflow WITHOUT tools section -> error
# ===========================================================================


class TestLibrarySoulToolWithoutWorkflowTools:
    """Library soul declaring tools must fail if the workflow has no tools: section."""

    def test_soul_with_tool_in_workflow_without_tools_section_raises(self):
        """AC1: Soul declares tools: [http] but workflow has no tools: section."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            _write_soul_file(
                base,
                "fetcher",
                soul_id="f1",
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
            with pytest.raises(ValueError, match="http"):
                parse_workflow_yaml(path)

    def test_soul_with_tool_in_workflow_with_empty_tools_section_raises(self):
        """AC1: Soul declares tools but workflow tools: [] is empty."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            _write_soul_file(
                base,
                "fetcher",
                soul_id="f1",
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
            with pytest.raises(ValueError, match="http"):
                parse_workflow_yaml(path)


# ===========================================================================
# AC2: Library soul with tools in a workflow WITH matching tools -> passes
# ===========================================================================


class TestLibrarySoulToolWithMatchingWorkflowTools:
    """Library soul declaring tools passes when the workflow declares them."""

    def test_soul_tool_declared_in_workflow_tools_passes(self):
        """AC2: Soul declares tools: [http], workflow has tools: [http]."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            _write_soul_file(
                base,
                "fetcher",
                soul_id="f1",
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
            # Should NOT raise — soul tool is declared in workflow tools
            wf = parse_workflow_yaml(path)
            block = wf.blocks["step"]
            inner = getattr(block, "inner_block", block)
            assert inner.soul.role == "Fetcher"
            assert inner.soul.resolved_tools is not None
            assert [tool.name for tool in inner.soul.resolved_tools] == ["http_request"]

    def test_soul_with_multiple_tools_all_declared_passes(self):
        """AC2: Soul with multiple tools all declared in workflow -> passes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            _write_soul_file(
                base,
                "agent",
                soul_id="a1",
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
# AC3: Error message names the soul file and the undeclared tool
# ===========================================================================


class TestErrorMessageContent:
    """Error must identify the soul (by filename / key) and the undeclared tool."""

    def test_error_names_the_soul_file(self):
        """AC3: Error message must contain the soul key (filename stem)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            _write_soul_file(
                base,
                "data_fetcher",
                soul_id="df1",
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
                  name: error_names_soul_test
                  entry: step
                  transitions:
                    - from: step
                      to: null
                """,
            )
            with pytest.raises(ValueError) as exc_info:
                parse_workflow_yaml(path)
            error_msg = str(exc_info.value)
            assert "data_fetcher" in error_msg

    def test_error_names_the_undeclared_tool(self):
        """AC3: Error message must contain the undeclared tool name."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            _write_soul_file(
                base,
                "worker",
                soul_id="w1",
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
                  name: error_names_tool_test
                  entry: step
                  transitions:
                    - from: step
                      to: null
                """,
            )
            with pytest.raises(ValueError) as exc_info:
                parse_workflow_yaml(path)
            error_msg = str(exc_info.value)
            assert "missing_tool" in error_msg


# ===========================================================================
# AC4: Souls without tools pass validation silently
# ===========================================================================


class TestSoulsWithoutToolsPassSilently:
    """Souls that don't declare any tools should pass governance silently."""

    def test_soul_without_tools_passes_governance(self):
        """AC4: Soul with no tools field -> no error from governance validation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            _write_soul_file(
                base,
                "plain_agent",
                soul_id="p1",
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
            # Should succeed without any ValueError
            wf = parse_workflow_yaml(path)
            block = wf.blocks["step"]
            inner = getattr(block, "inner_block", block)
            assert inner.soul.role == "Plain Agent"

    def test_mixed_souls_with_and_without_tools_only_validates_tooled_soul(self):
        """AC4: One soul has tools (undeclared), one doesn't -> error only for the tooled soul."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            _write_soul_file(
                base,
                "plain",
                soul_id="p1",
                role="Plain",
                prompt="No tools.",
            )
            _write_soul_file(
                base,
                "tooled",
                soul_id="t1",
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
            # Should error for 'tooled' soul, not for 'plain' soul
            with pytest.raises(ValueError) as exc_info:
                parse_workflow_yaml(path)
            error_msg = str(exc_info.value)
            assert "tooled" in error_msg
            assert "http" in error_msg


# ===========================================================================
# AC5: Dispatch exit soul_refs are also validated
# ===========================================================================


class TestDispatchExitSoulRefsValidated:
    """Tool governance must also check souls referenced by dispatch exit soul_refs."""

    def test_dispatch_exit_soul_with_undeclared_tool_raises(self):
        """AC5: Dispatch exit's soul_ref points to a soul with undeclared tools -> error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            _write_soul_file(
                base,
                "branch_agent",
                soul_id="ba1",
                role="Branch Agent",
                prompt="I handle branches.",
                tools=["http"],
            )
            _write_soul_file(
                base,
                "plain_branch",
                soul_id="pb1",
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
            with pytest.raises(ValueError) as exc_info:
                parse_workflow_yaml(path)
            error_msg = str(exc_info.value)
            assert "branch_agent" in error_msg
            assert "http" in error_msg

    def test_dispatch_exit_soul_with_declared_tool_passes(self):
        """AC5: Dispatch exit's soul_ref with properly declared tools -> passes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            _write_soul_file(
                base,
                "tooled_branch",
                soul_id="tb1",
                role="Tooled Branch",
                prompt="I use tools.",
                tools=["http"],
            )
            _write_soul_file(
                base,
                "plain_branch",
                soul_id="pb1",
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
            # Should NOT raise
            wf = parse_workflow_yaml(path)
            block = wf.blocks["fan"]
            inner = getattr(block, "inner_block", block)
            assert inner.branches[0].soul.role == "Tooled Branch"
            assert inner.branches[1].soul.role == "Plain Branch"


# ===========================================================================
# Edge Cases
# ===========================================================================


class TestEdgeCases:
    """Edge cases for library soul tool governance."""

    def test_soul_declares_multiple_tools_one_missing_error_names_missing(self):
        """Soul declares multiple tools, only one is missing -> error names the missing tool."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            _write_soul_file(
                base,
                "multi_tool_agent",
                soul_id="mt1",
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
            with pytest.raises(ValueError) as exc_info:
                parse_workflow_yaml(path)
            error_msg = str(exc_info.value)
            # Must name the missing tool, not the declared one
            assert "missing_file_tool" in error_msg

    def test_multiple_souls_reference_same_undeclared_tool_errors_on_first(self):
        """Multiple souls reference the same undeclared tool -> error on first encountered."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            _write_soul_file(
                base,
                "agent_a",
                soul_id="a1",
                role="Agent A",
                prompt="I am A.",
                tools=["undeclared_tool"],
            )
            _write_soul_file(
                base,
                "agent_b",
                soul_id="b1",
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
            # Should raise for at least one of the souls
            with pytest.raises(ValueError) as exc_info:
                parse_workflow_yaml(path)
            error_msg = str(exc_info.value)
            assert "undeclared_tool" in error_msg

    def test_soul_tool_ref_matches_workflow_tool_key_not_source(self):
        """Soul's tool ref must match the canonical workflow tool id exactly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            # Soul references a legacy source string instead of the canonical workflow tool id.
            _write_soul_file(
                base,
                "source_ref_agent",
                soul_id="sr1",
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
