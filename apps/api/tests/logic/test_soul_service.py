import pytest
from pydantic import ValidationError

from tests.logic.soul_service_helpers import (
    git,
    init_git_repo,
    make_real_git_soul_service,
    make_soul_repo,
    make_soul_service_with_git_mocks as make_service,
    make_workflow_repo,
    soul_entity,
    soul_entity_from_payload,
    soul_payload,
    workflow_entity,
)
from tests.logic.soul_usage_fixtures import (
    BROKEN_SOULS_YAML,
    dispatch_exit_yaml,
    legacy_soul_id_section_yaml,
    linear_blocks_yaml,
    no_blocks_yaml,
    wrong_shape_blocks_yaml,
)
from runsight_api.domain.errors import SoulAlreadyExists, SoulInUse, SoulNotFound
from runsight_api.logic.services.soul_service import SoulService


# --- list_souls ---


def test_list_souls_empty():
    soul_repo = make_soul_repo(souls=[])
    service = SoulService(soul_repo)
    result = service.list_souls()
    assert result == []
    soul_repo.list_all.assert_called_once()


def test_list_souls_multiple():
    souls = [
        soul_entity("alpha-soul", name="Alpha", role="Alpha"),
        soul_entity("beta-soul", name="Beta", role="Beta"),
    ]
    soul_repo = make_soul_repo(souls=souls)
    service = SoulService(soul_repo)
    result = service.list_souls()
    assert len(result) == 2
    assert result[0].id == "alpha-soul"
    assert result[0].role == "Alpha"
    assert result[1].id == "beta-soul"
    assert result[1].role == "Beta"


def test_list_souls_with_query_matches_id():
    souls = [
        soul_entity("alpha-soul", name="X", role="X"),
        soul_entity("beta-soul", name="Y", role="Y"),
        soul_entity("gamma-soul", name="Z", role="Z"),
    ]
    soul_repo = make_soul_repo(souls=souls)
    service = SoulService(soul_repo)
    result = service.list_souls(query="alpha")
    assert len(result) == 1
    assert result[0].id == "alpha-soul"


def test_list_souls_with_query_matches_role():
    souls = [
        soul_entity("alpha-role-soul", name="Alpha Soul", role="Alpha Soul"),
        soul_entity("beta-role-soul", name="Beta Soul", role="Beta Soul"),
    ]
    soul_repo = make_soul_repo(souls=souls)
    service = SoulService(soul_repo)
    result = service.list_souls(query="alpha")
    assert len(result) == 1
    assert result[0].role == "Alpha Soul"


def test_list_souls_with_query_case_insensitive():
    souls = [
        soul_entity("case-match-soul", name="Case Match", role="Case Match"),
    ]
    soul_repo = make_soul_repo(souls=souls)
    service = SoulService(soul_repo)
    result = service.list_souls(query="soul")
    assert len(result) == 1
    assert result[0].id == "case-match-soul"


def test_list_souls_with_workflow_repo_enriches_workflow_counts():
    souls = [
        soul_entity("researcher", name="Researcher", role="Researcher"),
        soul_entity("reviewer", name="Reviewer", role="Reviewer"),
    ]
    soul_repo = make_soul_repo(souls=souls)
    workflow_repo = make_workflow_repo(
        [
            workflow_entity(
                "research-workflow",
                "Research Flow",
                linear_blocks_yaml("researcher", "reviewer", block_names=("research", "review")),
            ),
            workflow_entity(
                "review-workflow",
                "Review Flow",
                linear_blocks_yaml("reviewer", block_names=("approve",)),
            ),
        ]
    )
    service = SoulService(soul_repo)

    result = service.list_souls(workflow_repo=workflow_repo)

    assert [s.workflow_count for s in result] == [1, 2]


# --- get_soul / usages ---


def test_get_soul_exists():
    mock_soul = soul_entity("alpha-soul", name="Research Soul", role="Research Soul")
    soul_repo = make_soul_repo(get_by_id=mock_soul)
    service = SoulService(soul_repo)
    res = service.get_soul("alpha-soul")
    assert res.id == "alpha-soul"
    assert res.role == "Research Soul"
    soul_repo.get_by_id.assert_called_once_with("alpha-soul")


def test_get_soul_not_found_returns_none():
    soul_repo = make_soul_repo(get_by_id=None)
    service = SoulService(soul_repo)
    res = service.get_soul("missing")
    assert res is None


