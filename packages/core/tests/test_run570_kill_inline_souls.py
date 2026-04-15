"""Failing tests for RUN-667: re-enable inline ``souls:`` in workflow YAML."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent
from unittest.mock import Mock, patch

import pytest
import yaml
from pydantic import ValidationError
from runsight_core.yaml.parser import parse_workflow_yaml
from runsight_core.yaml.schema import RunsightWorkflowFile


def _write_workflow_file(base_dir: Path, yaml_content: str) -> str:
    """Write a workflow YAML file so parser discovery uses the temp checkout root."""
    workflow_file = base_dir / "workflow.yaml"
    workflow_file.write_text(dedent(yaml_content), encoding="utf-8")
    return str(workflow_file)


def _write_soul_file(
    base_dir: Path,
    name: str,
    *,
    role: str,
    prompt: str,
    model_name: str | None = None,
) -> None:
    """Create ``custom/souls/<name>.yaml`` for external discovery coverage."""
    souls_dir = base_dir / "custom" / "souls"
    souls_dir.mkdir(parents=True, exist_ok=True)
    soul_data = {
        "id": name,
        "kind": "soul",
        "name": role,
        "role": role,
        "system_prompt": prompt,
    }
    if model_name:
        soul_data["model_name"] = model_name
    (souls_dir / f"{name}.yaml").write_text(
        yaml.safe_dump(soul_data, sort_keys=False),
        encoding="utf-8",
    )


def _unwrap_runtime_block(block):
    """Unwrap parser-added wrappers so assertions target the concrete block."""
    inner = getattr(block, "inner_block", block)
    return getattr(inner, "block", inner)


class TestInlineSoulParsing:
    """Inline souls should parse into runtime Souls and drive runner bootstrap."""

    def test_parse_workflow_yaml_resolves_inline_soul_refs(self, tmp_path: Path):
        workflow_path = _write_workflow_file(
            tmp_path,
            """\
            version: "1.0"
            id: inline_soul_parse
            kind: workflow
            config: {}
            souls:
              writer:
                id: writer
                kind: soul
                name: Inline Writer
                role: Inline Writer
                system_prompt: Draft carefully.
                model_name: gpt-4.1-mini
            blocks:
              draft:
                type: linear
                soul_ref: writer
            workflow:
              name: inline_soul_parse
              entry: draft
              transitions:
                - from: draft
                  to: null
            """,
        )

        with patch("runsight_core.yaml.parser.RunsightTeamRunner") as mock_runner:
            mock_runner.return_value = Mock()
            workflow = parse_workflow_yaml(workflow_path)

        block = _unwrap_runtime_block(workflow.blocks["draft"])
        assert block.soul.id == "writer"
        assert block.soul.role == "Inline Writer"
        assert block.soul.system_prompt == "Draft carefully."
        assert block.soul.model_name == "gpt-4.1-mini"
        assert mock_runner.call_args is not None
        assert mock_runner.call_args.kwargs["model_name"] == "gpt-4.1-mini"

    def test_inline_soul_tools_flow_through_tool_governance(self, tmp_path: Path):
        workflow_path = _write_workflow_file(
            tmp_path,
            """\
            version: "1.0"
            id: inline_soul_tools
            kind: workflow
            config:
              model_name: gpt-4o
            tools:
              - http
            souls:
              writer:
                id: writer
                kind: soul
                name: Tool Writer
                role: Tool Writer
                system_prompt: Use the workflow tool.
                tools:
                  - http
            blocks:
              draft:
                type: linear
                soul_ref: writer
            workflow:
              name: inline_soul_tools
              entry: draft
              transitions:
                - from: draft
                  to: null
            """,
        )

        workflow = parse_workflow_yaml(workflow_path)

        block = _unwrap_runtime_block(workflow.blocks["draft"])
        assert block.soul.tools == ["http"]
        assert block.soul.resolved_tools is not None
        assert [tool.name for tool in block.soul.resolved_tools] == ["http_request"]


class TestInlineSoulOverrides:
    """Inline soul defs should override external files on key collisions."""

    def test_inline_soul_overrides_external_file_with_warning(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ):
        _write_soul_file(
            tmp_path,
            "writer",
            role="External Writer",
            prompt="Use the library prompt.",
            model_name="claude-sonnet-4",
        )
        workflow_path = _write_workflow_file(
            tmp_path,
            """\
            version: "1.0"
            id: inline_override
            kind: workflow
            config: {}
            souls:
              writer:
                id: writer
                kind: soul
                name: Inline Writer
                role: Inline Writer
                system_prompt: Use the inline prompt.
                model_name: gpt-4.1-mini
            blocks:
              draft:
                type: linear
                soul_ref: writer
            workflow:
              name: inline_override
              entry: draft
              transitions:
                - from: draft
                  to: null
            """,
        )

        with patch("runsight_core.yaml.parser.RunsightTeamRunner") as mock_runner:
            mock_runner.return_value = Mock()
            with caplog.at_level("WARNING"):
                workflow = parse_workflow_yaml(workflow_path)

        block = _unwrap_runtime_block(workflow.blocks["draft"])
        assert block.soul.id == "writer"
        assert block.soul.kind == "soul"
        assert block.soul.name == "Inline Writer"
        assert block.soul.role == "Inline Writer"
        assert block.soul.system_prompt == "Use the inline prompt."
        assert block.soul.model_name == "gpt-4.1-mini"
        assert "Inline soul 'writer' overrides external soul file" in caplog.text
        assert mock_runner.call_args is not None
        assert mock_runner.call_args.kwargs["model_name"] == "gpt-4.1-mini"


class TestInlineSoulSchemaValidation:
    """Inline souls should validate that the dict key matches ``SoulDef.id``."""

    def test_model_validate_rejects_key_id_mismatch(self):
        raw = {
            "version": "1.0",
            "id": "test",
            "kind": "workflow",
            "workflow": {"name": "test", "entry": "draft"},
            "souls": {
                "writer": {
                    "id": "reviewer",
                    "kind": "soul",
                    "name": "Inline Writer",
                    "role": "Inline Writer",
                    "system_prompt": "Draft carefully.",
                }
            },
        }

        with pytest.raises(
            (ValidationError, ValueError),
            match=r"(key/id mismatch|writer.*reviewer.*match)",
        ):
            RunsightWorkflowFile.model_validate(raw)


class TestInlineSoulBackwardsCompatibility:
    """Existing workflows without inline souls should keep working unchanged."""

    def test_parse_workflow_yaml_without_souls_section_still_uses_external_souls(
        self, tmp_path: Path
    ):
        _write_soul_file(
            tmp_path,
            "writer",
            role="External Writer",
            prompt="Use the library prompt.",
        )
        workflow_path = _write_workflow_file(
            tmp_path,
            """\
            version: "1.0"
            id: no_inline_souls
            kind: workflow
            config:
              model_name: gpt-4o
            blocks:
              draft:
                type: linear
                soul_ref: writer
            workflow:
              name: no_inline_souls
              entry: draft
              transitions:
                - from: draft
                  to: null
            """,
        )

        workflow = parse_workflow_yaml(workflow_path)

        block = _unwrap_runtime_block(workflow.blocks["draft"])
        assert block.soul.id == "writer"
        assert block.soul.kind == "soul"
        assert block.soul.name == "External Writer"
        assert block.soul.role == "External Writer"
        assert block.soul.system_prompt == "Use the library prompt."

    def test_empty_souls_mapping_is_a_no_op_for_external_soul_resolution(self, tmp_path: Path):
        _write_soul_file(
            tmp_path,
            "writer",
            role="External Writer",
            prompt="Use the library prompt.",
        )
        workflow_path = _write_workflow_file(
            tmp_path,
            """\
            version: "1.0"
            id: empty_inline_souls
            kind: workflow
            config:
              model_name: gpt-4o
            souls: {}
            blocks:
              draft:
                type: linear
                soul_ref: writer
            workflow:
              name: empty_inline_souls
              entry: draft
              transitions:
                - from: draft
                  to: null
            """,
        )

        workflow = parse_workflow_yaml(workflow_path)

        block = _unwrap_runtime_block(workflow.blocks["draft"])
        assert block.soul.id == "writer"
        assert block.soul.kind == "soul"
        assert block.soul.name == "External Writer"
        assert block.soul.role == "External Writer"
        assert block.soul.system_prompt == "Use the library prompt."
