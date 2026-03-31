"""Red tests for RUN-376: explicit save = commit to main.

ADR-001: every save (create/update/delete) writes YAML then triggers
git add + git commit via GitService.  Tests verify that:

- WorkflowService.create_workflow calls GitService with correct commit message
- WorkflowService.update_workflow remains a non-commit update path
- SoulService.create_soul / update_soul / delete_soul call GitService
- No empty commits when nothing changed
- Providers are NOT committed (gitignored)
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from runsight_api.domain.value_objects import SoulEntity, WorkflowEntity

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def git_service():
    svc = Mock()
    svc.current_branch.return_value = "main"
    svc.is_clean.return_value = False
    return svc


@pytest.fixture
def workflow_repo():
    return Mock()


@pytest.fixture
def soul_repo():
    return Mock()


# ---------------------------------------------------------------------------
# 1. WorkflowService — create triggers git commit
# ---------------------------------------------------------------------------


class TestWorkflowCreateCommit:
    """POST /api/workflows → file write + git add + git commit."""

    def test_create_workflow_calls_git_commit(self, workflow_repo, git_service):
        """After creating a workflow, GitService.commit should be called."""
        from runsight_api.logic.services.workflow_service import WorkflowService

        created = WorkflowEntity(id="onboarding-abc12", name="Onboarding Flow")
        workflow_repo.create.return_value = created

        svc = WorkflowService(workflow_repo, git_service=git_service)
        svc.create_workflow({"name": "Onboarding Flow"})

        # GitService must have been called to commit
        git_service.commit_to_branch.assert_called_once()

    def test_create_workflow_commit_message_format(self, workflow_repo, git_service):
        """Commit message must be 'Create workflow: {name}'."""
        from runsight_api.logic.services.workflow_service import WorkflowService

        created = WorkflowEntity(id="onboarding-abc12", name="Onboarding Flow")
        workflow_repo.create.return_value = created

        svc = WorkflowService(workflow_repo, git_service=git_service)
        svc.create_workflow({"name": "Onboarding Flow"})

        _, kwargs = git_service.commit_to_branch.call_args
        # Accept either positional or keyword — normalize
        args, kwargs = git_service.commit_to_branch.call_args
        # message is the third positional arg or keyword
        all_args = list(args) + [kwargs.get("message", "")]
        commit_msg = None
        for a in all_args:
            if isinstance(a, str) and "Create workflow" in a:
                commit_msg = a
                break
        if commit_msg is None and "message" in kwargs:
            commit_msg = kwargs["message"]

        assert commit_msg is not None, (
            "commit_to_branch not called with a message containing 'Create workflow'"
        )
        assert "Onboarding Flow" in commit_msg

    def test_create_workflow_commits_to_main(self, workflow_repo, git_service):
        """Commits must target the main branch."""
        from runsight_api.logic.services.workflow_service import WorkflowService

        created = WorkflowEntity(id="test-wf", name="Test")
        workflow_repo.create.return_value = created

        svc = WorkflowService(workflow_repo, git_service=git_service)
        svc.create_workflow({"name": "Test"})

        args, kwargs = git_service.commit_to_branch.call_args
        # First positional arg should be the branch name "main"
        assert args[0] == "main", f"Expected commit to 'main', got '{args[0]}'"


# ---------------------------------------------------------------------------
# 2. WorkflowService — update triggers git commit
# ---------------------------------------------------------------------------


class TestWorkflowUpdateCommit:
    """PUT /api/workflows/:id remains a non-commit update path."""

    def test_update_workflow_does_not_call_git_commit(self, workflow_repo, git_service):
        """Workflow updates no longer imply a production commit."""
        from runsight_api.logic.services.workflow_service import WorkflowService

        updated = WorkflowEntity(id="wf-1", name="Updated Flow")
        workflow_repo.update.return_value = updated

        svc = WorkflowService(workflow_repo, git_service=git_service)
        svc.update_workflow("wf-1", {"name": "Updated Flow"})

        git_service.commit_to_branch.assert_not_called()

    def test_update_workflow_still_persists_the_requested_payload(self, workflow_repo, git_service):
        """Workflow updates still delegate the payload to the repository."""
        from runsight_api.logic.services.workflow_service import WorkflowService

        updated = WorkflowEntity(id="wf-1", name="My Cool Flow")
        workflow_repo.update.return_value = updated

        svc = WorkflowService(workflow_repo, git_service=git_service)
        svc.update_workflow("wf-1", {"name": "My Cool Flow"})

        workflow_repo.update.assert_called_once_with("wf-1", {"name": "My Cool Flow"})
        git_service.commit_to_branch.assert_not_called()


# ---------------------------------------------------------------------------
# 3. SoulService — create/update/delete trigger git commit
# ---------------------------------------------------------------------------


class TestSoulCreateCommit:
    """Soul creation must be committed with correct message."""

    def test_create_soul_calls_git_commit(self, soul_repo, git_service):
        from runsight_api.logic.services.soul_service import SoulService

        created = SoulEntity(id="soul_abc123", role="Reviewer")
        soul_repo.get_by_id.return_value = None
        soul_repo.create.return_value = created

        svc = SoulService(soul_repo, git_service=git_service)
        svc.create_soul({"id": "soul_abc123", "role": "Reviewer"})

        git_service.commit_to_branch.assert_called_once()

    def test_create_soul_commit_message(self, soul_repo, git_service):
        """Commit message: 'Create {id}.yaml'."""
        from runsight_api.logic.services.soul_service import SoulService

        created = SoulEntity(id="soul_abc123", role="Reviewer")
        soul_repo.get_by_id.return_value = None
        soul_repo.create.return_value = created

        svc = SoulService(soul_repo, git_service=git_service)
        svc.create_soul({"id": "soul_abc123", "role": "Reviewer"})

        args, kwargs = git_service.commit_to_branch.call_args
        all_args = list(args) + [kwargs.get("message", "")]
        commit_msg = None
        for a in all_args:
            if isinstance(a, str) and "Create" in a:
                commit_msg = a
                break
        if commit_msg is None and "message" in kwargs:
            commit_msg = kwargs["message"]

        assert commit_msg == "Create soul_abc123.yaml"
        assert args[1] == ["custom/souls/soul_abc123.yaml"]


class TestSoulUpdateCommit:
    """Soul update must be committed with correct message."""

    def test_update_soul_calls_git_commit(self, soul_repo, git_service):
        from runsight_api.logic.services.soul_service import SoulService

        existing = SoulEntity(id="soul_x", role="Old Name")
        soul_repo.get_by_id.return_value = existing
        soul_repo.update.return_value = SoulEntity(id="soul_x", role="New Name")

        svc = SoulService(soul_repo, git_service=git_service)
        svc.update_soul("soul_x", {"role": "New Name"})

        git_service.commit_to_branch.assert_called_once()

    def test_update_soul_commit_message(self, soul_repo, git_service):
        """Commit message: 'Update {id}.yaml'."""
        from runsight_api.logic.services.soul_service import SoulService

        existing = SoulEntity(id="soul_x", role="Old")
        soul_repo.get_by_id.return_value = existing
        soul_repo.update.return_value = SoulEntity(id="soul_x", role="New")

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


class TestSoulDeleteCommit:
    """Soul deletion must be committed with correct message."""

    def test_delete_soul_calls_git_commit(self, soul_repo, git_service):
        from runsight_api.logic.services.soul_service import SoulService

        soul_repo.get_by_id.return_value = SoulEntity(id="soul_gone", role="Gone")
        soul_repo.delete.return_value = True

        svc = SoulService(soul_repo, git_service=git_service)
        svc.delete_soul("soul_gone")

        git_service.commit_to_branch.assert_called_once()

    def test_delete_soul_commit_message(self, soul_repo, git_service):
        """Commit message: 'Delete {id}.yaml'."""
        from runsight_api.logic.services.soul_service import SoulService

        soul_repo.get_by_id.return_value = SoulEntity(id="soul_gone", role="Gone")
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


# ---------------------------------------------------------------------------
# 4. No empty commits when nothing changed
# ---------------------------------------------------------------------------


class TestNoEmptyCommits:
    """If file content did not change, no git commit should occur."""

    def test_workflow_update_no_change_skips_commit(self, workflow_repo, git_service):
        """When update produces no file diff, git commit must NOT be called."""
        from runsight_api.logic.services.workflow_service import WorkflowService

        # Simulate: repo.update returns entity but git reports working tree is clean
        updated = WorkflowEntity(id="wf-1", name="Same")
        workflow_repo.update.return_value = updated
        git_service.is_clean.return_value = True

        svc = WorkflowService(workflow_repo, git_service=git_service)
        svc.update_workflow("wf-1", {"name": "Same"})

        # If nothing changed on disk, commit_to_branch should NOT be called
        # (the implementation must check is_clean or git status before committing)
        # This test will fail because current impl doesn't integrate GitService at all
        git_service.commit_to_branch.assert_not_called()

    def test_soul_update_no_change_skips_commit(self, soul_repo, git_service):
        """When soul update produces no diff, git commit must NOT be called."""
        from runsight_api.logic.services.soul_service import SoulService

        existing = SoulEntity(id="soul_x", role="Same")
        soul_repo.get_by_id.return_value = existing
        soul_repo.update.return_value = SoulEntity(id="soul_x", role="Same")
        git_service.is_clean.return_value = True

        svc = SoulService(soul_repo, git_service=git_service)
        svc.update_soul("soul_x", {"role": "Same"})

        git_service.commit_to_branch.assert_not_called()


# ---------------------------------------------------------------------------
# 5. Constructor accepts git_service (DI contract)
# ---------------------------------------------------------------------------


class TestGitServiceInjection:
    """Services must accept an optional git_service parameter."""

    def test_workflow_service_accepts_git_service(self, workflow_repo, git_service):
        from runsight_api.logic.services.workflow_service import WorkflowService

        svc = WorkflowService(workflow_repo, git_service=git_service)
        assert svc.git_service is git_service

    def test_soul_service_accepts_git_service(self, soul_repo, git_service):
        from runsight_api.logic.services.soul_service import SoulService

        svc = SoulService(soul_repo, git_service=git_service)
        assert svc.git_service is git_service

    def test_workflow_service_git_service_defaults_none(self, workflow_repo):
        """Without git_service kwarg, it should default to None (backward compat)."""
        from runsight_api.logic.services.workflow_service import WorkflowService

        svc = WorkflowService(workflow_repo)
        assert svc.git_service is None

    def test_soul_service_git_service_defaults_none(self, soul_repo):
        """Without git_service kwarg, it should default to None (backward compat)."""
        from runsight_api.logic.services.soul_service import SoulService

        svc = SoulService(soul_repo)
        assert svc.git_service is None


# ---------------------------------------------------------------------------
# 6. Dependency wiring — deps.py provides git_service to services
# ---------------------------------------------------------------------------


class TestDepsWiring:
    """DI layer must wire GitService into WorkflowService and SoulService."""

    def test_get_workflow_service_includes_git_service(self):
        """get_workflow_service must inject a GitService instance."""
        import inspect

        from runsight_api.transport.deps import get_workflow_service

        sig = inspect.signature(get_workflow_service)
        param_names = list(sig.parameters.keys())
        # Should have a git_service parameter (via Depends)
        assert "git_service" in param_names, (
            f"get_workflow_service missing 'git_service' param. Has: {param_names}"
        )

    def test_get_soul_service_includes_git_service(self):
        """get_soul_service must inject a GitService instance."""
        import inspect

        from runsight_api.transport.deps import get_soul_service

        sig = inspect.signature(get_soul_service)
        param_names = list(sig.parameters.keys())
        assert "git_service" in param_names, (
            f"get_soul_service missing 'git_service' param. Has: {param_names}"
        )
