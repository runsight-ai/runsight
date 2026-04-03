from __future__ import annotations

from textwrap import dedent

from runsight_api.data.filesystem.workflow_repo import WorkflowRepository


def _write_child_workflow(base_path, *, filename: str, yaml_text: str) -> str:
    workflows_dir = base_path / "custom" / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)
    child_path = workflows_dir / filename
    child_path.write_text(dedent(yaml_text).strip() + "\n", encoding="utf-8")
    return f"custom/workflows/{filename}"


def test_create_rejects_callable_subworkflow_without_public_interface(tmp_path) -> None:
    child_ref = _write_child_workflow(
        tmp_path,
        filename="child-no-interface.yaml",
        yaml_text="""
        version: "1.0"
        workflow:
          name: child-no-interface
          entry: start
          transitions: []
        """,
    )
    repo = WorkflowRepository(base_path=str(tmp_path))

    parent_yaml = f"""
    version: "1.0"
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
    assert "interface" in entity.validation_error.lower()


def test_create_rejects_unknown_required_interface_input_binding(tmp_path) -> None:
    child_ref = _write_child_workflow(
        tmp_path,
        filename="child-contract.yaml",
        yaml_text="""
        version: "1.0"
        interface:
          inputs:
            - name: topic
              target: shared_memory.topic
              required: true
          outputs:
            - name: summary
              source: results.writer
        workflow:
          name: child-contract
          entry: start
          transitions: []
        """,
    )
    repo = WorkflowRepository(base_path=str(tmp_path))

    parent_yaml = f"""
    version: "1.0"
    blocks:
      call_child:
        type: workflow
        workflow_ref: {child_ref}
        inputs:
          question: shared_memory.topic
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
    assert "question" in entity.validation_error


def test_create_rejects_undeclared_child_output_binding(tmp_path) -> None:
    child_ref = _write_child_workflow(
        tmp_path,
        filename="child-contract.yaml",
        yaml_text="""
        version: "1.0"
        interface:
          inputs:
            - name: topic
              target: shared_memory.topic
              required: true
          outputs:
            - name: summary
              source: results.writer
        workflow:
          name: child-contract
          entry: start
          transitions: []
        """,
    )
    repo = WorkflowRepository(base_path=str(tmp_path))

    parent_yaml = f"""
    version: "1.0"
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
