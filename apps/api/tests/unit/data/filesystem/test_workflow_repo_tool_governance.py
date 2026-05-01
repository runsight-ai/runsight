"""Workflow repository tool governance validation.

Owner: apps/api filesystem workflow repository.
Boundary: API persistence must surface shared workflow tool-governance warnings
without reading developer runtime assets.
Exit criteria: remove when repository validation is covered by a stable shared
contract suite.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import runsight_api.data.filesystem.workflow_repo as workflow_repo_module
from runsight_api.domain.errors import InputValidationError
from runsight_api.data.filesystem.workflow_repo import WorkflowRepository
from runsight_core.yaml.validation import ValidationResult

FIXTURE_ROOT = Path(__file__).resolve().parents[3] / "fixtures" / "workflow_repo_tool_governance"


def _workflow_fixture_text(name: str) -> str:
    return (FIXTURE_ROOT / name).read_text(encoding="utf-8")


def _write_soul_file(tmp_path, soul_name: str, tools: list[str] | None = None) -> None:
    souls_dir = tmp_path / "custom" / "souls"
    souls_dir.mkdir(parents=True, exist_ok=True)
    tool_lines = ""
    if tools:
        tool_lines = "\ntools:\n" + "\n".join(f"  - {tool}" for tool in tools)
    (souls_dir / f"{soul_name}.yaml").write_text(
        f"""\
id: {soul_name}
kind: soul
name: {soul_name.title()}
role: {soul_name.title()}
system_prompt: Search the web.{tool_lines}
""",
        encoding="utf-8",
    )


def test_create_stores_tool_governance_warning_on_entity(tmp_path):
    repo = WorkflowRepository(base_path=str(tmp_path))
    _write_soul_file(tmp_path, "researcher", ["http"])

    entity = repo.create(
        {
            "name": "Governance Warning",
            "yaml": _workflow_fixture_text("undeclared-library-soul-tool.yaml"),
        }
    )

    assert entity.valid is True
    assert entity.validation_error is None
    assert entity.warnings == [
        {
            "message": (
                "soul:researcher (custom/souls/researcher.yaml) references undeclared "
                "tool:http. Declared tools: []"
            ),
            "source": "tool_governance",
            "context": "researcher",
        }
    ]


def test_update_recomputes_tool_governance_warning_from_raw_yaml(tmp_path):
    repo = WorkflowRepository(base_path=str(tmp_path))
    created = repo.create(
        {
            "name": "Governance Success",
            "yaml": _workflow_fixture_text("valid-declared-tool.yaml"),
        }
    )
    _write_soul_file(tmp_path, "researcher", ["http"])
    updated_yaml = _workflow_fixture_text("undeclared-library-soul-tool.yaml").replace(
        "id: governance_failure",
        f"id: {created.id}",
    )

    updated = repo.update(created.id, {"yaml": updated_yaml})

    assert updated.valid is True
    assert updated.validation_error is None
    assert updated.warnings == [
        {
            "message": (
                "soul:researcher (custom/souls/researcher.yaml) references undeclared "
                "tool:http. Declared tools: []"
            ),
            "source": "tool_governance",
            "context": "researcher",
        }
    ]


def test_create_validates_canonical_builtin_tool_ids_against_repo_contract(tmp_path):
    repo = WorkflowRepository(base_path=str(tmp_path))
    _write_soul_file(tmp_path, "researcher", ["http"])

    entity = repo.create(
        {
            "name": "Governance Success",
            "yaml": _workflow_fixture_text("valid-declared-tool.yaml"),
        }
    )

    assert entity.valid is True
    assert entity.validation_error is None


def test_create_surfaces_missing_custom_tool_id_validation_error(tmp_path):
    repo = WorkflowRepository(base_path=str(tmp_path))
    _write_soul_file(tmp_path, "researcher", ["lookup_profile"])

    entity = repo.create(
        {
            "name": "Missing Custom Tool",
            "yaml": _workflow_fixture_text("missing-custom-tool.yaml"),
        }
    )

    assert entity.valid is True
    assert entity.validation_error is None


def test_create_rejects_legacy_typed_tool_authoring(tmp_path):
    repo = WorkflowRepository(base_path=str(tmp_path))

    with pytest.raises(InputValidationError, match="list"):
        repo.create(
            {
                "name": "Legacy Typed Tool",
                "yaml": _workflow_fixture_text("legacy-typed-tool.yaml"),
            }
        )


def test_create_rejects_reserved_builtin_id_collision_with_custom_slug(tmp_path):
    repo = WorkflowRepository(base_path=str(tmp_path))
    _write_soul_file(tmp_path, "researcher", ["http"])
    tools_dir = tmp_path / "custom" / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)
    (tools_dir / "http.yaml").write_text(
        """\