def test_get_soul_usages_returns_matching_workflows_and_skips_bad_yaml():
    soul_repo = make_soul_repo(
        get_by_id=soul_entity("researcher", name="Researcher", role="Researcher")
    )
    workflow_repo = make_workflow_repo(
        [
            workflow_entity(
                "research-workflow",
                "Research Flow",
                linear_blocks_yaml("researcher", block_names=("draft",)),
            ),
            workflow_entity("review-workflow", "Broken Flow", BROKEN_SOULS_YAML),
            workflow_entity(
                "wrong-shape-workflow",
                "Wrong Shape",
                wrong_shape_blocks_yaml("researcher"),
            ),
            workflow_entity(
                "review-only-workflow",
                "Review Flow",
                linear_blocks_yaml("reviewer", block_names=("review",)),
            ),
            workflow_entity(
                "dispatch-workflow",
                "Dispatch Flow",
                dispatch_exit_yaml(
                    "researcher",
                    exit_id="research",
                    task="Research it",
                ),
            ),
        ]
    )
    service = SoulService(soul_repo)

    usages = service.get_soul_usages("researcher", workflow_repo)

    assert usages == [
        {"workflow_id": "research-workflow", "workflow_name": "Research Flow"},
        {"workflow_id": "dispatch-workflow", "workflow_name": "Dispatch Flow"},
    ]


def test_get_soul_usages_for_missing_soul_raises_not_found():
    soul_repo = make_soul_repo(get_by_id=None)
    workflow_repo = make_workflow_repo()
    service = SoulService(soul_repo)

    with pytest.raises(SoulNotFound) as exc_info:
        service.get_soul_usages("missing", workflow_repo)

    assert "missing" in str(exc_info.value)


def test_get_soul_usages_empty_when_unreferenced():
    soul_repo = make_soul_repo(
        get_by_id=soul_entity("researcher", name="Researcher", role="Researcher")
    )
    workflow_repo = make_workflow_repo(
        [
            workflow_entity(
                "research-workflow",
                "Declared But Unused",
                legacy_soul_id_section_yaml("researcher", "reviewer", block_name="review"),
            )
        ]
    )
    service = SoulService(soul_repo)

    usages = service.get_soul_usages("researcher", workflow_repo)

    assert usages == []


def test_compute_workflow_counts_skips_missing_sections_and_bad_yaml():
    souls = [
        soul_entity("researcher", name="Researcher", role="Researcher"),
        soul_entity("reviewer", name="Reviewer", role="Reviewer"),
    ]
    workflow_repo = make_workflow_repo(
        [
            workflow_entity("no-yaml-workflow", "No YAML", None),
            workflow_entity("broken-yaml-workflow", "Broken", BROKEN_SOULS_YAML),
            workflow_entity("empty-workflow", "Empty", no_blocks_yaml(name="Empty")),
            workflow_entity(
                "valid-workflow",
                "Valid",
                linear_blocks_yaml(
                    "researcher",
                    "reviewer",
                    block_names=("first", "second"),
                    include_unreferenced_block=True,
                ),
            ),
        ]
    )
    service = SoulService(make_soul_repo())

    counts = service._compute_workflow_counts(souls, workflow_repo)

    assert counts == {"researcher": 1, "reviewer": 1}


# --- create_soul ---


def test_create_soul_on_main_commits_custom_souls_path():
    soul_repo, git_service, service = make_service()
    created = soul_entity("custom-soul", name="Custom", role="Custom")
    soul_repo.get_by_id.return_value = None
    soul_repo.create.return_value = created
    git_service.is_clean.return_value = False
    git_service.current_branch.return_value = "main"

    result = service.create_soul(soul_payload("custom-soul", name="Custom", role="Custom"))

    assert result == created
    soul_repo.create.assert_called_once()
    git_service.commit_to_branch.assert_called_once_with(
        "main",
        ["custom/souls/custom-soul.yaml"],
        "Create custom-soul.yaml",
    )


def test_create_soul_skips_auto_commit_outside_main_branch():
    soul_repo, git_service, service = make_service()
    created = soul_entity("custom-soul", name="Custom", role="Custom")
    soul_repo.get_by_id.return_value = None
    soul_repo.create.return_value = created
    git_service.is_clean.return_value = False
    git_service.current_branch.return_value = "feature/soul-edit"

    result = service.create_soul(soul_payload("custom-soul", name="Custom", role="Custom"))

    assert result == created
    soul_repo.create.assert_called_once()
    git_service.commit_to_branch.assert_not_called()


