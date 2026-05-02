"""Shared builders for SoulService API logic tests."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import Mock

from runsight_api.data.filesystem.soul_repo import SoulRepository
from runsight_api.domain.value_objects import SoulEntity, WorkflowEntity
from runsight_api.logic.services.git_service import GitService
from runsight_api.logic.services.soul_service import SoulService

_UNSET = object()


def soul_entity(
    entity_id: str,
    *,
    name: str | None = None,
    role: str | None = None,
    kind: str = "soul",
    **overrides: Any,
) -> SoulEntity:
    resolved_role = role if role is not None else name
    if resolved_role is None:
        resolved_role = entity_id.replace("_", " ").replace("-", " ").title()
    resolved_name = name if name is not None else resolved_role
    return SoulEntity(
        id=entity_id,
        kind=kind,
        name=resolved_name,
        role=resolved_role,
        **overrides,
    )


def soul_payload(
    entity_id: str,
    *,
    name: str | None = None,
    role: str | None = None,
    kind: str = "soul",
    **overrides: Any,
) -> dict[str, Any]:
    entity = soul_entity(entity_id, name=name, role=role, kind=kind, **overrides)
    payload = entity.model_dump(exclude_none=True)
    return payload


def soul_entity_from_payload(data: dict[str, Any]) -> SoulEntity:
    return soul_entity(
        data["id"],
        kind=data.get("kind", "soul"),
        name=data.get("name", data.get("role", "")),
        role=data.get("role", ""),
    )


def workflow_entity(entity_id: str, name: str, yaml: str | None) -> WorkflowEntity:
    return WorkflowEntity(kind="workflow", id=entity_id, name=name, yaml=yaml)


def make_soul_repo(*, souls: list[SoulEntity] | None = None, get_by_id: Any = _UNSET) -> Mock:
    repo = Mock()
    if souls is not None:
        repo.list_all.return_value = souls
    if get_by_id is not _UNSET:
        repo.get_by_id.return_value = get_by_id
    return repo


def make_workflow_repo(workflows: list[WorkflowEntity] | None = None) -> Mock:
    repo = Mock()
    if workflows is not None:
        repo.list_all.return_value = workflows
    return repo


def make_git_service(*, branch: str = "main", is_clean: bool = False) -> Mock:
    git_service = Mock()
    git_service.is_clean.return_value = is_clean
    git_service.current_branch.return_value = branch
    return git_service


def make_soul_service_with_git_mocks() -> tuple[Mock, Mock, SoulService]:
    soul_repo = make_soul_repo()
    git_service = Mock()
    service = SoulService(soul_repo, git_service=git_service)
    return soul_repo, git_service, service


def make_library_usage_service(workflow_repo=None) -> tuple[Mock, SoulService]:
    soul_repo = make_soul_repo()
    service = SoulService(soul_repo, workflow_repo=workflow_repo)
    return soul_repo, service


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def init_git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.email", "contributor@example.invalid")
    git(repo, "config", "user.name", "Runsight Tests")
    (repo / "README.md").write_text("# repo")
    git(repo, "add", "README.md")
    git(repo, "commit", "-m", "initial commit")
    return repo


def make_real_git_soul_service(repo: Path) -> tuple[SoulRepository, GitService, SoulService]:
    soul_repo = SoulRepository(base_path=str(repo))
    git_service = GitService(repo_path=str(repo))
    service = SoulService(soul_repo, git_service=git_service)
    return soul_repo, git_service, service