type: custom
source: http
code: |
  def main(args):
      return {"shadowed": true}
""",
        encoding="utf-8",
    )

    entity = repo.create(
        {
            "name": "Governance Success",
            "yaml": _workflow_fixture_text("valid-declared-tool.yaml"),
        }
    )

    assert entity.valid is False
    assert entity.validation_error is not None
    assert "http" in entity.validation_error


def test_validate_yaml_content_preserves_error_and_warning_payloads(tmp_path, monkeypatch):
    repo = WorkflowRepository(base_path=str(tmp_path))

    error_result = ValidationResult()
    error_result.add_warning(
        "Tool definition produced a warning alongside an error",
        source="tool_definitions",
        context="http",
    )
    error_result.add_error(
        "Tool definition validation exploded",
        source="tool_definitions",
        context="http",
    )
    warning_result = ValidationResult()
    warning_result.add_warning(
        "Tool definition is only a warning",
        source="tool_definitions",
        context="http",
    )

    monkeypatch.setattr(
        workflow_repo_module,
        "_validate_declared_tool_definitions",
        lambda *args, **kwargs: error_result,
    )

    valid, validation_error, warnings = repo._validate_yaml_content(
        "governance-error", _workflow_fixture_text("valid-declared-tool.yaml")
    )

    assert valid is False
    assert validation_error is not None
    assert "Tool definition validation exploded" in validation_error
    assert warnings == error_result.warnings_as_dicts()


def test_validate_yaml_content_returns_warning_payloads_for_warning_only_result(
    tmp_path, monkeypatch
):
    repo = WorkflowRepository(base_path=str(tmp_path))

    warning_result = ValidationResult()
    warning_result.add_warning(
        "Tool definition is only a warning",
        source="tool_definitions",
        context="lookup_profile",
    )

    monkeypatch.setattr(
        workflow_repo_module,
        "_validate_declared_tool_definitions",
        lambda *args, **kwargs: warning_result,
    )

    valid, validation_error, warnings = repo._validate_yaml_content(
        "governance-warning", _workflow_fixture_text("valid-declared-tool.yaml")
    )

    assert valid is True
    assert validation_error is None
    assert warnings == warning_result.warnings_as_dicts()


def test_validate_yaml_content_returns_empty_warning_list_for_schema_error(tmp_path):
    repo = WorkflowRepository(base_path=str(tmp_path))

    valid, validation_error, warnings = repo._validate_yaml_content(
        "governance-schema-error", _workflow_fixture_text("legacy-typed-tool.yaml")
    )

    assert valid is False
    assert validation_error is not None
    assert warnings == []


def test_build_entity_attaches_warnings_from_validation_result(tmp_path, monkeypatch):
    repo = WorkflowRepository(base_path=str(tmp_path))

    warning_payloads = [
        {
            "message": "Tool definition is only a warning",
            "source": "tool_definitions",
            "context": "lookup_profile",
        }
    ]

    monkeypatch.setattr(
        repo,
        "_validate_yaml_content",
        lambda *args, **kwargs: (True, None, warning_payloads),
    )

    entity = repo._build_entity(
        {
            "id": "governance_success",
            "kind": "workflow",
            "workflow": {"name": "Governance Success"},
        },
        "governance_success",
        raw_yaml=_workflow_fixture_text("valid-declared-tool.yaml"),
    )

    assert entity.warnings == warning_payloads
