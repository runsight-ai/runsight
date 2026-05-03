"""Workflow saves commit creates while leaving updates as non-commit edits."""

from unittest.mock import Mock


from runsight_api.domain.value_objects import WorkflowEntity

pytest_plugins = ("tests.logic.save_commit_helpers",)


class TestWorkflowCreateCommit:
    """POST /api/workflows → file write + git add + git commit."""

    def test_create_workflow_calls_git_commit(self, workflow_repo, git_service):
        """After creating a workflow, GitService.commit should be called."""
        from runsight_api.logic.services.workflow_service import WorkflowService

        created = WorkflowEntity(kind="workflow", id="onboarding-abc12", name="Onboarding Flow")
        workflow_repo.create.return_value = created

        svc = WorkflowService(workflow_repo, Mock(), git_service=git_service)
        svc.create_workflow({"name": "Onboarding Flow"})

        # GitService must have been called to commit
        git_service.commit_to_branch.assert_called_once()

    def test_create_workflow_commit_message_format(self, workflow_repo, git_service):
        """Commit message must be 'Create workflow: {name}'."""
        from runsight_api.logic.services.workflow_service import WorkflowService

        created = WorkflowEntity(kind="workflow", id="onboarding-abc12", name="Onboarding Flow")
        workflow_repo.create.return_value = created

        svc = WorkflowService(workflow_repo, Mock(), git_service=git_service)
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

        created = WorkflowEntity(kind="workflow", id="test-wf", name="Test")
        workflow_repo.create.return_value = created

        svc = WorkflowService(workflow_repo, Mock(), git_service=git_service)
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

        updated = WorkflowEntity(kind="workflow", id="workflow-save-primary", name="Updated Flow")
        workflow_repo.update.return_value = updated

        svc = WorkflowService(workflow_repo, Mock(), git_service=git_service)
        svc.update_workflow("workflow-save-primary", {"name": "Updated Flow"})

        git_service.commit_to_branch.assert_not_called()

    def test_update_workflow_still_persists_the_requested_payload(self, workflow_repo, git_service):
        """Workflow updates still delegate the payload to the repository."""
        from runsight_api.logic.services.workflow_service import WorkflowService

        updated = WorkflowEntity(kind="workflow", id="workflow-save-primary", name="My Cool Flow")
        workflow_repo.update.return_value = updated

        svc = WorkflowService(workflow_repo, Mock(), git_service=git_service)
        svc.update_workflow("workflow-save-primary", {"name": "My Cool Flow"})

        workflow_repo.update.assert_called_once_with(
            "workflow-save-primary", {"name": "My Cool Flow"}
        )
        git_service.commit_to_branch.assert_not_called()


# ---------------------------------------------------------------------------
# 3. SoulService — create/update/delete trigger git commit
# ---------------------------------------------------------------------------
