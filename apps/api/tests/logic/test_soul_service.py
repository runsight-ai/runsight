import subprocess
from unittest.mock import Mock

import pytest

from runsight_api.data.filesystem.soul_repo import SoulRepository
from runsight_api.domain.errors import SoulAlreadyExists, SoulInUse, SoulNotFound
from runsight_api.domain.value_objects import SoulEntity, WorkflowEntity
from runsight_api.logic.services.git_service import GitService
from runsight_api.logic.services.soul_service import SoulService


def workflow_entity(id: str, name: str, yaml: str | None) -> WorkflowEntity:
    return WorkflowEntity(id=id, name=name, yaml=yaml)


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
        SoulEntity(id="soul_1", role="Alpha"),
        SoulEntity(id="soul_2", role="Beta"),
    ]
    soul_repo.list_all.return_value = souls
    service = SoulService(soul_repo)
    result = service.list_souls()
    assert result == souls
    assert len(result) == 2


def test_list_souls_with_query_matches_id():
    soul_repo = Mock()
    souls = [
        SoulEntity(id="soul_alpha", role="X"),
        SoulEntity(id="soul_beta", role="Y"),
        SoulEntity(id="soul_gamma", role="Z"),
    ]
    soul_repo.list_all.return_value = souls
    service = SoulService(soul_repo)
    result = service.list_souls(query="alpha")
    assert len(result) == 1
    assert result[0].id == "soul_alpha"


def test_list_souls_with_query_matches_role():
    soul_repo = Mock()
    souls = [
        SoulEntity(id="s1", role="Alpha Soul"),
        SoulEntity(id="s2", role="Beta Soul"),
    ]
    soul_repo.list_all.return_value = souls
    service = SoulService(soul_repo)
    result = service.list_souls(query="alpha")
    assert len(result) == 1
    assert result[0].role == "Alpha Soul"


def test_list_souls_with_query_case_insensitive():
    soul_repo = Mock()
    souls = [
        SoulEntity(id="SOUL_1", role="Test"),
    ]
    soul_repo.list_all.return_value = souls
    service = SoulService(soul_repo)
    result = service.list_souls(query="soul")
    assert len(result) == 1
    assert result[0].id == "SOUL_1"


