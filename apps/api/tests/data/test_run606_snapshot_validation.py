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


def test_update_rejects_child_chain_that_exceeds_inherited_workflow_max_depth(tmp_path) -> None:
    repo = WorkflowRepository(base_path=str(tmp_path))

    child_yaml = """
    version: "1.0"
    interface:
      inputs: []
      outputs: []
    workflow:
      name: child
      entry: finish
      transitions: []
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
    config:
      max_workflow_depth: 1
    """
    _write_workflow(repo, workflow_id="parent", yaml_text=parent_yaml)

    entity = repo.update("parent", {"yaml": dedent(parent_yaml).strip() + "\n"})

    assert entity.valid is False
    assert entity.validation_error is not None
    assert "call_child" in entity.validation_error
    assert "depth" in entity.validation_error.lower()


def test_update_rejects_nested_child_block_max_depth_already_exceeded_at_call_site(
    tmp_path,
) -> None:
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
        max_depth: 1
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
    assert "call_grandchild" in entity.validation_error
    assert "depth" in entity.validation_error.lower()


def test_update_rejects_grandchild_when_propagated_call_depth_reaches_block_limit(tmp_path) -> None:
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
        max_depth: 3
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
    assert "call_grandchild" in entity.validation_error
    assert "depth" in entity.validation_error.lower()


# ---------------------------------------------------------------------------
# Item 1 / 3a: Name-alias resolution — workflow.name vs filename
# ---------------------------------------------------------------------------


def test_update_resolves_child_workflow_by_declared_name_alias(tmp_path) -> None:
    """RUN-606 alias regression: build_runnable_workflow_registry() must resolve
    a child ref by its workflow.name even when the filename is different.

    Scenario:
      - Parent has ``workflow_ref: child-by-name``
      - Child file is ``custom/workflows/actual-child-file.yaml``
        with ``workflow: { name: child-by-name }`` and an interface declared
      - Resolution must succeed because workflow.name == workflow_ref

    This currently FAILS because _read_workflow_from_source() only tries
    path-like candidate guesses (e.g. ``child-by-name.yaml``) and never
    consults the workflow.name alias index.
    """
    repo = WorkflowRepository(base_path=str(tmp_path))

    child_yaml = """
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
      name: child-by-name
      entry: finish
      transitions: []
    """
    # Write child with a filename that does NOT match the workflow.name
    _write_workflow(repo, workflow_id="actual-child-file", yaml_text=child_yaml)

    parent_yaml = """
    version: "1.0"
    interface:
      inputs: []
      outputs: []
    blocks:
      call_child:
        type: workflow
        workflow_ref: child-by-name
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
    _write_workflow(repo, workflow_id="parent", yaml_text=parent_yaml)

    entity = repo.update("parent", {"yaml": dedent(parent_yaml).strip() + "\n"})

    # With correct alias resolution this should be valid
    assert entity.valid is True, (
        f"Expected valid=True (alias resolution should find child-by-name), "
        f"got validation_error: {entity.validation_error}"
    )
    assert entity.validation_error is None


def test_create_resolves_child_workflow_by_declared_name_alias(tmp_path) -> None:
    """RUN-606 alias regression through repo.create() path: same as above
    but exercising the create() entry point to confirm name-based alias
    resolution also works on first save.
    """
    repo = WorkflowRepository(base_path=str(tmp_path))

    child_yaml = """
    version: "1.0"
    interface:
      inputs: []
      outputs:
        - name: summary
          source: results.writer
    workflow:
      name: child-by-name
      entry: finish
      transitions: []
    """
    _write_workflow(repo, workflow_id="actual-child-file", yaml_text=child_yaml)

    parent_yaml = """
    version: "1.0"
    interface:
      inputs: []
      outputs: []
    blocks:
      call_child:
        type: workflow
        workflow_ref: child-by-name
    workflow:
      name: parent
      entry: call_child
      transitions:
        - from: call_child
          to: null
    """

    entity = repo.create({"name": "Parent", "yaml": dedent(parent_yaml).strip() + "\n"})

    assert entity.valid is True, (
        f"Expected valid=True (name alias resolution), "
        f"got validation_error: {entity.validation_error}"
    )
    assert entity.validation_error is None


# ---------------------------------------------------------------------------
# Item 2: max_depth semantic fix — parse-time validation
#
# The validate_workflow_call_contracts() traversal uses a single
# current_call_stack_depth counter that starts at 1 and increments by +2
# per recursion level.  The correct semantic is:
#   max_depth: N  =>  allow N nesting levels below the declaring block
#   max_depth: 1  =>  child only (parent->child)
#   max_depth: 2  =>  grandchild allowed (parent->child->grandchild)
#   max_depth: 3  =>  great-grandchild allowed
#
# To expose the +2 bug reliably, the child workflow must also set
# config.max_workflow_depth (or block-level max_depth) so that the
# propagated depth counter is actually checked at the deeper level.
# ---------------------------------------------------------------------------


def test_max_depth_3_allows_grandchild_with_propagated_config(tmp_path) -> None:
    """RUN-606 depth semantic: when BOTH the parent block AND the child
    workflow set max_depth=3, the grandchild (2 nesting levels) must be
    ALLOWED.

    Current behaviour (bug): starts at depth=1, recurses with +2, so the
    child level sees depth=3 and ``3 >= 3`` rejects the grandchild.
    Correct behaviour: depth increments by 1, so child level sees depth=2
    and ``2 < 3`` passes.
    """
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
    config:
      max_workflow_depth: 3
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
        max_depth: 3
    workflow:
      name: parent
      entry: call_child
      transitions:
        - from: call_child
          to: null
    """
    _write_workflow(repo, workflow_id="parent", yaml_text=parent_yaml)

    entity = repo.update("parent", {"yaml": dedent(parent_yaml).strip() + "\n"})

    assert entity.valid is True, (
        f"max_depth=3 should allow parent->child->grandchild (2 nesting levels), "
        f"got validation_error: {entity.validation_error}"
    )
    assert entity.validation_error is None


