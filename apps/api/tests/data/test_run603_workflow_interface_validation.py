from __future__ import annotations

from textwrap import dedent
from runsight_api.data.filesystem.workflow_repo import WorkflowRepository


def _write_child_workflow(base_path, *, filename: str, yaml_text: str) -> str:
    workflows_dir = base_path / "custom" / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)
    child_path = workflows_dir / filename
    child_path.write_text(dedent(yaml_text).strip() + "\n", encoding="utf-8")
    return f"custom/workflows/{filename}"


def test_create_rejects_legacy_workflow_interface_through_api_save(tmp_path) -> None:
    repo = WorkflowRepository(base_path=str(tmp_path))

    parent_yaml = """
    version: "1.0"
    id: parent
    kind: workflow
    interface:
      inputs: []
      outputs: []
    workflow:
      name: parent
      entry: start
      transitions: []
    """

    entity = repo.create({"name": "Parent", "yaml": dedent(parent_yaml).strip() + "\n"})

    assert entity.valid is False
    assert entity.validation_error is not None
    assert "legacy workflow interface is unsupported" in entity.validation_error.lower()


def test_create_rejects_public_output_name_without_child_source_path(tmp_path) -> None:
    _write_child_workflow(
        tmp_path,
        filename="child-contract.yaml",
        yaml_text="""
        version: "1.0"
        id: child-contract
        kind: workflow
        blocks: {}
        workflow:
          name: child-contract
          entry: start
          transitions: []
        """,
    )
    child_ref = "child-contract"
    repo = WorkflowRepository(base_path=str(tmp_path))

    parent_yaml = f"""
    version: "1.0"
    id: parent
    kind: workflow
    blocks:
      call_child:
        type: workflow
        workflow_ref: {child_ref}
        inputs:
          topic: shared_memory.topic
        outputs:
          results.summary: summary
    workflow:
      name: parent
      entry: call_child
      transitions:
        - from: call_child
          to: null
    """

    entity = repo.create({"name": "Parent", "yaml": dedent(parent_yaml).strip() + "\n"})

    assert entity.valid is False
    assert entity.validation_error is not None
    assert "child source path" in entity.validation_error.lower()


def test_create_rejects_unknown_required_interface_input_binding(tmp_path) -> None:
    _write_child_workflow(
        tmp_path,
        filename="child-contract.yaml",
        yaml_text="""
        version: "1.0"
        id: child-contract
        kind: workflow
        inputs:
          topic:
            type: string
        workflow:
          name: child-contract
          entry: start
          transitions: []
        """,
    )
    child_ref = "child-contract"
    repo = WorkflowRepository(base_path=str(tmp_path))

    parent_yaml = f"""
    version: "1.0"
    id: parent
    kind: workflow
    blocks:
      call_child:
        type: workflow
        workflow_ref: {child_ref}
        inputs:
          question: shared_memory.topic
        outputs:
          results.summary: results.writer
    workflow:
      name: parent
      entry: call_child
      transitions:
        - from: call_child
          to: null
    """

    entity = repo.create({"name": "Parent", "yaml": dedent(parent_yaml).strip() + "\n"})

    assert entity.valid is False
    assert entity.validation_error is not None
    assert "question" in entity.validation_error


def test_create_rejects_undeclared_child_output_binding(tmp_path) -> None:
    _write_child_workflow(
        tmp_path,
        filename="child-contract.yaml",
        yaml_text="""
        version: "1.0"
        id: child-contract
        kind: workflow
        workflow:
          name: child-contract
          entry: start
          transitions: []
        """,
    )
    child_ref = "child-contract"
    repo = WorkflowRepository(base_path=str(tmp_path))

    parent_yaml = f"""
    version: "1.0"
    id: parent
    kind: workflow
    blocks:
      call_child:
        type: workflow
        workflow_ref: {child_ref}
        inputs:
          topic: shared_memory.topic
        outputs:
          results.summary: detail
    workflow:
      name: parent
      entry: call_child
      transitions:
        - from: call_child
          to: null
    """

    entity = repo.create({"name": "Parent", "yaml": dedent(parent_yaml).strip() + "\n"})

    assert entity.valid is False
    assert entity.validation_error is not None
    assert "detail" in entity.validation_error


# ---------------------------------------------------------------------------
# Item 3c: Raw dotted-path bindings rejected through full API save path
# ---------------------------------------------------------------------------


def test_create_rejects_raw_dotted_path_input_key_through_api_save(tmp_path) -> None:
    """RUN-606 dotted-path rejection: using a raw child dotted path like
    ``shared_memory.topic`` as an input KEY (instead of a named interface
    binding like ``topic``) must be rejected when saving through the full
    repo.create() / _validate_yaml_content() path.

    This is already tested at the TypeAdapter / schema level in
    test_run603_workflow_interface_schema.py, but that only validates the
    Pydantic model in isolation.  This test confirms the rejection also
    fires through the complete API save flow (create → _validate_yaml_content).
    """
    _write_child_workflow(
        tmp_path,
        filename="child-contract.yaml",
        yaml_text="""
        version: "1.0"
        id: child-contract
        kind: workflow
        workflow:
          name: child-contract
          entry: start
          transitions: []
    """,
    )
    child_ref = "child-contract"
    repo = WorkflowRepository(base_path=str(tmp_path))

    parent_yaml = f"""
    version: "1.0"
    id: parent
    kind: workflow
    blocks:
      call_child:
        type: workflow
        workflow_ref: {child_ref}
        inputs:
          shared_memory.topic: shared_memory.parent_topic
        outputs:
          results.summary: results.writer
    workflow:
      name: parent
      entry: call_child
      transitions:
        - from: call_child
          to: null
    """

    entity = repo.create({"name": "Parent", "yaml": dedent(parent_yaml).strip() + "\n"})

    assert entity.valid is False, (
        "Raw dotted-path input key 'shared_memory.topic' should be rejected "
        "through the full API save path"
    )
    assert entity.validation_error is not None
    assert (
        "workflow block inputs must bind child interface names" in entity.validation_error.lower()
        or "dotted" in entity.validation_error.lower()
    )
