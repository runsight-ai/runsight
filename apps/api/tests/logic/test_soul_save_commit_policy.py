"""Soul create, update, and delete operations validate branch state before committing."""

from unittest.mock import Mock

import pytest

from runsight_api.domain.errors import GitError, ServiceUnavailable
from runsight_api.domain.value_objects import SoulEntity

pytest_plugins = ("tests.logic.save_commit_helpers",)


class TestSoulCreateCommit:
    """Soul creation must be committed with correct message."""

    def test_create_soul_calls_git_commit(self, soul_repo, git_service):
        from runsight_api.logic.services.soul_service import SoulService

        created = SoulEntity(
            id="soul_review_fixture", kind="soul", name="Reviewer", role="Reviewer"
        )
        soul_repo.get_by_id.return_value = None
        soul_repo.create.return_value = created

        svc = SoulService(soul_repo, git_service=git_service)
        svc.create_soul(
            {"id": "soul_review_fixture", "kind": "soul", "name": "Reviewer", "role": "Reviewer"}
        )

        git_service.commit_to_branch.assert_called_once()

    def test_create_soul_commit_message(self, soul_repo, git_service):
        """Commit message: 'Create {id}.yaml'."""
        from runsight_api.logic.services.soul_service import SoulService

        created = SoulEntity(
            id="soul_review_fixture", kind="soul", name="Reviewer", role="Reviewer"
        )
        soul_repo.get_by_id.return_value = None
        soul_repo.create.return_value = created

        svc = SoulService(soul_repo, git_service=git_service)
        svc.create_soul(
            {"id": "soul_review_fixture", "kind": "soul", "name": "Reviewer", "role": "Reviewer"}
        )

        args, kwargs = git_service.commit_to_branch.call_args
        all_args = list(args) + [kwargs.get("message", "")]
        commit_msg = None
        for a in all_args:
            if isinstance(a, str) and "Create" in a:
                commit_msg = a
                break
        if commit_msg is None and "message" in kwargs:
            commit_msg = kwargs["message"]

        assert commit_msg == "Create soul_review_fixture.yaml"
        assert args[1] == ["custom/souls/soul_review_fixture.yaml"]

    def test_create_soul_branch_lookup_failure_raises_and_does_not_persist(
        self, soul_repo, git_service, monkeypatch: pytest.MonkeyPatch
    ):
        from runsight_api.logic.services.soul_service import SoulService
        from runsight_api.logic.services import soul_service as soul_service_module

        git_service.current_branch.side_effect = ServiceUnavailable("branch lookup failed")
        monkeypatch.setattr(soul_service_module.logger, "warning", Mock())
        soul_repo.get_by_id.return_value = None
        soul_repo.create.return_value = SoulEntity(
            id="soul_review_fixture",
            kind="soul",
            name="Reviewer",
            role="Reviewer",
        )

        svc = SoulService(soul_repo, git_service=git_service)

        with pytest.raises(ServiceUnavailable, match="branch lookup failed"):
            svc.create_soul(
                {
                    "id": "soul_review_fixture",
                    "kind": "soul",
                    "name": "Reviewer",
                    "role": "Reviewer",
                }
            )

        soul_repo.create.assert_not_called()
        git_service.commit_to_branch.assert_not_called()

    def test_create_soul_detached_head_raises_and_does_not_persist(self, soul_repo, git_service):
        from runsight_api.logic.services.soul_service import SoulService

        git_service.current_branch.return_value = "HEAD"
        soul_repo.get_by_id.return_value = None
        soul_repo.create.return_value = SoulEntity(
            id="soul_review_fixture",
            kind="soul",
            name="Reviewer",
            role="Reviewer",
        )

        svc = SoulService(soul_repo, git_service=git_service)

        with pytest.raises(GitError, match="branch"):
            svc.create_soul(
                {
                    "id": "soul_review_fixture",
                    "kind": "soul",
                    "name": "Reviewer",
                    "role": "Reviewer",
                }
            )

        soul_repo.create.assert_not_called()
        git_service.commit_to_branch.assert_not_called()


