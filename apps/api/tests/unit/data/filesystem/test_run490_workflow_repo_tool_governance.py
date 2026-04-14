from __future__ import annotations

import runsight_api.data.filesystem.workflow_repo as workflow_repo_module
from runsight_api.data.filesystem.workflow_repo import WorkflowRepository
from runsight_core.yaml.validation import ValidationResult

UNDECLARED_LIBRARY_SOUL_TOOL_YAML = """\
version: "1.0"
config:
  model_name: gpt-4o
blocks:
  my_block:
    type: linear
    soul_ref: researcher
workflow:
  name: Governance Warning
  entry: my_block
  transitions:
    - from: my_block
      to: null
"""

VALID_DECLARED_TOOL_YAML = """\
version: "1.0"
config:
  model_name: gpt-4o
tools:
  - http
blocks:
  my_block:
    type: linear
    soul_ref: researcher
workflow:
  name: Governance Success
  entry: my_block
  transitions:
    - from: my_block
      to: null
"""

MISSING_CUSTOM_TOOL_YAML = """\
version: "1.0"
config:
  model_name: gpt-4o
tools:
  - lookup_profile
blocks:
  my_block:
    type: linear
    soul_ref: researcher
workflow:
  name: Missing Custom Tool
  entry: my_block
  transitions:
    - from: my_block
      to: null
"""

LEGACY_TYPED_TOOL_YAML = """\
version: "1.0"
config:
  model_name: gpt-4o
tools:
  http:
    type: builtin
    source: runsight/http
souls:
  researcher:
    id: researcher_1
    role: Researcher
    system_prompt: Search the web.
    tools:
      - http
blocks:
  my_block:
    type: linear
    soul_ref: researcher
workflow:
  name: Legacy Typed Tool
  entry: my_block
  transitions:
    - from: my_block
      to: null
"""


def _write_soul_file(tmp_path, soul_name: str, tools: list[str] | None = None) -> None:
    souls_dir = tmp_path / "custom" / "souls"
    souls_dir.mkdir(parents=True, exist_ok=True)
    tool_lines = ""
    if tools:
        tool_lines = "\ntools:\n" + "\n".join(f"  - {tool}" for tool in tools)
    (souls_dir / f"{soul_name}.yaml").write_text(
        f"""\
id: {soul_name}_1
role: {soul_name.title()}
system_prompt: Search the web.{tool_lines}
""",
        encoding="utf-8",
    )


def test_create_stores_tool_governance_warning_on_entity(tmp_path):
    repo = WorkflowRepository(base_path=str(tmp_path))
    _write_soul_file(tmp_path, "researcher", ["http"])

    entity = repo.create({"name": "Governance Warning", "yaml": UNDECLARED_LIBRARY_SOUL_TOOL_YAML})

    assert entity.valid is True
    assert entity.validation_error is None
    assert entity.warnings == [
        {
            "message": (
                "Soul 'researcher' (custom/souls/researcher.yaml) references undeclared "
                "tool 'http'. Declared tools: []"
            ),
            "source": "tool_governance",
            "context": "researcher",
        }
    ]


def test_update_recomputes_tool_governance_warning_from_raw_yaml(tmp_path):
    repo = WorkflowRepository(base_path=str(tmp_path))
    created = repo.create({"name": "Governance Success", "yaml": VALID_DECLARED_TOOL_YAML})
    _write_soul_file(tmp_path, "researcher", ["http"])

    updated = repo.update(created.id, {"yaml": UNDECLARED_LIBRARY_SOUL_TOOL_YAML})

    assert updated.valid is True
    assert updated.validation_error is None
    assert updated.warnings == [
        {
            "message": (
                "Soul 'researcher' (custom/souls/researcher.yaml) references undeclared "
                "tool 'http'. Declared tools: []"
            ),
            "source": "tool_governance",
            "context": "researcher",
        }
    ]


def test_create_validates_canonical_builtin_tool_ids_against_repo_contract(tmp_path):
    repo = WorkflowRepository(base_path=str(tmp_path))
    _write_soul_file(tmp_path, "researcher", ["http"])

    entity = repo.create({"name": "Governance Success", "yaml": VALID_DECLARED_TOOL_YAML})

    assert entity.valid is True
    assert entity.validation_error is None


def test_create_surfaces_missing_custom_tool_id_validation_error(tmp_path):
    repo = WorkflowRepository(base_path=str(tmp_path))
    _write_soul_file(tmp_path, "researcher", ["lookup_profile"])

    entity = repo.create({"name": "Missing Custom Tool", "yaml": MISSING_CUSTOM_TOOL_YAML})

    assert entity.valid is True
    assert entity.validation_error is None


def test_create_rejects_legacy_typed_tool_authoring(tmp_path):
    repo = WorkflowRepository(base_path=str(tmp_path))

    entity = repo.create({"name": "Legacy Typed Tool", "yaml": LEGACY_TYPED_TOOL_YAML})

    assert entity.valid is False
    assert entity.validation_error is not None
    assert "list" in entity.validation_error


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

    entity = repo.create({"name": "Governance Success", "yaml": VALID_DECLARED_TOOL_YAML})

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
        "governance-error", VALID_DECLARED_TOOL_YAML
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
        "governance-warning", VALID_DECLARED_TOOL_YAML
    )

    assert valid is True
    assert validation_error is None
    assert warnings == warning_result.warnings_as_dicts()


def test_validate_yaml_content_returns_empty_warning_list_for_schema_error(tmp_path):
    repo = WorkflowRepository(base_path=str(tmp_path))

    valid, validation_error, warnings = repo._validate_yaml_content(
        "governance-schema-error", LEGACY_TYPED_TOOL_YAML
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
        {"workflow": {"name": "Governance Success"}},
        "governance-warning",
        raw_yaml=VALID_DECLARED_TOOL_YAML,
    )

    assert entity.warnings == warning_payloads
