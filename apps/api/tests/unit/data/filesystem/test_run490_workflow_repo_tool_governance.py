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
      - runsight/http
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
  http_tool:
    type: builtin
    source: runsight/http
souls:
  researcher:
    id: researcher_1
    role: Researcher
    system_prompt: Search the web.
    tools:
      - http_tool
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


@pytest.mark.xfail(
    reason="RUN-570 removed inline souls; RUN-571 will wire library discovery", strict=True
)
def test_create_stores_tool_governance_validation_error_on_entity(tmp_path):
    repo = WorkflowRepository(base_path=str(tmp_path))

    entity = repo.create({"name": "Governance Failure", "yaml": INVALID_DIRECT_SOUL_TOOL_YAML})

    assert entity.valid is False
    assert entity.validation_error is not None
    assert "undeclared tool 'runsight/http'" in entity.validation_error


@pytest.mark.xfail(
    reason="RUN-570 removed inline souls; RUN-571 will wire library discovery", strict=True
)
def test_update_recomputes_tool_governance_validation_error_from_raw_yaml(tmp_path):
    repo = WorkflowRepository(base_path=str(tmp_path))
    created = repo.create({"name": "Governance Success", "yaml": VALID_DECLARED_TOOL_YAML})

    updated = repo.update(created.id, {"yaml": INVALID_DIRECT_SOUL_TOOL_YAML})

    assert updated.valid is False
    assert updated.validation_error is not None
    assert "undeclared tool 'runsight/http'" in updated.validation_error
