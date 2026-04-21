"""Red tests for RUN-954 workflow repository collaborator boundaries.

These tests lock the ownership seams called out in the ticket:

- create/update/patch remain persistence operations instead of invoking
  repository-owned validation helpers
- runnable workflow registry construction is not coupled to repository
  persistence paths
- YAML-only updates do not consult repository-owned canvas sidecar readers
- execution preparation does not reach through workflow_repo for registry
  construction

All tests in this file should fail on the pre-extraction implementation.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from textwrap import dedent
from unittest.mock import Mock

import pytest

from runsight_api.data.filesystem.workflow_repo import WorkflowRepository
from runsight_api.logic.services.execution_preparation import ExecutionPreparationService


def _workflow_yaml(
    *,
    workflow_id: str,
    workflow_name: str,
    child_ref: str | None = None,
) -> str:
    if child_ref is None:
        return (
            dedent(
                f"""\
                version: "1.0"
                id: {workflow_id}
                kind: workflow
                interface:
                  inputs: []
                  outputs: []
                blocks: {{}}
                workflow:
                  name: {workflow_name}
                  entry: finish
                  transitions:
                    - from: finish
                      to: null
                """
            ).strip()
            + "\n"
        )

    return (
        dedent(
            f"""\
            version: "1.0"
            id: {workflow_id}
            kind: workflow
            interface:
              inputs: []
              outputs: []
            blocks:
              call_child:
                type: workflow
                workflow_ref: {child_ref}
            workflow:
              name: {workflow_name}
              entry: call_child
              transitions:
                - from: call_child
                  to: null
            """
        ).strip()
        + "\n"
    )


def _write_child_workflow(tmp_path: Path, *, workflow_id: str = "child") -> None:
    child_path = tmp_path / "custom" / "workflows" / f"{workflow_id}.yaml"
    child_path.parent.mkdir(parents=True, exist_ok=True)
    child_path.write_text(
        _workflow_yaml(workflow_id=workflow_id, workflow_name="Child Workflow"),
        encoding="utf-8",
    )


@pytest.mark.parametrize("operation", ["create", "update", "patch"])
def test_persistence_methods_do_not_invoke_repo_validation_helper(
    tmp_path: Path, operation: str
) -> None:
    repo = WorkflowRepository(base_path=str(tmp_path))

    if operation != "create":
        repo.create({"yaml": _workflow_yaml(workflow_id="parent", workflow_name="Parent")})

    validate_yaml = Mock(return_value=(True, None, []))
    repo._validate_yaml_content = validate_yaml  # type: ignore[attr-defined]

    if operation == "create":
        created = repo.create(
            {"yaml": _workflow_yaml(workflow_id="parent", workflow_name="Parent")}
        )
        assert created.id == "parent"
    elif operation == "update":
        updated = repo.update(
            "parent",
            {"yaml": _workflow_yaml(workflow_id="parent", workflow_name="Parent Updated")},
        )
        assert updated.name == "Parent Updated"
    else:
        patched = repo.patch_yaml_field("parent", "enabled", True)
        assert patched.id == "parent"

    validate_yaml.assert_not_called()


@pytest.mark.parametrize("operation", ["create", "update", "patch"])
def test_persistence_methods_do_not_build_runnable_registry(tmp_path: Path, operation: str) -> None:
    repo = WorkflowRepository(base_path=str(tmp_path))
    _write_child_workflow(tmp_path)

    if operation == "update":
        repo.create({"yaml": _workflow_yaml(workflow_id="parent", workflow_name="Parent")})
    elif operation == "patch":
        repo.create(
            {
                "yaml": _workflow_yaml(
                    workflow_id="parent",
                    workflow_name="Parent",
                    child_ref="child",
                )
            }
        )

    build_registry = Mock(return_value=Mock())
    repo.build_runnable_workflow_registry = build_registry  # type: ignore[method-assign]

    if operation == "create":
        created = repo.create(
            {
                "yaml": _workflow_yaml(
                    workflow_id="parent",
                    workflow_name="Parent",
                    child_ref="child",
                )
            }
        )
        assert created.id == "parent"
    elif operation == "update":
        updated = repo.update(
            "parent",
            {
                "yaml": _workflow_yaml(
                    workflow_id="parent",
                    workflow_name="Parent With Child",
                    child_ref="child",
                )
            },
        )
        assert updated.name == "Parent With Child"
    else:
        patched = repo.patch_yaml_field("parent", "enabled", True)
        assert patched.id == "parent"

    build_registry.assert_not_called()


@pytest.mark.parametrize("operation", ["update", "patch"])
def test_yaml_only_persistence_does_not_read_repo_canvas_sidecar(
    tmp_path: Path, operation: str
) -> None:
    repo = WorkflowRepository(base_path=str(tmp_path))
    repo.create({"yaml": _workflow_yaml(workflow_id="parent", workflow_name="Parent")})

    read_canvas_sidecar = Mock(return_value={"nodes": [], "edges": []})
    repo._read_canvas_sidecar = read_canvas_sidecar  # type: ignore[attr-defined]

    if operation == "update":
        updated = repo.update(
            "parent",
            {"yaml": _workflow_yaml(workflow_id="parent", workflow_name="Parent Updated")},
        )
        assert updated.name == "Parent Updated"
    else:
        patched = repo.patch_yaml_field("parent", "enabled", True)
        assert patched.id == "parent"

    read_canvas_sidecar.assert_not_called()


def test_execution_preparation_does_not_reach_through_workflow_repo_for_registry_building() -> None:
    source = inspect.getsource(ExecutionPreparationService.prepare_for_launch)

    assert ".workflow_repo.build_runnable_workflow_registry(" not in source