def test_create_soul_existing_id_raises_conflict():
    soul_repo, _git_service, service = make_service()
    soul_repo.get_by_id.return_value = soul_entity(
        "custom-soul",
        name="Existing",
        role="Existing",
    )

    with pytest.raises(SoulAlreadyExists, match=r"soul:custom-soul"):
        service.create_soul(soul_payload("custom-soul", name="Custom", role="Custom"))
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
    repo = init_git_repo(tmp_path)
    _soul_repo, _git_service, service = make_real_git_soul_service(repo)

    created = service.create_soul(
        soul_payload(
            "researcher",
            name="Researcher",
            role="Researcher",
            system_prompt="Research the topic",
        )
    )

    assert created.id == "researcher"
    assert (repo / "custom" / "souls" / "researcher.yaml").exists()
    assert git(repo, "log", "-1", "--format=%s") == "Create researcher.yaml"
    tracked = git(repo, "ls-files", "--", "custom/souls/researcher.yaml")
    assert tracked == "custom/souls/researcher.yaml"


# --- update_soul ---


def test_update_soul_merges_existing_fields():
    existing = soul_entity(
        "alpha-soul",
        name="Old",
        role="Old",
        system_prompt="Keep me",
        provider="openai",
    )
    updated = soul_entity("alpha-soul", name="New", role="New")
    soul_repo = make_soul_repo(get_by_id=existing)
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
    soul_repo = make_soul_repo(get_by_id=None)
    service = SoulService(soul_repo)

    with pytest.raises(SoulNotFound) as exc_info:
        service.update_soul("missing", {"role": "New"})

    assert "missing" in str(exc_info.value)
    soul_repo.update.assert_not_called()


def test_update_soul_copy_on_edit_creates_copy_and_commits_new_path():
    soul_repo, git_service, service = make_service()
    existing = soul_entity("alpha-soul", name="Original", role="Original")
    soul_repo.get_by_id.return_value = existing
    git_service.is_clean.return_value = False
    git_service.current_branch.return_value = "main"

    soul_repo.create.side_effect = soul_entity_from_payload

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
    existing = soul_entity(
        "alpha-soul",
        name="Old",
        role="Old",
        system_prompt="Keep me",
    )
    updated = soul_entity(
        "alpha-soul",
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
    soul_repo.get_by_id.return_value = soul_entity("alpha-soul", name="Soul", role="Soul")
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
    soul_repo.get_by_id.return_value = soul_entity("alpha-soul", name="Soul", role="Soul")
    soul_repo.delete.return_value = True
    git_service.is_clean.return_value = False
    git_service.current_branch.return_value = "feature/soul-edit"

    result = service.delete_soul("alpha-soul")

    assert result is True
    soul_repo.delete.assert_called_once_with("alpha-soul")
    git_service.commit_to_branch.assert_not_called()


def test_delete_soul_not_found_raises_soul_not_found():
    soul_repo = make_soul_repo(get_by_id=None)
    service = SoulService(soul_repo)

    with pytest.raises(SoulNotFound) as exc_info:
        service.delete_soul("missing")

    assert "missing" in str(exc_info.value)
    soul_repo.delete.assert_not_called()


def test_delete_soul_in_use_raises_conflict_with_usage_details():
    soul_repo = make_soul_repo(get_by_id=soul_entity("reviewer", name="Reviewer", role="Reviewer"))
    workflow_repo = make_workflow_repo(
        [
            workflow_entity(
                "research-workflow",
                "Review One",
                linear_blocks_yaml("reviewer", block_names=("one",)),
            ),
            workflow_entity(
                "review-workflow",
                "Review Two",
                linear_blocks_yaml("reviewer", block_names=("two",)),
            ),
        ]
    )
    service = SoulService(soul_repo)

    with pytest.raises(SoulInUse) as exc_info:
        service.delete_soul("reviewer", workflow_repo=workflow_repo)

    details = exc_info.value.to_dict()["details"]
    assert len(details["usages"]) == 2
    assert details["usages"][0]["workflow_id"] == "research-workflow"
    soul_repo.delete.assert_not_called()


def test_delete_soul_force_true_deletes_even_when_in_use():
    soul_repo = make_soul_repo(get_by_id=soul_entity("reviewer", name="Reviewer", role="Reviewer"))
    soul_repo.delete.return_value = True
    workflow_repo = make_workflow_repo(
        [
            workflow_entity(
                "research-workflow",
                "Review One",
                linear_blocks_yaml("reviewer", block_names=("one",)),
            )
        ]
    )
    service = SoulService(soul_repo)

    result = service.delete_soul("reviewer", force=True, workflow_repo=workflow_repo)

    assert result is True
    soul_repo.delete.assert_called_once_with("reviewer")
