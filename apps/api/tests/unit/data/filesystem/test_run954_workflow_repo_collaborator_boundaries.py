"""Red tests for RUN-954 workflow repository collaborator boundaries.

This suite stays on observable behavior and explicit seam contracts:

- create, update, and patch preserve the current validation-result shape for
  missing nested workflow refs
- update and patch keep round-trip YAML editing and embedded-id semantics
- warning-only canvas sidecar failures remain explicit after YAML success
- execution preparation can consume a reusable registry-builder collaborator

The collaborator-seam assertions should fail on the pre-extraction
implementation.
"""

from __future__ import annotations

import logging
from pathlib import Path
from textwrap import dedent
from unittest.mock import Mock, sentinel

import pytest
import yaml

from runsight_api.data.filesystem.workflow_repo import WorkflowRepository
from runsight_api.domain.errors import InputValidationError
from runsight_api.logic.services.execution_preparation import ExecutionPreparationService


def _workflow_yaml(
    *,
    workflow_id: str,
    workflow_name: str,
    child_ref: str | None = None,
) -> str:
    blocks: dict[str, object] = {}
    entry = "finish"
    transitions: list[dict[str, str | None]] = [{"from": "finish", "to": None}]

    if child_ref is not None:
        blocks = {"call_child": {"type": "workflow", "workflow_ref": child_ref}}
        entry = "call_child"
        transitions = [{"from": "call_child", "to": None}]

    return yaml.safe_dump(
        {
            "version": "1.0",
            "id": workflow_id,
            "kind": "workflow",
            "interface": {"inputs": [], "outputs": []},
            "blocks": blocks,
            "workflow": {
                "name": workflow_name,
                "entry": entry,
                "transitions": transitions,
            },
        },
        sort_keys=False,
    )


def _commented_workflow_yaml(*, workflow_id: str = "parent", workflow_name: str = "Parent") -> str:
    return (
        dedent(
            f"""\
            # top-level comment
            version: "1.0"
            id: {workflow_id}
            kind: workflow
            workflow:
              name: {workflow_name}  # inline comment
              entry: finish
              transitions: []
            # blocks comment
            blocks: {{}}
            """
        ).strip()
        + "\n"
    )


def _missing_child_blocks() -> dict[str, dict[str, str]]:
    return {"call_child": {"type": "workflow", "workflow_ref": "missing-child"}}


@pytest.mark.parametrize("operation", ["create", "update", "patch"])
def test_missing_child_registry_validation_surfaces_invalid_entity_shape(
    tmp_path: Path, operation: str
) -> None:
    repo = WorkflowRepository(base_path=str(tmp_path))

    if operation != "create":
        repo.create({"yaml": _workflow_yaml(workflow_id="parent", workflow_name="Parent")})

    if operation == "create":
        entity = repo.create(
            {
                "yaml": _workflow_yaml(
                    workflow_id="parent",
                    workflow_name="Parent",
                    child_ref="missing-child",
                )
            }
        )
    elif operation == "update":
        entity = repo.update(
            "parent",
            {
                "yaml": _workflow_yaml(
                    workflow_id="parent",
                    workflow_name="Parent",
                    child_ref="missing-child",
                )
            },
        )
    else:
        entity = repo.patch_yaml_field("parent", "blocks", _missing_child_blocks())

    assert entity.id == "parent"
    assert entity.valid is False
    assert entity.validation_error is not None
    assert "cannot resolve ref 'missing-child'" in entity.validation_error
    assert entity.warnings == []
    assert "id: parent" in repo._get_path("parent").read_text(encoding="utf-8")


@pytest.mark.parametrize("operation", ["create", "update", "patch"])
def test_embedded_id_validation_failures_are_shaped_as_input_validation_errors(
    tmp_path: Path, operation: str
) -> None:
    repo = WorkflowRepository(base_path=str(tmp_path))
    original_yaml = _workflow_yaml(workflow_id="parent", workflow_name="Parent")

    if operation != "create":
        repo.create({"yaml": original_yaml})

    with pytest.raises(InputValidationError):
        if operation == "create":
            repo.create({"yaml": _workflow_yaml(workflow_id="BadId", workflow_name="Parent")})
        elif operation == "update":
            repo.update(
                "parent",
                {"yaml": _workflow_yaml(workflow_id="changed-id", workflow_name="Parent")},
            )
        else:
            repo.patch_yaml_field("parent", "id", "changed-id")

    workflow_path = repo._get_path("parent")
    if operation == "create":
        assert not workflow_path.exists()
    else:
        assert workflow_path.read_text(encoding="utf-8") == original_yaml


