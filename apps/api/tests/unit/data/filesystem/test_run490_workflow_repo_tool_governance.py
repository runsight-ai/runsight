import pytest
from runsight_api.data.filesystem.workflow_repo import WorkflowRepository

INVALID_DIRECT_SOUL_TOOL_YAML = """\
version: "1.0"
config:
  model_name: gpt-4o
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
  name: Governance Failure
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


@pytest.mark.xfail(
    reason="RUN-570 removed inline souls; RUN-571 will wire library discovery", strict=True
)
def test_create_stores_tool_governance_validation_error_on_entity(tmp_path):
    repo = WorkflowRepository(base_path=str(tmp_path))

    entity = repo.create({"name": "Governance Failure", "yaml": INVALID_DIRECT_SOUL_TOOL_YAML})

    assert entity.valid is False
    assert entity.validation_error is not None
    assert "undeclared tool 'http'" in entity.validation_error


@pytest.mark.xfail(
    reason="RUN-570 removed inline souls; RUN-571 will wire library discovery", strict=True
)
def test_update_recomputes_tool_governance_validation_error_from_raw_yaml(tmp_path):
    repo = WorkflowRepository(base_path=str(tmp_path))
    created = repo.create({"name": "Governance Success", "yaml": VALID_DECLARED_TOOL_YAML})

    updated = repo.update(created.id, {"yaml": INVALID_DIRECT_SOUL_TOOL_YAML})

    assert updated.valid is False
    assert updated.validation_error is not None
    assert "undeclared tool 'http'" in updated.validation_error


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

    assert entity.valid is False
    assert entity.validation_error is not None
    assert "custom/tools/lookup_profile.yaml" in entity.validation_error


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
