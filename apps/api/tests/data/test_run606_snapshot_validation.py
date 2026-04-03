from __future__ import annotations

from textwrap import dedent

from runsight_api.data.filesystem.workflow_repo import WorkflowRepository


def _write_workflow(repo: WorkflowRepository, *, workflow_id: str, yaml_text: str) -> None:
    repo.workflows_dir.mkdir(parents=True, exist_ok=True)
    (repo.workflows_dir / f"{workflow_id}.yaml").write_text(
        dedent(yaml_text).strip() + "\n",
        encoding="utf-8",
    )


def test_update_rejects_circular_child_reference_chain(tmp_path) -> None:
    repo = WorkflowRepository(base_path=str(tmp_path))

    child_yaml = """
    version: "1.0"
    interface:
      inputs: []
      outputs: []
    blocks:
      call_parent:
        type: workflow
        workflow_ref: custom/workflows/parent.yaml
    workflow:
      name: child
      entry: call_parent
      transitions:
        - from: call_parent
          to: null
    """
    _write_workflow(repo, workflow_id="child", yaml_text=child_yaml)

    parent_yaml = """
    version: "1.0"
    interface:
      inputs: []
      outputs: []
    blocks:
      call_child:
        type: workflow
        workflow_ref: custom/workflows/child.yaml
    workflow:
      name: parent
      entry: call_child
      transitions:
        - from: call_child
          to: null
    """
    _write_workflow(repo, workflow_id="parent", yaml_text=parent_yaml)

    entity = repo.update("parent", {"yaml": dedent(parent_yaml).strip() + "\n"})

    assert entity.valid is False
    assert entity.validation_error is not None
    assert (
        "circular" in entity.validation_error.lower() or "cycle" in entity.validation_error.lower()
    )


def test_update_rejects_nested_child_chain_that_exceeds_max_depth(tmp_path) -> None:
    repo = WorkflowRepository(base_path=str(tmp_path))

    grandchild_yaml = """
    version: "1.0"
    interface:
      inputs: []
      outputs: []
    workflow:
      name: grandchild
      entry: finish
      transitions: []
    """
    _write_workflow(repo, workflow_id="grandchild", yaml_text=grandchild_yaml)

    child_yaml = """
    version: "1.0"
    interface:
      inputs: []
      outputs: []
    blocks:
      call_grandchild:
        type: workflow
        workflow_ref: custom/workflows/grandchild.yaml
    workflow:
      name: child
      entry: call_grandchild
      transitions:
        - from: call_grandchild
          to: null
    """
    _write_workflow(repo, workflow_id="child", yaml_text=child_yaml)

    parent_yaml = """
    version: "1.0"
    interface:
      inputs: []
      outputs: []
    blocks:
      call_child:
        type: workflow
        workflow_ref: custom/workflows/child.yaml
        max_depth: 1
    workflow:
      name: parent
      entry: call_child
      transitions:
        - from: call_child
          to: null
    """
    _write_workflow(repo, workflow_id="parent", yaml_text=parent_yaml)

    entity = repo.update("parent", {"yaml": dedent(parent_yaml).strip() + "\n"})

    assert entity.valid is False
    assert entity.validation_error is not None
    assert "depth" in entity.validation_error.lower()