def test_update_round_trips_comments_and_embedded_id_when_renaming(tmp_path: Path) -> None:
    repo = WorkflowRepository(base_path=str(tmp_path))
    raw_yaml = _commented_workflow_yaml()
    repo.create({"yaml": raw_yaml})

    updated = repo.update("parent", {"name": "Renamed Parent", "yaml": raw_yaml})
    saved_yaml = repo._get_path("parent").read_text(encoding="utf-8")

    assert updated.id == "parent"
    assert updated.name == "Renamed Parent"
    assert "# top-level comment" in saved_yaml
    assert "# inline comment" in saved_yaml
    assert "# blocks comment" in saved_yaml
    assert "id: parent" in saved_yaml
    assert "name: Renamed Parent" in saved_yaml


def test_patch_round_trips_comments_and_embedded_id(tmp_path: Path) -> None:
    repo = WorkflowRepository(base_path=str(tmp_path))
    raw_yaml = _commented_workflow_yaml()
    repo.create({"yaml": raw_yaml})

    patched = repo.patch_yaml_field("parent", "enabled", True)
    saved_yaml = repo._get_path("parent").read_text(encoding="utf-8")

    assert patched.id == "parent"
    assert "# top-level comment" in saved_yaml
    assert "# inline comment" in saved_yaml
    assert "# blocks comment" in saved_yaml
    assert "id: parent" in saved_yaml
    assert "enabled: true" in saved_yaml.lower()


def test_update_exposes_canvas_sidecar_write_failure_as_warning_after_yaml_success(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    repo = WorkflowRepository(base_path=str(tmp_path))
    repo.create({"yaml": _workflow_yaml(workflow_id="parent", workflow_name="Parent")})
    repo.canvas_dir.rmdir()
    repo.canvas_dir.write_text("not-a-directory", encoding="utf-8")

    updated_yaml = _workflow_yaml(workflow_id="parent", workflow_name="Parent Updated")
    with caplog.at_level(logging.WARNING):
        updated = repo.update(
            "parent",
            {
                "yaml": updated_yaml,
                "canvas_state": {"nodes": [], "edges": []},
            },
        )

    assert repo._get_path("parent").read_text(encoding="utf-8") == updated_yaml
    assert updated.validation_error is None
    assert getattr(updated, "canvas_state", None) is None
    assert any("Failed to write canvas sidecar" in record.message for record in caplog.records)
    assert any(
        warning.get("source") == "canvas_sidecar"
        and warning.get("context") == "parent"
        and "write" in warning.get("message", "").lower()
        for warning in updated.warnings
    )


def test_prepare_for_launch_uses_injected_registry_builder_for_nested_git_snapshot() -> None:
    parent_yaml = _workflow_yaml(
        workflow_id="parent",
        workflow_name="Parent",
        child_ref="child",
    )
    workflow_repo = Mock()
    workflow_repo.get_by_id.return_value = None
    workflow_repo._get_path.return_value = Path("/tmp/custom/workflows/parent.yaml")
    provider_repo = Mock()
    provider_repo.list_all.return_value = []
    git_service = Mock()
    git_service.read_file.return_value = parent_yaml
    git_service.get_sha.return_value = "a" * 40
    registry_builder = Mock(return_value=sentinel.workflow_registry)
    parser = Mock(return_value=sentinel.parsed_workflow)

    service = ExecutionPreparationService(
        workflow_repo=workflow_repo,
        provider_repo=provider_repo,
        git_service=git_service,
        workflow_registry_builder=registry_builder,
    )

    prepared = service.prepare_for_launch(
        workflow_id="parent",
        branch="feature/sim",
        parser=parser,
        prepare_runtime_workflow=lambda **kwargs: (yaml.safe_load(kwargs["yaml_content"]), None),
        get_workflow_commit_sha=lambda _path: None,
    )

    assert prepared.workflow is sentinel.parsed_workflow
    registry_builder.assert_called_once_with(
        "parent",
        parent_yaml,
        git_ref="feature/sim",
        git_service=git_service,
    )
    assert parser.call_args.kwargs["workflow_registry"] is sentinel.workflow_registry
