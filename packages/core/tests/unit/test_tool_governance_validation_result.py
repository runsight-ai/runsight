from __future__ import annotations

import logging
from pathlib import Path
from textwrap import dedent
from types import SimpleNamespace

import pytest
import runsight_core.yaml.parser as parser_module
import yaml
from runsight_core.yaml.parser import parse_workflow_yaml, validate_tool_governance
from runsight_core.yaml.schema import RunsightWorkflowFile
from runsight_core.yaml.validation import ValidationResult, ValidationSeverity


def _make_yaml(
    *,
    tools: str = "",
    souls: str = "",
    blocks: str = "",
    transitions: str = "",
    entry: str = "my_block",
) -> str:
    return f"""\
version: "1.0"
id: run-839-tool-governance-test
kind: workflow
config:
  model_name: gpt-4o
{tools}
{souls}
blocks:
{blocks}
workflow:
  name: run_839_tool_governance_test
  entry: {entry}
  transitions:
{transitions}
"""


def _write_workflow_file(tmp_path: Path, yaml_str: str) -> str:
    workflow_file = tmp_path / "workflow.yaml"
    workflow_file.write_text(dedent(yaml_str), encoding="utf-8")
    return str(workflow_file)


def _load_file_def(yaml_str: str) -> RunsightWorkflowFile:
    return RunsightWorkflowFile.model_validate(yaml.safe_load(dedent(yaml_str)))


class TestValidateToolGovernanceResultContract:
    def test_returns_validation_result_with_warning_metadata_for_undeclared_tool(self):
        yaml_str = _make_yaml(
            entry="ingest",
            tools="""\
tools:
  - http""",
            souls="""\
souls:
  fetcher:
    id: fetcher
    kind: soul
    name: Fetcher
    role: Fetcher
    system_prompt: Fetch data.
    tools:
      - http
      - scraper""",
            blocks="""\
  ingest:
    type: linear
    soul_ref: fetcher""",
            transitions="""\
    - from: ingest
      to: null""",
        )
        file_def = _load_file_def(yaml_str)

        result = validate_tool_governance(file_def, file_def.souls)

        assert isinstance(result, ValidationResult)
        assert result.has_errors is False
        assert result.has_warnings is True
        assert result.issues == result.warnings
        assert len(result.warnings) == 1
        issue = result.warnings[0]
        assert issue.severity is ValidationSeverity.warning
        assert issue.source == "tool_governance"
        assert issue.context == "fetcher"
        assert "fetcher" in issue.message
        assert "scraper" in issue.message
        assert result.warnings_as_dicts() == [
            {
                "message": issue.message,
                "source": "tool_governance",
                "context": "fetcher",
            }
        ]

    def test_returns_empty_result_when_every_referenced_tool_is_declared(self):
        yaml_str = _make_yaml(
            tools="""\
tools:
  - http
  - file_io""",
            souls="""\
souls:
  builder:
    id: builder
    kind: soul
    name: Builder
    role: Builder
    system_prompt: Build things.
    tools:
      - http
      - file_io""",
            blocks="""\
  build:
    type: linear
    soul_ref: builder""",
            transitions="""\
    - from: build
      to: null""",
        )
        file_def = _load_file_def(yaml_str)

        result = validate_tool_governance(file_def, file_def.souls)

        assert isinstance(result, ValidationResult)
        assert result.issues == []
        assert result.has_errors is False
        assert result.has_warnings is False
        assert result.error_summary is None
        assert result.warnings_as_dicts() == []

    def test_returns_one_warning_per_soul_tool_pair(self):
        yaml_str = _make_yaml(
            tools="""\
tools:
  - http""",
            souls="""\
souls:
  fetcher:
    id: fetcher
    kind: soul
    name: Fetcher
    role: Fetcher
    system_prompt: Fetch data.
    tools:
      - scraper
  archiver:
    id: archiver
    kind: soul
    name: Archiver
    role: Archiver
    system_prompt: Archive data.
    tools:
      - scraper""",
            blocks="""\
  ingest:
    type: linear
    soul_ref: fetcher
  archive:
    type: linear
    soul_ref: archiver""",
            transitions="""\
    - from: ingest
      to: archive
    - from: archive
      to: null""",
        )
        file_def = _load_file_def(yaml_str)

        result = validate_tool_governance(file_def, file_def.souls)

        assert isinstance(result, ValidationResult)
        assert len(result.warnings) == 2
        assert {(issue.context, issue.source) for issue in result.warnings} == {
            ("fetcher", "tool_governance"),
            ("archiver", "tool_governance"),
        }
        assert all("scraper" in issue.message for issue in result.warnings)