class TestSoulUpdateCommit:
    """Soul update must be committed with correct message."""

    def test_update_soul_calls_git_commit(self, soul_repo, git_service):
        from runsight_api.logic.services.soul_service import SoulService

        existing = SoulEntity(id="soul_x", kind="soul", name="Old Name", role="Old Name")
        soul_repo.get_by_id.return_value = existing
        soul_repo.update.return_value = SoulEntity(
            id="soul_x", kind="soul", name="New Name", role="New Name"
        )

        svc = SoulService(soul_repo, git_service=git_service)
        svc.update_soul("soul_x", {"role": "New Name"})

        git_service.commit_to_branch.assert_called_once()

    def test_update_soul_commit_message(self, soul_repo, git_service):
        """Commit message: 'Update {id}.yaml'."""
        from runsight_api.logic.services.soul_service import SoulService

        existing = SoulEntity(id="soul_x", kind="soul", name="Old", role="Old")
        soul_repo.get_by_id.return_value = existing
        soul_repo.update.return_value = SoulEntity(id="soul_x", kind="soul", name="New", role="New")

        svc = SoulService(soul_repo, git_service=git_service)
        svc.update_soul("soul_x", {"role": "New"})

        args, kwargs = git_service.commit_to_branch.call_args
        all_args = list(args) + [kwargs.get("message", "")]
        commit_msg = None
        for a in all_args:
            if isinstance(a, str) and "Update" in a:
                commit_msg = a
                break
        if commit_msg is None and "message" in kwargs:
            commit_msg = kwargs["message"]

        assert commit_msg == "Update soul_x.yaml"
        assert args[1] == ["custom/souls/soul_x.yaml"]

    def test_update_soul_empty_branch_raises_and_does_not_persist(self, soul_repo, git_service):
        from runsight_api.logic.services.soul_service import SoulService

        git_service.current_branch.return_value = ""
        existing = SoulEntity(id="soul_x", kind="soul", name="Old", role="Old")
        soul_repo.get_by_id.return_value = existing
        soul_repo.update.return_value = SoulEntity(id="soul_x", kind="soul", name="New", role="New")

        svc = SoulService(soul_repo, git_service=git_service)

        with pytest.raises(GitError, match="branch"):
            svc.update_soul("soul_x", {"role": "New"})

        soul_repo.update.assert_not_called()
        git_service.commit_to_branch.assert_not_called()

    def test_update_soul_detached_head_raises_and_does_not_persist(self, soul_repo, git_service):
        from runsight_api.logic.services.soul_service import SoulService

        git_service.current_branch.return_value = "HEAD"
        existing = SoulEntity(id="soul_x", kind="soul", name="Old", role="Old")
        soul_repo.get_by_id.return_value = existing
        soul_repo.update.return_value = SoulEntity(id="soul_x", kind="soul", name="New", role="New")

        svc = SoulService(soul_repo, git_service=git_service)

        with pytest.raises(GitError, match="branch"):
            svc.update_soul("soul_x", {"role": "New"})

        soul_repo.update.assert_not_called()
        git_service.commit_to_branch.assert_not_called()


class TestSoulDeleteCommit:
    """Soul deletion must be committed with correct message."""

    def test_delete_soul_calls_git_commit(self, soul_repo, git_service):
        from runsight_api.logic.services.soul_service import SoulService

        soul_repo.get_by_id.return_value = SoulEntity(
            id="soul_gone", kind="soul", name="Gone", role="Gone"
        )
        soul_repo.delete.return_value = True

        svc = SoulService(soul_repo, git_service=git_service)
        svc.delete_soul("soul_gone")

        git_service.commit_to_branch.assert_called_once()

    def test_delete_soul_commit_message(self, soul_repo, git_service):
        """Commit message: 'Delete {id}.yaml'."""
        from runsight_api.logic.services.soul_service import SoulService

        soul_repo.get_by_id.return_value = SoulEntity(
            id="soul_gone", kind="soul", name="Gone", role="Gone"
        )
        soul_repo.delete.return_value = True

        svc = SoulService(soul_repo, git_service=git_service)
        svc.delete_soul("soul_gone")

        args, kwargs = git_service.commit_to_branch.call_args
        all_args = list(args) + [kwargs.get("message", "")]
        commit_msg = None
        for a in all_args:
            if isinstance(a, str) and "Delete" in a:
                commit_msg = a
                break
        if commit_msg is None and "message" in kwargs:
            commit_msg = kwargs["message"]

        assert commit_msg == "Delete soul_gone.yaml"
        assert args[1] == ["custom/souls/soul_gone.yaml"]

    def test_delete_soul_non_string_branch_raises_and_does_not_delete(self, soul_repo, git_service):
        from runsight_api.logic.services.soul_service import SoulService

        git_service.current_branch.return_value = None
        soul_repo.get_by_id.return_value = SoulEntity(
            id="soul_gone",
            kind="soul",
            name="Gone",
            role="Gone",
        )
        soul_repo.delete.return_value = True

        svc = SoulService(soul_repo, git_service=git_service)

        with pytest.raises(GitError, match="branch"):
            svc.delete_soul("soul_gone")

        soul_repo.delete.assert_not_called()
        git_service.commit_to_branch.assert_not_called()

    def test_delete_soul_detached_head_raises_and_does_not_delete(self, soul_repo, git_service):
        from runsight_api.logic.services.soul_service import SoulService

        git_service.current_branch.return_value = "HEAD"
        soul_repo.get_by_id.return_value = SoulEntity(
            id="soul_gone",
            kind="soul",
            name="Gone",
            role="Gone",
        )
        soul_repo.delete.return_value = True

        svc = SoulService(soul_repo, git_service=git_service)

        with pytest.raises(GitError, match="branch"):
            svc.delete_soul("soul_gone")

        soul_repo.delete.assert_not_called()
        git_service.commit_to_branch.assert_not_called()


# ---------------------------------------------------------------------------
# 4. No empty commits when nothing changed
# ---------------------------------------------------------------------------