def test_max_depth_1_rejects_grandchild_with_propagated_config(tmp_path) -> None:
    """max_depth=1 means only the immediate child is allowed; a grandchild
    (child calling another workflow) must be rejected.

    Both the parent block and the child config set max_depth=1 so the
    constraint is enforced at both levels.
    """
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
    config:
      max_workflow_depth: 1
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


def test_max_depth_2_rejects_great_grandchild_with_propagated_config(tmp_path) -> None:
    """max_depth=2 allows child + grandchild but a great-grandchild (3rd
    nesting level) must be rejected.  Config propagated to all levels.
    """
    repo = WorkflowRepository(base_path=str(tmp_path))

    great_grandchild_yaml = """
    version: "1.0"
    interface:
      inputs: []
      outputs: []
    workflow:
      name: great-grandchild
      entry: finish
      transitions: []
    """
    _write_workflow(repo, workflow_id="great-grandchild", yaml_text=great_grandchild_yaml)

    grandchild_yaml = """
    version: "1.0"
    interface:
      inputs: []
      outputs: []
    blocks:
      call_ggc:
        type: workflow
        workflow_ref: custom/workflows/great-grandchild.yaml
    workflow:
      name: grandchild
      entry: call_ggc
      transitions:
        - from: call_ggc
          to: null
    config:
      max_workflow_depth: 2
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
    config:
      max_workflow_depth: 2
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
        max_depth: 2
    workflow:
      name: parent
      entry: call_child
      transitions:
        - from: call_child
          to: null
    """
    _write_workflow(repo, workflow_id="parent", yaml_text=parent_yaml)

    entity = repo.update("parent", {"yaml": dedent(parent_yaml).strip() + "\n"})

    # great-grandchild is nesting level 3, max_depth=2 should reject it
    assert entity.valid is False
    assert entity.validation_error is not None
    assert "depth" in entity.validation_error.lower()


def test_max_depth_2_allows_grandchild_with_propagated_config(tmp_path) -> None:
    """max_depth=2 should ALLOW parent->child->grandchild (2 nesting levels).
    Config propagated to child level so the depth counter is actually checked.
    """
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
    config:
      max_workflow_depth: 2
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
        max_depth: 2
    workflow:
      name: parent
      entry: call_child
      transitions:
        - from: call_child
          to: null
    """
    _write_workflow(repo, workflow_id="parent", yaml_text=parent_yaml)

    entity = repo.update("parent", {"yaml": dedent(parent_yaml).strip() + "\n"})

    assert entity.valid is True, (
        f"max_depth=2 should allow parent->child->grandchild (2 nesting levels), "
        f"got validation_error: {entity.validation_error}"
    )