class TestWorkflowParserToolGovernanceWarnings:
    def test_parse_workflow_yaml_keeps_workflow_parseable_when_one_soul_tool_is_undeclared(
        self, tmp_path: Path
    ):
        yaml_str = _make_yaml(
            entry="ingest",
            tools="""\
tools:
  - http""",
            souls="""\
souls:
  fetcher:
    id: fetcher
    kind: soul
    name: Fetcher
    role: Fetcher
    system_prompt: Fetch data.
    tools:
      - http
      - scraper""",
            blocks="""\
  ingest:
    type: linear
    soul_ref: fetcher""",
            transitions="""\
    - from: ingest
      to: null""",
        )
        workflow_file = _write_workflow_file(tmp_path, yaml_str)

        workflow = parse_workflow_yaml(workflow_file)

        soul = workflow.blocks["ingest"].soul
        assert soul.resolved_tools is not None
        assert [tool.name for tool in soul.resolved_tools] == ["http_request"]

    def test_parse_workflow_yaml_returns_empty_resolved_tools_when_all_soul_tools_are_unavailable(
        self, tmp_path: Path
    ):
        yaml_str = _make_yaml(
            entry="ingest",
            tools="""\
tools: []""",
            souls="""\
souls:
  fetcher:
    id: fetcher
    kind: soul
    name: Fetcher
    role: Fetcher
    system_prompt: Fetch data.
    tools:
      - scraper""",
            blocks="""\
  ingest:
    type: linear
    soul_ref: fetcher""",
            transitions="""\
    - from: ingest
      to: null""",
        )
        workflow_file = _write_workflow_file(tmp_path, yaml_str)

        workflow = parse_workflow_yaml(workflow_file)

        soul = workflow.blocks["ingest"].soul
        assert soul.resolved_tools == []

    def test_parse_workflow_yaml_skips_one_failed_tool_resolution_and_logs_warning(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, tmp_path: Path
    ):
        yaml_str = _make_yaml(
            entry="route",
            tools="""\
tools:
  - http
  - file_io""",
            souls="""\
souls:
  router:
    id: router
    kind: soul
    name: Router
    role: Router
    system_prompt: Route requests.
    tools:
      - http
      - file_io""",
            blocks="""\
  route:
    type: linear
    soul_ref: router""",
            transitions="""\
    - from: route
      to: null""",
        )
        workflow_file = _write_workflow_file(tmp_path, yaml_str)

        monkeypatch.setattr(
            parser_module,
            "_validate_declared_tool_definitions",
            lambda *args, **kwargs: ValidationResult(),
        )

        def _fake_resolve_tool_for_parser(
            tool_id: str, *, base_dir: str, exits: object | None = None
        ):
            if tool_id == "file_io":
                raise ValueError("synthetic tool resolution failure")
            return SimpleNamespace(name="http_request", description="ok", parameters={})

        monkeypatch.setattr(
            parser_module, "_resolve_tool_for_parser", _fake_resolve_tool_for_parser
        )

        with caplog.at_level(logging.WARNING, logger="runsight_core.yaml.parser"):
            workflow = parse_workflow_yaml(workflow_file)

        soul = workflow.blocks["route"].soul
        assert [tool.name for tool in soul.resolved_tools] == ["http_request"]
        assert any(
            record.levelno == logging.WARNING and "file_io" in record.message
            for record in caplog.records
        )
