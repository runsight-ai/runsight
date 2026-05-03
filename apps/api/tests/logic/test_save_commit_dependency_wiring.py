"""GitService dependency injection and save-commit governance wiring."""

from unittest.mock import Mock


from runsight_api.domain.value_objects import SoulEntity, WorkflowEntity

pytest_plugins = ("tests.logic.save_commit_helpers",)


class TestNoEmptyCommits:
    """If file content did not change, no git commit should occur."""

    def test_workflow_update_no_change_skips_commit(self, workflow_repo, git_service):
        """When update produces no file diff, git commit must NOT be called."""
        from runsight_api.logic.services.workflow_service import WorkflowService

        # Simulate: repo.update returns entity but git reports working tree is clean
        updated = WorkflowEntity(kind="workflow", id="workflow-save-primary", name="Same")
        workflow_repo.update.return_value = updated
        git_service.is_clean.return_value = True

        svc = WorkflowService(workflow_repo, Mock(), git_service=git_service)
        svc.update_workflow("workflow-save-primary", {"name": "Same"})

        # If nothing changed on disk, commit_to_branch should not be called.
        # The service checks is_clean/git status before committing.
        git_service.commit_to_branch.assert_not_called()

    def test_soul_update_no_change_skips_commit(self, soul_repo, git_service):
        """When soul update produces no diff, git commit must NOT be called."""
        from runsight_api.logic.services.soul_service import SoulService

        existing = SoulEntity(id="soul_x", kind="soul", name="Same", role="Same")
        soul_repo.get_by_id.return_value = existing
        soul_repo.update.return_value = SoulEntity(
            id="soul_x", kind="soul", name="Same", role="Same"
        )
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

        svc = WorkflowService(workflow_repo, Mock(), git_service=git_service)
        assert svc.git_service is git_service

    def test_soul_service_accepts_git_service(self, soul_repo, git_service):
        from runsight_api.logic.services.soul_service import SoulService

        svc = SoulService(soul_repo, git_service=git_service)
        assert svc.git_service is git_service

    def test_workflow_service_git_service_defaults_none(self, workflow_repo):
        """Without git_service kwarg, it should default to None (backward compat)."""
        from runsight_api.logic.services.workflow_service import WorkflowService

        svc = WorkflowService(workflow_repo, Mock())
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
        import ast
        from pathlib import Path

        deps_path = (
            Path(__file__).resolve().parents[2] / "src" / "runsight_api" / "transport" / "deps.py"
        )
        module = ast.parse(deps_path.read_text())
        func = next(
            node
            for node in module.body
            if isinstance(node, ast.FunctionDef) and node.name == "get_workflow_service"
        )
        param_names = [arg.arg for arg in func.args.args]
        # Should have a git_service parameter (via Depends)
        assert "git_service" in param_names, (
            f"get_workflow_service missing 'git_service' param. Has: {param_names}"
        )

    def test_get_soul_service_includes_git_service(self):
        """get_soul_service must inject a GitService instance."""
        import ast
        from pathlib import Path

        deps_path = (
            Path(__file__).resolve().parents[2] / "src" / "runsight_api" / "transport" / "deps.py"
        )
        module = ast.parse(deps_path.read_text())
        func = next(
            node
            for node in module.body
            if isinstance(node, ast.FunctionDef) and node.name == "get_soul_service"
        )
        param_names = [arg.arg for arg in func.args.args]
        assert "git_service" in param_names, (
            f"get_soul_service missing 'git_service' param. Has: {param_names}"
        )