def test_list_souls_with_workflow_repo_enriches_workflow_counts():
    soul_repo = Mock()
    workflow_repo = Mock()
    souls = [
        SoulEntity(id="researcher", role="Researcher"),
        SoulEntity(id="reviewer", role="Reviewer"),
    ]
    soul_repo.list_all.return_value = souls
    workflow_repo.list_all.return_value = [
        workflow_entity(
            "wf_1",
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
            "wf_2",
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
    mock_soul = SoulEntity(id="soul_1", role="Test Soul")
    soul_repo.get_by_id.return_value = mock_soul
    service = SoulService(soul_repo)
    res = service.get_soul("soul_1")
    assert res is mock_soul
    assert res.id == "soul_1"
    soul_repo.get_by_id.assert_called_once_with("soul_1")


def test_get_soul_not_found_returns_none():
    soul_repo = Mock()
    soul_repo.get_by_id.return_value = None
    service = SoulService(soul_repo)
    res = service.get_soul("missing")
    assert res is None


def test_get_soul_usages_returns_matching_workflows_and_skips_bad_yaml():
    soul_repo = Mock()
    workflow_repo = Mock()
    soul_repo.get_by_id.return_value = SoulEntity(id="researcher", role="Researcher")
    workflow_repo.list_all.return_value = [
        workflow_entity(
            "wf_1",
            "Research Flow",
            """
blocks:
  draft:
    type: linear
    soul_ref: researcher
""",
        ),
        workflow_entity("wf_2", "Broken Flow", "souls: [broken"),
        workflow_entity(
            "wf_3",
            "Wrong Shape",
            """
blocks:
  - soul_ref: researcher
""",
        ),
        workflow_entity(
            "wf_4",
            "Review Flow",
            """
blocks:
  review:
    type: linear
    soul_ref: reviewer
""",
        ),
        workflow_entity(
            "wf_5",
            "Fanout Flow",
            """
blocks:
  route:
    type: fanout
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
        {"workflow_id": "wf_1", "workflow_name": "Research Flow"},
        {"workflow_id": "wf_5", "workflow_name": "Fanout Flow"},
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
    soul_repo.get_by_id.return_value = SoulEntity(id="researcher", role="Researcher")
    workflow_repo.list_all.return_value = [
        workflow_entity(
            "wf_1",
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
        SoulEntity(id="researcher", role="Researcher"),
        SoulEntity(id="reviewer", role="Reviewer"),
    ]
    workflow_repo.list_all.return_value = [
        workflow_entity("wf_none", "No YAML", None),
        workflow_entity("wf_bad", "Broken", "souls: [broken"),
        workflow_entity(
            "wf_empty",
            "Empty",
            """
workflow:
  name: Empty
""",
        ),
        workflow_entity(
            "wf_ok",
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


def test_create_soul_happy_path_uses_custom_souls_commit_path():
    soul_repo, git_service, service = make_service()
    created = SoulEntity(id="soul_custom", role="Custom")
    soul_repo.get_by_id.return_value = None
    soul_repo.create.return_value = created
    git_service.is_clean.return_value = False

    result = service.create_soul({"id": "soul_custom", "role": "Custom"})

    assert result == created
    soul_repo.create.assert_called_once()
    git_service.commit_to_branch.assert_called_once_with(
        "main",
        ["custom/souls/soul_custom.yaml"],
        "Create soul_custom.yaml",
    )


def test_create_soul_existing_id_raises_conflict():
    soul_repo, _git_service, service = make_service()
    soul_repo.get_by_id.return_value = SoulEntity(id="soul_custom", role="Existing")

    with pytest.raises(SoulAlreadyExists) as exc_info:
        service.create_soul({"id": "soul_custom", "role": "Custom"})

    assert "soul_custom" in str(exc_info.value)
    soul_repo.create.assert_not_called()


def test_create_soul_missing_id_auto_generates():
    soul_repo, _git_service, service = make_service()

    def capture_create(data):
        return SoulEntity(id=data["id"], role=data.get("role"))

    soul_repo.get_by_id.return_value = None
    soul_repo.create.side_effect = capture_create

    service.create_soul({"role": "Auto Soul"})

    call_args = soul_repo.create.call_args[0][0]
    assert call_args["id"].startswith("soul_")
    assert len(call_args["id"]) == len("soul_") + 8
    assert call_args["role"] == "Auto Soul"


def test_create_soul_real_git_commit_uses_custom_souls_path(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.email", "test@test.com")
    git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("# repo")
    git(repo, "add", "README.md")
    git(repo, "commit", "-m", "initial commit")

    soul_repo = SoulRepository(base_path=str(repo))
    git_service = GitService(repo_path=str(repo))
    service = SoulService(soul_repo, git_service=git_service)

    created = service.create_soul(
        {
            "id": "researcher",
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


def test_update_soul_happy_path():
    soul_repo = Mock()
    existing = SoulEntity(
        id="soul_1",
        role="Old",
        system_prompt="Keep me",
        assertions=[{"type": "contains", "value": "result"}],
    )
    updated = SoulEntity(id="soul_1", role="New")
    soul_repo.get_by_id.return_value = existing
    soul_repo.update.return_value = updated
    service = SoulService(soul_repo)

    result = service.update_soul("soul_1", {"role": "New"})

    assert result == updated
    soul_repo.update.assert_called_once()
    update_id, payload = soul_repo.update.call_args[0]
    assert update_id == "soul_1"
    assert payload["id"] == "soul_1"
    assert payload["role"] == "New"
    assert payload["system_prompt"] == "Keep me"
    assert payload["assertions"] == [{"type": "contains", "value": "result"}]


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
    existing = SoulEntity(id="soul_1", role="Original")
    soul_repo.get_by_id.return_value = existing
    git_service.is_clean.return_value = False

    def capture_create(data):
        return SoulEntity(id=data["id"], role=data.get("role", ""))

    soul_repo.create.side_effect = capture_create

    service.update_soul("soul_1", {"role": "Copy"}, copy_on_edit=True)

    soul_repo.create.assert_called_once()
    call_args = soul_repo.create.call_args[0][0]
    assert call_args["id"].startswith("soul_1_copy_")
    assert len(call_args["id"]) == len("soul_1_copy_") + 4
    assert call_args["role"] == "Copy"
    git_service.commit_to_branch.assert_called_once_with(
        "main",
        [f"custom/souls/{call_args['id']}.yaml"],
        f"Create {call_args['id']}.yaml",
    )
    soul_repo.update.assert_not_called()


# --- delete_soul ---


def test_delete_soul_happy_path_uses_custom_souls_commit_path():
    soul_repo, git_service, service = make_service()
    soul_repo.get_by_id.return_value = SoulEntity(id="soul_1", role="Soul")
    soul_repo.delete.return_value = True
    git_service.is_clean.return_value = False

    result = service.delete_soul("soul_1")

    assert result is True
    soul_repo.delete.assert_called_once_with("soul_1")
    git_service.commit_to_branch.assert_called_once_with(
        "main",
        ["custom/souls/soul_1.yaml"],
        "Delete soul_1.yaml",
    )


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
    soul_repo.get_by_id.return_value = SoulEntity(id="reviewer", role="Reviewer")
    workflow_repo.list_all.return_value = [
        workflow_entity(
            "wf_1",
            "Review One",
            """
souls:
  one:
    id: reviewer
""",
        ),
        workflow_entity(
            "wf_2",
            "Review Two",
            """
souls:
  two:
    id: reviewer
""",
        ),
    ]
    service = SoulService(soul_repo)

    with pytest.raises(SoulInUse) as exc_info:
        service.delete_soul("reviewer", workflow_repo=workflow_repo)

    details = exc_info.value.to_dict()["details"]
    assert len(details["usages"]) == 2
    assert details["usages"][0]["workflow_id"] == "wf_1"
    soul_repo.delete.assert_not_called()


def test_delete_soul_force_true_deletes_even_when_in_use():
    soul_repo = Mock()
    workflow_repo = Mock()
    soul_repo.get_by_id.return_value = SoulEntity(id="reviewer", role="Reviewer")
    soul_repo.delete.return_value = True
    workflow_repo.list_all.return_value = [
        workflow_entity(
            "wf_1",
            "Review One",
            """
souls:
  one:
    id: reviewer
""",
        )
    ]
    service = SoulService(soul_repo)

    result = service.delete_soul("reviewer", force=True, workflow_repo=workflow_repo)

    assert result is True
    soul_repo.delete.assert_called_once_with("reviewer")
