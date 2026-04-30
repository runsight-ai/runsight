import subprocess
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from runsight_api.data.filesystem.soul_repo import SoulRepository
from runsight_api.domain.errors import SoulAlreadyExists, SoulInUse, SoulNotFound
from runsight_api.domain.value_objects import SoulEntity, WorkflowEntity
from runsight_api.logic.services.git_service import GitService
from runsight_api.logic.services.soul_service import SoulService


def workflow_entity(id: str, name: str, yaml: str | None) -> WorkflowEntity:
    return WorkflowEntity(kind="workflow", id=id, name=name, yaml=yaml)


def make_service() -> tuple[Mock, Mock, SoulService]:
    soul_repo = Mock()
    git_service = Mock()
    service = SoulService(soul_repo, git_service=git_service)
    return soul_repo, git_service, service


def git(repo, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


# --- list_souls ---


def test_list_souls_empty():
    soul_repo = Mock()
    soul_repo.list_all.return_value = []
    service = SoulService(soul_repo)
    result = service.list_souls()
    assert result == []
    soul_repo.list_all.assert_called_once()


def test_list_souls_multiple():
    soul_repo = Mock()
    souls = [
        SoulEntity(id="alpha-soul", kind="soul", name="Alpha", role="Alpha"),
        SoulEntity(id="beta-soul", kind="soul", name="Beta", role="Beta"),
    ]
    soul_repo.list_all.return_value = souls
    service = SoulService(soul_repo)
    result = service.list_souls()
    assert len(result) == 2
    assert result[0].id == "alpha-soul"
    assert result[0].role == "Alpha"
    assert result[1].id == "beta-soul"
    assert result[1].role == "Beta"


def test_list_souls_with_query_matches_id():
    soul_repo = Mock()
    souls = [
        SoulEntity(id="alpha-soul", kind="soul", name="X", role="X"),
        SoulEntity(id="beta-soul", kind="soul", name="Y", role="Y"),
        SoulEntity(id="gamma-soul", kind="soul", name="Z", role="Z"),
    ]
    soul_repo.list_all.return_value = souls
    service = SoulService(soul_repo)
    result = service.list_souls(query="alpha")
    assert len(result) == 1
    assert result[0].id == "alpha-soul"


def test_list_souls_with_query_matches_role():
    soul_repo = Mock()
    souls = [
        SoulEntity(id="alpha-role-soul", kind="soul", name="Alpha Soul", role="Alpha Soul"),
        SoulEntity(id="beta-role-soul", kind="soul", name="Beta Soul", role="Beta Soul"),
    ]
    soul_repo.list_all.return_value = souls
    service = SoulService(soul_repo)
    result = service.list_souls(query="alpha")
    assert len(result) == 1
    assert result[0].role == "Alpha Soul"


def test_list_souls_with_query_case_insensitive():
    soul_repo = Mock()
    souls = [
        SoulEntity(id="case-match-soul", kind="soul", name="Case Match", role="Case Match"),
    ]
    soul_repo.list_all.return_value = souls
    service = SoulService(soul_repo)
    result = service.list_souls(query="soul")
    assert len(result) == 1
    assert result[0].id == "case-match-soul"


def test_list_souls_with_workflow_repo_enriches_workflow_counts():
    soul_repo = Mock()
    workflow_repo = Mock()
    souls = [
        SoulEntity(id="researcher", kind="soul", name="Researcher", role="Researcher"),
        SoulEntity(id="reviewer", kind="soul", name="Reviewer", role="Reviewer"),
    ]
    soul_repo.list_all.return_value = souls
    workflow_repo.list_all.return_value = [
        workflow_entity(
            "research-workflow",
            "Research Flow",
            """
blocks:
  research:
    type: linear
    soul_ref: researcher
  review:
    type: linear
    soul_ref: reviewer
""",
        ),
        workflow_entity(
            "review-workflow",
            "Review Flow",
            """
blocks:
  approve:
    type: linear
    soul_ref: reviewer
""",
        ),
    ]
    service = SoulService(soul_repo)

    result = service.list_souls(workflow_repo=workflow_repo)

    assert [s.workflow_count for s in result] == [1, 2]


# --- get_soul / usages ---


def test_get_soul_exists():
    soul_repo = Mock()
    mock_soul = SoulEntity(id="alpha-soul", kind="soul", name="Research Soul", role="Research Soul")
    soul_repo.get_by_id.return_value = mock_soul
    service = SoulService(soul_repo)
    res = service.get_soul("alpha-soul")
    assert res.id == "alpha-soul"
    assert res.role == "Research Soul"
    soul_repo.get_by_id.assert_called_once_with("alpha-soul")


def test_get_soul_not_found_returns_none():
    soul_repo = Mock()
    soul_repo.get_by_id.return_value = None
    service = SoulService(soul_repo)
    res = service.get_soul("missing")
    assert res is None


def test_get_soul_usages_returns_matching_workflows_and_skips_bad_yaml():
    soul_repo = Mock()
    workflow_repo = Mock()
    soul_repo.get_by_id.return_value = SoulEntity(
        id="researcher",
        kind="soul",
        name="Researcher",
        role="Researcher",
    )
    workflow_repo.list_all.return_value = [
        workflow_entity(
            "research-workflow",
            "Research Flow",
            """
blocks:
  draft:
    type: linear
    soul_ref: researcher
""",
        ),
        workflow_entity("review-workflow", "Broken Flow", "souls: [broken"),
        workflow_entity(
            "wrong-shape-workflow",
            "Wrong Shape",
            """
blocks:
  - soul_ref: researcher
""",
        ),
        workflow_entity(
            "review-only-workflow",
            "Review Flow",
            """
blocks:
  review:
    type: linear
    soul_ref: reviewer
""",
        ),
        workflow_entity(
            "dispatch-workflow",
            "Dispatch Flow",
            """
blocks:
  route:
    type: dispatch
    exits:
      - id: research
        label: Research
        soul_ref: researcher
        task: Research it
""",
        ),
    ]
    service = SoulService(soul_repo)

    usages = service.get_soul_usages("researcher", workflow_repo)

    assert usages == [
        {"workflow_id": "research-workflow", "workflow_name": "Research Flow"},
        {"workflow_id": "dispatch-workflow", "workflow_name": "Dispatch Flow"},
    ]


def test_get_soul_usages_for_missing_soul_raises_not_found():
    soul_repo = Mock()
    workflow_repo = Mock()
    soul_repo.get_by_id.return_value = None
    service = SoulService(soul_repo)

    with pytest.raises(SoulNotFound) as exc_info:
        service.get_soul_usages("missing", workflow_repo)

    assert "missing" in str(exc_info.value)


def test_get_soul_usages_empty_when_unreferenced():
    soul_repo = Mock()
    workflow_repo = Mock()
    soul_repo.get_by_id.return_value = SoulEntity(
        id="researcher",
        kind="soul",
        name="Researcher",
        role="Researcher",
    )
    workflow_repo.list_all.return_value = [
        workflow_entity(
            "research-workflow",
            "Declared But Unused",
            """
souls:
  researcher:
    id: researcher
blocks:
  review:
    type: linear
    soul_ref: reviewer
""",
        )
    ]
    service = SoulService(soul_repo)

    usages = service.get_soul_usages("researcher", workflow_repo)

    assert usages == []


def test_compute_workflow_counts_skips_missing_sections_and_bad_yaml():
    workflow_repo = Mock()
    souls = [
        SoulEntity(id="researcher", kind="soul", name="Researcher", role="Researcher"),
        SoulEntity(id="reviewer", kind="soul", name="Reviewer", role="Reviewer"),
    ]
    workflow_repo.list_all.return_value = [
        workflow_entity("no-yaml-workflow", "No YAML", None),
        workflow_entity("broken-yaml-workflow", "Broken", "souls: [broken"),
        workflow_entity(
            "empty-workflow",
            "Empty",
            """
workflow:
  name: Empty
""",
        ),
        workflow_entity(
            "valid-workflow",
            "Valid",
            """
blocks:
  first:
    type: linear
    soul_ref: researcher
  second:
    type: linear
    soul_ref: reviewer
  ignored:
    type: linear
""",
        ),
    ]
    service = SoulService(Mock())

    counts = service._compute_workflow_counts(souls, workflow_repo)

    assert counts == {"researcher": 1, "reviewer": 1}


# --- create_soul ---


def test_create_soul_on_main_commits_custom_souls_path():
    soul_repo, git_service, service = make_service()
    created = SoulEntity(id="custom-soul", kind="soul", name="Custom", role="Custom")
    soul_repo.get_by_id.return_value = None
    soul_repo.create.return_value = created
    git_service.is_clean.return_value = False
    git_service.current_branch.return_value = "main"

    result = service.create_soul(
        {"id": "custom-soul", "kind": "soul", "name": "Custom", "role": "Custom"}
    )

    assert result == created
    soul_repo.create.assert_called_once()
    git_service.commit_to_branch.assert_called_once_with(
        "main",
        ["custom/souls/custom-soul.yaml"],
        "Create custom-soul.yaml",
    )


def test_create_soul_skips_auto_commit_outside_main_branch():
    soul_repo, git_service, service = make_service()
    created = SoulEntity(id="custom-soul", kind="soul", name="Custom", role="Custom")
    soul_repo.get_by_id.return_value = None
    soul_repo.create.return_value = created
    git_service.is_clean.return_value = False
    git_service.current_branch.return_value = "feature/soul-edit"

    result = service.create_soul(
        {"id": "custom-soul", "kind": "soul", "name": "Custom", "role": "Custom"}
    )

    assert result == created
    soul_repo.create.assert_called_once()
    git_service.commit_to_branch.assert_not_called()


def test_create_soul_existing_id_raises_conflict():
    soul_repo, _git_service, service = make_service()
    soul_repo.get_by_id.return_value = SoulEntity(
        id="custom-soul",
        kind="soul",
        name="Existing",
        role="Existing",
    )

    with pytest.raises(SoulAlreadyExists, match=r"soul:custom-soul"):
        service.create_soul(
            {"id": "custom-soul", "kind": "soul", "name": "Custom", "role": "Custom"}
        )
    soul_repo.create.assert_not_called()


def test_create_soul_missing_id_is_rejected():
    soul_repo, _git_service, service = make_service()
    soul_repo.get_by_id.return_value = None

    with pytest.raises(ValidationError):
        service.create_soul(
            {
                "kind": "soul",
                "name": "Auto Soul",
                "role": "Auto Soul",
                "system_prompt": "Write carefully.",
            }
        )

    soul_repo.create.assert_not_called()


def test_create_soul_missing_kind_is_rejected():
    soul_repo, _git_service, service = make_service()
    soul_repo.get_by_id.return_value = None

    with pytest.raises(ValidationError):
        service.create_soul(
            {
                "id": "custom-soul",
                "name": "Custom",
                "role": "Custom",
                "system_prompt": "Write carefully.",
            }
        )


def test_create_soul_missing_name_is_rejected():
    soul_repo, _git_service, service = make_service()
    soul_repo.get_by_id.return_value = None

    with pytest.raises(ValidationError):
        service.create_soul(
            {
                "id": "custom-soul",
                "kind": "soul",
                "role": "Custom",
                "system_prompt": "Write carefully.",
            }
        )


def test_create_soul_real_git_commit_uses_custom_souls_path(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.email", "contributor@example.invalid")
    git(repo, "config", "user.name", "Runsight Tests")
    (repo / "README.md").write_text("# repo")
    git(repo, "add", "README.md")
    git(repo, "commit", "-m", "initial commit")

    soul_repo = SoulRepository(base_path=str(repo))
    git_service = GitService(repo_path=str(repo))
    service = SoulService(soul_repo, git_service=git_service)

    created = service.create_soul(
        {
            "id": "researcher",
            "kind": "soul",
            "name": "Researcher",
            "role": "Researcher",
            "system_prompt": "Research the topic",
        }
    )

    assert created.id == "researcher"
    assert (repo / "custom" / "souls" / "researcher.yaml").exists()
    assert git(repo, "log", "-1", "--format=%s") == "Create researcher.yaml"
    tracked = git(repo, "ls-files", "--", "custom/souls/researcher.yaml")
    assert tracked == "custom/souls/researcher.yaml"


# --- update_soul ---


def test_update_soul_merges_existing_fields():
    soul_repo = Mock()
    existing = SoulEntity(
        id="alpha-soul",
        kind="soul",
        name="Old",
        role="Old",
        system_prompt="Keep me",
        provider="openai",
    )
    updated = SoulEntity(id="alpha-soul", kind="soul", name="New", role="New")
    soul_repo.get_by_id.return_value = existing
    soul_repo.update.return_value = updated
    service = SoulService(soul_repo)

    result = service.update_soul("alpha-soul", {"role": "New"})

    assert result == updated
    soul_repo.update.assert_called_once()
    update_id, payload = soul_repo.update.call_args[0]
    assert update_id == "alpha-soul"
    assert payload["id"] == "alpha-soul"
    assert payload["role"] == "New"
    assert payload["system_prompt"] == "Keep me"
    assert payload["provider"] == "openai"


def test_update_soul_not_found_raises_soul_not_found():
    soul_repo = Mock()
    soul_repo.get_by_id.return_value = None
    service = SoulService(soul_repo)

    with pytest.raises(SoulNotFound) as exc_info:
        service.update_soul("missing", {"role": "New"})

    assert "missing" in str(exc_info.value)
    soul_repo.update.assert_not_called()


def test_update_soul_copy_on_edit_creates_copy_and_commits_new_path():
    soul_repo, git_service, service = make_service()
    existing = SoulEntity(id="alpha-soul", kind="soul", name="Original", role="Original")
    soul_repo.get_by_id.return_value = existing
    git_service.is_clean.return_value = False
    git_service.current_branch.return_value = "main"

    def capture_create(data):
        return SoulEntity(
            id=data["id"],
            kind=data.get("kind", "soul"),
            name=data.get("name", data.get("role", "")),
            role=data.get("role", ""),
        )

    soul_repo.create.side_effect = capture_create

    service.update_soul("alpha-soul", {"role": "Copy"}, copy_on_edit=True)

    soul_repo.create.assert_called_once()
    call_args = soul_repo.create.call_args[0][0]
    assert call_args["id"].startswith("alpha-soul_copy_")
    assert len(call_args["id"]) == len("alpha-soul_copy_") + 4
    assert call_args["role"] == "Copy"
    git_service.commit_to_branch.assert_called_once_with(
        "main",
        [f"custom/souls/{call_args['id']}.yaml"],
        f"Create {call_args['id']}.yaml",
    )
    soul_repo.update.assert_not_called()


def test_update_soul_skips_auto_commit_outside_main_branch():
    soul_repo, git_service, service = make_service()
    existing = SoulEntity(
        id="alpha-soul",
        kind="soul",
        name="Old",
        role="Old",
        system_prompt="Keep me",
    )
    updated = SoulEntity(
        id="alpha-soul",
        kind="soul",
        name="New",
        role="New",
        system_prompt="Keep me",
    )
    soul_repo.get_by_id.return_value = existing
    soul_repo.update.return_value = updated
    git_service.is_clean.return_value = False
    git_service.current_branch.return_value = "feature/soul-edit"

    result = service.update_soul("alpha-soul", {"role": "New"})

    assert result == updated
    soul_repo.update.assert_called_once()
    git_service.commit_to_branch.assert_not_called()


# --- delete_soul ---


def test_delete_soul_on_main_commits_custom_souls_path():
    soul_repo, git_service, service = make_service()
    soul_repo.get_by_id.return_value = SoulEntity(
        id="alpha-soul",
        kind="soul",
        name="Soul",
        role="Soul",
    )
    soul_repo.delete.return_value = True
    git_service.is_clean.return_value = False
    git_service.current_branch.return_value = "main"

    result = service.delete_soul("alpha-soul")

    assert result is True
    soul_repo.delete.assert_called_once_with("alpha-soul")
    git_service.commit_to_branch.assert_called_once_with(
        "main",
        ["custom/souls/alpha-soul.yaml"],
        "Delete alpha-soul.yaml",
    )


def test_delete_soul_skips_auto_commit_outside_main_branch():
    soul_repo, git_service, service = make_service()
    soul_repo.get_by_id.return_value = SoulEntity(
        id="alpha-soul",
        kind="soul",
        name="Soul",
        role="Soul",
    )
    soul_repo.delete.return_value = True
    git_service.is_clean.return_value = False
    git_service.current_branch.return_value = "feature/soul-edit"

    result = service.delete_soul("alpha-soul")

    assert result is True
    soul_repo.delete.assert_called_once_with("alpha-soul")
    git_service.commit_to_branch.assert_not_called()


def test_delete_soul_not_found_raises_soul_not_found():
    soul_repo = Mock()
    soul_repo.get_by_id.return_value = None
    service = SoulService(soul_repo)

    with pytest.raises(SoulNotFound) as exc_info:
        service.delete_soul("missing")

    assert "missing" in str(exc_info.value)
    soul_repo.delete.assert_not_called()


def test_delete_soul_in_use_raises_conflict_with_usage_details():
    soul_repo = Mock()
    workflow_repo = Mock()
    soul_repo.get_by_id.return_value = SoulEntity(
        id="reviewer",
        kind="soul",
        name="Reviewer",
        role="Reviewer",
    )
    workflow_repo.list_all.return_value = [
        workflow_entity(
            "research-workflow",
            "Review One",
            """
blocks:
  one:
    type: linear
    soul_ref: reviewer
""",
        ),
        workflow_entity(
            "review-workflow",
            "Review Two",
            """
blocks:
  two:
    type: linear
    soul_ref: reviewer
""",
        ),
    ]
    service = SoulService(soul_repo)

    with pytest.raises(SoulInUse) as exc_info:
        service.delete_soul("reviewer", workflow_repo=workflow_repo)

    details = exc_info.value.to_dict()["details"]
    assert len(details["usages"]) == 2
    assert details["usages"][0]["workflow_id"] == "research-workflow"
    soul_repo.delete.assert_not_called()


def test_delete_soul_force_true_deletes_even_when_in_use():
    soul_repo = Mock()
    workflow_repo = Mock()
    soul_repo.get_by_id.return_value = SoulEntity(
        id="reviewer",
        kind="soul",
        name="Reviewer",
        role="Reviewer",
    )
    soul_repo.delete.return_value = True
    workflow_repo.list_all.return_value = [
        workflow_entity(
            "research-workflow",
            "Review One",
            """
blocks:
  one:
    type: linear
    soul_ref: reviewer
""",
        )
    ]
    service = SoulService(soul_repo)

    result = service.delete_soul("reviewer", force=True, workflow_repo=workflow_repo)

    assert result is True
    soul_repo.delete.assert_called_once_with("reviewer")
