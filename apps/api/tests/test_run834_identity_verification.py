from __future__ import annotations

from pathlib import Path
from textwrap import dedent
from unittest.mock import Mock

import pytest

from runsight_api.data.filesystem.provider_repo import FileSystemProviderRepo
from runsight_api.data.filesystem.soul_repo import SoulRepository
from runsight_api.data.filesystem.workflow_repo import WorkflowRepository
from runsight_api.domain.errors import InputValidationError
from runsight_api.domain.value_objects import WorkflowEntity
from runsight_api.logic.services.provider_service import ProviderService
from runsight_api.logic.services.run_service import RunService
from runsight_api.logic.services.soul_service import SoulService
from runsight_api.logic.services.workflow_service import WorkflowService


def _workflow_yaml(*, workflow_id: str, workflow_name: str, child_ref: str | None = None) -> str:
    entry = "start"
    if child_ref is not None:
        entry = "call_child"
    return (
        f"""version: "1.0"
id: {workflow_id}
kind: workflow
interface:
  inputs: []
  outputs: []
blocks: {{}}
workflow:
  name: {workflow_name}
  entry: {entry}
  transitions: []
"""
        if child_ref is None
        else dedent(
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
              entry: {entry}
              transitions:
                - from: {entry}
                  to: null
            """
        ).strip()
        + "\n"
    )


def _workflow_file(
    base_dir: Path, *, relative_path: str, workflow_id: str, workflow_name: str
) -> Path:
    path = base_dir / "custom" / "workflows" / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
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
              entry: start
              transitions: []
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    return path


def test_workflow_repository_create_and_update_use_embedded_ids(tmp_path: Path) -> None:
    repo = WorkflowRepository(base_path=str(tmp_path))

    created = repo.create(
        {"yaml": _workflow_yaml(workflow_id="research-review", workflow_name="Research Review")}
    )
    assert created.id == "research-review"
    assert created.name == "Research Review"
    assert (tmp_path / "custom" / "workflows" / "research-review.yaml").exists()

    updated = repo.update(
        "research-review",
        {
            "yaml": _workflow_yaml(
                workflow_id="research-review",
                workflow_name="Research Review v2",
            )
        },
    )
    assert updated.id == "research-review"
    assert updated.name == "Research Review v2"

    with pytest.raises(
        ValueError,
        match="embedded workflow id 'research-review-v2' does not match requested workflow:research-review",
    ):
        repo.update(
            "research-review",
            {
                "yaml": _workflow_yaml(
                    workflow_id="research-review-v2",
                    workflow_name="Research Review Renamed",
                )
            },
        )


def test_workflow_repository_create_requires_embedded_id(tmp_path: Path) -> None:
    repo = WorkflowRepository(base_path=str(tmp_path))

    with pytest.raises(InputValidationError, match="Workflow must have an id"):
        repo.create(
            {
                "yaml": dedent(
                    """\
                    version: "1.0"
                    kind: workflow
                    interface:
                      inputs: []
                      outputs: []
                    workflow:
                      name: Research Review
                      entry: start
                      transitions: []
                    """
                )
            }
        )


def test_workflow_repository_validate_yaml_rejects_missing_id_and_wrong_kind(
    tmp_path: Path,
) -> None:
    repo = WorkflowRepository(base_path=str(tmp_path))

    valid, validation_error, warnings = repo._validate_yaml_content(
        "research-review",
        dedent(
            """\
            version: "1.0"
            kind: workflow
            workflow:
              name: Research Review
              entry: start
              transitions: []
            """
        ),
    )
    assert valid is False
    assert validation_error is not None
    assert "id" in validation_error.lower()
    assert warnings == []

    valid, validation_error, warnings = repo._validate_yaml_content(
        "research-review",
        dedent(
            """\
            version: "1.0"
            id: research-review
            kind: pipeline
            workflow:
              name: Research Review
              entry: start
              transitions: []
            """
        ),
    )
    assert valid is False
    assert validation_error is not None
    assert "kind" in validation_error.lower()
    assert warnings == []


def test_workflow_repository_builds_registry_by_embedded_id(tmp_path: Path) -> None:
    child_path = _workflow_file(
        tmp_path, relative_path="child.yaml", workflow_id="child", workflow_name="Child Flow"
    )
    parent_yaml = _workflow_yaml(
        workflow_id="parent",
        workflow_name="Parent Flow",
        child_ref="child",
    )

    registry = WorkflowRepository(base_path=str(tmp_path)).build_runnable_workflow_registry(
        "parent",
        parent_yaml,
    )

    assert registry.get("parent").workflow.name == "Parent Flow"
    assert registry.get("child").workflow.name == "Child Flow"

    with pytest.raises(ValueError, match="cannot resolve ref"):
        registry.get(child_path.name)


def test_provider_service_create_uses_embedded_id_and_writes_filename(tmp_path: Path) -> None:
    repo = FileSystemProviderRepo(base_path=str(tmp_path))
    service = ProviderService(repo, Mock())

    provider = service.create_provider(id="openai", kind="provider", name="OpenAI")

    assert provider.id == "openai"
    assert provider.kind == "provider"
    assert (tmp_path / "custom" / "providers" / "openai.yaml").exists()


def test_soul_service_create_and_list_round_trip_embedded_identity(tmp_path: Path) -> None:
    repo = SoulRepository(base_path=str(tmp_path))
    service = SoulService(repo)

    soul = service.create_soul(
        {
            "id": "researcher",
            "kind": "soul",
            "name": "Senior Researcher",
            "role": "Researcher",
            "system_prompt": "You are a senior researcher.",
        }
    )

    assert soul.id == "researcher"
    assert soul.kind == "soul"
    assert soul.name == "Senior Researcher"
    assert repo.get_by_id("researcher") is not None
    assert service.list_souls()[0].kind == "soul"


def test_run_service_create_run_stores_embedded_workflow_id() -> None:
    workflow_repo = Mock()
    workflow_repo.get_by_id.return_value = WorkflowEntity(
        kind="workflow",
        id="research-review",
        name="Research Review",
        yaml=_workflow_yaml(workflow_id="research-review", workflow_name="Research Review"),
    )
    run_repo = Mock()
    run_repo.create_run.side_effect = lambda run: run

    service = RunService(run_repo, workflow_repo)
    run = service.create_run("research-review", {"instruction": "go"})

    assert run.workflow_id == "research-review"
    assert run.workflow_name == "Research Review"
    run_repo.create_run.assert_called_once()


def test_workflow_service_create_simulation_forwards_embedded_yaml_unchanged() -> None:
    workflow_repo = Mock()
    run_repo = Mock()
    git_service = Mock()
    git_service.create_sim_branch.return_value = Mock(branch="sim/research-review", sha="abc123")

    service = WorkflowService(workflow_repo, run_repo, git_service=git_service)
    yaml_text = _workflow_yaml(workflow_id="research-review", workflow_name="Research Review")
    result = service.create_simulation("research-review", yaml_text)

    assert result == {"branch": "sim/research-review", "commit_sha": "abc123"}
    git_service.create_sim_branch.assert_called_once_with(
        workflow_slug="research-review",
        yaml_content=yaml_text,
        yaml_path="custom/workflows/research-review.yaml",
    )


def test_workflow_service_create_simulation_rejects_mutated_workflow_id() -> None:
    workflow_repo = Mock()
    run_repo = Mock()
    git_service = Mock()

    service = WorkflowService(workflow_repo, run_repo, git_service=git_service)
    yaml_text = _workflow_yaml(workflow_id="changed-id", workflow_name="Changed")

    with pytest.raises(
        InputValidationError,
        match="embedded workflow id 'changed-id' does not match requested workflow:research-review",
    ):
        service.create_simulation("research-review", yaml_text)

    git_service.create_sim_branch.assert_not_called()
